"""READ-ONLY: what the SSC runner (ssc_ca) decided: counts per IST day and status, the cards each daily SSC PDF would
show, every code-check stop, and 'said no' rows whose title matches WATCH words (recall check on expected stories)."""
import os
import time
from collections import Counter, defaultdict

from common.db import close_all, upsc_db
from reports.data import DAY, IST, ssc_items
import datetime as dt

from reports.periods import daily, ist_date

WATCH = [w.strip().lower() for w in (os.environ.get("WATCH") or
         "green energy,hdfc,bagchi,forex,foreign exchange,reserves,gst,repo,isro,exercise,missile,day,nobel,award").split(",")]
up = upsc_db()
try:
    now = int(time.time())
    rows = up.execute("SELECT article_id, published_at, status, topic, importance, scope, reason, title, prompt_version "
                      "FROM ssc_ca WHERE published_at >= ? ORDER BY published_at DESC", [now - 8 * DAY]).rows
    by_day = defaultdict(Counter)
    for r in rows:
        by_day[time.strftime("%d %b", time.gmtime(r[1] + IST))][r[2]] += 1
    print("## ssc_ca rows by IST day (last 8 days)\n")
    for d, c in by_day.items():
        print(f"- {d}: " + ", ".join(f"{k} {v}" for k, v in c.most_common()))
    print(f"\nprompt versions: {Counter(r[8] for r in rows)}")
    today = (now + IST) // DAY * DAY - IST
    for back in (0, 1, 2):
        p = daily(ist_date(now) - dt.timedelta(days=back))
        its = ssc_items(up, p)
        print(f"\n## Daily SSC PDF {p['key']}: {len(its)} cards")
        for it in its:
            k = it["ssc_kit"]
            print(f"- [{it['ssc_topic'][0]} {it['ssc_topic'][1]} · {it['importance']}] {it['title'][:100]} ({it['id']})\n"
                  f"    Q: {k['question_en']} | A: {k['answer_en']}")
    print("\n## Stopped by a code check (last 3 days)\n")
    for r in rows:
        if r[1] >= today - 2 * DAY and r[2] == "skip" and r[6] and not str(r[6]).startswith(("model: no", "importance",
                                                                                               "duplicate")):
            print(f"- {str(r[7])[:100]} — {r[6]} ({r[3]} · {r[4]} · {r[5]}) ({r[0]})")
    print("\n## Said no, title matches a WATCH word (last 3 days)\n")
    for r in rows:
        t = str(r[7] or "").lower()
        if r[1] >= today - 2 * DAY and r[2] == "skip" and str(r[6]).startswith(("model: no", "importance")) \
                and any(w in t for w in WATCH):
            print(f"- {str(r[7])[:110]} — {r[6]} ({r[3]} · {r[4]}) ({r[0]})")
    print("\n## Failed\n")
    for r in rows:
        if r[2] == "failed":
            print(f"- {str(r[7])[:100]} — {str(r[6])[:150]} ({r[0]})")
finally:
    close_all()
