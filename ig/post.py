"""Instagram: one post a day since 20 Oct 2026 (Yash: people don't read much), English then its Hindi twin (IST):

  19:00 / 21:00  "Today in 60 seconds"   up to 6 slides (ig.digest): lead story, number of the day, the other 4
                 stories in one line each, a 3-question SSC quiz, answers. Built from the formats below.
  Reels: every reel of the Satyadheesh/reels pipeline is also posted as an Instagram Reel (ig.reel).

  Older formats, kept for --now / --dry-run but no longer scheduled: explain (morning explainer, ig.explain),
  ssc (5-question SSC quiz, ig.formats), upsc ("Today's 5", ig.slides), qotd (number/question of the day).

  python -m ig.post --scheduled            (post whatever slot is due: due from 35 min before to 2.5 h after its time)
  python -m ig.post --now --format ssc --langs en
  python -m ig.post --dry-run [--format all] (render slides + captions to the previews branch, post nothing)
  python -m ig.post --dry-run --format qotd      (the old 'Number of the day', kept but no longer posted)
  python -m ig.post --check-setup          (token + account check only)

Runs start every 30 min (GitHub cron, cron-job.org as the reliable starter). Slides are rendered with Chromium,
pushed to the public `ig-media` branch (Instagram fetches images from a public URL) and published with the
Instagram API. Each post is recorded in ig_posts (key ig:<format>:<day>:<lang>; the UPSC carousel keeps its old
key ig:daily:<day>:<lang>), so a rerun only posts what is missing. A Hindi post without Hindi content is skipped.
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
from reports.data import Window, editions, hindi_title
from reports.render import SIZE, pick_cards
from tg.periods import DAY, ist_date, ist_midnight, target_ts

from .caption import caption
from .graph import IG, current_token
from .slides import FIT_JS, fact_pairs, slides_html
from .text import looks_whole, tidy

HERE = pathlib.Path(__file__).resolve().parent
REPORTS = HERE.parent / "reports"          # fonts live here
OUT = HERE.parent / "ig_out"
LATE_LIMIT = 4 * 3600
HI_MIN = 4                                 # Hindi post only when 4 of the 5 stories have Hindi


def today_period(now, day=None):
    d = dt.date.fromisoformat(day) if day else ist_date(now)
    start = ist_midnight(d)
    return {"kind": "daily", "key": d.isoformat(), "start": start, "end": start + DAY, "first": d, "last": d}


BOILER = re.compile(r"\bcase study\b|\bGS ?[1-4]\b|\b(?:key|important) (?:topic|issue)\b", re.I)


def story(it, lang, en=None):
    """One story slide. 'Why' is the note's why-in-news: the kit's takeaway is nearly always boilerplate
    ('Monetary policy: a key GS3 topic …', 87 of 88 on 8-9 Oct) and is used only when it isn't (checked on the
    English kit, so both languages make the same choice)."""
    hi = lang == "hi"
    kit = (it.get("kit_hi") if hi else it.get("kit")) or {}
    title = kit.get("short_title") or (hindi_title(it) if hi else it["title_en"])
    en_take = (it.get("kit") or {}).get("takeaway")
    why = kit.get("takeaway") if en_take and kit.get("takeaway") and not BOILER.search(en_take) else it["why"]
    if why == it["why"] and not looks_whole((en or it)["why"]) and kit.get("brief_text"):
        # a why-in-news saved cut off (~2% of notes; judged on the English, `en`, which the Hindi translates):
        # the kit's one-line brief, which is whole
        why = kit["brief_text"]
    return {"id": it["id"], "title": tidy(title, 170), "why": tidy(why, 240), "paper": it["paper"], "subject": it["subject"],
            "facts": [(lab, tidy(txt, 170)) for lab, txt in fact_pairs(kit.get("facts"), it["pointers"], hi)][:3],
            "mcq": kit.get("mcq")}


def pick(p, w):
    """The day's 5 stories = the PDF's own '5 stories you can't skip' (reports.render.pick_cards), from the same
    English/Hindi pairing as the PDFs (reports.data.editions): same stories, same parts, so the Hindi carousel is the
    English one in Hindi. Also returns the quiz story: the most important one whose quiz exists in both languages.
    Without enough Hindi yet: English only."""
    en_ed, hi_ed, _, _ = editions(p, w.period(p, "en"), w.period(p, "hi"))
    n_top, n_cards = SIZE["daily"][:2]
    ids = [it["id"] for it in pick_cards(en_ed, n_cards, "daily")[:n_top]]
    pos = {it["id"]: k for k, it in enumerate(en_ed)}
    order = [pos[i] for i in ids]
    quiz = next((k for k, it in enumerate(en_ed) if (it.get("kit") or {}).get("mcq")), None)
    pair = lambda eds: [eds[k] for k in order] if eds else []
    return pair(en_ed), pair(hi_ed), (en_ed[quiz] if quiz is not None else None), (hi_ed[quiz] if hi_ed and quiz is not None else None)


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


def hindi_cards(cards):
    """Hindi SSC cards with the Hindi text in the question_en / answer_en / key_fact_en fields the quiz code reads."""
    return [{**c, "ssc_kit": {**c["ssc_kit"], "question_en": c["ssc_kit"]["question_hi"],
                              "answer_en": c["ssc_kit"]["answer_hi"], "key_fact_en": c["ssc_kit"].get("key_fact_hi") or ""}}
            for c in cards]


def push_media(files_by_dir, branch, msg):
    """Commit the slides to a branch of this (public) repo; returns the raw URL prefix."""
    repo, tok = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_TOKEN")
    if branch != "ig-media" and os.environ.get("CORE_TOKEN") and repo:
        # dry-run previews go to the private code repo; only ig-media must be public (Instagram fetches from it)
        repo, tok = f"{repo}-core", os.environ["CORE_TOKEN"]
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


SLOTS = [("digest", "en", "19:00"), ("digest", "hi", "21:00")]  # one post a day since 20 Oct 2026
EARLY, LATE = 35 * 60, int(2.5 * 3600)


def post_key(fmt, day, lang):
    return f"ig:daily:{day}:{lang}" if fmt == "upsc" else f"ig:{fmt}:{day}:{lang}"


def render_pages(html, n, lang, folder):
    """Screenshot each <section class="s"> of `html` (1080x1350) to folder/NN.jpg."""
    from playwright.sync_api import sync_playwright
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


class Builder:
    """Builds one post (slides html + caption) per format and language; data is loaded once per run."""

    def __init__(self, upsc, now, day=None):
        self.upsc, self.now = upsc, now
        self.today = today_period(now, day)
        self.yday = today_period(self.today["start"] - 3600)
        self._w, self._ssc = {}, {}

    def window(self, p):
        if p["key"] not in self._w:
            self._w[p["key"]] = Window(self.upsc, main_db(), p["start"], p["end"], translation_db())
        return self._w[p["key"]]

    def stories(self, p):
        top, top_hi, quiz_en, quiz_hi = pick(p, self.window(p))
        return top, top_hi, quiz_en, quiz_hi

    def upsc_post(self, lang):
        p = self.today
        top, top_hi, quiz_en, quiz_hi = self.stories(p)
        if len(top) < 3:
            return None, f"only {len(top)} notes today"
        q_en = quiz_of([story(quiz_en, "en")]) if quiz_en else None
        q_hi = quiz_of([story(quiz_hi, "hi")]) if quiz_hi else None
        if top_hi and not (q_en and q_hi):
            q_en = q_hi = None  # the quiz runs in both carousels or in neither
        if lang == "hi" and len(top_hi) < HI_MIN:
            return None, f"Hindi: {len(top_hi)} of {len(top)} stories translated (needs {HI_MIN})"
        st = [story(i, lang) for i in top] if lang == "en" else [story(h, lang, en) for h, en in zip(top_hi, top)]
        is_today = p["first"] == ist_date(time.time())
        html, n = slides_html(p["first"], st, q_en if lang == "en" else q_hi, lang, is_today)
        return (html, n, caption(p["first"], st, bool(q_en if lang == "en" else q_hi), lang, is_today)), None

    def ssc_cards(self, hours=24):
        """SSC cards of the last `hours` (English, plus the Hindi ones the Hindi service has written)."""
        if hours not in self._ssc:
            from reports.data import ssc_items, ssc_items_hi
            # today: the 24 h up to now; a past --day: that whole day
            end = int(self.now) if self.today["key"] == ist_date(self.now).isoformat() else self.today["end"]
            p = {"kind": "daily", "key": self.today["key"], "start": end - hours * 3600, "end": end, "first": self.today["first"]}
            en = ssc_items(self.upsc, p) or []
            try:
                hi, _ = ssc_items_hi(en, translation_db(), ready=0.0)
            except Exception:
                hi = None
            self._ssc[hours] = (en, hi or [])
        return self._ssc[hours]

    def qotd_post(self, lang):
        from .formats import qotd_caption, qotd_html, qotd_number, qotd_question
        # the most telling number among yesterday's 10 best notes (same English/Hindi pairing as the PDFs)
        p = self.yday
        w = self.window(p)
        en_ed, hi_ed, _, _ = editions(p, w.period(p, "en"), w.period(p, "hi"))
        en, hi = qotd_number([story(i, "en") for i in en_ed[:10]], [story(i, "hi") for i in hi_ed[:10]] if hi_ed else None)
        if not en:  # no number today: the top SSC question
            cards_en, cards_hi = self.ssc_cards()
            if cards_en:
                c = max(cards_en, key=lambda c: c["importance"] or 0)
                h = next((x for x in cards_hi if x["id"] == c["id"]), None)
                k = c["ssc_kit"]
                en, hi = qotd_question({"question": k["question_en"], "answer": k["answer_en"], "key": k["key_fact_en"],
                                        "title": c["title"]},
                                       {"question": h["ssc_kit"]["question_hi"], "answer": h["ssc_kit"]["answer_hi"],
                                        "key": h["ssc_kit"].get("key_fact_hi")} if h else None)
        if lang == "hi" and en and not hi:  # the number has no Hindi version: the top SSC question in Hindi instead
            cards_en, cards_hi = self.ssc_cards()
            if cards_hi:
                h = max(cards_hi, key=lambda c: c["importance"] or 0)["ssc_kit"]
                _, hi = qotd_question({"question": "", "answer": "", "key": "", "title": ""},
                                      {"question": h["question_hi"], "answer": h["answer_hi"], "key": h.get("key_fact_hi")})
        item = en if lang == "en" else hi
        if not item:
            return None, "no number or question with " + ("Hindi" if lang == "hi" else "content")
        html, n = qotd_html(item, lang)
        return (html, n, qotd_caption(item, lang)), None

    def explain_post(self, lang):
        """The morning explainer (ig.explain): one of yesterday's top notes, the same one in both languages."""
        from .explain import explain_caption, explain_html, extras, pick as pick_explain
        if not hasattr(self, "_explain"):
            p = self.yday
            w = self.window(p)
            en_ed, hi_ed, _, _ = editions(p, w.period(p, "en"), w.period(p, "hi"))
            ex = extras(self.upsc, main_db(), translation_db(), en_ed[:12])
            self._explain = pick_explain(en_ed, hi_ed, ex)
        pe, ph = self._explain
        p = pe if lang == "en" else ph
        if not p:
            return None, "no note with Mains angles or a backstory yesterday" if not pe else "the explainer has no Hindi"
        q = None
        if pe.get("mcq") and (ph is None or ph.get("mcq")):
            q_en = quiz_of([{"id": pe["id"], "mcq": pe["mcq"]}])
            q_hi = quiz_of([{"id": ph["id"], "mcq": ph["mcq"]}]) if ph else None
            if q_en and (ph is None or q_hi):  # in both posts or in neither
                q = q_en if lang == "en" else q_hi
        html, n = explain_html(p, q, lang)
        return (html, n, explain_caption(p, bool(q), lang)), None

    def ssc_post(self, lang):
        from reports.render import date_label
        from .formats import ssc_caption, ssc_quiz_html
        for hours in (24, 48, 72):  # a quiet day: take the last two or three days
            quiz, keys, cards = self._ssc_quiz(lang, hours)
            if len(quiz) >= 5:
                break
        if len(quiz) < 5:
            return None, f"only {len(quiz)} quiz questions from {len(cards)} {lang} SSC cards"
        label = date_label(self.today["first"], lang == "hi")
        html, n = ssc_quiz_html(quiz, keys, lang, label)
        return (html, n, ssc_caption(quiz, lang, label)), None

    def _ssc_quiz(self, lang, hours):
        from reports.render import ssc_quiz
        cards_en, cards_hi = self.ssc_cards(hours)
        cards = cards_en if lang == "en" else cards_hi
        if lang == "hi":  # the quiz reads question_en / answer_en: give it the Hindi text
            cards = hindi_cards(cards)
        # wrong options: the other cards, plus (English) the week's cards before them
        pool = [(c["ssc_kit"]["question_en"], c["ssc_kit"]["answer_en"], c["ssc_topic"][0]) for c in cards]
        pool += list(getattr(cards_en if lang == "en" else cards_hi, "pool", ()))
        quiz = ssc_quiz(cards, 5, f"ig:{self.today['key']}:{lang}", pool)
        keys = [next((c["ssc_kit"].get("key_fact_en") or "" for c in cards if c["ssc_kit"]["question_en"] == q), "")
                for q, _, _ in quiz]
        return quiz, keys, cards

    def digest_post(self, lang):
        """The one daily post (ig.digest): today's 5 notes, the most telling number among today's 10 best notes, and
        3 one-line SSC questions from the last 24 h (48 h on a quiet day)."""
        from .digest import digest_caption, digest_html, quick_quiz
        from .formats import qotd_number
        p = self.today
        top, top_hi, _, _ = self.stories(p)
        if len(top) < 3:
            return None, f"only {len(top)} notes today"
        if lang == "hi" and len(top_hi) < HI_MIN:
            return None, f"Hindi: {len(top_hi)} of {len(top)} stories translated (needs {HI_MIN})"
        st = [story(i, lang) for i in top] if lang == "en" else [story(h, lang, en) for h, en in zip(top_hi, top)]
        if not hasattr(self, "_num"):
            w = self.window(p)
            en_ed, hi_ed, _, _ = editions(p, w.period(p, "en"), w.period(p, "hi"))
            self._num = qotd_number([story(i, "en") for i in en_ed[:10]], [story(i, "hi") for i in hi_ed[:10]] if hi_ed else None)
        number = self._num[0] if lang == "en" else self._num[1]
        quiz = []
        for hours in (24, 48):
            cards_en, cards_hi = self.ssc_cards(hours)
            quiz = quick_quiz(cards_en if lang == "en" else hindi_cards(cards_hi))
            if len(quiz) >= 3:
                break
        html, n = digest_html(p["first"], st, number, quiz, lang)
        return (html, n, digest_caption(p["first"], st, number, quiz, lang)), None

    def build(self, fmt, lang):
        return {"upsc": self.upsc_post, "qotd": self.qotd_post, "ssc": self.ssc_post, "explain": self.explain_post,
                "digest": self.digest_post}[fmt](lang)


