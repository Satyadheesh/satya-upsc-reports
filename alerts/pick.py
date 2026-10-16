"""Top-news alerts, SHADOW MODE: every hour, find the news an ordinary person in India would want a notification
about, and send what it WOULD notify to the admin Telegram chat only (TELEGRAM_TEST_CHAT_ID). Nothing reaches users.

  1. cheap signals (alerts.signals): outlets covering the story, daily-life words, national scope, disasters,
     running timelines, UPSC importance; foreign-only and local crime count against
  2. the top few (score >= THRESHOLD) go to the AI editor (alerts.judge): notify? importance 1-10, why, the line
  3. picked = notify and importance >= 7, 07:00-22:00 IST, at most 3 a day, 90 min apart
Every judged story is stored in alert_candidates (UPSC DB) with its signals and decision, to tune this later.

  python -m alerts.pick              (hourly run)
  python -m alerts.pick --summary    (the day's picks and best rejects to the admin chat; the 22:00 IST run does it)
  python -m alerts.pick --dry-run [--no-ai]   (print only: no DB writes, no Telegram)"""
import argparse
import html
import json
import os
import time

from common.db import close_all, in_chunks, main_db, translation_db, upsc_db

from . import signals as S

THRESHOLD = 6
MAX_JUDGE = 4
REJUDGE_GAIN = 4          # a rejected story is judged again once its score has grown this much
MIN_IMPORTANCE = 7
DAILY_CAP = 3
GAP = 90 * 60
QUIET_FROM, QUIET_TO = 22, 7   # IST hours without notifications
SUMMARY_HOUR = 22              # IST: the hourly run in this hour also sends the day's summary
SITE = "https://satyadheesh.in"


def ist_hour(ts):
    return time.gmtime(ts + 19800).tm_hour


def ist_day_start(ts):
    return (int(ts) + 19800) // 86400 * 86400 - 19800


def e(s):
    return html.escape(str(s or ""), quote=False)


def hindi_line(trans, ids):
    if trans is None or not ids:
        return ""
    rows = in_chunks(trans, "SELECT article_id, rephrased_title_hi FROM translations WHERE article_id IN ({ph})", ids)
    by = {r[0]: r[1] for r in rows if r[1]}
    return next((" ".join(by[i].split()) for i in ids if i in by), "")


def admin_text(c, n_today):
    sig = c["signals"]
    when = time.strftime("%H:%M", time.gmtime(time.time() + 19800))
    return (f"<b>Would notify</b> ({n_today}/{DAILY_CAP} today, {when} IST) · importance {c['importance']}/10\n\n"
            f"<b>EN:</b> {e(c['line_en'])}\n<b>HI:</b> {e(c['line_hi']) or '<i>(Hindi headline not ready yet)</i>'}\n\n"
            f"<i>Editor:</i> {e(c['why'])}\n<i>Signals:</i> {e('; '.join(sig['why']) or '-')} · {e(sig['category'])}"
            f" · score {c['score']:.0f}\n<i>Outlets:</i> {e(', '.join(sig['sources']))}\n"
            f"<a href=\"{SITE}/news/{sig['lead_id']}\">On SatyaDheesh</a>")


def summary_text(rows, day_start):
    picked = [r for r in rows if r["decision"] == "picked"]
    blocked = [r for r in rows if (r["decision"] or "").startswith("blocked")]
    rejected = sorted([r for r in rows if r["decision"] == "rejected"], key=lambda r: -(r["importance"] or 0))[:5]
    d = time.strftime("%d %b", time.gmtime(day_start + 19800 + 3600))
    out = [f"<b>Top-news alerts, shadow mode — {d}</b>", f"Judged {sum(1 for r in rows if r['judged_at'])} stories; "
           f"{len(picked)} would have been sent.", ""]
    if picked:
        out.append("<b>Would have sent:</b>")
        out += [f"• {time.strftime('%H:%M', time.gmtime(r['decided_at'] + 19800))} — {e(r['line_en'])} ({r['importance']}/10)" for r in picked]
    if blocked:
        out += ["", "<b>Good but held back (limit, gap or night):</b>"]
        out += [f"• {e(r['line_en'])} ({r['importance']}/10, {r['decision'].split(':')[1]})" for r in blocked[:5]]
    if rejected:
        out += ["", "<b>Best of the rejected:</b>"]
        out += [f"• {e(r['line_en'])} ({r['importance']}/10) — {e(r['why'])}" for r in rejected]
    return "\n".join(out)[:4000]


