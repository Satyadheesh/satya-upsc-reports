"""Generate SSC CGL flashcards for one shard of notes using Gemma 4 12B.

  python -m kit.run_ssc --ids 1,2,3 [--preview out/]
"""
import argparse
import json
import os
import time

from common.db import close_all, in_chunks, main_db, upsc_db
from .model import MODEL_NAME, Model, download
from .ssc import (
    PROMPT_VERSION,
    SscInvalid,
    build_messages,
    schema,
    validate_ssc_card,
)

TRIES = 3
DEADLINE = int(os.environ.get("SHARD_DEADLINE_SEC") or 3000)
COLS = (
    "article_id, gs_paper, subject, syllabus_node, exam_type, why_in_news, fact_box, prelims_pointers, "
    "mains_question, keywords, updated_at"
)


def _json(s, default):
    try:
        return json.loads(s) if s else default
    except (TypeError, ValueError):
        return default


def load_notes(ids, preview=False):
    up, mn = upsc_db(), main_db()
    notes = {}
    for r in in_chunks(up, f"SELECT {COLS} FROM upsc_articles WHERE article_id IN ({{ph}})", ids):
        notes[r[0]] = {
            "article_id": r[0],
            "gs_paper": r[1],
            "subject": r[2],
            "syllabus_node": r[3],
            "exam_type": r[4],
            "why_in_news": r[5],
            "fact_box": r[6],
            "prelims_pointers": _json(r[7], []),
            "mains_question": r[8],
            "keywords": _json(r[9], []),
            "updated_at": r[10],
        }
    for aid, reph, orig in in_chunks(mn, "SELECT id, rephrased_title, title FROM articles WHERE id IN ({ph})", ids):
        if aid in notes:
            notes[aid]["title"] = (reph or "").strip() or None
            notes[aid]["original_title"] = (orig or "").strip() or None

    prior = {}
    if notes and not preview:
        for aid, status, attempts in in_chunks(
            up, "SELECT article_id, status, attempts FROM ssc_kit WHERE article_id IN ({ph})", ids
        ):
            if status == "failed":
                prior[aid] = attempts
    return up, notes, prior


def generate_card(model, note, lang="en"):
    feedback = None
    err = None
    sc = schema(lang)
    max_tokens = 320 if lang == "hi" else 220
    for i in range(TRIES):
        try:
            msgs = build_messages(note, lang=lang, feedback=feedback)
            raw = model.chat(msgs, sc, temperature=0.2 if i == 0 else 0.4, max_tokens=max_tokens)
            card = validate_ssc_card(raw, note, lang=lang)
            return card, None
        except (SscInvalid, ValueError, KeyError) as e:
            err = str(e)[:200]
            feedback = err
    return None, err


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", required=True)
    parser.add_argument("--preview")
    args = parser.parse_args()

    ids = [int(x.strip()) for x in args.ids.split(",") if x.strip().isdigit()]
    if not ids:
        print("no ids to process")
        return

    preview = bool(args.preview)
    out_dir = args.preview
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    up, notes, prior = load_notes(ids, preview=preview)
    print(f"loaded {len(notes)} notes for SSC kit shard")

    model_path = download()
    model = Model(model_path)

    start = time.time()
    done_count = 0
    failed_count = 0
    preview_records = []

    for idx, aid in enumerate(ids):
        if time.time() - start > DEADLINE:
            print(f"deadline reached after {idx} notes")
            break

        note = notes.get(aid)
        if not note:
            continue

        attempts = (prior.get(aid) or 0) + 1
        now = int(time.time())

        # 1. Generate English
        card_en, err_en = generate_card(model, note, lang="en")
        # 2. Generate Hindi
        card_hi, err_hi = generate_card(model, note, lang="hi")

        status = "done" if (card_en and card_hi) else "failed"
        err = f"EN: {err_en} | HI: {err_hi}" if status == "failed" else None

        if status == "done":
            done_count += 1
            print(f"[{idx+1}/{len(ids)}] note {aid}: OK -> EN: {card_en['ssc_question'][:50]}... | HI: {card_hi['ssc_question'][:50]}...")
            if preview:
                preview_records.append({"article_id": aid, "en": card_en, "hi": card_hi})
        else:
            failed_count += 1
            print(f"[{idx+1}/{len(ids)}] note {aid}: FAILED -> {err}")

        if not preview:
            up.execute(
                "INSERT OR REPLACE INTO ssc_kit ("
                "article_id, status, attempts, "
                "question_en, answer_en, key_fact_en, static_gk_en, "
                "question_hi, answer_hi, key_fact_hi, static_gk_hi, "
                "note_updated_at, model, prompt_version, error, created_at, updated_at"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    aid,
                    status,
                    attempts,
                    card_en.get("ssc_question") if card_en else None,
                    card_en.get("ssc_answer") if card_en else None,
                    card_en.get("key_fact") if card_en else None,
                    card_en.get("static_gk") if card_en else None,
                    card_hi.get("ssc_question") if card_hi else None,
                    card_hi.get("answer_hi", card_hi.get("ssc_answer")) if card_hi else None,
                    card_hi.get("key_fact") if card_hi else None,
                    card_hi.get("static_gk") if card_hi else None,
                    note.get("updated_at"),
                    MODEL_NAME,
                    PROMPT_VERSION,
                    err,
                    now,
                    now,
                ],
            )

    if preview and out_dir:
        jsonl_path = os.path.join(out_dir, f"ssc_shard_{os.environ.get('SHARD_NAME', '0')}.jsonl")
        with open(jsonl_path, "w", encoding="utf-8") as f:
            for rec in preview_records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"wrote {len(preview_records)} cards to {jsonl_path}")

    print(f"SSC shard finished: {done_count} done, {failed_count} failed in {time.time() - start:.1f}s")


if __name__ == "__main__":
    try:
        main()
    finally:
        close_all()
