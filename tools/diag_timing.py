"""READ-ONLY: how fast the site answers from a GitHub runner: time to first byte and total per page, 4 tries each,
with Cloudflare's cache status, nginx's cache result and whether the fallback Worker served a saved copy."""
import re
import statistics
import time

import requests

SITE = "https://satyadheesh.in"
UA = {"User-Agent": "Mozilla/5.0 (compatible; SatyaDheeshAudit/1.0)", "Accept-Encoding": "gzip, br"}


def one(url):
    t0 = time.time()
    r = requests.get(url, headers=UA, stream=True, timeout=60, allow_redirects=False)
    ttfb = time.time() - t0
    body = r.content
    return r, ttfb, time.time() - t0, len(body)


home = requests.get(SITE + "/", headers=UA, timeout=60).text
assets = re.findall(r'/_next/static/[^"\']+\.(?:js|css)', home)[:2]
paths = ["/cdn-cgi/trace", "/", "/upsc", "/timelines", "/news/138876", "/news/138876?lang=hi", "/health", "/api/data"] + assets
print("| path | status | ttfb median (s) | ttfb all | total median | KB | cf-cache | nginx | fallback | colo |")
print("|---|---|---|---|---|---|---|---|---|---|")
for p in paths:
    runs = []
    for _ in range(4):
        try:
            runs.append(one(SITE + p))
        except Exception as ex:
            print(f"| {p} | error {type(ex).__name__} |")
        time.sleep(1)
    if not runs:
        continue
    r = runs[-1][0]
    tt = [x[1] for x in runs]
    ray = r.headers.get("cf-ray", "")
    print(f"| {p[:40]} | {r.status_code} | {statistics.median(tt):.2f} | {' '.join(f'{x:.2f}' for x in tt)} | "
          f"{statistics.median([x[2] for x in runs]):.2f} | {runs[-1][3] // 1000} | {r.headers.get('cf-cache-status', '-')} | "
          f"{r.headers.get('x-cache', '-')} | {r.headers.get('x-satya-fallback', '-')} | {ray.split('-')[-1] if ray else '-'} |")
