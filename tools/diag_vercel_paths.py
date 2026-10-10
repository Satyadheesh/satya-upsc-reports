"""READ-ONLY: cache state of chosen paths on the live site (two fetches each): x-vercel-cache, cache-control, size.
URLS (space separated) overrides the default set; one event, minister and vaade page are taken from sitemap.xml."""
import os
import re
import time
import urllib.request

SITE = os.environ.get("SITE") or "https://satyadheesh.in"


def get(path, ua="Mozilla/5.0 (SatyaDiag)"):
    req = urllib.request.Request(SITE + path, headers={"User-Agent": ua})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            b = r.read()
            h = r.headers
            return r.status, len(b), h.get("x-vercel-cache"), h.get("cache-control"), h.get("age"), h.get("content-type"), b
    except urllib.error.HTTPError as e:
        return e.code, 0, e.headers.get("x-vercel-cache"), e.headers.get("cache-control"), None, None, b""
    except Exception as e:
        return type(e).__name__, 0, None, None, None, None, b""


sm = get("/sitemap.xml")[6].decode(errors="ignore")
locs = re.findall(r"<loc>https://[^/<]+([^<]+)</loc>", sm)
pick = lambda pre: next((l for l in locs if l.startswith(pre) and "lang=" not in l), None)
extra = [p for p in (pick("/event/"), pick("/minister/"), pick("/vaade/")) if p]
paths = os.environ.get("URLS", "").split() or [
    "/", "/opengraph-image", "/upsc", "/upsc/opengraph-image", "/upsc/note/133529", "/upsc/note/133529/opengraph-image",
    "/upsc?paper=gs2", "/search?q=rbi", "/ssc", "/upsc/current-affairs", "/robots.txt",
    *extra, *[p.rstrip("/") + "/opengraph-image" for p in extra],
    "/upsc?utm_source=x", "/?fbclid=abc",
]
print("| path | status | bytes | cache 1st | 2nd | 3rd (after 5 s) | age | cache-control |")
print("|---|---|---|---|---|---|---|---|")
for p in paths:
    a, b = get(p), get(p)
    time.sleep(5)
    c = get(p)
    print(f"| {p} | {a[0]} | {a[1]:,} | {a[2]} | {b[2]} | {c[2]} | {c[4]} | {c[3]} |")
print("\n## robots.txt\n```")
print(get("/robots.txt")[6].decode(errors="ignore")[:1500])
print("```")
