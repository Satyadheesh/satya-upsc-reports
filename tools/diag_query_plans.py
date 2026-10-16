"""READ-ONLY: query plans and timings of the site's news list queries on the main DB (the logger caught 5-10 s ones,
e.g. /source/<name>). EXPLAIN QUERY PLAN reads no rows; each query then runs once to time it."""
import time
from common.db import close_all, main_db

COLS = ("a.id, a.title, a.rephrased_title, a.url, s.name AS source_name, a.image_url, a.scraped_at, a.category, a.sentiment, "
        "a.sentiment_target, a.rephrased_article, a.party_mentioned, a.ministers_mentioned, a.states_mentioned, a.cities_mentioned, "
        "a.topic_tags, a.civic_flag, a.civic_flag_score, a.civic_flag_category, a.civic_flag_reason")
ST = "a.status IN ('classified', 'entity_processed', 'processed')"
m = main_db()
try:
    src = m.execute("SELECT id, name FROM sources ORDER BY id").rows
    aj = next((r for r in src if "jazeera" in str(r[1]).lower()), src[0])
    party = m.execute("SELECT slug FROM article_entities WHERE kind = 'party' ORDER BY article_id DESC LIMIT 1").rows[0][0]
    qs = [
        ("source page (" + str(aj[1]) + ")", f"SELECT {COLS} FROM articles a LEFT JOIN sources s ON a.source_id = s.id WHERE {ST} AND a.source_id = ? ORDER BY a.scraped_at DESC LIMIT 100", [aj[0]]),
        ("category page (politics)", f"SELECT {COLS} FROM articles a LEFT JOIN sources s ON a.source_id = s.id WHERE {ST} AND a.category = ? ORDER BY a.scraped_at DESC LIMIT 100", ["politics"]),
        ("party page (" + party + ")", f"SELECT {COLS} FROM article_entities ae JOIN articles a ON a.id = ae.article_id LEFT JOIN sources s ON a.source_id = s.id WHERE ae.kind = 'party' AND ae.slug = ? AND {ST} ORDER BY ae.article_id DESC LIMIT 100", [party]),
        ("feed (latest 100)", f"SELECT {COLS} FROM articles a LEFT JOIN sources s ON a.source_id = s.id WHERE {ST} ORDER BY a.scraped_at DESC LIMIT 100", []),
    ]
    print("## indexes on articles")
    for r in m.execute("SELECT name, sql FROM sqlite_master WHERE type = 'index' AND tbl_name = 'articles'").rows:
        print(f"- {r[0]}: {r[1]}")
    for name, sql, args in qs:
        plan = m.execute("EXPLAIN QUERY PLAN " + sql, args).rows
        t = time.time(); n = len(m.execute(sql, args).rows); dt = time.time() - t
        print(f"\n## {name}: {n} rows in {dt:.2f}s (from GitHub, US)\n" + "\n".join(f"- {r[-1]}" for r in plan))
finally:
    close_all()
