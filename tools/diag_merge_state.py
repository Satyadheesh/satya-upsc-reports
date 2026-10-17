"""READ-ONLY: state of the timeline clean-up tables and of a few timelines."""
from common.db import close_all, main_db, upsc_db
m = main_db()
u = upsc_db()
try:
    for t in ("event_redirects", "event_merge_checks"):
        ok = m.execute("SELECT 1 FROM sqlite_master WHERE name = ?", [t]).rows
        print(t, "exists" if ok else "missing", m.execute(f"SELECT COUNT(*) FROM {t}").rows[0][0] if ok else "")
    print("event_articles cols:", [r[1] for r in m.execute("PRAGMA table_info(event_articles)").rows])
    print("events cols:", [r[1] for r in m.execute("PRAGMA table_info(events)").rows])
    for eid in (13895, 13923):
        print(eid, m.execute("SELECT id, title, article_count FROM events WHERE id = ?", [eid]).rows,
              "rows:", m.execute("SELECT COUNT(*) FROM event_articles WHERE event_id = ?", [eid]).rows[0][0])
    print("sync_marks:", u.execute("SELECT * FROM sync_marks").rows if u.execute("SELECT 1 FROM sqlite_master WHERE name='sync_marks'").rows else 'missing')
    print("stories:", m.execute("SELECT COUNT(DISTINCT story_id), COUNT(*) FROM events WHERE story_id IS NOT NULL").rows)
    print("repeats marked:", m.execute("SELECT COUNT(*) FROM event_articles WHERE dup_of IS NOT NULL").rows)
    print(m.execute("SELECT old_id, old_slug, new_id FROM event_redirects").rows if m.execute("SELECT 1 FROM sqlite_master WHERE name='event_redirects'").rows else '')
finally:
    close_all()
