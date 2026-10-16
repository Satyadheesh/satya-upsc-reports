"""READ-ONLY: fetch a few live pages fresh and show their title, status and visible text (to see what a page shows)."""
import html, re, time, urllib.request
for p in ["/upsc/note/134733", "/upsc/note/132662?lang=hi", "/upsc", "/upsc?lang=hi"]:
    url = f"https://satyadheesh.in{p}{'&' if '?' in p else '?'}diag={int(time.time())}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "SatyaDiag/1"}), timeout=60) as r:
            b = r.read().decode("utf-8", "replace"); st = r.status
    except Exception as e:
        b, st = getattr(e, "read", lambda: b"")().decode("utf-8", "replace") if hasattr(e, "read") else "", getattr(e, "code", type(e).__name__)
    t = re.search(r"<title>([^<]*)", b)
    body = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", b)
    txt = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", body)).split())
    print(f"## {p} -> {st}\n- title: {t.group(1) if t else '-'}\n- text: {txt[:700]}\n- markers: " +
          ", ".join(k for k in ("could not be found", "404", "NEXT_NOT_FOUND", "Application error", "digest") if k in b) + "\n")
