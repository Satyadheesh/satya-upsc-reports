"""Build the Brief and Detailed report PDFs (daily / weekly / monthly × English / Hindi) and store them
in the UPSC DB (upsc_reports + upsc_report_chunks) under keys like daily:2026-10-01:en:brief.

  python -m reports.build --scope recent|nightly|all [--force] [--only weekly:] [--preview out/]

Notes are fetched once for the whole window, every report's content hash is compared with the stored
one, and only changed reports are printed (Chromium, so Hindi shaping is right). --preview renders
PDFs + page images into a folder and stores nothing.
"""
import argparse
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import time

from common.db import close_all, main_db, translation_db, upsc_db

from . import render
from .data import select, Window
from .periods import periods_for, parse

REPORT_VERSION = 3          # bump when layout or selection changes: every PDF is rebuilt
HI_READY = 0.8              # Hindi edition only once this share of the notes is translated
CHUNK = 400 * 1024
HERE = pathlib.Path(__file__).parent
FOOTER = ('<div style="width:100%;font:7px Helvetica,Arial,sans-serif;color:#857d75;padding:0 12mm;display:flex;'
          'justify-content:space-between;letter-spacing:.08em"><span><b style="color:#120f0b;letter-spacing:.18em">SATYADHEESH</b>'
          '&nbsp;&nbsp;·&nbsp;&nbsp;{label}</span><span>satyadheesh.in/upsc&nbsp;&nbsp;·&nbsp;&nbsp;'
          '<span class="pageNumber"></span> / <span class="totalPages"></span></span></div>')


def ensure_tables(c):
    c.batch([
        "CREATE TABLE IF NOT EXISTS upsc_reports (key TEXT PRIMARY KEY, kind TEXT NOT NULL, period TEXT NOT NULL, "
        "lang TEXT NOT NULL, hash TEXT NOT NULL, items INTEGER NOT NULL, bytes INTEGER NOT NULL, "
        "chunks INTEGER NOT NULL, updated_at INTEGER NOT NULL)",
        "CREATE TABLE IF NOT EXISTS upsc_report_chunks (key TEXT NOT NULL, n INTEGER NOT NULL, data BLOB NOT NULL, "
        "PRIMARY KEY (key, n))",
    ])


def store(c, key, p, lang, h, items, pdf):
    import libsql_client
    parts = [pdf[i:i + CHUNK] for i in range(0, len(pdf), CHUNK)]
    st = [libsql_client.Statement("DELETE FROM upsc_report_chunks WHERE key = ?", [key])]
    st += [libsql_client.Statement("INSERT INTO upsc_report_chunks (key, n, data) VALUES (?, ?, ?)", [key, n, x])
           for n, x in enumerate(parts)]
    st.append(libsql_client.Statement(
        "INSERT OR REPLACE INTO upsc_reports (key, kind, period, lang, hash, items, bytes, chunks, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", [key, p["kind"], p["key"], lang, h, items, len(pdf), len(parts), int(time.time())]))
    c.batch(st)  # one transaction: the site never serves half a PDF


