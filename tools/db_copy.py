"""Copy a whole database into a new, EMPTY one (16 Oct 2026: the UPSC DB moves from US East and the Hindi translation DB
from Ireland to Mumbai, next to the server and the main DB).

  python -m tools.db_copy --which upsc|translation --mode plan     read-only: schema, row counts, new DB empty?
  python -m tools.db_copy --which upsc|translation --mode copy     schema + every row (refuses a new DB that has data)
  python -m tools.db_copy --which upsc|translation --mode resume   carry on after an interrupted copy (new rows only)
  python -m tools.db_copy --which upsc|translation --mode verify   read-only: row counts and last row ids, old vs new

Old DB: SATYA_UPSC_DB_URL/TOKEN or SATYA_TRANSLATION_DB_URL/TOKEN. New DB: NEW_UPSC_DB_URL/TOKEN or
NEW_TRANSLATION_DB_URL/TOKEN. The old DB is only read. Run copy only while nothing writes to the old DB.
Tables keep their row ids; indexes and triggers are created after the rows; AUTOINCREMENT counters are copied."""
import argparse
import os
import sys
import time

SKIP = ("sqlite_", "_litestream", "libsql_", "_cf_", "__turso")  # __turso_internal_*: the new DBs' own bookkeeping
BATCH_BYTES = 1_500_000
BATCH_ROWS = 400


def client(prefix, which):
    import libsql_client
    up = which.upper()
    url, tok = os.environ.get(f"{prefix}{up}_DB_URL"), os.environ.get(f"{prefix}{up}_DB_TOKEN")
    if not url or not tok:
        raise SystemExit(f"missing {prefix}{up}_DB_URL / _TOKEN")
    url = url.strip().replace("libsql://", "https://").replace("turso://", "https://")
    return libsql_client.create_client_sync(url=url, auth_token=tok.strip())


def objects(db):
    rows = db.execute("SELECT type, name, tbl_name, sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY rowid").rows
    return [r for r in rows if not r[1].startswith(SKIP)]


def tables(objs):
    return [(n, s) for t, n, _, s in objs if t == "table"]


def count(db, t):
    return db.execute(f'SELECT COUNT(*) FROM "{t}"').rows[0][0]


def has_rowid(db, t):
    try:
        db.execute(f'SELECT rowid FROM "{t}" LIMIT 1')
        return True
    except Exception:
        return False


def size(v):
    return len(v) if isinstance(v, (str, bytes)) else 8


def plan(old, new):
    objs = objects(old)
    virt = [n for n, s in tables(objs) if s.upper().startswith("CREATE VIRTUAL")]
    print("## old DB")
    tot = 0
    for n, _ in tables(objs):
        c = count(old, n)
        tot += c
        print(f"- {n}: {c:,} rows")
    print(f"- indexes: {sum(1 for o in objs if o[0] == 'index')}, triggers: {sum(1 for o in objs if o[0] == 'trigger')}, "
          f"views: {sum(1 for o in objs if o[0] == 'view')}, total rows {tot:,}")
    if virt:
        print(f"- VIRTUAL TABLES (not handled by this tool): {virt}")
    newobjs = objects(new)
    print(f"\n## new DB: {len(newobjs)} objects" + (" (EMPTY: ready)" if not newobjs else ""))
    for t, n, _, _ in newobjs[:20]:
        print(f"- {t} {n}" + (f": {count(new, n):,} rows" if t == "table" else ""))
    return objs, newobjs, virt


