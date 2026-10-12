"""READ-ONLY: English (Latin-script) words left in the visible text of live Hindi pages.
URLS (space-separated paths) overrides the default set. Writes nothing anywhere."""
import os, re, html, urllib.request
from collections import Counter

SITE = os.environ.get("SITE") or "https://satyadheesh.in"
ALLOW = set("SatyaDheesh SATYADHEESH UPSC CSE GS GS1 GS2 GS3 GS4 PDF SSC CGL CHSL MTS IAS PIB MCQ IST".split())
DEFAULT = ["/timelines?lang=hi", "/upsc?lang=hi", "/upsc/current-affairs/2026-10-11?lang=hi", "/upsc/reports?lang=hi",
           "/event/deshmukh-death-sparks-political-outrage-call-for-action?lang=hi",
           "/event/congress-appoints-leadership-for-punjab-elections-2027?lang=hi",
           "/upsc/note/135055?lang=hi", "/upsc/note/135041?lang=hi", "/upsc/note/68494?lang=hi",
           "/upsc/subject/polity?lang=hi"]


def get(path):
    sep = "&" if "?" in path else "?"
    req = urllib.request.Request(SITE + path + f"{sep}purity=1", headers={"User-Agent": "SatyaPurityCheck/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status, r.read().decode("utf-8", "replace")


def visible(h):
    h = re.sub(r"(?is)<(script|style|noscript|svg|head)[^>]*>.*?</\1>", " ", h)
    h = re.sub(r"(?s)<[^>]+>", " ", h)
    return html.unescape(h)


print("# Live Hindi pages: Latin-script words in the visible text\n")
for path in (os.environ.get("URLS") or "").split() or DEFAULT:
    try:
        st, h = get(path)
        t = visible(h)
        ws = [w for w in re.findall(r"[A-Za-z][A-Za-z'’\-]{2,}", t) if w not in ALLOW]
        common = ", ".join(f"{w}×{c}" for w, c in Counter(ws).most_common(15))
        title = re.search(r"<title>(.*?)</title>", h, re.S)
        print(f"- `{path}` ({st}): {len(ws)} Latin words / {len(t.split())} words. Title: {html.unescape(title.group(1)) if title else '-'}\n  Most: {common}")
    except Exception as e:
        print(f"- `{path}`: fetch failed ({e})")