def content_hash(p, lang, edition, items):
    kit = (lambda i: (i.get("kit_hi") if lang == "hi" else i.get("kit")) or {})
    sig = [[i["id"], i["title"], i["why"], i["fact_box"], i["pointers"], i["mains"], i["related"], i["paper"], i["subject"],
            kit(i).get("short_title"), kit(i).get("takeaway"), kit(i).get("brief_text"), kit(i).get("facts"), kit(i).get("mcq")]
           for i in items]
    raw = json.dumps({"v": REPORT_VERSION, "k": p["kind"], "p": p["key"], "l": lang, "e": edition, "n": sig},
                     ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def label(p, lang, edition):
    kind = {"daily": "DAILY", "weekly": "WEEKLY", "monthly": "MONTHLY"}[p["kind"]]
    return f"UPSC {kind} {'BRIEF' if edition == 'brief' else 'DETAILED NOTES'}{' (HINDI)' if lang == 'hi' else ''} · {p['key']}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", default="recent", choices=["recent", "nightly", "all"])
    ap.add_argument("--period", default="", help="periods instead of a scope, e.g. 'daily:2026-10-01 weekly:2026-W40'")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", default="", help="only keys containing this text, e.g. ':brief' or 'weekly:'")
    ap.add_argument("--preview", default="", help="render into this folder; store nothing")
    args = ap.parse_args()

    if args.period:
        periods = [parse(*x.split(":", 1)) for x in args.period.split()]
    else:
        periods = periods_for(args.scope, time.time())
    upsc, main = upsc_db(), main_db()
    try:
        trans = translation_db()
    except SystemExit:
        trans = None
        print("::warning::translation DB not configured: Hindi editions skipped")
    if not args.preview:
        ensure_tables(upsc)
    start, end = min(p["start"] for p in periods), max(p["end"] for p in periods)
    t0 = time.time()
    w = Window(upsc, main, start, min(end, int(time.time()) + 86400), trans)
    print(f"{len(w.rows)} notes in window ({len(periods)} periods) loaded in {time.time() - t0:.1f}s")
    stored = {r[0]: r[1] for r in upsc.execute("SELECT key, hash FROM upsc_reports").rows} if not args.preview else {}

    jobs = []
    for p in periods:
        en_items = w.period(p, "en")
        if not en_items:
            continue
        chosen_en, total, _ = select(p, en_items)
        langs = [("en", chosen_en, 1.0)]
        if trans is not None:
            chosen_hi, _, share = select(p, en_items, w.period(p, "hi"))
            if share >= HI_READY:
                langs.append(("hi", chosen_hi, share))
            else:
                print(f"  {p['kind']}:{p['key']}:hi not ready ({share:.0%} translated)")
        for lang, items, _ in langs:
            for edition in ("brief", "detailed"):
                key = f"{p['kind']}:{p['key']}:{lang}:{edition}"
                if args.only and args.only not in key:
                    continue
                h = content_hash(p, lang, edition, items)
                if not args.force and not args.preview and stored.get(key) == h:
                    continue
                jobs.append((key, p, lang, edition, items, total, h))
    print(f"{len(jobs)} reports to build")
    if not jobs:
        return

    from playwright.sync_api import sync_playwright
    out = pathlib.Path(args.preview) if args.preview else None
    if out:
        out.mkdir(parents=True, exist_ok=True)
    built = failed = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        for key, p, lang, edition, items, total, h in jobs:
            t = time.time()
            try:
                html = (render.brief if edition == "brief" else render.detailed)(p, items, total, lang)
                f = HERE / f"_render_{os.getpid()}.html"
                f.write_text(html, encoding="utf-8")
                page.goto(f.as_uri(), wait_until="load")
                page.evaluate("document.fonts.ready")
                page.wait_for_timeout(200)
                pdf = page.pdf(format="A4", print_background=True, prefer_css_page_size=True, display_header_footer=True,
                               header_template="<div></div>", footer_template=FOOTER.format(label=label(p, lang, edition)))
                f.unlink(missing_ok=True)
                pages = pdf.count(b"/Type /Page") - pdf.count(b"/Type /Pages")
                if out:
                    name = re.sub(r"[^A-Za-z0-9]+", "_", key)
                    (out / f"{name}.pdf").write_bytes(pdf)
                    subprocess.run(["pdftoppm", "-png", "-r", "60", "-l", "3", str(out / f"{name}.pdf"), str(out / name)], check=False)
                else:
                    store(upsc, key, p, lang, h, len(items), pdf)
                built += 1
                print(f"  {key}: {len(items)} notes, {pages} pages, {len(pdf) // 1024} KB, {time.time() - t:.1f}s")
            except Exception as ex:
                failed += 1
                print(f"::warning::{key} failed: {type(ex).__name__}: {ex}")
        browser.close()
    print(f"done: {built} built, {failed} failed")
    if failed and not built:
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    finally:
        close_all()
