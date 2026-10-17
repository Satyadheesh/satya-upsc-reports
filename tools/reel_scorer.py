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


SCRIPT_SYSTEM = """You are an expert Indian short-form news storyteller creating high-retention Instagram Reels in natural conversational Hindi.
For the given news article, write a punchy 4-part narration script strictly in natural, everyday Hindi (Devanagari script).
The script MUST sound natural and conversational when spoken aloud by an Indian creator.
Avoid formal bureaucratic Hindi or robotic clichés. Never output raw English words unless they are everyday terms (like 'dialysis', 'center', 'doctor', 'hospital', 'ticket').

Structure:
1. headline_hi: Catchy on-screen headline in Hindi (max 8 words)
2. hook_say: 1-2 opening spoken lines in Hindi grabbing immediate attention
3. core_title_hi: Short title for core news card (max 8 words)
4. core_say: 2-3 spoken lines explaining what actually happened in simple concrete Hindi
5. twist_stat: The key number or word (e.g. '₹999' or '22 केंद्र')
6. twist_label: Short label (e.g. 'डायलिसिस फ़ीस' or 'नए केंद्र')
7. twist_say: 1-2 spoken lines explaining the ground reality, key number, or budget/contrast
8. question_hi: On-screen question for engagement card
9. engagement_say: A natural thought-provoking question encouraging comments and discussion
"""

SCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "headline_hi": {"type": "string"},
        "hook_say": {"type": "string"},
        "core_title_hi": {"type": "string"},
        "core_say": {"type": "string"},
        "twist_stat": {"type": "string"},
        "twist_label": {"type": "string"},
        "twist_say": {"type": "string"},
        "question_hi": {"type": "string"},
        "engagement_say": {"type": "string"}
    },
    "required": [
        "headline_hi", "hook_say", "core_title_hi", "core_say",
        "twist_stat", "twist_label", "twist_say", "question_hi", "engagement_say"
    ]
}


def dispatch_daily_reel(u_db, m_db, model=None, force=False):
    """Dispatches the top viral story of the day to Satyadheesh/reels via repository_dispatch."""
    token = os.environ.get("CORE_TOKEN") or os.environ.get("GITHUB_PAT") or os.environ.get("GITHUB_PAT_CLASSIC")
    if not token:
        print("  Notice: No GitHub PAT found (CORE_TOKEN); skipping reel dispatch.")
        return

    now = int(time.time())
    # Ensure at most 1 reel per 12 hours unless force=True
    if not force:
        # Check 1: Turso DB reel_posts
        try:
            recent = u_db.execute("SELECT max(dispatched_at) FROM reel_posts").rows
            if recent and recent[0][0] and (now - int(recent[0][0])) < 12 * 3600:
                last_ago_hrs = (now - int(recent[0][0])) / 3600
                print(f"  Daily reel already dispatched {last_ago_hrs:.1f}h ago (< 12 hours). Skipping duplicate dispatch.")
                return
        except Exception:
            pass

        # Check 2: Satyadheesh/reels GitHub Actions runs (in case run was triggered directly)
        try:
            import datetime
            import urllib.request
            gh_url = "https://api.github.com/repos/Satyadheesh/reels/actions/workflows/daily-reel.yml/runs?status=success&per_page=1"
            req = urllib.request.Request(gh_url, headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "satya-reel-scorer"
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
                runs = data.get("workflow_runs", [])
                if runs:
                    updated = datetime.datetime.fromisoformat(runs[0]["updated_at"].replace("Z", "+00:00"))
                    diff_hrs = (datetime.datetime.now(datetime.timezone.utc) - updated).total_seconds() / 3600.0
                    if diff_hrs < 12.0:
                        print(f"  Reel already posted to Telegram {diff_hrs:.1f}h ago (< 12 hours). Skipping dispatch.")
                        return
        except Exception as e:
            print(f"  Note: GitHub Actions run check: {e}")

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

    # Synthesize complete 4-part Hindi script using Gemma 4 12B if model is loaded
    script_data = None
    if model:
        print(f"  Synthesizing fluent 4-part Hindi narration for #{aid} with Gemma 4 12B...")
        try:
            sprompt = (
                f"Headline: {title}\n"
                f"Topic: {topic}\n"
                f"Opening Hook Angle: {hook}\n"
                f"Wow Fact: {fact}\n"
                f"Article Details:\n{body[:1200]}\n"
            )
            script_data = model.json(SCRIPT_SYSTEM, sprompt, SCRIPT_SCHEMA, temperature=0.2, max_tokens=350)
        except Exception as e:
            print(f"  Script generation warning: {e}")

    headline_hi = (script_data and script_data.get("headline_hi")) or title[:40]
    hook_say = (script_data and script_data.get("hook_say")) or hook
    core_title = (script_data and script_data.get("core_title_hi")) or "पूरी जानकारी"
    core_say = (script_data and script_data.get("core_say")) or f"इस मामले की पूरी जानकारी ये है कि {fact}।"
    twist_stat = (script_data and script_data.get("twist_stat")) or "बड़ा बदलाव"
    twist_label = (script_data and script_data.get("twist_label")) or "का असर"
    twist_say = (script_data and script_data.get("twist_say")) or f"ज़मीनी सच्चाई ये है कि {fact}।"
    q_hi = (script_data and script_data.get("question_hi")) or "आपकी क्या राय है?"
    eng_say = (script_data and script_data.get("engagement_say")) or "इस पूरे मामले पर आपकी क्या सोच है? कमेंट में बताइए और फ़ॉलो कीजिए सत्याधीश।"

    payload = {
        "article_id": aid,
        "category": topic,
        "headline": headline_hi,
        "image_url": img,
        "hook": {
            "badge": "ताज़ा पड़ताल",
            "title": headline_hi,
            "subtitle": "सत्याधीश रिपोर्ट",
            "say": hook_say
        },
        "core": {
            "badge": "मुख्य जानकारी",
            "title": core_title,
            "points": [fact[:80] or "सटीक रिपोर्ट", "सत्यापित डेटा", "The Hindu"],
            "source": "The Hindu",
            "say": core_say
        },
        "twist": {
            "badge": "ज़मीनी हक़ीक़त",
            "big_stat": twist_stat,
            "stat_label": twist_label,
            "detail": fact[:80] or "ज़मीनी हक़ीक़त",
            "say": twist_say
        },
        "engagement": {
            "headline": "सत्याधीश चर्चा",
            "question": q_hi,
            "cta": "कमेंट में अपनी राय ज़रूर लिखें!",
            "say": eng_say
        }
    }

    print(f"\n🚀 Dispatching top viral reel to Satyadheesh/reels:")
    print(f"   Article #{aid} (Score {score}/10) [{topic}]")
    print(f"   Hook: {hook_say[:70]}")

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
        dispatch_daily_reel(u_db, m_db, model=model, force=args.dispatch)


if __name__ == "__main__":
    try:
        main()
    finally:
        close_all()
