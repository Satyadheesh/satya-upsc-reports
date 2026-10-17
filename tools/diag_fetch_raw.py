"""READ-ONLY: fetch site URLs without following redirects; print status, Location and redirect hints in the HTML."""
import http.client
import os
import re

for path in (os.environ.get("URLS") or "/").split():
    c = http.client.HTTPSConnection("satyadheesh.in", timeout=30)
    c.request("GET", path, headers={"User-Agent": "Mozilla/5.0 (compatible; SatyaDheeshAudit/1.0)"})
    r = c.getresponse()
    body = r.read().decode("utf-8", "replace")
    print(f"## {path}\n- status {r.status}, location: {r.getheader('location')}, cache: {r.getheader('x-nextjs-cache')} / {r.getheader('x-cache-status') or r.getheader('x-cache')}")
    for pat in (r'<meta[^>]+http-equiv="refresh"[^>]*>', r'NEXT_REDIRECT[^"\\]{0,160}', r'<title>[^<]*</title>'):
        m = re.search(pat, body)
        print(f"- {pat[:22]}: {m.group(0)[:220] if m else '-'}")
    print()
