"""READ-ONLY: size, free (unused) pages and row counts of the old and new Hindi and UPSC databases."""
from tools.db_copy import client, objects, tables, count

for which in ("translation", "upsc"):
    print(f"## {which}\n| | size | of which free (reusable, not data) | data | rows |\n|---|---|---|---|---|")
    for label, prefix in (("old", "SATYA_"), ("new", "NEW_")):
        db = client(prefix, which)
        pc, ps, fl = (db.execute(f"PRAGMA {x}").rows[0][0] for x in ("page_count", "page_size", "freelist_count"))
        rows = sum(count(db, n) for n, _ in tables(objects(db)))
        print(f"| {label} | {pc * ps / 1048576:.1f} MB | {fl * ps / 1048576:.1f} MB | {(pc - fl) * ps / 1048576:.1f} MB | {rows:,} |")
        db.close()
    print()