def rows_since(upsc, since):
    cols = ["story_key", "article_id", "score", "signals", "judged_at", "notify", "importance", "why", "line_en", "line_hi",
            "decision", "decided_at"]
    rs = upsc.execute(f"SELECT {', '.join(cols)} FROM alert_candidates WHERE decided_at >= ? ORDER BY decided_at", [since]).rows
    return [dict(zip(cols, r)) for r in rs]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-ai", action="store_true", help="skip the AI editor (signals only)")
    ap.add_argument("--summary", action="store_true", help="only send the day's summary")
    ap.add_argument("--threshold", type=float, default=THRESHOLD, help="testing: a lower bar to exercise the AI editor")
    args = ap.parse_args()
    dry = args.dry_run
    now = time.time()
    upsc, main_, trans = upsc_db(), main_db(), translation_db()
    chat = os.environ.get("TELEGRAM_TEST_CHAT_ID")
    bot = None
    if not dry and chat:
        from tg.telegram import Bot
        bot = Bot()

    def send_summary():
        rows = rows_since(upsc, ist_day_start(now))
        text = summary_text(rows, ist_day_start(now))
        print("\n" + text)
        if bot:
            bot.message(chat, text)

    if args.summary:
        send_summary()
        return

    arts = S.load(main_, upsc, now)
    groups = S.stories(arts)
    fresh = [g for g in groups if g[0]["at"] >= now - S.FRESH]
    ids = [a["id"] for g in fresh for a in g]
    tl, us = S.timeline_depth(main_, ids), S.upsc_scores(upsc, ids)
    scored = sorted(((S.score(g, now, tl, us), g) for g in fresh), key=lambda x: -x[0][0])
    known = {r[0]: dict(judged_at=r[1], decision=r[2], score=r[3]) for r in upsc.execute(
        "SELECT story_key, judged_at, decision, score FROM alert_candidates WHERE first_seen >= ?", [now - 3 * 86400]).rows}
    print(f"{len(arts)} articles in {S.WINDOW // 3600} h -> {len(groups)} stories; {len(fresh)} new in the last "
          f"{S.FRESH // 3600} h")
    for (sc, sig), g in scored[:12]:
        print(f"  {sc:5.1f}  {sig['titles'][0][:100]}  [{'; '.join(sig['why'])}]")

    todo = []
    for (sc, sig), g in scored:
        if sc < args.threshold or len(todo) >= MAX_JUDGE:
            break
        k = known.get(S.story_key(g))
        if k and k["judged_at"] and not (k["decision"] == "rejected" and sc >= (k["score"] or 0) + REJUDGE_GAIN):
            continue
        todo.append((sc, sig, g))

    editor = None
    if todo and not args.no_ai:
        try:
            from .judge import Editor
            editor = Editor()
        except Exception as ex:
            print(f"::warning::AI editor unavailable ({type(ex).__name__}: {str(ex)[:150]}); signals only")
    day0 = ist_day_start(now)
    picks_today = [r for r in rows_since(upsc, day0) if r["decision"] == "picked"]
    last_pick = max((r["decided_at"] for r in picks_today), default=0)
    for sc, sig, g in todo:
        lead = sig["lead_id"]
        blob = main_.execute("SELECT rephrased_article FROM articles WHERE id = ?", [lead]).rows
        summary = S.text_of(blob[0][0]) if blob else ""
        if editor:
            v = editor.judge(sig, summary)
        else:  # no AI: a conservative rule
            v = dict(notify=sc >= 10, importance=min(10, int(sc)), why="signals only (no AI editor)", line=sig["titles"][0])
        c = dict(score=sc, signals=sig, importance=v["importance"], why=v["why"], line_en=v["line"] or sig["titles"][0],
                 line_hi=hindi_line(trans, [a["id"] for a in g]))
        h = ist_hour(now)
        if not v["notify"] or v["importance"] < MIN_IMPORTANCE:
            decision = "rejected"
        elif h >= QUIET_FROM or h < QUIET_TO:
            decision = "blocked:night"
        elif len(picks_today) >= DAILY_CAP:
            decision = "blocked:limit"
        elif now - last_pick < GAP:
            decision = "blocked:gap"
        else:
            decision = "picked"
        print(f"\n[{decision}] {c['line_en']}\n  importance {v['importance']}, notify {v['notify']}: {v['why']}\n  HI: {c['line_hi']}")
        msg_id = None
        if decision == "picked":
            picks_today.append({"decided_at": now})
            last_pick = now
            if bot:
                try:
                    msg_id = bot.message(chat, admin_text(c, len(picks_today)))["message_id"]
                except Exception as ex:
                    print(f"::warning::admin message failed: {type(ex).__name__}")
            print(f"::notice title=Would notify::{c['line_en']}")
        if not dry:
            upsc.execute(
                "INSERT OR REPLACE INTO alert_candidates (story_key, article_id, first_seen, score, signals, judged_at, notify, "
                "importance, why, line_en, line_hi, decision, decided_at, admin_msg) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [S.story_key(g), lead, int(sig["first_seen"]), sc, S.dumps(sig), int(now), int(v["notify"]), v["importance"],
                 v["why"], c["line_en"], c["line_hi"], decision, int(now), msg_id])
    if not todo:
        print("nothing above the threshold this hour")
    if ist_hour(now) == SUMMARY_HOUR and not dry:
        sent = upsc.execute("SELECT 1 FROM telegram_posts WHERE key = ?", [f"alerts-summary:{day0}"]).rows
        if not sent:
            send_summary()
            upsc.execute("INSERT OR REPLACE INTO telegram_posts (key, chat, message_id, posted_at) VALUES (?, ?, ?, ?)",
                         [f"alerts-summary:{day0}", str(chat), 0, int(now)])


if __name__ == "__main__":
    try:
        main()
    finally:
        close_all()
