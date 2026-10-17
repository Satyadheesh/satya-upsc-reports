"""READ-ONLY: the timelines with the most updates in the last 3 days (to pick ones to follow while testing)."""
import time
from common.db import close_all, main_db
m = main_db()
try:
    since = int(time.time()) - 3 * 86400
    rows = m.execute("SELECT e.slug, e.title, COUNT(*) AS n, MAX(ea.event_date) FROM event_articles ea JOIN events e ON e.id = ea.event_id "
                     "WHERE ea.event_date >= ? AND e.slug IS NOT NULL GROUP BY ea.event_id ORDER BY n DESC LIMIT 10", [since]).rows
    for slug, title, n, last in rows:
        print(f"- {n} updates, last {time.strftime('%d %b %H:%M', time.gmtime(last + 19800))} IST — {title}\n  https://satyadheesh.in/event/{slug}?follow-beta=1")
finally:
    close_all()
