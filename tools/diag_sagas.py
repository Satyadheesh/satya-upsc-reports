"""READ-ONLY: how timelines are grouped into sagas today (events.saga_id), with samples."""
import random
import time
from common.db import close_all, main_db

m = main_db()
try:
    rows = m.execute("SELECT saga_id, COUNT(*), SUM(article_count), MAX(last_seen) FROM events WHERE saga_id IS NOT NULL AND title IS NOT NULL GROUP BY saga_id").rows
    print(f"# Sagas\n\n{len(rows)} sagas, {sum(r[1] for r in rows)} timelines in them; "
          f"{m.execute('SELECT COUNT(*) FROM events WHERE title IS NOT NULL').rows[0][0]} titled timelines in all")
    sizes = sorted((r[1] for r in rows), reverse=True)
    print("largest sizes:", sizes[:15])
    recent = [r for r in rows if r[3] and r[3] > time.time() - 60 * 86400]
    print(f"{len(recent)} sagas with an update in the last 60 days\n")
    random.seed(7)
    pick = sorted(recent, key=lambda r: -r[1])[:6] + random.sample(recent, min(8, len(recent)))
    for sid, n, arts, last in pick:
        print(f"## saga {sid} ({n} timelines)")
        for t in m.execute("SELECT id, title, article_count, first_seen, last_seen FROM events WHERE saga_id = ? AND title IS NOT NULL ORDER BY first_seen LIMIT 12", [sid]).rows:
            print(f"- {t[0]} {t[1]} ({t[2]}) {time.strftime('%d %b %Y', time.gmtime(t[3] or 0))}–{time.strftime('%d %b', time.gmtime(t[4] or 0))}")
        print()
finally:
    close_all()
