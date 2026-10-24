"""Post the newspaper-style PDFs of the last 24 hours to the three newspaper channels, at the same morning time as the
main channel's daily report (Yash, 24 Oct 2026).

  python -m paper.post --mode scheduled --at 05:00   build now, wait for 05:00 IST, post
  python -m paper.post --mode test                   build and post everything to TELEGRAM_TEST_CHAT_ID now
  python -m paper.post --mode now                    build and post to the channels now
  python -m paper.post --mode dry-run                build, post nothing

Channels: The Hindu English -> @thehindu_in_english, The Hindu Hindi -> @thehindu_in_hindi, every paper in English
and in Hindi (two albums) -> @newspapers_for_upsc_pdf. Each post is recorded in telegram_posts, so a rerun (the
backup crons) posts only what is missing; a morning post is never sent more than LATE_LIMIT late.
"""
import argparse
import datetime as dt
import os
import time

from common.db import close_all, upsc_db
from tg.post import mark, posted
from tg.telegram import Bot

from .build import IST, build_all
from .render import MONTHS_HI

# Numeric ids (a private channel has no @handle). Yash, 24 Oct 2026: these channels are private, for his own reading.
HINDU_EN, HINDU_HI, ALL = "-1004343898066", "-1004391165331", "-1004413160494"
NAMES = {HINDU_EN: "TheHindu in English", HINDU_HI: "TheHindu in Hindi", ALL: "Newspapers for UPSC"}


def is_private(bot, chat):
    """The PDFs carry the papers' original reports and photos: personal use only. Never post to a public channel."""
    try:
        info = bot.call("getChat", {"chat_id": chat})
    except Exception as e:
        print(f"::error::getChat {NAMES.get(chat, chat)} failed: {str(e)[:120]}")
        return False
    if info.get("username"):
        print(f"::error::{NAMES.get(chat, chat)} is PUBLIC (@{info['username']}): not posting. Make it private first.")
        return False
    return True
LATE_LIMIT = 4 * 3600
ALBUM_MAX = 10


def day_label(d, hi):
    return f"{d.day} {MONTHS_HI[d.month - 1]} {d.year}" if hi else d.strftime("%-d %b %Y")


def cap_one(name, d, hi):
    return f"<b>{name}</b> · {day_label(d, hi)}"


def cap_all(names, d, hi):
    return f"<b>{'आज के अख़बार' if hi else 'Today’s newspapers'}</b> · {day_label(d, hi)}\n{', '.join(names)}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="dry-run", choices=["dry-run", "test", "now", "scheduled", "check"])
    ap.add_argument("--at", default="05:00")
    a = ap.parse_args()
    if a.mode == "check":   # can the bot post in each channel? (nothing is sent)
        bot = Bot()
        me = bot.call("getMe")
        for ch in (HINDU_EN, HINDU_HI, ALL):  # by id
            try:
                chat = bot.call("getChat", {"chat_id": ch})
                mem = bot.call("getChatMember", {"chat_id": ch, "user_id": me["id"]})
                ok = mem.get("status") == "administrator" and mem.get("can_post_messages", True)
                print(f"{ch}: '{chat.get('title')}' id={chat.get('id')} public={'@' + chat['username'] if chat.get('username') else 'no (private)'} "
                      f"bot={mem.get('status')} can_post={mem.get('can_post_messages')} -> {'OK' if ok else 'NOT OK'}")
            except Exception as e:
                print(f"{ch}: NOT OK ({str(e)[:160]})")
        return
    now = dt.datetime.now(IST)
    day = now.date()
    h, m = (int(x) for x in a.at.split(":"))
    target = dt.datetime(day.year, day.month, day.day, h, m, tzinfo=IST).timestamp()
    if a.mode == "scheduled" and time.time() > target + LATE_LIMIT:
        print(f"::warning::too late for this morning's newspapers ({now:%H:%M} IST); nothing posted")
        return

    upsc = upsc_db()
    test_chat = os.environ.get("TELEGRAM_TEST_CHAT_ID")
    jobs = []   # (key, chat, [(pdf, name)], caption)
    def add(chat, tag, docs, cap):
        if not docs:
            return
        real = test_chat if a.mode == "test" else chat
        key = f"paper:{day.isoformat()}:{chat}:{tag}" + (":test" if a.mode == "test" else "")
        if a.mode in ("now", "scheduled") and posted(upsc, key):
            print(f"already posted: {key}")
            return
        jobs.append((key, real, docs, cap))

    if a.mode in ("now", "scheduled"):
        keys = [f"paper:{day.isoformat()}:{c}:{t}" for c, t in
                ((HINDU_EN, "thehindu:en"), (HINDU_HI, "thehindu:hi"), (ALL, "all:en"), (ALL, "all:hi"))]
        if all(posted(upsc, k) for k in keys):
            print("all of today's newspaper posts are already out")
            return

    res = build_all(day=day)
    for lang in ("en", "hi"):
        hi = lang == "hi"
        h_ = res.get(("thehindu", lang))
        if h_:
            add(HINDU_HI if hi else HINDU_EN, f"thehindu:{lang}", [(h_[0], h_[1])], cap_one(h_[3] if hi else h_[2], day, hi))
        mine = [(k, v) for k, v in res.items() if k[1] == lang][:ALBUM_MAX]
        add(ALL, f"all:{lang}", [(v[0], v[1]) for _, v in mine], cap_all([v[3] if hi else v[2] for _, v in mine], day, hi))

    for key, chat, docs, cap in jobs:
        print(f"{key}: {len(docs)} PDF(s) -> {'TEST CHAT' if a.mode == 'test' else chat}\n  {cap!r}")
    if a.mode == "dry-run" or not jobs:
        return
    if a.mode == "scheduled":
        wait = target - time.time()
        if wait > 0:
            print(f"waiting {wait / 60:.0f} min for {a.at} IST", flush=True)
            time.sleep(wait)
    bot = Bot()
    failed = 0
    private = {c: is_private(bot, c) for c in {j[1] for j in jobs}} if a.mode != "test" else {}
    for key, chat, docs, cap in jobs:
        if a.mode != "test" and not private.get(chat):
            failed += 1
            continue
        try:
            msg = bot.documents(chat, docs, cap)
            if a.mode != "test":
                mark(upsc, key, chat, msg.get("message_id"))
            print(f"posted {key}")
        except Exception as e:
            failed += 1
            print(f"::error::{key} failed: {type(e).__name__}: {str(e)[:200]}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    finally:
        close_all()
