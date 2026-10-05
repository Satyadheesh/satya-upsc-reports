"""READ-ONLY: main-DB articles of the last 2 days by category and status, with sample titles (for the SSC runner)."""
import collections
import time

from common.db import close_all, main_db

now = int(time.time())
m = main_db()
try:
    floor = m.execute("SELECT id FROM articles WHERE scraped_at >= ? ORDER BY scraped_at LIMIT 1", [now - 2 * 86400]).rows
    fid = floor[0][0] if floor else 0
    rows = m.execute("SELECT id, category, status, rephrased_article IS NOT NULL, COALESCE(NULLIF(rephrased_title,''), title) "
                     "FROM articles WHERE id >= ? ORDER BY id DESC", [fid]).rows
    print(f"{len(rows)} articles since id {fid}")
    print("by status:", collections.Counter((r[2], bool(r[3])) for r in rows).most_common())
    cats = collections.defaultdict(list)
    for r in rows:
        cats[r[1]].append(r[4])
    for c, ts in sorted(cats.items(), key=lambda x: -len(x[1])):
        print(f"\n## {c}: {len(ts)}")
        for t in ts[:8]:
            print(f"- {(t or '')[:110]}")
finally:
    close_all()
