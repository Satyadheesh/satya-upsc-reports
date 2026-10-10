"""READ-ONLY: refresh cooldown rows (site_revalidations in the main DB) and cache state / size of key pages."""
import time, urllib.request
from common.db import close_all, main_db

m = main_db()
try:
    try:
        rows = m.execute("SELECT key, at FROM site_revalidations ORDER BY at DESC").rows
        print("## Refresh cooldowns (site_revalidations)")
        for k, at in rows:
            print(f"- {k}: last refresh {time.strftime('%d %b %H:%M:%S UTC', time.gmtime(at / 1000))} ({(time.time() * 1000 - at) / 60000:.0f} min ago)")
        if not rows:
            print("- table exists, no refresh yet")
    except Exception as e:
        print("## Refresh cooldowns: table not there yet:", type(e).__name__, str(e)[:120])
finally:
    close_all()

print("\n## Pages (two fetches each)")
print("| path | status | bytes | cache 1st | cache 2nd | age |")
print("|---|---|---|---|---|---|")
for p in ["/", "/?lang=hi", "/upsc", "/vaade", "/netas", "/party/bjp", "/upsc/current-affairs", "/sitemap.xml", "/sitemap-notes.xml"]:
    out = []
    for _ in range(2):
        req = urllib.request.Request("https://satyadheesh.in" + p, headers={"User-Agent": "SatyaDiag/1"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                b = r.read(); out.append((r.status, len(b), r.headers.get("x-vercel-cache"), r.headers.get("age")))
        except Exception as e:
            out.append((type(e).__name__, 0, "-", "-"))
    (s, n, c1, a), (_, _, c2, a2) = out
    print(f"| {p} | {s} | {n:,} | {c1} | {c2} | {a2} |")
