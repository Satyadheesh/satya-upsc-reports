"""READ-ONLY: what the report builder has stored (upsc_reports) — newest builds, by edition, and the latest periods."""
import time

from common.db import close_all, upsc_db

now = int(time.time())
up = upsc_db()
try:
    ago = lambda t: f"{(now - t) / 3600:.1f} h ago"
    rows = up.execute("SELECT key, items, bytes, updated_at FROM upsc_reports ORDER BY updated_at DESC LIMIT 25").rows
    print("== newest 25 stored")
    for k, n, b, t in rows:
        print(f"{k:42} {n:>4} notes {b // 1024:>5} KB  {ago(t)}")
    print("\n== by edition (count, newest, oldest update)")
    for ed in ("brief", "detailed", "ssc"):
        r = up.execute("SELECT COUNT(*), MAX(updated_at), MIN(updated_at) FROM upsc_reports WHERE key LIKE ?", [f"%:{ed}"]).rows[0]
        print(f"{ed:9} {r[0]:>4}  newest {ago(r[1]) if r[1] else '-'}  oldest {ago(r[2]) if r[2] else '-'}")
    print("\n== daily keys for the last 4 days")
    for k, n, b, t in up.execute("SELECT key, items, bytes, updated_at FROM upsc_reports WHERE key LIKE 'daily:2026-10-0%' "
                                 "ORDER BY key").rows:
        print(f"{k:42} {n:>4} notes {b // 1024:>5} KB  {ago(t)}")
    print("\n== stored before the last 24 h (would be stale after a REPORT_VERSION bump)")
    print(up.execute("SELECT COUNT(*) FROM upsc_reports WHERE updated_at < ?", [now - 86400]).rows[0][0])
finally:
    close_all()
