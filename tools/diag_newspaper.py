"""READ-ONLY: what a 'last 24 hours' newspaper edition per source could contain: articles per source, how many have a
rephrased body, image, category, and Hindi translation coverage; the columns of articles/translations."""
import time
import zlib

from common.db import close_all, main_db, translation_db

m = main_db()
t = translation_db()
now = int(time.time())
since = now - 86400
print("articles columns:", [r[1] for r in m.execute("PRAGMA table_info(articles)").rows])
print("translations columns:", [r[1] for r in t.execute("PRAGMA table_info(translations)").rows])
print("sources:", m.execute("SELECT id, name FROM sources ORDER BY id").rows)
rows = m.execute("SELECT a.id, s.name, a.category, a.image_url IS NOT NULL AND a.image_url != '', a.rephrased_article IS NOT NULL, "
                 "a.status, a.rephrased_title FROM articles a LEFT JOIN sources s ON a.source_id = s.id "
                 "WHERE a.scraped_at >= ?", [since]).rows
print(f"\nlast 24 h: {len(rows)} articles")
from collections import Counter, defaultdict
by = defaultdict(Counter)
for r in rows:
    by[r[1]]["n"] += 1; by[r[1]]["img"] += bool(r[3]); by[r[1]]["reph"] += bool(r[4]); by[r[1]][f"cat:{r[2]}"] += 1
ids = [r[0] for r in rows]
hi = set()
for i in range(0, len(ids), 400):
    ch = ids[i:i + 400]
    hi |= {x[0] for x in t.execute(f"SELECT article_id FROM translations WHERE article_id IN ({','.join('?' * len(ch))}) "
                                   "AND rephrased_title_hi IS NOT NULL", ch).rows}
src = {r[0]: r[1] for r in rows}
for r in rows:
    if r[0] in hi:
        by[r[1]]["hi"] += 1
print("\n| source | articles | rephrased | image | hindi | categories |\n|---|---|---|---|---|---|")
for s, c in sorted(by.items(), key=lambda kv: -kv[1]["n"]):
    cats = ", ".join(f"{k[4:]} {v}" for k, v in c.most_common() if k.startswith("cat:"))[:160]
    print(f"| {s} | {c['n']} | {c['reph']} | {c['img']} | {c['hi']} | {cats} |")
ex = m.execute("SELECT a.rephrased_title, a.rephrased_article FROM articles a WHERE a.scraped_at >= ? AND a.rephrased_article IS NOT NULL "
               "LIMIT 1", [since]).rows
if ex:
    body = ex[0][1]
    try:
        body = zlib.decompress(body).decode()
    except Exception:
        body = str(body)
    print("\nexample:", ex[0][0], "|", len(body), "chars |", body[:400])
close_all()
