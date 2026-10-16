"""Before switching to the new Mumbai databases: run the queries our code depends on against the OLD and the NEW
database and compare the answers (both read-only), then a write test in a scratch table on the NEW database only
(created and dropped here). Usage: python -m tools.db_compat --which upsc|translation"""
import argparse
import time

from tools.db_copy import client

DAY = 86400


def queries(which, now):
    if which == "upsc":
        return [
            ("window (INDEXED BY idx_upsc_pub + kit join)",
             "SELECT a.article_id, a.upsc_score, k.status FROM upsc_articles a INDEXED BY idx_upsc_pub LEFT JOIN upsc_kit k "
             "ON k.article_id = a.article_id WHERE a.published_at >= ? AND a.published_at < ? "
             "ORDER BY a.upsc_score DESC, a.published_at DESC LIMIT 60", [now - 3 * DAY, now]),
            ("Hindi extras todo (partial index idx_upsc_extras_todo)",
             "SELECT article_id FROM upsc_articles INDEXED BY idx_upsc_extras_todo WHERE translated_hi = 1 AND hi_extras = 0 "
             "AND (article_id % ?) = ? ORDER BY published_at DESC LIMIT ?", [4, 1, 50]),
            ("SSC cards (INDEXED BY idx_ssc_ca_status)",
             "SELECT article_id FROM ssc_ca INDEXED BY idx_ssc_ca_status WHERE status = 'card' AND published_at >= ? "
             "AND published_at < ? ORDER BY article_id", [now - 7 * DAY, now]),
            ("days list (GROUP BY)",
             "SELECT ((published_at + 19800) / 86400) AS d, COUNT(*) AS n, MAX(published_at) AS last FROM upsc_articles "
             "WHERE published_at >= ? GROUP BY d ORDER BY d DESC LIMIT 30", [now - 40 * DAY]),
            ("related notes (subqueries)",
             "SELECT article_id FROM upsc_articles WHERE subject = (SELECT subject FROM upsc_articles WHERE article_id = "
             "(SELECT MAX(article_id) FROM upsc_articles)) AND article_id != 0 AND published_at <= ? "
             "ORDER BY published_at DESC LIMIT 14", [now]),
            ("JSON functions", "SELECT article_id, json_extract(prelims_pointers, '$[0].type'), json_array_length(keywords) "
             "FROM upsc_articles WHERE prelims_pointers IS NOT NULL ORDER BY article_id DESC LIMIT 20", []),
            ("ig / telegram records", "SELECT key, posted_at FROM ig_posts ORDER BY posted_at DESC LIMIT 5", []),
            ("report chunks (big rows)", "SELECT key, n, length(data) FROM upsc_report_chunks ORDER BY rowid DESC LIMIT 5", []),
        ]
    return [
        ("note translations", "SELECT article_id, length(why_in_news_hi), mains_dimensions_hi IS NOT NULL FROM upsc_translations "
         "ORDER BY article_id DESC LIMIT 50", []),
        ("headline translations", "SELECT article_id, length(rephrased_title_hi) FROM translations ORDER BY article_id DESC LIMIT 50", []),
        ("milestones by article (idx)", "SELECT article_id, length(milestone_hi) FROM event_milestone_translations "
         "WHERE article_id IN (SELECT article_id FROM event_milestone_translations ORDER BY article_id DESC LIMIT 30)", []),
        ("timeline titles", "SELECT event_id, title_hi FROM event_translations ORDER BY event_id DESC LIMIT 30", []),
        ("kit translations JSON", "SELECT article_id, json_array_length(facts_hi) FROM upsc_kit_translations ORDER BY article_id DESC LIMIT 20", []),
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--which", choices=["upsc", "translation"], required=True)
    a = ap.parse_args()
    old, new = client("SATYA_", a.which), client("NEW_", a.which)
    bad = 0
    now = int(time.time())
    print(f"## {a.which}: same answers?\n| query | old | new | same | old s | new s |\n|---|---|---|---|---|---|")
    for name, sql, args in queries(a.which, now):
        res = []
        for db in (old, new):
            t = time.time()
            try:
                rows = [tuple(r) for r in db.execute(sql, args).rows]
                res.append((rows, None, time.time() - t))
            except Exception as e:
                res.append((None, f"{type(e).__name__}: {str(e)[:120]}", time.time() - t))
        (ro, eo, to), (rn, en, tn) = res
        same = eo is None and en is None and ro == rn
        bad += not same
        print(f"| {name} | {eo or len(ro)} | {en or len(rn)} | {'yes' if same else 'NO'} | {to:.2f} | {tn:.2f} |")
    print("\n## write test on the NEW database (scratch table __compat_test, dropped at the end)")
    steps = [
        ("create", "CREATE TABLE IF NOT EXISTS __compat_test (id INTEGER PRIMARY KEY, v TEXT, n INTEGER DEFAULT 0)", []),
        ("insert", "INSERT INTO __compat_test (id, v) VALUES (1, 'a'), (2, 'b')", []),
        ("upsert", "INSERT INTO __compat_test (id, v) VALUES (1, 'x') ON CONFLICT(id) DO UPDATE SET v = excluded.v, n = n + 1", []),
        ("insert or replace", "INSERT OR REPLACE INTO __compat_test (id, v) VALUES (2, 'y')", []),
        ("update", "UPDATE __compat_test SET n = n + 5 WHERE id = 2", []),
        ("alter add column", "ALTER TABLE __compat_test ADD COLUMN extra TEXT", []),
        ("partial index", "CREATE INDEX IF NOT EXISTS __compat_idx ON __compat_test(n) WHERE n > 0", []),
        ("read back", "SELECT id, v, n, extra FROM __compat_test ORDER BY id", []),
        ("drop", "DROP TABLE __compat_test", []),
    ]
    for name, sql, args in steps:
        try:
            r = new.execute(sql, args)
            print(f"- {name}: ok" + (f" -> {[tuple(x) for x in r.rows]}" if name == "read back" else ""))
        except Exception as e:
            bad += 1
            print(f"- {name}: FAILED {type(e).__name__}: {str(e)[:200]}")
    try:
        new.execute("DROP TABLE IF EXISTS __compat_test")
    except Exception:
        pass
    print("\nRESULT: " + ("ALL GOOD" if not bad else f"{bad} PROBLEMS"))
    for c in (old, new):
        c.close()


if __name__ == "__main__":
    main()
