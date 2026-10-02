"""Make study kits for one shard of notes.  python -m kit.run --ids 1,2,3 [--preview out/]

Per note: one model call, validated (kit/validate.py); up to 2 retries that tell the model what was wrong.
Saved to upsc_kit as 'done', or 'failed' with attempts+1 (setup retries it until MAX_ATTEMPTS).
With --preview nothing is written to the DB: kits go to a JSONL file for review.
"""
import argparse
import json
import os
import time

from common.db import close_all, in_chunks, main_db, upsc_db

from .model import MODEL_NAME, Model, download
from .prompt import PROMPT_VERSION, SYSTEM, mcq_type, schema, user_prompt
from .validate import Invalid, validate

TRIES = 3
DEADLINE = int(os.environ.get("SHARD_DEADLINE_SEC") or 3000)
COLS = ("article_id, gs_paper, subject, syllabus_node, exam_type, why_in_news, fact_box, prelims_pointers, "
        "mains_question, keywords, updated_at")


def _json(s, default):
    try:
        return json.loads(s) if s else default
    except (TypeError, ValueError):
        return default


def load_notes(ids):
    up, mn = upsc_db(), main_db()
    notes = {}
    for r in in_chunks(up, f"SELECT {COLS} FROM upsc_articles WHERE article_id IN ({{ph}})", ids):
        notes[r[0]] = {"article_id": r[0], "gs_paper": r[1], "subject": r[2], "syllabus_node": r[3], "exam_type": r[4],
                       "why_in_news": r[5], "fact_box": r[6], "prelims_pointers": _json(r[7], []),
                       "mains_question": r[8], "keywords": _json(r[9], []), "updated_at": r[10]}
    for aid, reph, orig in in_chunks(mn, "SELECT id, rephrased_title, title FROM articles WHERE id IN ({ph})", ids):
        if aid in notes:
            notes[aid]["title"] = (reph or "").strip() or None
            notes[aid]["original_title"] = (orig or "").strip() or None
    prior = {r[0]: r[1] for r in in_chunks(up, "SELECT article_id, attempts FROM upsc_kit WHERE article_id IN ({ph}) "
                                                "AND status = 'failed'", ids)} if notes else {}
    return up, notes, prior


def make_kit(model, note):
    kind = mcq_type(note["article_id"])
    feedback, err = None, None
    for i in range(TRIES):
        try:
            raw = model.json(SYSTEM, user_prompt(note, kind, feedback), schema(kind), temperature=0.2 if i == 0 else 0.5)
            return validate(raw, note, note["article_id"], kind), i + 1, None
        except (Invalid, ValueError) as e:
            err = str(e)[:200]
            feedback = err
    return None, TRIES, err


def save(c, aid, note, kit, err, prior_attempts):
    now = int(time.time())
    if kit:
        c.execute(
            "INSERT OR REPLACE INTO upsc_kit (article_id, status, attempts, short_title, takeaway, brief_lead, brief_text, "
            "facts, mcq, note_updated_at, model, prompt_version, error, created_at, updated_at, translated_hi) "
            "VALUES (?, 'done', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, 0)",
            [aid, prior_attempts + 1, kit["short_title"], kit["takeaway"], kit["brief_lead"], kit["brief_text"],
             json.dumps(kit["facts"], ensure_ascii=False), json.dumps(kit["mcq"], ensure_ascii=False),
             note.get("updated_at"), MODEL_NAME, PROMPT_VERSION, now, now])
    else:
        c.execute(
            "INSERT INTO upsc_kit (article_id, status, attempts, error, note_updated_at, model, prompt_version, created_at, updated_at) "
            "VALUES (?, 'failed', ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(article_id) DO UPDATE SET status = 'failed', "
            "attempts = excluded.attempts, error = excluded.error, note_updated_at = excluded.note_updated_at, "
            "updated_at = excluded.updated_at",
            [aid, prior_attempts + 1, err, note.get("updated_at"), MODEL_NAME, PROMPT_VERSION, now, now])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default="")
    ap.add_argument("--preview", default="", help="write kits to this folder instead of the DB")
    args = ap.parse_args()
    ids = [int(x) for x in args.ids.split(",") if x.strip()]
    if not ids:
        print("nothing to do")
        return
    t0 = time.time()
    up, notes, prior = load_notes(ids)
    print(f"{len(notes)}/{len(ids)} notes loaded; loading model")
    model = Model(download())
    print(f"model ready in {time.time() - t0:.0f}s")
    out = None
    if args.preview:
        os.makedirs(args.preview, exist_ok=True)
        out = open(os.path.join(args.preview, f"kits-{os.environ.get('SHARD_NAME', 'local')}.jsonl"), "a", encoding="utf-8")
    ok = failed = 0
    for aid in ids:
        if time.time() - t0 > DEADLINE:
            print(f"deadline reached, {len(ids) - ok - failed} left for the next run")
            break
        note = notes.get(aid)
        if not note:
            print(f"{aid}: note not found, skipped")
            continue
        t = time.time()
        kit, tries, err = make_kit(model, note)
        secs = time.time() - t
        if out:
            out.write(json.dumps({"article_id": aid, "note": note, "kit": kit, "tries": tries, "error": err,
                                  "seconds": round(secs, 1)}, ensure_ascii=False) + "\n")
            out.flush()
        else:
            save(up, aid, note, kit, err, prior.get(aid, 0))
        if kit:
            ok += 1
            print(f"{aid}: ok ({tries} {'try' if tries == 1 else 'tries'}, {secs:.0f}s) {kit['short_title']}")
        else:
            failed += 1
            print(f"::warning::{aid}: failed after {tries} tries ({secs:.0f}s): {err}")
    print(f"done: {ok} ok, {failed} failed, {time.time() - t0:.0f}s")


if __name__ == "__main__":
    try:
        main()
    finally:
        close_all()
