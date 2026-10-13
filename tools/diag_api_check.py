"""READ-ONLY: fetch site API URLs (URLS, space-separated paths) and summarise the JSON (list sizes, flags, timing)."""
import json, os, time, urllib.request

SITE = os.environ.get("SITE") or "https://satyadheesh.in"
for path in (os.environ.get("URLS") or "").split():
    t0 = time.time()
    try:
        with urllib.request.urlopen(urllib.request.Request(SITE + path, headers={"User-Agent": "SatyaCheck/1.0"}), timeout=60) as r:
            body = r.read()
            d = json.loads(body)
        summ = {k: (len(v) if isinstance(v, list) else v) for k, v in d.items()} if isinstance(d, dict) else type(d).__name__
        first = next((v[:2] for v in d.values() if isinstance(v, list)), None) if isinstance(d, dict) else None
        print(f"- `{path}` {r.status} {time.time() - t0:.1f}s {summ}")
        if first:
            print("  first:", [(x.get("id"), x.get("title"), x.get("last_seen")) for x in first if isinstance(x, dict)])
    except Exception as e:
        print(f"- `{path}` failed: {e}")
