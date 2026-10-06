"""Re-apply the current code checks (gate.rules + gate.card_ok) to stored SSC cards, without a model call.

  python -m sscca.recheck --days 8 [--apply] --md recheck.md
Cards that now fail become status 'skip' with reason 'recheck: ...' (only with --apply). Skips are never revived.
"""
import argparse
import time

from common.db import close_all, upsc_db

from .gate import TOPICS, card_ok, rules
from .articles import load


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=8)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--md", default="recheck.md")
    a = ap.parse_args()
    up = upsc_db()
    now = int(time.time())
    rows = up.execute("SELECT article_id, topic, importance, scope, fact, title, question, answer FROM ssc_ca "
                      "WHERE status = 'card' AND published_at >= ? ORDER BY published_at DESC", [now - a.days * 86400]).rows
    arts = load([int(r[0]) for r in rows]) if rows else {}
    drop, keep = [], []
    for aid, topic, imp, scope, fact, title, q, ans in rows:
        art = arts.get(int(aid)) or {"title": title or "", "body": ""}
        text = art["body"][:2500]
        why = (rules(topic, int(imp or 0), scope or "", fact or "", title or "", text) if topic in TOPICS else "no topic") \
            or card_ok({"ssc_question": q, "ssc_answer": ans}, fact or "", title or "", text)
        (drop if why else keep).append((aid, topic, imp, title, q, ans, why))
    if a.apply and drop:
        for aid, *_, why in drop:
            up.execute("UPDATE ssc_ca SET status = 'skip', reason = ?, updated_at = ? WHERE article_id = ?",
                       [f"recheck: {why}"[:1000], now, aid])
    L = [f"## SSC cards recheck ({'applied' if a.apply else 'dry run'}), last {a.days} days", "",
         f"{len(rows)} cards: **{len(keep)} kept, {len(drop)} dropped**", "", "### Dropped"]
    L += [f"- [{TOPICS.get(t, ('', t))[1]} · {i}] {str(ti)[:100]} — **{w}** ({aid})\n  - Q: {q} | A: {an}"
          for aid, t, i, ti, q, an, w in drop] or ["- none"]
    L += ["", "### Kept"]
    L += [f"- [{TOPICS.get(t, ('', t))[1]} · {i}] {str(ti)[:100]} ({aid})\n  - Q: {q} | A: {an}"
          for aid, t, i, ti, q, an, w in keep] or ["- none"]
    open(a.md, "w").write("\n".join(L) + "\n")
    print("\n".join(L[:4]))


if __name__ == "__main__":
    try:
        main()
    finally:
        close_all()
