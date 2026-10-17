"""Universal Viral Reels Scorer (Gemma 4 12B).

Scores incoming raw news articles across all topics (cinema, infrastructure, science,
curiosities, consumer hacks, defense, sports, etc.) on viral potential (0 to 10)
for Instagram Reels & YouTube Shorts, enforcing a strict zero-defamation/zero-blame gate.

Results are saved to `reel_candidates` in the UPSC DB.
"""
import argparse
import json
import os
import time

from common.db import close_all, in_chunks, main_db, upsc_db
from kit.model import MODEL_NAME, Model, download

SYSTEM = """You are an expert executive producer for viral short-form news videos (Instagram Reels & YouTube Shorts) for ordinary Indian audiences.
Your goal is to evaluate news stories across ALL topics (cinema/Bollywood, infrastructure, science, space, quirky/bizarre curiosities, defense, sports, consumer hacks, economy, nature) and score their viral potential.

EVALUATION CRITERIA (0 to 10):
1. Scroll-Stopping Hook (0-3): Does the story start with a fascinating contrast, question, or paradox that immediately stops someone scrolling?
2. Scale & Wow Factor (0-3): Does it feature an impressive physical scale, record, massive budget, high number, or unusual feat?
3. Talkability & Shareability (0-4): Would an ordinary Indian share this on WhatsApp with friends or family saying "Did you know this?"

STRICT ZERO-TOLERANCE SAFETY GATE (Score must be 0):
- Political mudslinging, party rivalry, or finger-pointing.
- Crimes, murders, sexual offenses, tragic deaths, accidents with casualties, grief/mourning.
- Personal celebrity scandals, divorces, custody battles, drug allegations.
- Unverified allegations or defamation risks.

Answer in JSON:
- "viral_score": Integer 0 to 10 (7+ means excellent reel material, 0 if safety gate triggered)
- "topic": Short category string (e.g. "cinema", "infrastructure", "science_space", "consumer_hack", "defence", "curiosity", "sports", "economy")
- "hook_angle": A compelling opening hook or question in conversational Hindi (Devanagari)
- "wow_fact": The single most impressive number, record, or fact in the story
- "why": One short sentence explaining the score
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "viral_score": {"type": "integer", "minimum": 0, "maximum": 10},
        "topic": {"type": "string"},
        "hook_angle": {"type": "string"},
        "wow_fact": {"type": "string"},
        "why": {"type": "string"}
    },
    "required": ["viral_score", "topic", "hook_angle", "wow_fact", "why"]
}


def decompress(blob, limit=1200):
    if not blob:
        return ""
    import zlib
    raw = []
    if isinstance(blob, (bytes, bytearray, memoryview)):
        raw.append(bytes(blob))
    else:
        import base64
        try:
            raw.append(base64.b64decode(str(blob), validate=True))
        except Exception:
            return str(blob)[:limit]
    for b in raw:
        for wbits in (15, 47):
            try:
                return zlib.decompress(b, wbits).decode("utf-8", "replace")[:limit]
            except Exception:
                pass
        try:
            return b.decode("utf-8")[:limit]
        except Exception:
            pass
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=30, help="Number of unscored articles to evaluate")
    ap.add_argument("--dry-run", action="store_true", help="Print scores without writing to DB")
    args = ap.parse_args()

    now = int(time.time())
    m_db = main_db()
    u_db = upsc_db()

    # Find articles from the last 24 hours not yet scored in reel_candidates
    since = now - 24 * 3600
    already = {r[0] for r in u_db.execute("SELECT article_id FROM reel_candidates WHERE created_at >= ?", [since - 86400]).rows}

    # Fetch candidate articles
    rows = m_db.execute(
        "SELECT id, title, rephrased_title, rephrased_article, category, scraped_at "
        "FROM articles WHERE scraped_at >= ? ORDER BY id DESC LIMIT 150",
        [since]
    ).rows

    candidates = []
    for r in rows:
        aid = int(r[0])
        if aid not in already:
            candidates.append({
                "id": aid,
                "title": r[2] or r[1],
                "body": decompress(r[3]),
                "category": r[4],
                "scraped_at": int(r[5])
            })
        if len(candidates) >= args.batch:
            break

    if not candidates:
        print(f"No new unscored articles found in the last 24h.")
        return

    print(f"Evaluating {len(candidates)} new articles with Gemma 4 12B ({MODEL_NAME})...")
    model = Model(download())

    scored_count = 0
    high_score_count = 0

    for idx, art in enumerate(candidates, start=1):
        prompt = (
            f"Title: {art['title']}\n"
            f"Category: {art['category']}\n"
            f"Article Body:\n{art['body'][:1000]}\n"
        )
        try:
            res = model.json(SYSTEM, prompt, SCHEMA, temperature=0.1, max_tokens=250)
            score = int(res.get("viral_score") or 0)
            topic = str(res.get("topic") or art["category"])
            hook = str(res.get("hook_angle") or "")
            fact = str(res.get("wow_fact") or "")
            why = str(res.get("why") or "")

            print(f"[{idx}/{len(candidates)}] ID {art['id']} -> Score {score}/10 [{topic}] {art['title'][:70]}")
            if score >= 7:
                print(f"    🌟 High Viral Score: {hook}")
                high_score_count += 1

            if not args.dry_run:
                u_db.execute(
                    "INSERT OR REPLACE INTO reel_candidates "
                    "(article_id, published_at, topic, viral_score, hook_angle, wow_fact, why, model, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [art["id"], art["scraped_at"], topic, score, hook, fact, why, MODEL_NAME, now]
                )
            scored_count += 1
        except Exception as e:
            print(f"  Error scoring article {art['id']}: {e}")

    print(f"\nDone: {scored_count} articles scored ({high_score_count} with viral score >= 7).")


if __name__ == "__main__":
    try:
        main()
    finally:
        close_all()