def read_page(old, collist, n, rid, last, off, limit):
    """Up to `limit` rows; halves the page when the database refuses an answer that big (big PDF chunks)."""
    while True:
        try:
            if rid:
                return old.execute(f'SELECT {collist} FROM "{n}" WHERE rowid > ? ORDER BY rowid LIMIT {limit}',
                                   [last if last is not None else -(2 ** 62)]).rows, limit
            return old.execute(f'SELECT {collist} FROM "{n}" LIMIT {limit} OFFSET {off}').rows, limit
        except Exception as e:
            if limit == 1:
                raise
            limit = max(1, limit // 4)
            print(f"  ({n}: answer too big ({type(e).__name__}), reading {limit} rows at a time)", flush=True)


def copy(old, new, resume=False):
    objs, newobjs, virt = plan(old, new)
    if virt:
        raise SystemExit("virtual tables present: not copying")
    have = {n for t, n, _, _ in newobjs if t == "table"}
    if not resume:
        if any(t == "table" and count(new, n) for t, n, _, _ in newobjs):
            raise SystemExit("the new DB already has data: not copying (use resume after an interrupted copy)")
        for t, n, _, _ in newobjs:  # leftovers of an earlier, interrupted copy (no rows)
            if t in ("table", "view"):
                new.execute(f'DROP {t.upper()} IF EXISTS "{n}"')
        have = set()
    t0 = time.time()
    for n, sql in tables(objs):
        if n not in have:
            new.execute(sql)
    print(f"\n## copying ({len(tables(objs))} tables)", flush=True)
    for n, _ in tables(objs):
        cols = [r[1] for r in old.execute(f'PRAGMA table_info("{n}")').rows]
        rid = has_rowid(old, n)
        sel_cols = (["rowid"] if rid else []) + cols
        collist = ", ".join(f'"{c}"' for c in sel_cols)
        ins = f'INSERT INTO "{n}" ({collist}) VALUES ({", ".join("?" * len(sel_cols))})'
        done, last, off, tn, limit = 0, None, 0, time.time(), 2000
        if resume and n in have:
            if rid:
                last = new.execute(f'SELECT MAX(rowid) FROM "{n}"').rows[0][0]
            elif count(new, n):
                if count(new, n) == count(old, n):
                    print(f"- {n}: already complete")
                    continue
                raise SystemExit(f"{n}: partly copied and has no row ids: empty it by hand first")
        while True:
            rows, limit = read_page(old, collist, n, rid, last, off, limit)
            if not rows:
                break
            batch, b = [], 0
            for r in rows:
                vals = list(r)
                batch.append((ins, vals))
                b += sum(size(v) for v in vals)
                if b >= BATCH_BYTES or len(batch) >= BATCH_ROWS:
                    new.batch(batch)
                    batch, b = [], 0
            if batch:
                new.batch(batch)
            done += len(rows)
            off += len(rows)
            if rid:
                last = rows[-1][0]
        print(f"- {n}: {done:,} rows in {time.time() - tn:.0f}s", flush=True)
    existing = {o[1] for o in objects(new)}
    for t, n, _, sql in objs:
        if t in ("index", "trigger", "view") and n not in existing:
            new.execute(sql)
    try:
        seq = old.execute("SELECT name, seq FROM sqlite_sequence").rows
        for name, s in seq:
            new.execute("DELETE FROM sqlite_sequence WHERE name = ?", [name])
            new.execute("INSERT INTO sqlite_sequence (name, seq) VALUES (?, ?)", [name, s])
        print(f"- AUTOINCREMENT counters: {len(seq)}")
    except Exception as e:
        print(f"- AUTOINCREMENT counters: none ({type(e).__name__})")
    print(f"\ncopy finished in {(time.time() - t0) / 60:.1f} min")
    verify(old, new)


def verify(old, new):
    print("\n## verify (old vs new)\n| table | old rows | new rows | old last id | new last id | ok |\n|---|---|---|---|---|---|")
    bad = 0
    objs = objects(old)
    for n, _ in tables(objs):
        co, cn = count(old, n), count(new, n)
        lo = ln = "-"
        if has_rowid(old, n):
            lo = old.execute(f'SELECT MAX(rowid) FROM "{n}"').rows[0][0]
            ln = new.execute(f'SELECT MAX(rowid) FROM "{n}"').rows[0][0]
        ok = co == cn and lo == ln
        bad += not ok
        print(f"| {n} | {co:,} | {cn:,} | {lo} | {ln} | {'yes' if ok else 'NO'} |")
    no, nn = [o[1] for o in objs if o[0] != "table"], [o[1] for o in objects(new) if o[0] != "table"]
    missing = sorted(set(no) - set(nn))
    print(f"\nindexes/triggers/views: old {len(no)}, new {len(nn)}" + (f"; MISSING {missing}" if missing else ""))
    print("RESULT: " + ("IDENTICAL" if not bad and not missing else f"DIFFERENT ({bad} tables)"))
    if bad or missing:
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--which", choices=["upsc", "translation"], required=True)
    ap.add_argument("--mode", choices=["plan", "copy", "resume", "verify"], default="plan")
    a = ap.parse_args()
    old, new = client("SATYA_", a.which), client("NEW_", a.which)
    try:
        {"plan": plan, "copy": copy, "resume": lambda o, n: copy(o, n, resume=True), "verify": verify}[a.mode](old, new)
    finally:
        for c in (old, new):
            try:
                c.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
