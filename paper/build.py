"""Build the newspaper-style PDFs of the last 24 hours (one per paper and language).

  python -m paper.build --out out/            (PDFs + page-1/2 PNGs for a preview; posts nothing)

paper/post.py uses build_all() and posts the result to the Telegram channels.
"""
import argparse
import datetime as dt
import os
import pathlib
import subprocess
import time

from common.db import close_all, main_db, translation_db

from . import render
from .data import MIN_STORIES, PAPERS, edition, window

REPORTS = pathlib.Path(__file__).parent.parent / "reports"   # fonts/ live here (render inlines url(fonts/...))
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
FOOTER = ('<div style="width:100%;font:6.5px Helvetica,Arial,sans-serif;color:#857d75;padding:0 11mm;display:flex;'
          'justify-content:space-between;letter-spacing:.08em"><span><b style="color:#141210;letter-spacing:.18em">SATYADHEESH</b>'
          '&nbsp;&nbsp;·&nbsp;&nbsp;{label}</span><span>PAGE <span class="pageNumber"></span> / <span class="totalPages"></span></span></div>')


def fetch_images(items, workers=16):
    """Download each story photo once and re-encode it at print size (≤900 px, JPEG q68) as a data URI, so the PDF
    stays small (embedding the publishers' full-size files made a 24-story edition 13 MB) and nothing depends on the
    network while printing. A photo that fails to download is simply left out."""
    import base64
    import io
    from concurrent.futures import ThreadPoolExecutor

    import requests
    from PIL import Image

    from .data import image_variant

    def one(it):
        url = image_variant(it.get("image"), True)
        if not url:
            return
        try:
            r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                                                                       "(KHTML, like Gecko) Chrome/126 Safari/537.36"})
            if r.status_code != 200 or len(r.content) < 3000:
                return
            im = Image.open(io.BytesIO(r.content)).convert("RGB")
            if im.width < 300:
                return
            im.thumbnail((900, 900))
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=68, optimize=True, progressive=True)
            it["image_data"] = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
        except Exception:
            return

    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(one, items))
    print(f"photos: {sum(1 for i in items if i.get('image_data'))}/{sum(1 for i in items if i.get('image'))} downloaded", flush=True)


def plan(items):
    """[(paper, slug, paper_hi, lang, stories)] for every paper/language with enough stories."""
    out = []
    for paper, slug, paper_hi in PAPERS:
        for lang in ("en", "hi"):
            st = edition(items, paper, lang)
            if len(st) >= MIN_STORIES:
                out.append((paper, slug, paper_hi, lang, st))
    return out


def file_name(slug, lang, day):
    return f"{slug}-{'hindi' if lang == 'hi' else 'english'}-{day.isoformat()}.pdf"


def build_all(day=None, only=None, out=None):
    """{(slug, lang): (pdf_bytes, file_name, paper, paper_hi, n_stories)}"""
    day = day or dt.datetime.now(IST).date()
    main, trans = main_db(), translation_db()
    items = window(main, trans)
    jobs = [j for j in plan(items) if not only or j[1] in only]
    fetch_images([i for i in items if i["source"] in {j[0] for j in jobs}])
    print(f"{len(items)} stories in the last 24 h; {len(jobs)} editions: "
          + ", ".join(f"{j[1]}/{j[3]} ({len(j[4])})" for j in jobs), flush=True)
    from playwright.sync_api import sync_playwright
    res = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        for paper, slug, paper_hi, lang, st in jobs:
            t = time.time()
            html = render.render(paper, paper_hi, st, lang, day)
            f = REPORTS / f"_paper_{os.getpid()}.html"
            f.write_text(html, encoding="utf-8")
            page.goto(f.as_uri(), wait_until="load", timeout=120000)
            page.evaluate("document.fonts.ready")
            page.wait_for_timeout(200)
            label = f"{(paper_hi if lang == 'hi' else paper).upper()} · {day.strftime('%-d %b %Y').upper()} · PERSONAL COPY"
            pdf = page.pdf(print_background=True, prefer_css_page_size=True, display_header_footer=True,
                           header_template="<div></div>", footer_template=FOOTER.format(label=label))
            f.unlink(missing_ok=True)
            name = file_name(slug, lang, day)
            res[(slug, lang)] = (pdf, name, paper, paper_hi, len(st))
            pages = pdf.count(b"/Type /Page") - pdf.count(b"/Type /Pages")
            print(f"  {name}: {len(st)} stories, {pages} pages, {len(pdf) // 1024} KB, {time.time() - t:.1f}s", flush=True)
            if out:
                out.mkdir(parents=True, exist_ok=True)
                (out / name).write_bytes(pdf)
                subprocess.run(["pdftoppm", "-png", "-r", "70", "-l", "2", str(out / name), str(out / name[:-4])], check=False)
        browser.close()
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out")
    ap.add_argument("--only", default="", help="comma-separated slugs, e.g. thehindu,toi")
    a = ap.parse_args()
    try:
        build_all(only=[s for s in a.only.split(",") if s], out=pathlib.Path(a.out))
    finally:
        close_all()


if __name__ == "__main__":
    main()
