"""Post today's UPSC carousel to Instagram at an exact IST time (English, then Hindi).

  python -m ig.post --at 19:00            (scheduled: waits for 19:00 IST)
  python -m ig.post --dry-run             (render slides + captions to the previews branch, post nothing)
  python -m ig.post --check-setup         (token + account check only)

cron-job.org starts the workflow ~20 min early (GitHub crons are the backup). Slides are rendered with Chromium,
pushed to the public `ig-media` branch (Instagram fetches images from a public URL), and published with the
Instagram API. Each language is recorded in ig_posts, so a rerun only posts what is missing; Hindi waits for
4 of the 5 stories to be translated and is retried by the 21:00 IST catch-up run.
"""
import argparse
import datetime as dt
import os
import pathlib
import re
import subprocess
import sys
import time

import requests

from common.db import close_all, main_db, translation_db, upsc_db
from reports.data import Window, editions, hindi_title, select
from tg.periods import DAY, ist_date, ist_midnight, target_ts

from .caption import caption
from .graph import IG, current_token
from .slides import FIT_JS, fact_pairs, slides_html

HERE = pathlib.Path(__file__).resolve().parent
REPORTS = HERE.parent / "reports"          # fonts live here
OUT = HERE.parent / "ig_out"
LATE_LIMIT = 4 * 3600
HI_MIN = 4                                 # Hindi post only when 4 of the 5 stories have Hindi


def today_period(now, day=None):
    d = dt.date.fromisoformat(day) if day else ist_date(now)
    start = ist_midnight(d)
    return {"kind": "daily", "key": d.isoformat(), "start": start, "end": start + DAY, "first": d, "last": d}


def tidy(s, n):
    """First sentence(s) up to n characters, cut at a sentence/clause end, never mid-word, no '…'."""
    s = " ".join(str(s or "").split())
    if len(s) <= n:
        return s
    for sep in (". ", "। ", "; ", ", "):
        k = s.rfind(sep, 0, n)
        if k > n // 3:
            return s[:k].rstrip(" ,;") + ("." if sep == ". " else "।" if sep == "। " else "")
    return s[: s.rfind(" ", 0, n)]


def story(it, lang):
    hi = lang == "hi"
    kit = (it.get("kit_hi") if hi else it.get("kit")) or {}
    title = kit.get("short_title") or (hindi_title(it) if hi else it["title_en"])
    why = kit.get("takeaway") or tidy(it["why"], 200)
    return {"id": it["id"], "title": tidy(title, 110), "why": tidy(why, 220), "paper": it["paper"], "subject": it["subject"],
            "facts": [(lab, tidy(txt, 170)) for lab, txt in fact_pairs(kit.get("facts"), it["pointers"], hi)][:3],
            "mcq": kit.get("mcq")}


def pick(p, w):
    """Top 5 of the day (same order as the reports), stories with a study kit first so slides have takeaways + facts.
    English and Hindi come from the same pairing as the PDFs (reports.data.editions): the same 5 stories with the same
    parts, so the Hindi carousel is the English one in Hindi. Without enough Hindi yet: English only."""
    en_ed, hi_ed, _, _ = editions(p, w.period(p, "en"), w.period(p, "hi"))
    order = sorted(range(len(en_ed)), key=lambda k: (not en_ed[k].get("kit"), k))[:5]
    return [en_ed[k] for k in order], ([hi_ed[k] for k in order] if hi_ed else [])


META = re.compile(r"^(?:the|this) (?:note|article|news) (?:states|says|mentions|notes|reports) that\s+|^according to the (?:note|article),?\s+|"
                  r"^(?:नोट|लेख) के अनुसार,?\s*", re.I)


def _no_meta(t):
    """'The note states that the Chairperson receives…' -> 'The Chairperson receives…' (readers never see 'the note')."""
    t = " ".join(str(t or "").split())
    out = META.sub("", t)
    return out[:1].upper() + out[1:] if out != t else t


