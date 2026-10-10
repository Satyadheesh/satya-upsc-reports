"""READ-ONLY: progress of the 10 Oct Hindi redo (notes + kits of the last 10 days), Hindi SSC cards, Hindi SSC PDFs."""
import time

from common.db import close_all, translation_db as trans_db, upsc_db

CUT = 1791627300   # redo marked at 10 Oct 10:15 UTC
now = int(time.time())
since = now - 10 * 86400
up, tr = upsc_db(), trans_db()
try:
    ids = [r[0] for r in up.execute("SELECT article_id FROM upsc_articles WHERE published_at >= ?", [since]).rows]
    todo_n = up.execute("SELECT COUNT(*) FROM upsc_articles WHERE published_at >= ? AND translated_hi = 0", [since]).rows[0][0]
    kit = dict(up.execute("SELECT k.translated_hi, COUNT(*) FROM upsc_kit k JOIN upsc_articles a ON a.article_id = k.article_id "
                          "WHERE a.published_at >= ? AND k.status = 'done' GROUP BY 1", [since]).rows)
    new_n = new_k = 0
    for i in range(0, len(ids), 400):
        ch = ids[i:i + 400]
        ph = ",".join("?" * len(ch))
        new_n += tr.execute(f"SELECT COUNT(*) FROM upsc_translations WHERE article_id IN ({ph}) AND translated_at >= ?", [*ch, CUT]).rows[0][0]
        new_k += tr.execute(f"SELECT COUNT(*) FROM upsc_kit_translations WHERE article_id IN ({ph}) AND translated_at >= ?", [*ch, CUT]).rows[0][0]
    print(f"notes (last 10 days, {len(ids)}): {new_n} re-translated since 10:15 UTC, {todo_n} still waiting")
    print(f"kits: {new_k} re-translated since 10:15 UTC; state counts {kit} (0 = waiting, 1 = done, <0 = failed tries)")
    try:
        print("ssc_ca hi_state:", up.execute("SELECT hi_state, COUNT(*) FROM ssc_ca WHERE status = 'card' GROUP BY 1").rows)
    except Exception as e:
        print("ssc_ca hi_state: n/a", type(e).__name__)
    try:
        print("ssc_ca_translations rows:", tr.execute("SELECT COUNT(*), MAX(translated_at) FROM ssc_ca_translations").rows[0])
    except Exception as e:
        print("ssc_ca_translations: n/a", type(e).__name__)
    print("Hindi SSC PDFs:", up.execute("SELECT key, items, updated_at FROM upsc_reports WHERE key LIKE '%:hi:ssc' ORDER BY updated_at DESC LIMIT 5").rows)
finally:
    close_all()
