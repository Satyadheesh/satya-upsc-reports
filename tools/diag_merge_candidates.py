"""READ-ONLY: pairs of recent timelines that look like the same story (centroid cosine + shared rare entity keys)."""
import json
import time
from collections import Counter

import numpy as np

from common.db import close_all, main_db

m = main_db()
WATCH = {12562, 13054, 12890, 13152, 13063, 13091, 13049, 13594, 13787, 13800, 13347, 13144, 13781,
         13036, 10577, 13894, 12969, 12976}


def q(sql, args=()):
    for i in range(3):
        try:
            return m.execute(sql, list(args)).rows
        except Exception:
            if i == 2:
                raise
            time.sleep(2)


try:
    print('events schema:', q("SELECT sql FROM sqlite_master WHERE name = 'events'")[0][0].replace('\n', ' '))
    print('redirect-ish tables:', [r[0] for r in q("SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE '%redirect%' OR name LIKE 'tl_%')")])
    freq = Counter()
    for (k,) in q("SELECT entity_keys FROM events WHERE entity_keys IS NOT NULL"):
        try:
            freq.update(set(json.loads(k)))
        except Exception:
            pass
    print('most common keys:', freq.most_common(25))
    since = int(time.time()) - 60 * 86400
    rows = q("SELECT id, title, entity_keys, centroid, article_count, first_seen, last_seen, state, saga_id FROM events "
             "WHERE title IS NOT NULL AND slug IS NOT NULL AND last_seen >= ?", [since])
    ev = []
    for r in rows:
        c = np.frombuffer(bytes(r[3]), dtype=np.float32) if r[3] else None
        if c is None or not len(c):
            continue
        c = c / (np.linalg.norm(c) or 1)
        ev.append(dict(id=r[0], title=r[1], keys=set(json.loads(r[2] or '[]')), c=c, n=r[4], first=r[5], last=r[6], state=r[7], saga=r[8]))
    print(f'\n{len(ev)} titled timelines seen in the last 60 days; dim {len(ev[0]["c"])}')
    C = np.stack([e['c'] for e in ev])
    S = C @ C.T
    pairs = []
    for i in range(len(ev)):
        for j in range(i + 1, len(ev)):
            s = float(S[i, j])
            shared = ev[i]['keys'] & ev[j]['keys']
            rare = {k for k in shared if freq[k] <= 200}
            if s >= 0.60 or ({ev[i]['id'], ev[j]['id']} <= WATCH):
                pairs.append((s, len(shared), sorted(rare), ev[i], ev[j]))
    pairs.sort(key=lambda p: -p[0])
    print(f'\n## Pairs with cosine >= 0.60 ({sum(1 for p in pairs if p[0] >= 0.6)}), plus the watched ones\n')
    print('| cos | shared | rare shared | A (n) | B (n) |\n|---|---|---|---|---|')
    for s, ns, rare, a, b in pairs[:260]:
        w = ' **W**' if a['id'] in WATCH and b['id'] in WATCH else ''
        print(f"| {s:.3f}{w} | {ns} | {', '.join(rare[:5])} | {a['id']} {a['title'][:60]} ({a['n']}) | {b['id']} {b['title'][:60]} ({b['n']}) |")
    print('\n## Watched pairs not shown above\n')
    for s, ns, rare, a, b in pairs[260:]:
        if a['id'] in WATCH and b['id'] in WATCH:
            print(f"- {s:.3f} shared {ns} rare {rare[:5]} | {a['id']} {a['title'][:50]} | {b['id']} {b['title'][:50]}")
    print('\n## Keys of watched timelines\n')
    for e in ev:
        if e['id'] in WATCH:
            print(f"- {e['id']} {e['title'][:60]}: {sorted(e['keys'])}")
finally:
    close_all()
