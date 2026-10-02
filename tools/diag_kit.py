"""READ-ONLY: study kit progress (English + Hindi) and a few Hindi samples."""
import json
import time

from common.db import close_all, translation_db, upsc_db

now = int(time.time())
up, tr = upsc_db(), translation_db()
try:
    since = now - 30 * 86400
    print("== English study kit (notes of the last 30 days)")
    total = up.execute("SELECT COUNT(*) FROM upsc_articles INDEXED BY idx_upsc_pub WHERE published_at >= ?", [since]).rows[0][0]
    rows = up.execute("SELECT k.status, k.prompt_version, COUNT(*) FROM upsc_kit k JOIN upsc_articles a ON a.article_id = k.article_id "
                      "WHERE a.published_at >= ? GROUP BY k.status, k.prompt_version", [since]).rows
    print(f"notes: {total}")
    for s, pv, n in rows:
        print(f"  {s:6} {pv}: {n}")
    print("\n== Hindi study kit (upsc_kit.translated_hi)")
    for st, n in up.execute("SELECT translated_hi, COUNT(*) FROM upsc_kit WHERE status = 'done' GROUP BY translated_hi").rows:
        label = {1: "translated", 0: "waiting"}.get(st, f"failed x{-st}" if st and st < 0 else str(st))
        print(f"  {label}: {n}")
    try:
        n, last = tr.execute("SELECT COUNT(*), MAX(translated_at) FROM upsc_kit_translations").rows[0]
        print(f"upsc_kit_translations rows: {n}; newest {round((now - (last or now)) / 60)} min ago")
        print("\n== samples")
        for aid, st, tk, mcq in tr.execute("SELECT article_id, short_title_hi, takeaway_hi, mcq_hi FROM upsc_kit_translations "
                                           "ORDER BY translated_at DESC LIMIT 3").rows:
            m = json.loads(mcq)
            print(f"- {aid}: {st}\n  क्यों ज़रूरी: {tk}\n  Q: {m['question']}")
            for i, s in enumerate(m.get("statements") or []):
                print(f"     {i + 1}. {s}")
            print("     " + " | ".join(f"({'abcd'[i]}) {o}{' *' if i == m['answer'] else ''}" for i, o in enumerate(m["options"])))
    except Exception as e:
        print(f"upsc_kit_translations: not created yet ({type(e).__name__})")
finally:
    close_all()
