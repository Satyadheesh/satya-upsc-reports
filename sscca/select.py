"""Pick news articles the SSC runner hasn't judged yet and split them across parallel runners.

  python -m sscca.select           (GitHub outputs: shards, more)
Newest first; skips crime news, articles without a rephrase, and stories (same news cluster) that already have a card.
"""
import json
import os
import time

from common.db import close_all, in_chunks, main_db, upsc_db

from .gate import GATE_VERSION

SHARDS = int(os.environ.get("SHARDS") or 8)
BATCH = int(os.environ.get("BATCH") or 240)
DAYS = int(os.environ.get("DAYS") or 2)
MAX_ATTEMPTS = 3
ELIGIBLE = ("classified", "entity_processed", "processed")
SKIP_CATEGORIES = {"crime"}


def output(**kv):
    lines = [f"{k}={v}" for k, v in kv.items()]
    print("\n".join(lines))
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write("\n".join(lines) + "\n")


def main():
    now = int(time.time())
    m, up = main_db(), upsc_db()
    floor = m.execute("SELECT id FROM articles WHERE scraped_at >= ? ORDER BY scraped_at LIMIT 1", [now - DAYS * 86400]).rows
    fid = floor[0][0] if floor else 0
    ph = ",".join("?" * len(ELIGIBLE))
    arts = m.execute(f"SELECT id, category, cluster_id, scraped_at FROM articles WHERE id >= ? AND status IN ({ph}) "
                     f"AND rephrased_article IS NOT NULL ORDER BY id DESC", [fid, *ELIGIBLE]).rows
    ids = [int(r[0]) for r in arts]
    seen = {int(r[0]): (r[1], r[2], r[3]) for r in in_chunks(
        up, "SELECT article_id, status, attempts, prompt_version FROM ssc_ca WHERE article_id IN ({ph})", ids)} if ids else {}
    carded = {r[0] for r in up.execute("SELECT cluster_id FROM ssc_ca WHERE status = 'card' AND cluster_id IS NOT NULL "
                                       "AND published_at >= ?", [now - (DAYS + 3) * 86400]).rows}
    todo, dup = [], []
    for aid, cat, cluster, pub in arts:
        aid = int(aid)
        if (cat or "").lower() in SKIP_CATEGORIES:
            continue
        st = seen.get(aid)
        if st and st[0] in ("card", "skip") and st[2] == GATE_VERSION:
            continue
        if st and st[0] == "failed" and (st[1] or 0) >= MAX_ATTEMPTS:
            continue
        if cluster and cluster in carded and not (st and st[0] == "card"):
            dup.append((aid, cluster, int(pub or now)))
            continue
        todo.append(aid)
    # same story already has a card: record without a model call (not in a preview run)
    for aid, cluster, pub in ([] if os.environ.get("PREVIEW") == "true" else dup):
        up.execute("INSERT OR REPLACE INTO ssc_ca (article_id, published_at, cluster_id, status, attempts, reason, "
                   "prompt_version, created_at, updated_at) VALUES (?, ?, ?, 'skip', 1, 'duplicate story', ?, ?, ?)",
                   [aid, pub, cluster, GATE_VERSION, now, now])
    batch = todo[:BATCH]
    n = min(SHARDS, len(batch)) or 1
    shards = [",".join(map(str, batch[i::n])) for i in range(n) if batch[i::n]]
    print(f"{len(arts)} articles in {DAYS} days, {len(todo)} to judge, {len(dup)} duplicates, {len(batch)} this run")
    output(shards=json.dumps(shards or [""]), more=str(len(todo) > len(batch)).lower(), todo=len(todo))


if __name__ == "__main__":
    try:
        main()
    finally:
        close_all()
