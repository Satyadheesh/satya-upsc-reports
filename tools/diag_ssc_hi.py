"""READ-ONLY: Hindi SSC cards and the Hindi SSC PDFs."""
from common.db import close_all, translation_db, upsc_db

up, tr = upsc_db(), translation_db()
def one(db, sql, args=()):
    try:
        return db.execute(sql, list(args)).rows
    except Exception as e:
        return [(f"error: {e}",)]
try:
    print("ssc_ca columns:", [r[1] for r in one(up, "PRAGMA table_info(ssc_ca)")])
    print("cards by hi_state:", one(up, "SELECT hi_state, COUNT(*) FROM ssc_ca WHERE status = 'card' GROUP BY hi_state"))
    print("ssc_ca_translations rows:", one(tr, "SELECT COUNT(*), MAX(translated_at) FROM ssc_ca_translations"))
    print("Hindi SSC PDFs (newest 8):", one(up, "SELECT key FROM upsc_reports WHERE key LIKE '%:hi:ssc' ORDER BY key DESC LIMIT 8"))
    print("English SSC PDFs (newest 3):", one(up, "SELECT key FROM upsc_reports WHERE key LIKE '%:en:ssc' ORDER BY key DESC LIMIT 3"))
finally:
    close_all()
