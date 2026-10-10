"""READ-ONLY: Instagram posting history (ig_posts) and token state."""
import time
from common.db import close_all, upsc_db
up = upsc_db()
try:
    print("## ig_posts (newest 20)")
    for k, mid, t in up.execute("SELECT key, media_id, posted_at FROM ig_posts ORDER BY posted_at DESC LIMIT 20").rows:
        print(f"- {k}: media {mid} at {time.strftime('%d %b %H:%M UTC', time.gmtime(t))}")
    print("\n## tables with 'ig' in the name")
    print([r[0] for r in up.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%ig%'").rows])
finally:
    close_all()
