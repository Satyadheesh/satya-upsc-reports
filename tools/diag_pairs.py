"""READ-ONLY: notes of given article ids (DIAG_IDS env or the default list) with title, paper/subject, why, dims."""
import json
import os
import time

from common.db import close_all, in_chunks, main_db, upsc_db

ids = [int(x) for x in (os.environ.get("DIAG_IDS") or "129835,129801,129798,129419").split(",")]
up, mn = upsc_db(), main_db()
try:
    t = {r[0]: (r[1], r[2], r[3]) for r in in_chunks(mn, "SELECT a.id, COALESCE(NULLIF(a.rephrased_title,''), a.title), a.cluster_id, "
                                                          "(SELECT MIN(event_id) FROM event_articles e WHERE e.article_id = a.id) "
                                                          "FROM articles a WHERE a.id IN ({ph})", ids)}
    for r in in_chunks(up, "SELECT article_id, published_at, gs_paper, subject, syllabus_node, why_in_news, mains_dimensions, "
                           "prompt_version, event_id, cluster_id FROM upsc_articles WHERE article_id IN ({ph})", ids):
        title, cl, ev = t.get(r[0], ("?", None, None))
        print(f"## {r[0]} · {time.strftime('%d %b %H:%M', time.gmtime(r[1] + 19800))} IST · {r[2]}/{r[3]}/{r[4]} · {r[7]} · event {r[8]}/{ev} cluster {r[9]}/{cl}")
        print(f"TITLE: {title}\nWHY: {r[5]}")
        for d in json.loads(r[6] or "[]"):
            print(f"  - {d}")
        print()
    n = up.execute("SELECT COUNT(*) FROM upsc_articles WHERE mains_dimensions LIKE '%…%' AND published_at >= ?", [int(time.time()) - 30 * 86400]).rows[0][0]
    m = up.execute("SELECT COUNT(*) FROM upsc_articles WHERE published_at >= ?", [int(time.time()) - 30 * 86400]).rows[0][0]
    print(f"notes (30 days) with a cut-off mains dimension: {n} of {m}")
    for col in ("why_in_news", "fact_box", "prelims_pointers", "mains_question"):
        k = up.execute(f"SELECT COUNT(*) FROM upsc_articles WHERE {col} LIKE '%…%' AND published_at >= ?", [int(time.time()) - 30 * 86400]).rows[0][0]
        print(f"  {col} with '…': {k}")
finally:
    close_all()
