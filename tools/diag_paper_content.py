"""READ-ONLY: what the original article text and images look like for the newspaper PDFs (lengths, junk lines,
image hosts), 3 samples from The Hindu and 1 each from TOI and ET."""
import re
import time
from collections import Counter

from common.db import close_all, main_db
from paper.data import text

m = main_db()
since = int(time.time()) - 86400
rows = m.execute("SELECT a.id, s.name, a.title, a.content, a.image_url FROM articles a JOIN sources s ON a.source_id = s.id "
                 "WHERE a.scraped_at >= ? AND s.name IN ('The Hindu','Times of India','Economic Times')", [since]).rows
by = {}
for r in rows:
    by.setdefault(r[1], []).append((r[0], r[2], text(r[3]), r[4] or ""))
for src, its in by.items():
    L = sorted(len(c) for _, _, c, _ in its)
    hosts = Counter(re.sub(r"^https?://([^/]+).*", r"\1", i) for *_, i in its)
    print(f"\n## {src}: {len(its)} articles; content chars p10/p50/p90 = {L[len(L)//10]}/{L[len(L)//2]}/{L[9*len(L)//10]}; "
          f"empty {sum(1 for x in L if x < 200)}; image hosts {hosts.most_common(4)}")
    for aid, title, c, img in its[: (3 if src == 'The Hindu' else 1)]:
        print(f"\n### {aid} {title}\nimage: {img}\n```\n{c[:1500]}\n...\n{c[-400:]}\n```")
close_all()
