"""Post the daily / weekly UPSC report to the Telegram channel at an exact IST time.

  python -m tg.post --kind daily  --at 05:00     (yesterday's report)
  python -m tg.post --kind weekly --at 07:00     (this week's report, Sunday morning)

GitHub starts scheduled jobs late, so the workflow starts ~40 min early and this script waits for the
report and then for the exact minute. Each part (English PDF, Hindi PDF, quiz) is recorded in
telegram_posts, so a backup run or a rerun only posts what is missing.
--dry-run prints everything and sends nothing.
"""
import argparse
import os
import sys
import time

from common.db import close_all, main_db, translation_db, upsc_db

from .content import caption, headlines, quiz_polls, read_pdf, top_notes
from .periods import file_key, file_name, label, period_for, target_ts
from .telegram import Bot

READY_WAIT = 60 * 60      # keep checking for a missing English report until target + 60 min
LATE_LIMIT = 6 * 3600     # never post a "morning" report more than 6 h late


def posted(upsc, key):
    return bool(upsc.execute("SELECT 1 FROM telegram_posts WHERE key = ?", [key]).rows)


def mark(upsc, key, chat, message_id):
    upsc.execute("INSERT OR REPLACE INTO telegram_posts (key, chat, message_id, posted_at) VALUES (?, ?, ?, ?)",
                 [key, str(chat), message_id, int(time.time())])


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
    if time.time() > target + LATE_LIMIT and not args.now:
        print(f"::warning::more than {LATE_LIMIT // 3600} h past {args.at} IST; not posting a stale morning report")
        return

    upsc, main, trans = upsc_db(), main_db(), translation_db()
    keys = {lang: tag + file_key(p, lang) for lang in ("en", "hi")}
    keys["quiz"] = tag + f"{p['kind']}:{p['key']}:quiz"
    if not args.dry_run and all(posted(upsc, k) for k in keys.values()):
        print("already posted, nothing to do")
        return

    # The English report must exist; wait for it (the nightly rebuild runs at 02:41 IST).
    en_pdf, en_meta = read_pdf(upsc, file_key(p, "en"))
    while en_pdf is None and time.time() < target + READY_WAIT and not args.dry_run:
        print("English report not stored yet; checking again in 5 min", flush=True)
        time.sleep(300)
        en_pdf, en_meta = read_pdf(upsc, file_key(p, "en"))
    if en_pdf is None:
        print(f"::error::no stored English PDF for {file_key(p, 'en')} — nothing posted")
        sys.exit(1)
    hi_pdf, hi_meta = read_pdf(upsc, file_key(p, "hi"))
    if hi_pdf is None:
        print(f"::warning::Hindi PDF for {p['key']} not ready (under 80% translated); posting English only")

    notes = top_notes(upsc, p)
    cap_en = caption(p, en_meta["items"], headlines(main, trans, notes), hi=False)
    cap_hi = caption(p, hi_meta["items"], headlines(main, trans, notes, hi=True), hi=True) if hi_pdf else None
    polls = quiz_polls(upsc, p)
    quiz_intro = ("<b>Quick quiz</b> — " + ("5 questions from yesterday's news." if p["kind"] == "daily"
                                              else "questions from this week's news.") + " Answers show after you vote.")

    if args.dry_run:
        print(f"\n--- English PDF ({len(en_pdf) // 1024} KB, {file_name(p, 'en')})\n{cap_en}")
        if cap_hi:
            print(f"\n--- Hindi PDF ({len(hi_pdf) // 1024} KB, {file_name(p, 'hi')})\n{cap_hi}")
        print(f"\n--- {len(polls)} quiz polls")
        for q in polls:
            print(f"\nQ: {q['question']}\n" + "\n".join(f"  {'*' if i == q['correct'] else ' '} {o}" for i, o in enumerate(q["options"]))
                  + f"\n  ({q['explanation']})")
        return

    sleep_until(target, f"for {args.at} IST")
    bot = Bot()
    if not posted(upsc, keys["en"]):
        m = bot.document(chat, en_pdf, file_name(p, "en"), cap_en)
        mark(upsc, keys["en"], chat, m["message_id"])
        print(f"posted English PDF at {time.strftime('%H:%M:%S', time.gmtime(time.time() + 19800))} IST")
    if hi_pdf and not posted(upsc, keys["hi"]):
        m = bot.document(chat, hi_pdf, file_name(p, "hi"), cap_hi)
        mark(upsc, keys["hi"], chat, m["message_id"])
        print("posted Hindi PDF")
    if polls and not posted(upsc, keys["quiz"]):
        first = bot.message(chat, quiz_intro)
        for q in polls:
            bot.quiz(chat, q["question"], q["options"], q["correct"], q["explanation"])
            time.sleep(1)
        mark(upsc, keys["quiz"], chat, first["message_id"])
        print(f"posted {len(polls)} quiz polls")
    elif not polls:
        print("no quiz yet (study kit not live for this period)")


if __name__ == "__main__":
    try:
        main()
    finally:
        close_all()
