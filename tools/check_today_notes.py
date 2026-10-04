"""Check which notes of today have an entry in ssc_kit vs missing."""
import time

from common.db import close_all, main_db, upsc_db
from reports.data import Window

now = int(time.time())
up, mn = upsc_db(), main_db()
try:
    # 2026-10-04
    start = 1791052200  # approximately today's midnight IST
    # Let's inspect rows in upsc_articles for today
    rows = up.execute("SELECT article_id, title_hi_state FROM upsc_articles WHERE published_at >= ? ORDER BY published_at DESC LIMIT 30", [now - 86400]).rows
    print(f"Notes in last 24h: {len(rows)}")
    for r in rows:
        aid = r[0]
        k = up.execute("SELECT status, question_en, answer_en FROM ssc_kit WHERE article_id = ?", [aid]).rows
        if k:
            print(f"  [OK] note {aid}: Q={k[0][1][:60]} | A={k[0][2]}")
        else:
            print(f"  [MISSING] note {aid} has NO entry in ssc_kit!")
finally:
    close_all()