def publish(ig, upsc, built, fmt, day, lang, folder, target=None):
    """Render, push to ig-media, wait for `target` (unix time), publish, record."""
    html, n, cap = built
    files = render_pages(html, n, lang, folder)
    (folder / "caption.txt").write_text(cap, encoding="utf-8")
    rel = f"ig/{day}/{fmt}-{lang}" if fmt != "upsc" else f"ig/{day}/{lang}"
    base = push_media({rel: files + [folder / "caption.txt"]}, "ig-media", f"instagram slides {day} {fmt} {lang}")
    urls = [f"{base}/{rel}/{f.name}" for f in files]
    wait_public(urls)
    if target and target > time.time():
        print(f"waiting {(target - time.time()) / 60:.1f} min", flush=True)
        time.sleep(target - time.time())
    media_id = ig.carousel(urls, cap)
    upsc.execute("INSERT OR REPLACE INTO ig_posts (key, media_id, posted_at) VALUES (?, ?, ?)",
                 [post_key(fmt, day, lang), media_id, int(time.time())])
    try:
        link = ig.get(media_id, fields="permalink").get("permalink")
    except Exception as ex:
        link = f"media {media_id} (permalink lookup failed: {ex})"
    print(f"posted {fmt} {lang} at {time.strftime('%H:%M:%S', time.gmtime(time.time() + 19800))} IST: {link}")
    print(f"::notice title=Instagram {fmt} {lang}::{link}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scheduled", action="store_true", help="post the slots due now (see SLOTS)")
    ap.add_argument("--at", default="", help="old cron-job.org call (--at 19:00): same as --scheduled")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--now", action="store_true")
    ap.add_argument("--check-setup", action="store_true")
    ap.add_argument("--format", default="digest", help="digest | upsc | explain | ssc | qotd | all (with --now / --dry-run)")
    ap.add_argument("--langs", default="en,hi")
    ap.add_argument("--day", default="", help="this IST day instead of today (YYYY-MM-DD)")
    args = ap.parse_args()
    upsc = upsc_db()

    if args.check_setup:
        ig = IG(current_token(upsc))
        print(f"Instagram account: @{ig.username} (id {ig.user_id}); token OK; API {os.environ.get('IG_API_VERSION', 'v23.0')}")
        for m in ig.get(f"{ig.user_id}/media", fields="timestamp,media_type,permalink", limit=3).get("data", []):
            print(f"  recent: {m.get('timestamp')} {m.get('media_type')} {m.get('permalink')}")
        return

    now = time.time()
    b = Builder(upsc, now, args.day or None)
    day = b.today["key"]
    langs = [l for l in args.langs.split(",") if l in ("en", "hi")]
    fmts = ["digest"] if args.format == "all" else [args.format]

    if args.dry_run:
        out = {}
        for fmt in fmts:
            for lang in langs:
                built, why = b.build(fmt, lang)
                if not built:
                    print(f"::warning::{fmt} {lang}: {why}")
                    continue
                folder = OUT / day / f"{fmt}-{lang}"
                files = render_pages(built[0], built[1], lang, folder)
                (folder / "caption.txt").write_text(built[2], encoding="utf-8")
                out[f"ig/{day}/{fmt}-{lang}"] = files + [folder / "caption.txt"]
                print(f"\n--- {fmt} {lang}: {len(files)} slides\n{built[2]}")
        if out:
            base = push_media(out, "previews", f"instagram preview {day}")
            print(f"\npreview: {base}/ig/{day}/")
        return

    if args.now:
        due = [(f, l, None) for f in fmts for l in langs]
    else:  # scheduled: slots from 35 min before to 2.5 h after their time, earliest first
        due = []
        for fmt, lang, hhmm in SLOTS:
            t = target_ts(now, hhmm)
            if t - EARLY <= now <= t + LATE and lang in langs:
                due.append((fmt, lang, t))
    due = [(f, l, t) for f, l, t in due if not posted(upsc, post_key(f, day, l))]
    if not due:
        print("nothing due")
        return
    ig = IG(current_token(upsc))   # fail early (bad token) before rendering
    print(f"posting as @{ig.username}: {', '.join(f'{f}/{l}' for f, l, _ in due)}")
    failed = 0
    for fmt, lang, t in due:
        try:
            built, why = b.build(fmt, lang)
            if not built:
                print(f"::warning::{fmt} {lang} skipped: {why}")
                continue
            publish(ig, upsc, built, fmt, day, lang, OUT / day / f"{fmt}-{lang}", t)
        except Exception as ex:  # one failed post must not stop the next
            failed += 1
            print(f"::warning::{fmt} {lang} failed: {type(ex).__name__}: {str(ex)[:300]}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    finally:
        close_all()
