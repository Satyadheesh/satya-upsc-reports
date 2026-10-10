"""READ-ONLY: is the 'Something wrong, or something missing?' card and the 'Report a mistake' links live?"""
import re, urllib.request

PAGES = ["/upsc", "/upsc?lang=hi", "/ssc", "/ssc/current-affairs/2026-10-09", "/upsc/note/133529", "/upsc/reports"]
for path in PAGES:
    req = urllib.request.Request("https://satyadheesh.in" + path, headers={"User-Agent": "SatyaDiag/1"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            b = r.read().decode("utf-8", "replace")
            cache, status = r.headers.get("x-vercel-cache"), r.status
    except Exception as ex:
        print(f"- {path}: ERROR {ex}")
        continue
    card = "Something wrong, or something missing?" in b or "कोई गलती या कोई कमी?" in b
    mails = len(re.findall(r'mailto:thesatyadheesh@gmail\.com\?subject=', b))
    print(f"- {path}: {status} cache={cache} card={'yes' if card else 'NO'} correction-links={mails} bytes={len(b):,}")
