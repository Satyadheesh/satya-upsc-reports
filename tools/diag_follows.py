"""READ-ONLY: timeline follows (devices, follows, waiting updates) and the notification job's bookmark."""
import time
from common.db import close_all, main_db
m = main_db()
try:
    def q(s, a=()):
        return m.execute(s, list(a)).rows
    print("devices:", q("SELECT COUNT(*), SUM(last_sent_at > 0), MAX(created_at) FROM tl_push"))
    print("follows:", q("SELECT COUNT(*), COUNT(DISTINCT endpoint), SUM(pending > 0), MAX(last_sent_at) FROM tl_follows"))
    for r in q("SELECT f.event_id, e.title, f.pending, f.last_sent_at, f.created_at FROM tl_follows f LEFT JOIN events e ON e.id = f.event_id ORDER BY f.created_at DESC LIMIT 10"):
        print(f"- {r[0]} {str(r[1])[:60]} pending={r[2]} last_sent={time.strftime('%d %b %H:%M', time.gmtime((r[3] or 0) + 19800)) if r[3] else '-'} followed={time.strftime('%d %b %H:%M', time.gmtime(r[4] + 19800))} IST")
    print("bookmark:", q("SELECT * FROM tl_meta"))
finally:
    close_all()
