"""Post the daily / weekly UPSC report to the Telegram channel at an exact IST time.

  python -m tg.post --kind daily  --at 05:00     (yesterday's report)
  python -m tg.post --kind weekly --at 07:00     (this week's report, Sunday morning)

cron-job.org starts the workflow ~20 min early (GitHub crons are the backup). This script first asks the
report builder to rebuild this period (so the PDFs carry the latest notes and Hindi corrections), waits for
the exact minute and posts: English Brief + Detailed, Hindi Brief + Detailed, then the quiz. If the Hindi
PDFs aren't ready (stored once >= 80% of the notes are translated) it posts the rest, keeps asking for a
rebuild and posts Hindi as soon as it exists; later catch-up runs try again, and the admin chat is told if
Hindi still hasn't gone out. Each part is recorded in telegram_posts, so a rerun only posts what is missing.
--dry-run prints everything and sends nothing.
"""
import argparse
import os
import sys
import time

import requests

from common.db import close_all, main_db, translation_db, upsc_db

from reports.data import Window, editions, select
from reports.render import SIZE, pick_cards

from .content import caption, quiz_polls, read_editions
from .periods import file_key, file_name, label, period_for, target_ts
from .telegram import Bot

READY_WAIT = 60 * 60      # keep checking for a missing English report until target + 60 min
HI_WAIT = 100 * 60        # keep checking for a missing Hindi report until target + 100 min (job limit 150)
REBUILD_EVERY = 30 * 60   # while waiting, ask the builder to rebuild this period this often
LATE_LIMIT = 6 * 3600     # never post a "morning" report more than 6 h late


def posted(upsc, key):
    return bool(upsc.execute("SELECT 1 FROM telegram_posts WHERE key = ?", [key]).rows)


def mark(upsc, key, chat, message_id):
    upsc.execute("INSERT OR REPLACE INTO telegram_posts (key, chat, message_id, posted_at) VALUES (?, ?, ?, ?)",
                 [key, str(chat), message_id, int(time.time())])


def request_build(p):
    """Ask reports.yml to rebuild just this period (only changed PDFs are re-printed). Needs the workflow's
    GITHUB_TOKEN with actions: write; silently skipped elsewhere."""
    tok, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    if not tok or not repo:
        return
    try:
        r = requests.post(f"https://api.github.com/repos/{repo}/actions/workflows/reports.yml/dispatches",
                          headers={"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"},
                          json={"ref": "main", "inputs": {"period": f"{p['kind']}:{p['key']}"}}, timeout=30)
        print(f"asked for a rebuild of {p['kind']}:{p['key']} (HTTP {r.status_code})", flush=True)
    except requests.RequestException as e:
        print(f"::warning::rebuild request failed: {type(e).__name__}")


def docs_for(p, lang, pdfs):
    return [(pdf, file_name(p, lang, ed)) for pdf, ed in pdfs]


