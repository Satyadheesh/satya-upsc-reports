"""Preview report for the SSC runner: what it would keep (with the card) and what it skipped, for a human to judge.

  python -m sscca.review out/*.json --md review.md
"""
import argparse
import json
from collections import Counter

from .gate import TOPICS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--md", required=True)
    a = ap.parse_args()
    rows = [r for f in a.files for r in json.load(open(f))]
    cards = [r for r in rows if r.get("card")]
    kept_no_card = [r for r in rows if r.get("keep") and not r.get("card")]
    stopped = [r for r in rows if not r.get("keep") and r.get("why") not in ("model: no",) and not str(r.get("why")).startswith("importance")]
    L = [f"## SSC current affairs runner — preview on {len(rows)} articles", "",
         "| | count |", "|---|---|",
         f"| articles judged | {len(rows)} |",
         f"| SSC cards | {len(cards)} |",
         f"| kept by the gate but no valid card | {len(kept_no_card)} |",
         f"| model said yes, a code check stopped it | {len(stopped)} |",
         f"| model said no / low importance | {len(rows) - len(cards) - len(kept_no_card) - len(stopped)} |", "",
         "**Cards by topic:** " + ", ".join(f"{TOPICS[k][1]} {v}" for k, v in Counter(r['topic'] for r in cards).most_common()), "",
         "### Cards (tick if an SSC paper could ask it)"]
    for r in sorted(cards, key=lambda r: (-r["importance"], r["topic"])):
        c = r["card"]
        L += [f"- [ ] **{TOPICS[r['topic']][1]} · {r['importance']}** · {r['title'][:110]} ({r['id']})",
              f"  - Q: {c['ssc_question']}", f"  - A: **{c['ssc_answer']}**",
              f"  - Key: {c.get('key_fact')}" + (f" · GK: {c['static_gk']}" if c.get("static_gk") else "")]
    L += ["", "### Kept, but no card passed the checks"]
    L += [f"- {r['title'][:110]} — {str(r.get('card_error'))[:200]}" for r in kept_no_card] or ["- none"]
    L += ["", "### Stopped by a code check"]
    L += [f"- {r['title'][:110]} — **{r['why']}** ({r['topic']}) — _{r['fact'][:150]}_" for r in stopped] or ["- none"]
    L += ["", "### Said no (sample of 60)"]
    no = [r for r in rows if r.get("why") == "model: no" or str(r.get("why")).startswith("importance")]
    L += [f"- {r['title'][:120]} ({r['why']})" for r in no[:60]] or ["- none"]
    open(a.md, "w").write("\n".join(L) + "\n")
    print("\n".join(L[:12]))


if __name__ == "__main__":
    main()
