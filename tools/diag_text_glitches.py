"""READ-ONLY: recent headlines with odd text (digit-for-letter like 'Contr0l', a doubled phrase like 'Rail Vikas Rail Vikas')."""
import re
import time
from common.db import close_all, main_db

m = main_db()
try:
    since = int(time.time()) - 4 * 86400
    rows = m.execute("SELECT id, title, rephrased_title, scraped_at FROM articles INDEXED BY idx_articles_scraped "
                     "WHERE scraped_at >= ? ORDER BY scraped_at DESC LIMIT 6000", [since]).rows
    print(f"# Text glitches in {len(rows)} headlines of the last 4 days\n")
    leet = re.compile(r"\b[A-Za-z]+0[A-Za-z]+\b|\b[A-Za-z]+[13][A-Za-z]{2,}\b")
    dbl = re.compile(r"\b(\w+(?: \w+){0,2}) \1\b")
    n = 0
    for i, t, r, at in rows:
        for label, text in (("title", t or ""), ("rephrased", r or "")):
            hits = [x for x in leet.findall(text) if not re.match(r"(?i)^(g20|h1n1|b2b|covid19|mp3|4g|5g)$", x)]
            d = dbl.search(text)
            if hits or (d and not d.group(1).isdigit()):
                n += 1
                if n <= 60:
                    print(f"- {i} {label}: {text[:160]}  ← {hits or d.group(0)}")
    print(f"\n{n} glitches")
finally:
    close_all()
