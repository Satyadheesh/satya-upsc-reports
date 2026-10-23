"""READ-ONLY: which of the site's own URLs (from its sitemaps) answer with an error. A sample from every sitemap,
fetched one at a time like a crawler (no redirects followed): status, where redirects go, soft 404s (a 200 page that
says "not found" or is noindex), slow answers, and whether the gate or the fallback Worker answered."""
import collections
import os
import random
import re
import time
import urllib.error
import urllib.request

SITE = "https://satyadheesh.in"
UA = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
PER_MAP = int(os.environ.get("SAMPLE") or 30)
random.seed(int(time.time()) // 3600)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


opener = urllib.request.build_opener(NoRedirect)


def get(url, timeout=45):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    t = time.time()
    try:
        with opener.open(req, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read().decode("utf-8", "replace"), time.time() - t
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers or {}), (e.read() or b"").decode("utf-8", "replace"), time.time() - t
    except Exception as e:
        return 0, {}, f"{type(e).__name__}: {e}", time.time() - t


def locs(xml):
    return re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml)


robots = get(SITE + "/robots.txt")[2]
maps = re.findall(r"(?im)^sitemap:\s*(\S+)", robots) or [SITE + "/sitemap.xml"]
children, seen = [], set()
while maps:
    m = maps.pop(0)
    if m in seen:
        continue
    seen.add(m)
    st, _, body, _ = get(m)
    if st != 200:
        print(f"- sitemap {m}: HTTP {st}")
        continue
    if "<sitemapindex" in body:
        maps += locs(body)
    else:
        children.append((m, locs(body)))
total = sum(len(u) for _, u in children)
print(f"{len(children)} sitemaps, {total} URLs; checking up to {PER_MAP} random URLs from each\n")

res = []
for m, urls in children:
    for u in random.sample(urls, min(PER_MAP, len(urls))):
        st, h, body, secs = get(u)
        kind = "ok"
        if st == 0:
            kind = "no answer"
        elif st >= 500:
            kind = f"{st}" + (f" gate:{h.get('X-Satya-Gate') or h.get('x-satya-gate')}" if (h.get('X-Satya-Gate') or h.get('x-satya-gate')) else "")
        elif st == 404:
            kind = "404"
        elif 300 <= st < 400:
            kind = f"{st} -> {(h.get('Location') or h.get('location') or '')[:80]}"
        elif st == 200:
            title = (re.search(r"<title[^>]*>(.*?)</title>", body, re.S) or [None, ""])[1]
            noindex = re.search(r'<meta[^>]+name="robots"[^>]+noindex', body)
            if noindex or re.search(r"not found|404|पेज नहीं मिला", title, re.I):
                kind = "soft 404 (noindex/not found)"
            elif re.search(r'http-equiv="refresh"', body):
                kind = "meta refresh (redirect)"
        fb = h.get("x-satya-fallback") or h.get("X-Satya-Fallback")
        res.append((m.rsplit("/", 1)[-1], u, st, kind, secs, fb))
        time.sleep(0.4)

bad = [r for r in res if r[3] != "ok"]
print(f"## {len(res)} URLs checked, {len(bad)} not OK ({100 * len(bad) / max(1, len(res)):.1f}%)\n")
print("| sitemap | checked | not OK | kinds |\n|---|---|---|---|")
by = collections.defaultdict(list)
for r in res:
    by[r[0]].append(r)
for m, rs in by.items():
    k = collections.Counter(r[3].split(" ->")[0] for r in rs if r[3] != "ok")
    print(f"| {m} | {len(rs)} | {sum(k.values())} | {', '.join(f'{n}× {x}' for x, n in k.most_common())} |")
print("\n## not OK (first 60)")
for m, u, st, kind, secs, fb in bad[:60]:
    print(f"- {st} {kind} · {secs:.1f}s{' · fallback ' + fb if fb else ''} · {u}")
slow = sorted(res, key=lambda r: -r[4])[:8]
print("\n## slowest")
for m, u, st, kind, secs, fb in slow:
    print(f"- {secs:.1f}s {st} {u}")
