"""READ-ONLY: how many UPSC notes each GS paper gets (all time, last 30 and 7 days), GS4 in detail, and what the
site's GS4 page shows."""
import time
import urllib.request

from common.db import close_all, upsc_db

u = upsc_db()
now = int(time.time())
print("| paper | all | 30 days | 7 days | latest |\n|---|---|---|---|---|")
for r in u.execute("SELECT gs_paper, COUNT(*), SUM(published_at >= ?), SUM(published_at >= ?), MAX(published_at) FROM upsc_articles "
                   "GROUP BY gs_paper ORDER BY gs_paper", [now - 30 * 86400, now - 7 * 86400]).rows:
    print(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {time.strftime('%Y-%m-%d', time.gmtime(r[4] or 0))} |")
print("\nGS4 by subject (all time):")
for r in u.execute("SELECT subject, COUNT(*) FROM upsc_articles WHERE gs_paper = 'GS4' GROUP BY subject ORDER BY 2 DESC").rows:
    print(f"- {r[0]}: {r[1]}")
print("\nlatest 8 GS4 notes:")
cols = [c[1] for c in u.execute("PRAGMA table_info(upsc_articles)").rows]
print("columns:", ", ".join(cols))
for r in u.execute("SELECT article_id, published_at, subject, upsc_score FROM upsc_articles WHERE gs_paper = 'GS4' "
                   "ORDER BY published_at DESC LIMIT 8").rows:
    print(f"- {r[0]} {time.strftime('%Y-%m-%d', time.gmtime(r[1] or 0))} {r[2]} score={r[3]}")
for path in ("/upsc?paper=GS4", "/upsc/subject/ethics"):
    try:
        req = urllib.request.Request("https://satyadheesh.in" + path, headers={"User-Agent": "Mozilla/5.0 (compatible; SatyaDheeshAudit/1.0)"})
        body = urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "replace")
        print(f"\n{path}: {len(body)} bytes; 'note/' links: {body.count('/upsc/note/')}; "
              f"empty-state text: {[t for t in ('No notes', 'no notes', 'कोई नोट', 'Nothing') if t in body]}")
    except Exception as e:
        print(f"\n{path}: {type(e).__name__}: {e}")
close_all()