def quiz_of(stories, only_id=None):
    for s in stories:
        if only_id is not None and s["id"] != only_id:
            continue
        m = s.get("mcq")
        if m and m.get("options") and len(m["options"]) == 4 and len(m.get("question", "")) <= 260:
            return {"question": m["question"], "statements": m.get("statements"), "options": m["options"],
                    "answer": int(m["answer"]), "explanation": tidy(_no_meta(m.get("explanation")), 260)}
    return None


def render(day, stories, quiz, lang, folder, is_today=True):
    from playwright.sync_api import sync_playwright
    html, n = slides_html(day, stories, quiz, lang, is_today)
    folder.mkdir(parents=True, exist_ok=True)
    page_file = REPORTS / f"_ig_{lang}.html"   # next to reports/fonts so the bundled fonts load
    page_file.write_text(html, encoding="utf-8")
    files = []
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": 1080, "height": 1350}, device_scale_factor=1)
        pg.goto(page_file.as_uri(), wait_until="load")
        pg.evaluate("document.fonts.ready")
        pg.wait_for_timeout(300)
        pg.evaluate(FIT_JS)
        for k in range(n):
            f = folder / f"{k + 1:02d}.jpg"
            pg.locator("section.s").nth(k).screenshot(path=str(f), type="jpeg", quality=92)
            files.append(f)
        b.close()
    page_file.unlink()
    return files


def push_media(files_by_dir, branch, msg):
    """Commit the slides to a branch of this (public) repo; returns the raw URL prefix."""
    repo, tok = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_TOKEN")
    if not repo or not tok:
        raise SystemExit("GITHUB_REPOSITORY / GITHUB_TOKEN missing (run inside the workflow)")
    wt = pathlib.Path("/tmp/ig_wt")
    subprocess.run(["rm", "-rf", str(wt)], check=True)
    wt.mkdir()
    git = lambda *a: subprocess.run(["git", *a], cwd=wt, check=True, capture_output=True, text=True)
    git("init", "-q")
    git("config", "user.name", "github-actions[bot]")
    git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    git("remote", "add", "origin", f"https://x-access-token:{tok}@github.com/{repo}.git")
    if subprocess.run(["git", "fetch", "-q", "--depth", "1", "origin", branch], cwd=wt, capture_output=True).returncode == 0:
        git("checkout", "-q", "-b", branch, "FETCH_HEAD")
    else:
        git("checkout", "-q", "--orphan", branch)
    for rel, files in files_by_dir.items():
        d = wt / rel
        subprocess.run(["rm", "-rf", str(d)], check=True)
        d.mkdir(parents=True)
        for f in files:
            (d / f.name).write_bytes(f.read_bytes())
    git("add", "-A")
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=wt).returncode != 0:  # same slides as an earlier run: nothing to push
        git("commit", "-qm", msg)
        git("push", "-q", "origin", f"HEAD:{branch}")
    return f"https://raw.githubusercontent.com/{repo}/{branch}"


def wait_public(urls, limit=180):
    t0 = time.time()
    for u in urls:
        while True:
            try:
                r = requests.head(u, timeout=30, allow_redirects=True)
                if r.ok and r.headers.get("content-type", "").startswith("image/"):
                    break
            except requests.RequestException:
                pass
            if time.time() - t0 > limit:
                raise SystemExit(f"slide not reachable at {u}")
            time.sleep(5)


