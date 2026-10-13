"""READ-ONLY: UPSC notes per news source (last 14 days), per day for the top sources."""
import time
from collections import Counter, defaultdict
from common.db import close_all, main_db, upsc_db

now = int(time.time()); since = now - 14 * 86400
up, m = upsc_db(), main_db()
try:
    rows = up.execute("SELECT article_id, published_at FROM upsc_articles WHERE published_at >= ?", [since]).rows
    ids = [r[0] for r in rows]; day = {r[0]: time.strftime('%m-%d', time.gmtime(r[1] + 19800)) for r in rows}
    src = {}
    for ch in [ids[i:i + 400] for i in range(0, len(ids), 400)]:
        q = f"SELECT a.id, s.name FROM articles a LEFT JOIN sources s ON s.id = a.source_id WHERE a.id IN ({','.join('?' * len(ch))})"
        for i, n in m.execute(q, ch).rows:
            src[i] = n
    c = Counter(src.values())
    print(f"notes in 14 days: {len(ids)}")
    for n, k in c.most_common(25):
        print(f"  {k:5}  {n}")
    per = defaultdict(Counter)
    for i in ids:
        per[src.get(i)][day[i]] += 1
    for n, _ in c.most_common(4):
        print(f"\n{n}: " + ", ".join(f"{d}:{per[n][d]}" for d in sorted(per[n])))
finally:
    close_all()
