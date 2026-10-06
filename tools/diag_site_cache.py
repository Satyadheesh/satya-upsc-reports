"""READ-ONLY: the site's persistent data cache (next_data_cache in the main DB): rows and bytes per version."""
from common.db import close_all, main_db

m = main_db()
try:
    rows = m.execute("SELECT ver, COUNT(*), SUM(LENGTH(value)), MIN(last_modified), MAX(last_modified) FROM next_data_cache GROUP BY ver ORDER BY MAX(last_modified) DESC").rows
    import time
    print("ver | rows | MB | oldest | newest")
    for v, n, b, lo, hi in rows:
        f = lambda ms: time.strftime('%d %b %H:%M', time.gmtime((ms or 0) / 1000))
        print(f"{v} | {n} | {(b or 0) / 1e6:.1f} | {f(lo)} | {f(hi)}")
    print("total rows", sum(r[1] for r in rows), "MB", round(sum((r[2] or 0) for r in rows) / 1e6, 1))
    big = m.execute("SELECT key, LENGTH(value) FROM next_data_cache ORDER BY LENGTH(value) DESC LIMIT 8").rows
    for k, b in big:
        print(f"  {b / 1e3:.0f} KB  {k[:110]}")
finally:
    close_all()
