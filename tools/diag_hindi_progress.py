"""READ-ONLY: progress of the Hindi coverage work (timelines, UPSC notes, mains dimensions / keywords) and the
partial indexes it uses. Writes nothing."""
import time
from common.db import close_all, main_db, translation_db, upsc_db

now = int(time.time())
m, tr, up = main_db(), translation_db(), upsc_db()


def one(db, sql, args=()):
    try:
        return db.execute(sql, list(args)).rows
    except Exception as e:
        return [(f"error: {e}",)]


try:
    print("# Hindi coverage progress\n")
    print("events (titled, slug) by translated_hi:",
          one(m, "SELECT translated_hi, COUNT(*) FROM events WHERE title IS NOT NULL AND slug IS NOT NULL GROUP BY translated_hi"))
    print("event_articles with text by translated_hi:",
          one(m, "SELECT translated_hi, COUNT(*) FROM event_articles WHERE milestone IS NOT NULL GROUP BY translated_hi"))
    print("Hindi event titles:", one(tr, "SELECT COUNT(*) FROM event_translations WHERE title_hi IS NOT NULL AND title_hi != ''"),
          "Hindi milestones:", one(tr, "SELECT COUNT(*) FROM event_milestone_translations"))
    print("indexes (main):", one(m, "SELECT name FROM sqlite_master WHERE type='index' AND name IN "
                                    "('idx_ea_hi_todo','idx_events_hi_todo','idx_articles_hi_todo')"))
    print("migration marker:", one(tr, "SELECT * FROM hindi_meta WHERE key = 'timeline_flags_v1'"))
    print("\nUPSC notes by translated_hi:", one(up, "SELECT translated_hi, COUNT(*) FROM upsc_articles GROUP BY translated_hi"))
    print("UPSC hi_extras (translated notes):", one(up, "SELECT hi_extras, COUNT(*) FROM upsc_articles WHERE translated_hi = 1 GROUP BY hi_extras"))
    print("upsc_translations with dims / keywords:", one(tr, "SELECT SUM(mains_dimensions_hi IS NOT NULL AND mains_dimensions_hi != '[]'), "
                                                          "SUM(keywords_hi IS NOT NULL AND keywords_hi != '[]'), COUNT(mains_dimensions_hi) FROM upsc_translations"))
    print("newest UPSC translation:", one(tr, "SELECT (? - MAX(translated_at)) / 60 FROM upsc_translations", (now,)), "min ago")
    print("\nsamples (dims / keywords):")
    for r in one(tr, "SELECT article_id, mains_dimensions_hi, keywords_hi FROM upsc_translations WHERE keywords_hi IS NOT NULL "
                     "AND keywords_hi != '[]' ORDER BY translated_at DESC LIMIT 4"):
        print("-", *r)
    print("\nsamples (new milestones):")
    for r in one(tr, "SELECT event_id, article_id, milestone_hi FROM event_milestone_translations ORDER BY rowid DESC LIMIT 4"):
        print("-", *r)
finally:
    close_all()
