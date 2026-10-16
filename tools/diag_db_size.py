"""READ-ONLY: size of each database (pages x page size) and its biggest tables (row counts), to plan local read
copies on the server (16 Oct 2026: the UPSC DB is in US East and the translation DB in Ireland; the server is in Mumbai)."""
from common.db import close_all, main_db, translation_db, upsc_db

for name, db in (("main", main_db()), ("upsc", upsc_db()), ("translation", translation_db())):
    try:
        pc = db.execute("PRAGMA page_count").rows[0][0]
        ps = db.execute("PRAGMA page_size").rows[0][0]
        print(f"## {name}: {pc * ps / 1048576:.0f} MB ({pc} pages of {ps} B)")
        tabs = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '_litestream%'").rows]
        counts = []
        for t in tabs:
            try:
                counts.append((db.execute(f'SELECT COUNT(*) FROM "{t}"').rows[0][0], t))
            except Exception as e:
                counts.append((-1, f"{t} ({type(e).__name__})"))
        for n, t in sorted(counts, reverse=True)[:8]:
            print(f"- {t}: {n:,} rows")
    except Exception as e:
        print(f"## {name}: error {type(e).__name__}: {str(e)[:200]}")
    print()
close_all()
