"""READ-ONLY: the daily Brief's top 5 (key story cards) for the last 21 days, to spot odd picks."""
import time

from common.db import close_all, main_db, upsc_db
from reports.data import DAY, IST, Window, by_importance
from reports.render import pick_cards

now = int(time.time())
today = (now + IST) // DAY * DAY - IST
start = today - 21 * DAY
up, mn = upsc_db(), main_db()
try:
    w = Window(up, mn, start, today + DAY)
    d = today
    while d >= start:
        items = sorted(w.day(d), key=by_importance)
        top = pick_cards(items, 5, "daily")
        print(f"\n## {time.strftime('%d %b', time.gmtime(d + IST))} ({len(items)} notes)")
        for it in top:
            print(f"- s{it['score']}{'-' if it.get('demote') else ''} r{it['related']} {it['paper']}/{it['subject']}/{it['node']} [{it['source']}] {it['title_en'][:110]}"
                  f"\n    why: {it['why'][:160]}")
        d -= DAY
finally:
    close_all()
