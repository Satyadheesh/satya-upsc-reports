"""READ-ONLY: check ssc_kit entries and stored ssc reports."""
import time

from common.db import close_all, upsc_db

up = upsc_db()
try:
    print("=== upsc_reports (ssc keys) ===")
    for r in up.execute("SELECT key, bytes, updated_at FROM upsc_reports WHERE key LIKE '%:ssc%' ORDER BY updated_at DESC").rows:
        print(f"key={r[0]}, bytes={r[1]}, updated_at={r[2]} ({time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(r[2]))})")

    print("\n=== ssc_kit count ===")
    total = up.execute("SELECT COUNT(*) FROM ssc_kit").rows[0][0]
    done = up.execute("SELECT COUNT(*) FROM ssc_kit WHERE status='done'").rows[0][0]
    print(f"ssc_kit total: {total}, done: {done}")
    for r in up.execute("SELECT article_id, question_en, answer_en, static_gk_en FROM ssc_kit WHERE status='done' LIMIT 3").rows:
        print(f"- {r[0]}: {r[1]}\n  Ans: {r[2]}\n  Static: {r[3]}")
finally:
    close_all()
