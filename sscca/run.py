"""SSC current-affairs runner, one shard: judge each article (sscca.gate), write an SSC card for the kept ones
(kit.run_ssc.generate_card: question/answer checks, LLM judge, verified static GK) and store it in ssc_ca.

  python -m sscca.run --ids 1,2,3 [--preview out/]
"""
import argparse
import json
import os
import time
import zlib

from common.db import close_all, in_chunks, main_db, upsc_db
from kit.model import MODEL_NAME, Model, download
from kit.run_ssc import generate_card

from .gate import GATE_VERSION, TOPICS, check

DEADLINE = int(os.environ.get("SHARD_DEADLINE_SEC") or 3000)


def decode(blob):
    if blob is None:
        return ""
    if isinstance(blob, (bytes, bytearray, memoryview)):
        try:
            return zlib.decompress(bytes(blob)).decode("utf-8")
        except zlib.error:
            return bytes(blob).decode("utf-8", "ignore")
    return str(blob)


def load(ids):
    m = main_db()
    arts = {}
    for aid, title, orig, reph, content, cat, pub, cluster in in_chunks(
            m, "SELECT id, rephrased_title, title, rephrased_article, content, category, scraped_at, cluster_id "
               "FROM articles WHERE id IN ({ph})", ids):
        body = decode(reph)
        if len(body) < 400:
            body = (body + "\n" + decode(content)).strip()
        arts[int(aid)] = {"id": int(aid), "title": (title or orig or "").strip(), "original_title": (orig or "").strip(),
                          "body": body, "category": cat, "published_at": int(pub or 0), "cluster_id": cluster}
    return arts


def save(up, a, status, attempts, gate=None, card=None, reason=None):
    now = int(time.time())
    g = gate or {}
    c = card or {}
    up.execute(
        "INSERT OR REPLACE INTO ssc_ca (article_id, published_at, cluster_id, status, attempts, topic, importance, scope, "
        "fact, title, question, answer, key_fact, static_gk, reason, model, prompt_version, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [a["id"], a["published_at"], a["cluster_id"], status, attempts, g.get("topic"), g.get("importance"),
         g.get("scope"), g.get("fact"), a["title"], c.get("ssc_question"), c.get("ssc_answer"), c.get("key_fact"),
         c.get("static_gk"), (reason or "")[:1000], MODEL_NAME, GATE_VERSION, now, now])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", required=True)
    ap.add_argument("--preview", default="")
    a = ap.parse_args()
    ids = [int(x) for x in a.ids.split(",") if x.strip().isdigit()]
    if not ids:
        print("no ids")
        return
    arts = load(ids)
    up = upsc_db()
    prior = {int(r[0]): int(r[1] or 0) for r in in_chunks(
        up, "SELECT article_id, attempts FROM ssc_ca WHERE status = 'failed' AND article_id IN ({ph})", ids)}
    model = Model(download())
    t0, kept, cards, rows = time.time(), 0, 0, []
    for i, aid in enumerate(ids, 1):
        if time.time() - t0 > DEADLINE:
            print(f"deadline after {i - 1} articles")
            break
        art = arts.get(aid)
        if not art or len(art["body"]) < 200:
            continue
        attempts = prior.get(aid, 0) + 1
        g = check(model, art["title"], art["body"])
        if not g["keep"]:
            print(f"[{i}/{len(ids)}] {aid} skip ({g['why']}; {g['topic']}) {art['title'][:70]}", flush=True)
            if not a.preview:
                save(up, art, "failed" if g["why"].startswith("error") else "skip", attempts, g, reason=g["why"])
            rows.append({"id": aid, "title": art["title"], **g})
            continue
        kept += 1
        # the card is written from the article: title, the gate's fact first, then the article text
        note = {"article_id": aid, "title": art["title"], "original_title": art["original_title"],
                "subject": TOPICS[g["topic"]][1], "why_in_news": g["fact"], "fact_box": art["body"][:1500],
                "prelims_pointers": [], "keywords": [], "mains_question": ""}
        card, err = generate_card(model, note)
        if card:
            cards += 1
            print(f"[{i}/{len(ids)}] {aid} CARD [{g['topic']}/{g['importance']}] {card['ssc_question'][:70]} -> {card['ssc_answer']}",
                  flush=True)
            if not a.preview:
                save(up, art, "card", attempts, g, card, reason="kept")
        else:
            print(f"[{i}/{len(ids)}] {aid} kept but no valid card: {str(err)[:160]}", flush=True)
            if not a.preview:
                save(up, art, "failed" if attempts < 3 else "skip", attempts, g, reason=f"card: {str(err)[:800]}")
        rows.append({"id": aid, "title": art["title"], **g, "card": card, "card_error": None if card else str(err)[:400]})
    if a.preview:
        os.makedirs(a.preview, exist_ok=True)
        with open(os.path.join(a.preview, f"sscca-{os.environ.get('SHARD_NAME', '0')}.json"), "w") as f:
            json.dump(rows, f, ensure_ascii=False)
    print(f"done: {len(rows)} judged, {kept} kept, {cards} cards in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    try:
        main()
    finally:
        close_all()
