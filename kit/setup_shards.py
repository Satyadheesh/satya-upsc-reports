"""Pick the notes that need a study kit and split them across the runners (matrix job).

Normal runs scan only the last RECENT_DAYS of notes (cheap on row reads). A full scan of the
LOOKBACK_DAYS window runs until the backfill is done, then once a night (21:xx UTC) to pick up
notes the UPSC service rewrote. Needs a kit when: no kit yet, the note changed since its kit
was made, or an earlier attempt failed and attempts < MAX_ATTEMPTS.

Preview mode (PREVIEW_N > 0): picks N recent notes across GS papers, ignores kit state, writes nothing.
"""
import json
import os
import time

from common.db import close_all, upsc_db

from .prompt import PROMPT_VERSION

SHARDS = int(os.environ.get("SHARDS") or 5)
BATCH = int(os.environ.get("BATCH") or 120)
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
    shards = [ids[i::n] for i in range(n)]  # newest notes spread over every runner
    return [",".join(map(str, s)) for s in shards if s]


def preview(c, now):
    rows = c.execute("SELECT article_id, gs_paper FROM upsc_articles INDEXED BY idx_upsc_pub "
                     "WHERE published_at >= ? ORDER BY published_at DESC LIMIT 400", [now - 2 * 86400]).rows
    by_paper = {}
    for aid, paper in rows:
        by_paper.setdefault(paper, []).append(aid)
    picked = []
    while len(picked) < PREVIEW_N and any(by_paper.values()):
        for p in sorted(by_paper):
            if by_paper[p] and len(picked) < PREVIEW_N:
                picked.append(by_paper[p].pop(0))
    return picked


def meta(c, key, value=None):
    if value is None:
        r = c.execute("SELECT value FROM kit_meta WHERE key = ?", [key]).rows
        return r[0][0] if r else None
    c.execute("INSERT OR REPLACE INTO kit_meta (key, value) VALUES (?, ?)", [key, str(value)])


def main():
    c = upsc_db()
    now = int(time.time())
    if PREVIEW_N:
        ids = preview(c, now)
        output(shards=json.dumps(split(ids) or [""]), more="false", mode="preview", todo=len(ids))
        return

    full = FULL or meta(c, "backfill_done") != "1" or time.gmtime(now).tm_hour == 21
    since = now - (LOOKBACK_DAYS if full else RECENT_DAYS) * 86400
    rows = c.execute(
        "SELECT a.article_id, a.updated_at, k.status, k.attempts, k.note_updated_at, k.prompt_version "
        "FROM upsc_articles a INDEXED BY idx_upsc_pub LEFT JOIN upsc_kit k ON k.article_id = a.article_id "
        "WHERE a.published_at >= ? ORDER BY a.published_at DESC", [since]).rows
    todo, recheck = [], []
    for aid, upd, status, attempts, made_from, pv in rows:
        if status is None:
            todo.append(aid)
        elif status == "done" and (made_from or 0) < (upd or 0):
            todo.append(aid)
        elif status == "failed" and (attempts or 0) < MAX_ATTEMPTS:
            todo.append(aid)
        elif status == "done" and pv != PROMPT_VERSION:
            recheck.append(aid)  # made before the current checks: verify (cheap), remake only if it fails
    todo += recheck
    if full and not todo:
        meta(c, "backfill_done", "1")
    batch = todo[:BATCH]
    print(f"mode={'full' if full else 'recent'}: {len(rows)} notes scanned, {len(todo)} need a kit, {len(batch)} this run")
    output(shards=json.dumps(split(batch) or [""]), more=str(len(todo) > len(batch)).lower(),
           mode="full" if full else "recent", todo=len(todo))


if __name__ == "__main__":
    try:
        main()
    finally:
        close_all()
