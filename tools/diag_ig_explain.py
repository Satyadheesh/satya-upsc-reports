"""READ-ONLY: for the Instagram explainer (ig.explain), yesterday's top 12 notes: their timeline (event), the
timeline's updates before the note, Mains angles, and which earlier notes the keyword rule would call 'the same story'."""
import json
import time

from common.db import close_all, in_chunks, main_db, translation_db, upsc_db
from ig.post import Builder
from reports.data import editions
from tg.periods import ist_date

up, m = upsc_db(), main_db()
try:
    b = Builder(up, time.time())
    p = b.yday
    w = b.window(p)
    en_ed, hi_ed, _, _ = editions(p, w.period(p, "en"), w.period(p, "hi"))
    top = en_ed[:12]
    ids = [it["id"] for it in top]
    ev_of = {r[0]: r[1] for r in in_chunks(m, "SELECT article_id, event_id FROM event_articles WHERE article_id IN ({ph})", ids)}
    print(f"day {p['key']}: {len(en_ed)} notes, Hindi edition: {bool(hi_ed)}; {len(ev_of)} of {len(ids)} top notes are on a timeline\n")
    for k, it in enumerate(top):
        ev = ev_of.get(it["id"])
        print(f"## {k + 1}. [{it['paper']}] {it['title_en']}")
        dims = up.execute("SELECT mains_dimensions FROM upsc_articles WHERE article_id = ?", [it["id"]]).rows
        print("- dims:", json.loads(dims[0][0] or "[]") if dims else None)
        if ev:
            e = m.execute("SELECT title, article_count, first_seen FROM events WHERE id = ?", [ev]).rows
            print(f"- timeline {ev}: {e[0][0] if e else '?'} ({e[0][1] if e else '?'} articles)")
            ms = m.execute("SELECT ea.article_id, ea.event_date, COALESCE(ea.milestone, a.rephrased_title, a.title) FROM event_articles ea "
                           "JOIN articles a ON a.id = ea.article_id WHERE ea.event_id = ? ORDER BY ea.event_date", [ev]).rows
            before = [r for r in ms if (r[1] or 0) < it["published_at"] - 6 * 3600]
            print(f"- {len(before)} updates before this note; latest 6:")
            for a, ts, t in before[-6:]:
                print(f"    - {ist_date(ts or 0)} [{a}] {t}")
            notes = {r[0] for r in in_chunks(up, "SELECT article_id FROM upsc_articles WHERE article_id IN ({ph})", [r[0] for r in before])}
            print(f"- of which with a UPSC note: {len(notes)}")
        else:
            print("- no timeline")
        print()
finally:
    close_all()
