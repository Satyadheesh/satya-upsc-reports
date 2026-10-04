"""Pick notes that need an SSC CGL flashcard and split them across 7 parallel runners."""
import json
import os
import time

from common.db import close_all, upsc_db
from .ssc import PROMPT_VERSION

SHARDS = int(os.environ.get("SHARDS") or 18)
BATCH = int(os.environ.get("BATCH") or 140)
LOOKBACK_DAYS = int(os.environ.get("LOOKBACK_DAYS") or 30)
RECENT_DAYS = int(os.environ.get("RECENT_DAYS") or 3)
MAX_ATTEMPTS = int(os.environ.get("MAX_ATTEMPTS") or 3)
PREVIEW_N = int(os.environ.get("PREVIEW_N") or 0)
FULL = os.environ.get("FULL", "").lower() in ("1", "true", "yes")


def output(**kv):
    path = os.environ.get("GITHUB_OUTPUT")
    lines = [f"{k}={v}" for k, v in kv.items()]
    print("\n".join(lines))
    if path:
        with open(path, "a") as f:
            f.write("\n".join(lines) + "\n")


def split(ids):
    n = min(SHARDS, len(ids)) or 1
    shards = [ids[i::n] for i in range(n)]
    return [",".join(map(str, s)) for s in shards if s]


def preview(c, now):
    rows = c.execute(
        "SELECT article_id FROM upsc_articles INDEXED BY idx_upsc_pub "
        "WHERE published_at >= ? ORDER BY published_at DESC LIMIT 200",
        [now - 2 * 86400],
    ).rows
    return [r[0] for r in rows[:PREVIEW_N]]


def main():
    c = upsc_db()
    now = int(time.time())
    if PREVIEW_N:
        ids = preview(c, now)
        output(shards=json.dumps(split(ids) or [""]), more="false", mode="preview", todo=len(ids))
        return

    since = now - (LOOKBACK_DAYS if FULL else RECENT_DAYS) * 86400

    # Ensure table exists before querying
    c.execute(
        "CREATE TABLE IF NOT EXISTS ssc_kit ("
        "article_id INTEGER PRIMARY KEY, status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 1, "
        "question_en TEXT, answer_en TEXT, key_fact_en TEXT, static_gk_en TEXT, "
        "question_hi TEXT, answer_hi TEXT, key_fact_hi TEXT, static_gk_hi TEXT, "
        "note_updated_at INTEGER, model TEXT, prompt_version TEXT, error TEXT, "
        "created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL)"
    )

    rows = c.execute(
        "SELECT a.article_id, a.updated_at, k.status, k.attempts, k.note_updated_at, k.prompt_version "
        "FROM upsc_articles a INDEXED BY idx_upsc_pub LEFT JOIN ssc_kit k ON k.article_id = a.article_id "
        "WHERE a.published_at >= ? ORDER BY a.published_at DESC",
        [since],
    ).rows

    todo = []
    for aid, upd, status, attempts, made_from, pv in rows:
        if status is None:
            todo.append(aid)
        elif status == "done" and (made_from or 0) < (upd or 0):
            todo.append(aid)
        elif status == "failed" and (attempts or 0) < MAX_ATTEMPTS:
            todo.append(aid)
        elif status == "done" and pv != PROMPT_VERSION:
            todo.append(aid)

    batch = todo[:BATCH]
    print(f"SSC mode={'full' if FULL else 'recent'}: {len(rows)} notes scanned, {len(todo)} need SSC kit, {len(batch)} this run")
    output(
        shards=json.dumps(split(batch) or [""]),
        more=str(len(todo) > len(batch)).lower(),
        mode="full" if FULL else "recent",
        todo=len(todo),
    )


if __name__ == "__main__":
    try:
        main()
    finally:
        close_all()
