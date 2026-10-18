"""READ-ONLY: picked alerts and whether the admin Telegram message went out (admin_msg = Telegram message id)."""
import time
from common.db import close_all, upsc_db
u = upsc_db()
try:
    for r in u.execute("SELECT decided_at, decision, importance, admin_msg, line_en FROM alert_candidates WHERE decision = 'picked' OR decision LIKE 'blocked%' ORDER BY decided_at").rows:
        print(f"- {time.strftime('%d %b %H:%M', time.gmtime((r[0] or 0) + 19800))} IST {r[1]} imp {r[2]} admin_msg={r[3]}: {str(r[4])[:90]}")
    print("summaries:", u.execute("SELECT key, chat, message_id, posted_at FROM telegram_posts WHERE key LIKE 'alerts-summary%'").rows)
finally:
    close_all()
