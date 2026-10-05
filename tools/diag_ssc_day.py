"""READ-ONLY: every SSC card of the last 3 IST days, as the daily SSC PDF shows them (note headline, topic, card)."""
import time

from common.db import close_all, main_db, upsc_db
from reports.data import DAY, IST, Window, by_importance
from reports.render import _map_ssc_topic

now = int(time.time())
today = (now + IST) // DAY * DAY - IST
up, mn = upsc_db(), main_db()
try:
    w = Window(up, mn, today - 3 * DAY, today + DAY)
    for d in (today, today - DAY, today - 2 * DAY):
        items = sorted(w.day(d), key=by_importance)
        with_card = [i for i in items if (i.get("ssc_kit") or {}).get("question_en")]
        print(f"\n## {time.strftime('%d %b', time.gmtime(d + IST))}: {len(items)} notes, {len(with_card)} SSC cards")
        for it in with_card:
            k = it["ssc_kit"]
            code, topic = _map_ssc_topic(it)
            print(f"- [{code} {topic}] {it['paper']}/{it['subject']} | {it['title_en'][:90]}\n"
                  f"    Q: {k['question_en']}\n    A: {k['answer_en']} | Key: {k['key_fact_en']} | GK: {k['static_gk_en']}")
finally:
    close_all()
