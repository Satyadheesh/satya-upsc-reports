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
Your goal is to evaluate news stories across ALL topics (politics & political funding/chanda, cinema/Bollywood, infrastructure, science, space, quirky/bizarre curiosities, defense, sports, consumer hacks, economy, nature) and score their viral potential.

EVALUATION CRITERIA (0 to 10):
1. Scroll-Stopping Hook (0-3): Does the story start with a fascinating contrast, question, or paradox that immediately stops someone scrolling?
2. Scale & Wow Factor (0-3): Does it feature an impressive physical scale, record, massive budget, high number, or unusual feat?
3. Talkability & Shareability (0-4): Would an ordinary Indian share this on WhatsApp with friends or family saying "Did you know this?" (e.g. mind-blowing political donation/chanda figures, electoral bond disclosures, declared neta assets vs reality, giant taxpayer spending, viral cinema/sports milestones, tech wonders).

WHAT TO REJECT (Score 0):
- Routine partisan name-calling, spokesperson bickering, or unverified verbal allegations without official records.
- Mundane procedural press releases or local party committee reshuffles.
- Violent crimes, murders, sexual offenses, tragic deaths, accidents with casualties, grief/mourning.
- Personal celebrity scandals, divorces, custody battles.
- Defamation hazards (claims must be grounded in official records, EC filings, CAG audits, affidavits, or established data).

Answer in JSON:
- "viral_score": Integer 0 to 10 (7+ means excellent reel material, 0 if rejection criteria met)
- "topic": Short category string (e.g. "politics_funding", "cinema", "infrastructure", "science_space", "consumer_hack", "defence", "curiosity", "sports", "economy")
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


def dispatch_daily_reel(u_db, m_db, force=False):
    """Dispatches the top viral story of the day to Satyadheesh/reels via repository_dispatch."""
    token = os.environ.get("CORE_TOKEN") or os.environ.get("GITHUB_PAT") or os.environ.get("GITHUB_PAT_CLASSIC")
    if not token:
        print("  Notice: No GitHub PAT found (CORE_TOKEN); skipping reel dispatch.")
        return

    now = int(time.time())
    # Ensure at most 1 reel per ~18 hours unless force=True
    if not force:
        try:
            recent = u_db.execute("SELECT max(dispatched_at) FROM reel_posts").rows
            if recent and recent[0][0] and (now - int(recent[0][0])) < 18 * 3600:
                last_ago_hrs = (now - int(recent[0][0])) / 3600
                print(f"  Daily reel already dispatched {last_ago_hrs:.1f}h ago. Skipping duplicate dispatch.")
                return
        except Exception:
            pass

    # Find the highest viral score candidate (>= 7) from the last 24h not yet reeled
    since = now - 24 * 3600
    try:
        candidates = u_db.execute(
            "SELECT c.article_id, c.topic, c.viral_score, c.hook_angle, c.wow_fact, c.why "
            "FROM reel_candidates c "
            "WHERE c.viral_score >= 7 AND c.created_at >= ? "
            "  AND c.article_id NOT IN (SELECT article_id FROM reel_posts) "
            "ORDER BY c.viral_score DESC, c.published_at DESC "
            "LIMIT 1",
            [since]
        ).rows
    except Exception as e:
        print(f"  Error querying reel_candidates for dispatch: {e}")
        return

    if not candidates:
        print("  No new high viral candidate (score >= 7) available to dispatch right now.")
        return

    top = candidates[0]
    aid, topic, score, hook, fact, why = int(top[0]), str(top[1]), int(top[2]), str(top[3]), str(top[4]), str(top[5])

    # Fetch article details from main DB
    art_rows = m_db.execute(
        "SELECT title, rephrased_title, rephrased_article, category, image_url, url "
        "FROM articles WHERE id = ?",
        [aid]
    ).rows

    if not art_rows:
        print(f"  Article {aid} not found in main DB.")
        return

    r = art_rows[0]
    title = r[1] or r[0]
    body = decompress(r[2])
    cat = r[3] or topic
    img = r[4] or ""
    source_url = r[5] or ""

    payload = {
        "article_id": aid,
        "title": title,
        "topic": topic,
        "viral_score": score,
        "hook_angle": hook,
        "wow_fact": fact,
        "body": body[:1200],
        "image_url": img,
        "source": "The Hindu"
    }

    print(f"\n🚀 Dispatching top viral reel to Satyadheesh/reels:")
    print(f"   Article #{aid} (Score {score}/10) [{topic}]")
    print(f"   Hook: {hook}")

    import urllib.request
    req = urllib.request.Request(
        "https://api.github.com/repos/Satyadheesh/reels/dispatches",
        data=json.dumps({"event_type": "generate_reel", "client_payload": payload}).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "satya-reel-scorer"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status in (200, 204):
                print(f"✅ Successfully dispatched reel event for #{aid} to Satyadheesh/reels!")
                u_db.execute(
                    "INSERT OR REPLACE INTO reel_posts (article_id, title, topic, viral_score, hook_angle, dispatched_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    [aid, title, topic, score, hook, now]
                )
            else:
                print(f"⚠️ Dispatch returned status {resp.status}")
    except Exception as e:
        print(f"❌ Failed to dispatch to Satyadheesh/reels: {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=30, help="Number of unscored articles to evaluate")
    ap.add_argument("--dry-run", action="store_true", help="Print scores without writing to DB")
    ap.add_argument("--dispatch", action="store_true", help="Force dispatch of top candidate")
    ap.add_argument("--no-dispatch", action="store_true", help="Do not trigger reels repo")
    args = ap.parse_args()

    now = int(time.time())
    m_db = main_db()
    u_db = upsc_db()

    # Find articles from the last 24 hours not yet scored in reel_candidates
    since = now - 24 * 3600
    already = {r[0] for r in u_db.execute("SELECT article_id FROM reel_candidates WHERE created_at >= ?", [since - 86400]).rows}

    # Fetch candidate articles across all categories
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
        if not args.no_dispatch and not args.dry_run:
            dispatch_daily_reel(u_db, m_db, force=args.dispatch)
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

    if not args.no_dispatch and not args.dry_run:
        dispatch_daily_reel(u_db, m_db, force=args.dispatch)


if __name__ == "__main__":
    try:
        main()
    finally:
        close_all()
