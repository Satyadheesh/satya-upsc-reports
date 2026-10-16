"""READ-ONLY: the signals a 'top news for everyone' picker would use, over the last 48 h: how stories cluster across
outlets, categories, geo focus, civic flags, timelines. To calibrate the scoring before building it."""
import collections
import time
from common.db import close_all, in_chunks, main_db

m = main_db()
try:
    now = int(time.time())
    rows = m.execute("SELECT a.id, a.cluster_id, a.source_id, a.scraped_at, a.category, a.geo_focus, a.civic_flag, a.civic_flag_score, "
                     "a.rephrased_title, a.title, a.status, a.translated_hi FROM articles a INDEXED BY idx_articles_scraped "
                     "WHERE a.scraped_at >= ?", [now - 48 * 3600]).rows
    print(f"articles in 48 h: {len(rows)}; statuses {collections.Counter(r[10] for r in rows).most_common(6)}")
    print("categories:", collections.Counter(r[4] for r in rows).most_common(12))
    print("geo_focus:", collections.Counter(r[5] for r in rows).most_common(8))
    print("with cluster_id:", sum(1 for r in rows if r[1]), "| civic flagged:", sum(1 for r in rows if r[6] == 1))
    cl = collections.defaultdict(list)
    for r in rows:
        if r[1]:
            cl[r[1]].append(r)
    sizes = collections.Counter(min(len({x[2] for x in v}), 10) for v in cl.values())
    print("clusters by number of distinct outlets:", sorted(sizes.items()))
    ev = {r[0]: r[1] for r in in_chunks(m, "SELECT article_id, event_id FROM event_articles WHERE article_id IN ({ph})", [r[0] for r in rows])}
    print(f"articles on a timeline: {len(ev)}")
    top = sorted(cl.values(), key=lambda v: -len({x[2] for x in v}))[:25]
    print("\n## top 25 clusters (outlets | articles | first seen IST | category | geo | on timeline | headline)")
    for v in top:
        v.sort(key=lambda x: x[3])
        h = next((x[8] for x in v if x[8]), v[0][9])
        print(f"- {len({x[2] for x in v})} | {len(v)} | {time.strftime('%d %b %H:%M', time.gmtime(v[0][3] + 19800))} | {v[0][4]} | {v[0][5]} | "
              f"{any(x[0] in ev for x in v)} | {(h or '')[:110]}")
finally:
    close_all()
