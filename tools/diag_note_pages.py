"""READ-ONLY: loads UPSC note pages on the live site (English and Hindi), with a cache-busting parameter so the
app builds them, and reports status, time, and whether the note, study kit and related notes are on the page.
Used after the 16 Oct 2026 note-page change (database lookups side by side)."""
import random
import re
import time
import urllib.request

from common.db import close_all, upsc_db

up = upsc_db()
try:
    now = int(time.time())
    rows = up.execute("SELECT article_id, translated_hi FROM upsc_articles WHERE published_at BETWEEN ? AND ? "
                      "AND length(why_in_news) > 80 ORDER BY published_at DESC LIMIT 400", [now - 120 * 86400, now - 3 * 86400]).rows
    random.seed(now)
    pick = random.sample(rows, 6) + [r for r in rows if r[1] == 1][:2]
    print("| note | lang | status | seconds | why in news | kit | related | hreflang hi |\n|---|---|---|---|---|---|---|---|")
    for aid, hi in pick:
        for lang in (["en", "hi"] if hi == 1 else ["en"]):
            url = f"https://satyadheesh.in/upsc/note/{aid}?{'lang=hi&' if lang == 'hi' else ''}diag={now}{aid}"
            t = time.time()
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "SatyaDiag/1"}), timeout=60) as r:
                    b, st = r.read().decode("utf-8", "replace"), r.status
            except Exception as e:
                b, st = "", getattr(e, "code", type(e).__name__)
            dt = round(time.time() - t, 2)
            why = ("Why in news" in b or "चर्चा में क्यों" in b)
            kit = ("Practice question" in b or "Show answer" in b or "उत्तर देखें" in b)
            rel = bool(re.search(r"More [^<]{1,60} notes<", b)) or "पर और नोट्स" in b
            hl = bool(re.search(r"hreflang=\"hi-IN\"", b, re.I))
            print(f"| {aid} | {lang} | {st} | {dt} | {why} | {kit} | {rel} | {hl} |")
finally:
    close_all()
