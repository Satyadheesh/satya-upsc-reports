"""READ-ONLY: a real browser load of a few pages from a GitHub runner (mobile size, fresh profile each time):
when the page's HTML arrived, when it was usable, the largest paint, and the slowest files it waited for."""
import json
import subprocess
import sys

subprocess.run([sys.executable, "-m", "pip", "install", "-q", "playwright"], check=True)
subprocess.run([sys.executable, "-m", "playwright", "install", "--with-deps", "chromium"], check=True, capture_output=True)
from playwright.sync_api import sync_playwright  # noqa: E402

PAGES = [("/", None), ("/", "hi"), ("/?lang=hi", None)]
LCP_JS = """() => new Promise(res => { let v = 0; new PerformanceObserver(l => { for (const e of l.getEntries()) v = e.startTime; })
  .observe({type: 'largest-contentful-paint', buffered: true}); setTimeout(() => res(v), 1500); })"""
with sync_playwright() as pw:
    b = pw.chromium.launch()
    for path, cookie in PAGES:
        for attempt in (1, 2):
            ctx = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, user_agent=
                                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
            if cookie:
                ctx.add_cookies([{"name": "satya_lang", "value": cookie, "domain": "satyadheesh.in", "path": "/"}])
            pg = ctx.new_page()
            reqs = []
            pg.on("requestfinished", lambda r: reqs.append(r))
            try:
                pg.goto("https://satyadheesh.in" + path, wait_until="load", timeout=60000)
                pg.wait_for_timeout(2500)
                nav = pg.evaluate("() => JSON.stringify(performance.getEntriesByType('navigation')[0])")
                nav = json.loads(nav)
                lcp = pg.evaluate(LCP_JS)
                slow = []
                for r in reqs:
                    t = r.timing
                    if t and t.get("responseEnd", -1) > 0:
                        slow.append((t["responseEnd"] - max(t.get("requestStart", 0), 0), r.url))
                slow.sort(reverse=True)
                hdr = pg.evaluate("() => 0")
                print(f"## {path} cookie={cookie} try {attempt}\n- html first byte {nav['responseStart']:.0f} ms, html done {nav['responseEnd']:.0f} ms, "
                      f"DOM ready {nav['domContentLoadedEventEnd']:.0f} ms, load {nav['loadEventEnd']:.0f} ms, largest paint {lcp:.0f} ms, "
                      f"{len(reqs)} requests, {sum((r.sizes().get('responseBodySize', 0) for r in reqs)) // 1024} KB")
                for d, u in slow[:6]:
                    print(f"  - {d:.0f} ms {u[:110]}")
                big = sorted(((r.sizes().get('responseBodySize', 0), r.url) for r in reqs), reverse=True)[:6]
                for sz, u in big:
                    print(f"  * {sz // 1024} KB {u[:130]}")
            except Exception as ex:
                print(f"## {path} cookie={cookie} try {attempt}: {type(ex).__name__}: {str(ex)[:200]}")
            ctx.close()
    b.close()
