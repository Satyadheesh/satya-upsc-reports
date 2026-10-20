"""READ-ONLY: which smaller versions of the news photos the image hosts serve (the cards show 96 px thumbnails
but load 1200 px photos)."""
import collections
import re
from urllib.parse import urlparse

import requests

UA = {"User-Agent": "Mozilla/5.0 (compatible; SatyaDheeshAudit/1.0)"}
feed = requests.get("https://satyadheesh.in/api/data?type=feed&param=all&lang=en&limit=60", headers=UA, timeout=60).json()
items = feed if isinstance(feed, list) else feed.get("articles") or feed.get("items") or feed.get("data") or []
urls = [a.get("image_url") for a in items if isinstance(a, dict) and a.get("image_url")]
print(f"{len(urls)} image urls; hosts: {collections.Counter(urlparse(u).netloc for u in urls).most_common()}\n")


def size(u):
    try:
        r = requests.get(u, headers=UA, timeout=30)
        return r.status_code, len(r.content), r.headers.get("content-type", "")
    except Exception as ex:
        return type(ex).__name__, 0, ""


VARIANTS = [
    (r"LANDSCAPE_1200", ["LANDSCAPE_480", "LANDSCAPE_320", "LANDSCAPE_615", "SQUARE_80", "SQUARE_160", "SQUARE_240"]),
    (r"width-1200,height-900", ["width-320,height-240", "width-160,height-120"]),
    (r"\?w=\d+", ["?w=320", "?w=160"]),
    (r"width=\d+", ["width=320"]),
]
seen = set()
for u in urls:
    host = urlparse(u).netloc
    if host in seen:
        continue
    seen.add(host)
    print(f"## {host}\n- original {size(u)}  {u[:140]}")
    for pat, subs in VARIANTS:
        if re.search(pat, u):
            for s in subs:
                v = re.sub(pat, s, u, count=1)
                print(f"- {s}: {size(v)}")
    print()
