"""READ-ONLY: the stored SSC report PDFs (key, questions, size, built at)."""
import time
from common.db import close_all, upsc_db
up = upsc_db()
try:
    for k, n, b, t in up.execute("SELECT key, items, bytes, updated_at FROM upsc_reports WHERE key LIKE '%:ssc' ORDER BY updated_at DESC LIMIT 30").rows:
        print(f"- {k}: {n} questions, {b // 1024} KB, built {time.strftime('%d %b %H:%M', time.gmtime(t + 19800))} IST")
finally:
    close_all()
