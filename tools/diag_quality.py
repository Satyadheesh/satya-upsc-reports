"""READ-ONLY: material for a hand quality check — 30 notes with their source article and Hindi,
20 study-kit MCQs with their note, and 2 monthly PDFs saved to /tmp/diag_out."""
import json
import os
import random
import time
import zlib

from common.db import close_all, in_chunks, main_db, translation_db, upsc_db


def decode(v):
    if v is None:
        return ""
    if isinstance(v, (bytes, bytearray)):
        try:
            return zlib.decompress(bytes(v)).decode("utf-8", "replace")
        except zlib.error:
            return bytes(v).decode("utf-8", "replace")
    return str(v)


now = int(time.time())
rng = random.Random(20261003)
up, mn, tr = upsc_db(), main_db(), translation_db()
out = os.environ.get("DIAG_OUT", "/tmp/diag_out")
os.makedirs(out, exist_ok=True)
try:
    rows = up.execute("SELECT article_id, gs_paper, subject, syllabus_node, exam_type, upsc_score, why_in_news, fact_box, "
                      "prelims_pointers, mains_question FROM upsc_articles INDEXED BY idx_upsc_pub WHERE published_at >= ?",
                      [now - 14 * 86400]).rows
    by_paper = {}
    for r in rows:
        by_paper.setdefault(r[1], []).append(r)
    picked = []
    for paper, quota in (("GS1", 6), ("GS2", 12), ("GS3", 12)):
        pool = by_paper.get(paper, [])
        picked += rng.sample(pool, min(quota, len(pool)))
    ids = [r[0] for r in picked]
    arts = {r[0]: r for r in in_chunks(mn, "SELECT id, COALESCE(NULLIF(rephrased_title, ''), title), rephrased_article, content "
                                           "FROM articles WHERE id IN ({ph})", ids)}
    hi = {r[0]: r for r in in_chunks(tr, "SELECT article_id, why_in_news_hi, fact_box_hi, prelims_pointers_hi FROM upsc_translations "
                                         "WHERE article_id IN ({ph})", ids)}
    hit = {r[0]: r[1] for r in in_chunks(tr, "SELECT article_id, rephrased_title_hi FROM translations WHERE article_id IN ({ph})", ids)}
    print(f"# Quality sample — 30 notes (last 14 days, {len(rows)} notes)\n")
    for i, r in enumerate(picked, 1):
        aid = r[0]
        a = arts.get(aid)
        body = decode(a[2]) if a else ""
        if len(body) < 400 and a:
            body = (body + "\n" + decode(a[3])).strip()
        print(f"## N{i} · {aid} · {r[1]} / {r[2]} / {r[3]} · {r[4]} · score {r[5]}")
        print(f"TITLE: {a[1] if a else '?'}")
        print(f"ARTICLE: {' '.join(body.split())[:1400]}")
        print(f"WHY: {r[6]}\nFACTS: {r[7]}")
        for p in json.loads(r[8] or "[]"):
            print(f"  - {p.get('type')}: {p.get('text')}")
        print(f"MAINS: {r[9]}")
        h = hi.get(aid)
        print(f"HI TITLE: {hit.get(aid)}\nHI WHY: {h[1] if h else None}\nHI FACTS: {h[2] if h else None}\n")

    print("\n# 20 study-kit MCQs\n")
    kits = up.execute("SELECT k.article_id, k.mcq, k.facts, k.short_title, k.takeaway, a.why_in_news, a.fact_box, a.prelims_pointers "
                      "FROM upsc_kit k JOIN upsc_articles a ON a.article_id = k.article_id WHERE k.status = 'done'").rows
    for i, r in enumerate(rng.sample(kits, min(20, len(kits))), 1):
        m = json.loads(r[1])
        print(f"## Q{i} · {r[0]} · {m['type']}\nHEADLINE: {r[3]}\nTAKEAWAY: {r[4]}")
        print(f"NOTE WHY: {r[5]}\nNOTE FACTS: {r[6]}\nNOTE POINTERS: {'; '.join(p.get('text','') for p in json.loads(r[7] or '[]'))}")
        print(f"KIT FACTS: {'; '.join(f['label'] + ': ' + f['text'] for f in json.loads(r[2] or '[]'))}")
        print(f"Q: {m['question']}")
        for j, s in enumerate(m.get("statements") or []):
            print(f"   {j + 1}. {s}")
        for j, o in enumerate(m["options"]):
            print(f"   ({'abcd'[j]}) {o}{'  <-- key' if j == m['answer'] else ''}")
        print(f"EXPL: {m['explanation']}\n")

    for key in ("monthly:2026-09:en:brief", "monthly:2026-09:hi:detailed"):
        data = b"".join(bytes(x[0]) for x in up.execute("SELECT data FROM upsc_report_chunks WHERE key = ? ORDER BY n", [key]).rows)
        if data:
            open(os.path.join(out, key.replace(":", "_") + ".pdf"), "wb").write(data)
            print(f"saved {key}: {len(data) // 1024} KB")
finally:
    close_all()