def posted(upsc, key):
    return bool(upsc.execute("SELECT 1 FROM ig_posts WHERE key = ?", [key]).rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--at", default="19:00")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--now", action="store_true")
    ap.add_argument("--check-setup", action="store_true")
    ap.add_argument("--langs", default="en,hi")
    ap.add_argument("--day", default="", help="post this IST day's notes instead of today's (YYYY-MM-DD)")
    args = ap.parse_args()
    upsc = upsc_db()

    if args.check_setup:
        ig = IG(current_token(upsc))
        print(f"Instagram account: @{ig.username} (id {ig.user_id}); token OK; API {os.environ.get('IG_API_VERSION', 'v23.0')}")
        for m in ig.get(f"{ig.user_id}/media", fields="timestamp,media_type,permalink", limit=3).get("data", []):
            print(f"  recent: {m.get('timestamp')} {m.get('media_type')} {m.get('permalink')}")
        return

    start = time.time()
    p = today_period(start, args.day or None)
    target = start if (args.now or args.dry_run) else target_ts(start, args.at)
    if time.time() > target + LATE_LIMIT and not args.now:
        print(f"::warning::more than {LATE_LIMIT // 3600} h past {args.at} IST; not posting")
        return
    langs = [l for l in args.langs.split(",") if l in ("en", "hi")]
    keys = {l: f"ig:daily:{p['key']}:{l}" for l in langs}
    if not args.dry_run and all(posted(upsc, k) for k in keys.values()):
        print("already posted, nothing to do")
        return
    if not args.dry_run:
        ig = IG(current_token(upsc))   # fail early (bad token) before rendering
        print(f"posting as @{ig.username}")

    w = Window(upsc, main_db(), p["start"], p["end"], translation_db())
    top, top_hi = pick(p, w)
    if len(top) < 3:
        print(f"::warning::only {len(top)} notes today; nothing posted")
        return
    posts = {}
    st_en = [story(i, "en") for i in top]
    q_en = quiz_of(st_en)
    q_id = next((s["id"] for s in st_en if q_en and s.get("mcq") and s["mcq"].get("question") == q_en["question"]), None)
    if "en" in langs:
        posts["en"] = (st_en, q_en)
    if "hi" in langs:
        if len(top_hi) >= HI_MIN:
            st = [story(i, "hi") for i in top_hi]
            posts["hi"] = (st, quiz_of(st, q_id) if q_id is not None else None)
        else:
            print(f"::warning::Hindi: {len(top_hi)} of {len(top)} stories translated (needs {HI_MIN}); the 21:00 IST catch-up retries")

    rendered = {}
    for lang, (st, q) in posts.items():
        if not args.dry_run and posted(upsc, keys[lang]):
            continue
        is_today = p["first"] == ist_date(time.time())
        files = render(p["first"], st, q, lang, OUT / p["key"] / lang, is_today)
        cap = caption(p["first"], st, bool(q), lang, is_today)
        (OUT / p["key"] / lang / "caption.txt").write_text(cap, encoding="utf-8")
        rendered[lang] = (files, cap)
        print(f"\n--- {lang}: {len(files)} slides, caption {len(cap)} chars\n{cap}")
    if not rendered:
        return

    branch = "previews" if args.dry_run else "ig-media"
    base = push_media({f"ig/{p['key']}/{l}": f + [OUT / p["key"] / l / "caption.txt"] for l, (f, _) in rendered.items()},
                      branch, f"instagram {'preview' if args.dry_run else 'slides'} {p['key']}")
    if args.dry_run:
        print(f"\npreview: {base}/ig/{p['key']}/")
        return

    for lang, (files, cap) in rendered.items():
        urls = [f"{base}/ig/{p['key']}/{lang}/{f.name}" for f in files]
        wait_public(urls)
        left = target - time.time()
        if left > 0:
            print(f"waiting {left / 60:.1f} min for {args.at} IST", flush=True)
            time.sleep(left)
        media_id = ig.carousel(urls, cap)
        upsc.execute("INSERT OR REPLACE INTO ig_posts (key, media_id, posted_at) VALUES (?, ?, ?)", [keys[lang], media_id, int(time.time())])
        try:
            link = ig.get(media_id, fields="permalink").get("permalink")
        except Exception as ex:
            link = f"media {media_id} (permalink lookup failed: {ex})"
        print(f"posted {lang} carousel at {time.strftime('%H:%M:%S', time.gmtime(time.time() + 19800))} IST: {link}")
        print(f"::notice title=Instagram {lang}::{link}")


if __name__ == "__main__":
    try:
        main()
    finally:
        close_all()
