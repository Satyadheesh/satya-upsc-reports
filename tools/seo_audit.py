"""READ-ONLY SEO audit of the live site: fetches pages like a crawler and reports what Google sees.

  URLS="https://satyadheesh.in/upsc ..." python tools/seo_audit.py
Per page: status, final URL, <title> (and length), meta description (length), robots, canonical, hreflang, H1s,
JSON-LD @types (and parse errors), word count, internal links. Plus robots.txt and the sitemaps (URL counts, a
sample of URLs re-fetched for status/indexability).
"""
import json
import os
import re
import sys
import time
import urllib.request
from html.parser import HTMLParser

SITE = "https://satyadheesh.in"
UA = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
DEFAULT = [
    "/", "/upsc", "/upsc?lang=hi", "/upsc?paper=GS2", "/upsc/current-affairs", "/upsc/reports",
    "/upsc/current-affairs/__LATEST__", "/upsc/current-affairs/__LATEST__?lang=hi",
    "/upsc/current-affairs/week/__WEEK__", "/upsc/current-affairs/month/__MONTH__",
]


def fetch(url, timeout=40):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-IN"})
    t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            return r.status, r.geturl(), dict(r.headers), body.decode("utf-8", "replace"), time.time() - t
    except urllib.error.HTTPError as e:
        return e.code, url, dict(e.headers or {}), (e.read() or b"").decode("utf-8", "replace"), time.time() - t
    except Exception as e:
        return 0, url, {}, f"ERROR {type(e).__name__}: {e}", time.time() - t


class P(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title, self.in_title, self.metas, self.links, self.h1, self.in_h1 = "", False, [], [], [], False
        self.ld, self.in_ld, self.text, self.skip, self.a = [], False, [], 0, []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "title":
            self.in_title = True
        elif tag == "meta":
            self.metas.append(a)
        elif tag == "link":
            self.links.append(a)
        elif tag == "h1":
            self.in_h1 = True
            self.h1.append("")
        elif tag == "script" and a.get("type") == "application/ld+json":
            self.in_ld = True
            self.ld.append("")
        elif tag in ("script", "style", "noscript"):
            self.skip += 1
        elif tag == "a" and a.get("href"):
            self.a.append(a["href"])

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        elif tag == "h1":
            self.in_h1 = False
        elif tag == "script" and self.in_ld:
            self.in_ld = False
        elif tag in ("script", "style", "noscript") and self.skip:
            self.skip -= 1

    def handle_data(self, d):
        if self.in_title:
            self.title += d
        if self.in_h1 and self.h1:
            self.h1[-1] += d
        if self.in_ld:
            self.ld[-1] += d
        elif not self.skip:
            self.text.append(d)


def ld_types(blobs):
    types, errs = [], 0
    for b in blobs:
        try:
            d = json.loads(b)
        except Exception:
            errs += 1
            continue
        for x in (d if isinstance(d, list) else d.get("@graph", [d]) if isinstance(d, dict) else []):
            t = x.get("@type") if isinstance(x, dict) else None
            types.append("/".join(t) if isinstance(t, list) else str(t))
    return types, errs


def audit(path):
    url = path if path.startswith("http") else SITE + path
    st, final, hd, body, secs = fetch(url)
    print(f"\n### {path}\n- status **{st}** in {secs:.1f}s" + (f" → {final}" if final != url else ""))
    if st != 200:
        print(f"- body: {body[:200]!r}")
        return []
    p = P()
    p.feed(body)
    meta = {(m.get("name") or m.get("property") or "").lower(): m.get("content", "") for m in p.metas}
    canon = [l.get("href") for l in p.links if (l.get("rel") or "") == "canonical"]
    alts = [(l.get("hreflang"), l.get("href")) for l in p.links if (l.get("rel") or "") == "alternate" and l.get("hreflang")]
    types, errs = ld_types(p.ld)
    words = len(re.findall(r"\w+", " ".join(p.text)))
    internal = sorted({h.split("#")[0] for h in p.a if h.startswith("/") or h.startswith(SITE)})
    desc = meta.get("description", "")
    print(f"- title ({len(p.title)}): {p.title}")
    print(f"- description ({len(desc)}): {desc[:220]}")
    print(f"- robots: {meta.get('robots', '(none)')} · x-robots-tag: {hd.get('X-Robots-Tag', hd.get('x-robots-tag', '-'))}")
    print(f"- canonical: {canon}")
    print(f"- hreflang: {alts}")
    print(f"- h1: {[h.strip()[:90] for h in p.h1]}")
    print(f"- JSON-LD: {types}" + (f" · **{errs} parse errors**" if errs else ""))
    print(f"- og:title: {meta.get('og:title', '-')[:90]} · og:image: {meta.get('og:image', '-')[:90]}")
    print(f"- words: {words} · internal links: {len(internal)} · cache-control: {hd.get('Cache-Control', hd.get('cache-control', '-'))}")
    og = meta.get("og:image")
    if og and os.environ.get("CHECK_OG"):
        st2, _, h2, _, s2 = fetch(og)
        print(f"- og:image fetch: {st2} {h2.get('Content-Type', h2.get('content-type', ''))} in {s2:.1f}s")
    return internal


def sitemap(url, sample=6):
    st, _, _, body, secs = fetch(url, timeout=240)
    locs = re.findall(r"<loc>([^<]+)</loc>", body)
    print(f"\n### sitemap {url}\n- status {st} in {secs:.1f}s, {len(locs)} URLs" + (f" · {body[:150]!r}" if st != 200 else ""))
    kinds = {}
    for l in locs:
        k = re.sub(r"\d{4}-\d{2}(-\d{2})?|W\d+|\d+", "#", l.replace(SITE, ""))[:60]
        kinds[k] = kinds.get(k, 0) + 1
    for k, v in sorted(kinds.items(), key=lambda x: -x[1])[:25]:
        print(f"  - {v} × {k}")
    return locs


def main():
    st, _, _, robots, _ = fetch(SITE + "/robots.txt")
    print(f"## SEO audit {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}\n\n### robots.txt ({st})\n```\n{robots.strip()[:800]}\n```")
    maps = re.findall(r"(?im)^sitemap:\s*(\S+)", robots) or [SITE + "/sitemap.xml"]
    locs = []
    for m in maps:
        locs += sitemap(m)
    day = next((re.search(r"current-affairs/(\d{4}-\d{2}-\d{2})", l).group(1) for l in locs
                if re.search(r"current-affairs/\d{4}-\d{2}-\d{2}$", l)), "2026-10-05")
    week = next((re.search(r"week/([\w-]+)", l).group(1) for l in locs if "/week/" in l), "2026-W40")
    month = next((re.search(r"month/([\w-]+)", l).group(1) for l in locs if "/month/" in l), "2026-09")
    paths = (os.environ.get("URLS") or "").split() or DEFAULT
    follow = [f for f in (os.environ.get("FOLLOW") or "").split() if f]
    for p in paths:
        links = audit(p.replace("__LATEST__", day).replace("__WEEK__", week).replace("__MONTH__", month)) or []
        for f in follow:  # also audit the first link on the page that contains this text
            hit = next((l for l in links if f in l), None)
            if hit:
                audit(hit)
                follow = [x for x in follow if x != f]
    extra = int(os.environ.get("SAMPLE") or 0)
    if extra:
        import random
        random.seed(1)
        for l in random.sample(locs, min(extra, len(locs))):
            audit(l)


if __name__ == "__main__":
    main()