def sleep_until(ts, why):
    left = ts - time.time()
    if left > 0:
        print(f"waiting {left / 60:.1f} min {why}", flush=True)
        time.sleep(left)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=["daily", "weekly"], required=True)
    ap.add_argument("--at", default="05:00", help="IST time to post, HH:MM")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--now", action="store_true", help="don't wait for the posting time")
    ap.add_argument("--test", action="store_true", help="post to TELEGRAM_TEST_CHAT_ID instead of the channel")
    args = ap.parse_args()

    chat = os.environ.get("TELEGRAM_TEST_CHAT_ID" if args.test else "TELEGRAM_CHAT_ID")
    if not chat and not args.dry_run:
        raise SystemExit(f"Missing secret {'TELEGRAM_TEST_CHAT_ID' if args.test else 'TELEGRAM_CHAT_ID'}")
    start = time.time()
    p = period_for(args.kind, start)
    target = start if args.now or args.dry_run else target_ts(start, args.at)
    tag = "test:" if args.test else ""
    print(f"{args.kind} report {p['key']} ({label(p)}), posting at {time.strftime('%H:%M:%S', time.gmtime(target + 19800))} IST"
          + (" [dry run]" if args.dry_run else ""))
    if args.kind == "weekly" and not (args.now or args.dry_run) and time.gmtime(target + 19800).tm_wday != 6:
        print("::warning::the weekly report is posted on Sunday only (week not finished); nothing posted")
        return
    if time.time() > target + LATE_LIMIT and not args.now:
        print(f"::warning::more than {LATE_LIMIT // 3600} h past {args.at} IST; not posting a stale morning report")
        return

    upsc, main, trans = upsc_db(), main_db(), translation_db()
    keys = {lang: tag + file_key(p, lang) for lang in ("en", "hi")}
    keys["quiz"] = tag + f"{p['kind']}:{p['key']}:quiz"
    if not args.dry_run and all(posted(upsc, k) for k in keys.values()):
        print("already posted, nothing to do")
        return

    live = not (args.dry_run or args.test or args.now)
    asked = 0
    if live and target - time.time() > 8 * 60:
        request_build(p)  # fresh PDFs (latest notes + Hindi corrections) before the posting time
        asked = time.time()

    # The English report must exist; wait for it (the nightly rebuild runs at 02:50 IST).
    en_pdfs, en_meta = read_editions(upsc, file_key(p, "en"))
    while not en_pdfs and time.time() < target + READY_WAIT and not args.dry_run:
        print("English report not stored yet; checking again in 5 min", flush=True)
        time.sleep(300)
        en_pdfs, en_meta = read_editions(upsc, file_key(p, "en"))
    if not en_pdfs:
        print(f"::error::no stored English PDF for {file_key(p, 'en')} — nothing posted")
        sys.exit(1)
    hi_pdfs, hi_meta = read_editions(upsc, file_key(p, "hi"))

    # Top stories = the report's own top stories (same selection as the PDF)
    w = Window(upsc, main, p["start"], p["end"], trans)
    en_items = w.period(p, "en")
    n_top, n_cards = SIZE[p["kind"]][:2]
    top = lambda items: pick_cards(items, n_cards, p["kind"])[:n_top]  # the PDF's own 'top stories'
    en_ed, hi_ed, _, _ = editions(p, en_items, w.period(p, "hi") if hi_pdfs else None)
    heads_en = [(((it.get("kit") or {}).get("short_title") or it["title"]), it["paper"]) for it in top(en_ed)]
    cap_en = caption(p, en_meta["items"], heads_en, hi=False, both=len(en_pdfs) > 1)

    def hindi_caption(w):
        chosen_hi = top(editions(p, w.period(p, "en"), w.period(p, "hi"))[1] or [])
        return caption(p, hi_meta["items"], [(((it.get("kit_hi") or {}).get("short_title") or it["title"]), it["paper"])
                                             for it in chosen_hi], hi=True, both=len(hi_pdfs) > 1)
    cap_hi = hindi_caption(w) if hi_pdfs else None
    polls = quiz_polls(upsc, p)
    quiz_intro = ("<b>Quick quiz</b> — " + ("5 questions from yesterday's news." if p["kind"] == "daily"
                                              else "questions from this week's news.") + " Answers show after you vote.")

    if args.dry_run:
        for lang, pdfs, cap in (("en", en_pdfs, cap_en), ("hi", hi_pdfs, cap_hi)):
            if not pdfs:
                print(f"\n--- {lang}: not ready (under 80% translated)")
                continue
            print(f"\n--- {lang}: " + ", ".join(f"{name} ({len(pdf) // 1024} KB)" for pdf, name in docs_for(p, lang, pdfs)))
            print(cap)
        print(f"\n--- {len(polls)} quiz polls")
        for q in polls:
            print(f"\nQ: {q['question']}\n" + "\n".join(f"  {'*' if i == q['correct'] else ' '} {o}" for i, o in enumerate(q["options"]))
                  + f"\n  ({q['explanation']})")
        return

    sleep_until(target, f"for {args.at} IST")
    if asked:  # the rebuild asked for above has finished by now: post the newest PDFs
        en_pdfs = read_editions(upsc, file_key(p, "en"))[0] or en_pdfs
        hi_new, hi_meta_new = read_editions(upsc, file_key(p, "hi"))
        if hi_new:
            if not hi_pdfs:
                hi_meta = hi_meta_new
                hi_pdfs = hi_new
                cap_hi = hindi_caption(w)
            hi_pdfs = hi_new
    bot = Bot()
    now_ist = lambda: time.strftime('%H:%M:%S', time.gmtime(time.time() + 19800))

    def post_lang(lang, pdfs, cap):
        if pdfs and not posted(upsc, keys[lang]):
            m = bot.documents(chat, docs_for(p, lang, pdfs), cap)
            mark(upsc, keys[lang], chat, m["message_id"])
            print(f"posted {lang} PDFs ({', '.join(ed for _, ed in pdfs)}) at {now_ist()} IST", flush=True)

    def post_quiz():
        if polls and not posted(upsc, keys["quiz"]):
            first = bot.message(chat, quiz_intro)
            for q in polls:
                bot.quiz(chat, q["question"], q["options"], q["correct"], q["explanation"])
                time.sleep(1)
            mark(upsc, keys["quiz"], chat, first["message_id"])
            print(f"posted {len(polls)} quiz polls")
        elif not polls:
            print("no quiz yet (study kit not live for this period)")

    post_lang("en", en_pdfs, cap_en)
    post_lang("hi", hi_pdfs, cap_hi)
    post_quiz()
    if posted(upsc, keys["hi"]) or not live:
        return

    # Hindi not ready: keep rebuilding and checking; post it the moment it exists.
    print(f"::warning::Hindi PDFs for {p['key']} not ready at {now_ist()} IST; waiting for them", flush=True)
    while time.time() < max(target, start) + HI_WAIT:
        if time.time() - asked >= REBUILD_EVERY:
            request_build(p)
            asked = time.time()
        time.sleep(300)
        hi_pdfs, hi_meta = read_editions(upsc, file_key(p, "hi"))
        if hi_pdfs:
            post_lang("hi", hi_pdfs, hindi_caption(Window(upsc, main, p["start"], p["end"], trans)))
            return
    share = select(p, en_items, Window(upsc, main, p["start"], p["end"], trans).period(p, "hi"))[2]
    msg = (f"Hindi {p['kind']} report {p['key']} not posted yet: {share:.0%} of its notes are translated "
           f"(needs 80%). Later runs keep trying until {time.strftime('%H:%M', time.gmtime(target + LATE_LIMIT + 19800))} IST.")
    print(f"::error::{msg}")
    admin = os.environ.get("TELEGRAM_TEST_CHAT_ID")
    if admin and not args.test and admin != str(chat):
        try:
            bot.message(admin, msg)
        except Exception as e:
            print(f"admin alert failed: {type(e).__name__}")


if __name__ == "__main__":
    try:
        main()
    finally:
        close_all()
