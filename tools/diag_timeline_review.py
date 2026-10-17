"""READ-ONLY: checks an outside review of /timelines — split stories, the '5+ updates' list, one blurb, off-topic entries."""
import time
from common.db import close_all, main_db

m = main_db()


def ist(t):
    return time.strftime('%d %b %Y', time.gmtime((t or 0) + 19800))


def q(sql, args=()):
    for i in range(3):
        try:
            return m.execute(sql, list(args)).rows
        except Exception as e:  # Turso drops connections now and then
            if i == 2:
                raise
            time.sleep(2)


def events_like(label, words, limit=40):
    cond = ' OR '.join(['LOWER(e.title) LIKE ?'] * len(words))
    rows = q(f"SELECT e.id, e.slug, e.title, e.article_count, (SELECT COUNT(*) FROM event_articles ea WHERE ea.event_id = e.id), "
             f"e.first_seen, e.last_seen, e.state, e.saga_id FROM events e WHERE e.title IS NOT NULL AND ({cond}) "
             f"ORDER BY e.last_seen DESC LIMIT {limit}", [f'%{w}%' for w in words])
    print(f"\n### {label} ({len(rows)})\n")
    print('| id | title | count col | real updates | first | last | state | saga |\n|---|---|---|---|---|---|---|---|')
    for r in rows:
        print(f"| {r[0]} | [{r[2]}](https://satyadheesh.in/event/{r[1]}) | {r[3]} | {r[4]} | {ist(r[5])} | {ist(r[6])} | {r[7]} | {r[8]} |")
    return rows


try:
    print('# Timeline review check\n')
    print('events columns:', [r[1] for r in q('PRAGMA table_info(events)')])

    # 1. The page's first 120 (what /timelines renders)
    top = q("SELECT e.id, e.title, e.article_count, (SELECT COUNT(*) FROM event_articles ea WHERE ea.event_id = e.id), e.last_seen, e.saga_id "
            "FROM events e WHERE e.title IS NOT NULL AND e.slug IS NOT NULL AND e.slug != '' ORDER BY e.last_seen DESC LIMIT 120")
    print(f"\n## First 120 on /timelines\n- with article_count < 5: {sum(1 for r in top if r[2] < 5)}")
    print(f"- article_count differs from real update rows: {sum(1 for r in top if r[2] != r[3])}")
    for r in top:
        if r[2] != r[3]:
            print(f"  - {r[0]} {r[1][:70]} — count {r[2]}, rows {r[3]}")

    # 2. Split stories
    events_like('Election Commission / CEC', ['election commission', 'chief election', ' cec', 'cec ', 'gyanesh', 'voter deletion',
                                              'voter list', 'electoral roll', 'vote chori', 'vote theft', 'impeach'])
    events_like('Cockroach Janta Party', ['cockroach'])
    events_like('Captain Smit', ['smit'])

    # 3. The 'Protests and detentions' blurb
    for ev in q("SELECT id, title FROM events WHERE slug = 'protests-and-detentions-over-election-chief-allegations'"):
        print(f"\n## Latest updates of {ev[0]} {ev[1]}\n")
        for r in q("SELECT ea.event_date, ea.milestone, a.rephrased_title, a.title, ea.article_id FROM event_articles ea "
                   "JOIN articles a ON a.id = ea.article_id WHERE ea.event_id = ? ORDER BY ea.event_date DESC LIMIT 8", [ev[0]]):
            print(f"- {ist(r[0])} art {r[4]} — milestone: {r[1]}\n  headline: {r[2] or r[3]}")
    print('\n## Any timeline whose latest updates mention Imran Khan\n')
    for r in q("SELECT ea.event_id, e.title, ea.event_date, COALESCE(ea.milestone, a.rephrased_title, a.title) FROM event_articles ea "
               "JOIN articles a ON a.id = ea.article_id JOIN events e ON e.id = ea.event_id "
               "WHERE ea.event_date > ? AND (LOWER(COALESCE(ea.milestone,'')) LIKE '%imran khan%' OR LOWER(COALESCE(a.rephrased_title, a.title)) LIKE '%imran khan%') "
               "ORDER BY ea.event_date DESC LIMIT 15", [int(time.time()) - 30 * 86400]):
        print(f"- event {r[0]} {r[1]} · {ist(r[2])} — {r[3]}")

    # 4. Off-topic candidates
    events_like('Kanaka Durga / Starlink / hijack', ['kanaka', 'durga temple', 'starlink', 'hijack', 'pirat'])
finally:
    close_all()
