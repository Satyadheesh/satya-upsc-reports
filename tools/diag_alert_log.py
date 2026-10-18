"""READ-ONLY: what the top-news alert picker decided so far (alert_candidates)."""
import time
from common.db import close_all, upsc_db
u = upsc_db()
try:
    rows = u.execute("SELECT decision, COUNT(*), MAX(decided_at) FROM alert_candidates GROUP BY decision").rows
    print("# Alert decisions\n"); [print(f"- {r[0]}: {r[1]} (last {time.strftime('%d %b %H:%M', time.gmtime((r[2] or 0) + 19800))} IST)") for r in rows]
    print("\n## Last 15 judged\n")
    for r in u.execute("SELECT decided_at, decision, importance, score, line_en, why FROM alert_candidates WHERE decided_at IS NOT NULL ORDER BY decided_at DESC LIMIT 30").rows:
        print(f"- {time.strftime('%d %b %H:%M', time.gmtime((r[0] or 0) + 19800))} {r[1]} imp {r[2]} score {r[3]}: {str(r[4])[:110]} — {str(r[5])[:120]}")
finally:
    close_all()
