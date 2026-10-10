"""One SSC card per story, across outlets and days.

Two cards are the same story when they share a news cluster, or (within 7 days) their words overlap strongly:
title + gate fact + question + answer, overlap coefficient >= 0.6 (0.7 across topics), or >= 0.4 with the same
answer (thresholds per topic below). Several outlets file the same Nobel or RBI story with different clusters, and the runner writes a card
for each; without this the daily PDF repeats yesterday's cards and the weekly shows the RBI hike three times.
"""
import re

DAY = 86400
WINDOW = 7 * DAY
STOP = set("""the a an of and in on at for to by with from as is was are were be been its his her their this that which
who what when where how did does do has have had will would into after over under new first india indian says said
year years day days than more most also amid about against while during before since between through per cent percent
crore lakh rs announced announce announces government union minister ministry january february march april may june
july august september october november december monday tuesday wednesday thursday friday saturday sunday current
name named""".split())


def _stem(w):
    for suf in ("ies", "es", "s", "ing", "ed"):
        if len(w) > 5 and w.endswith(suf):
            return w[:-len(suf)]
    return w


def words(s):
    s = (s or "").lower().replace("’", "'").replace("‘", "'")
    s = re.sub(r"(\d),(?=\d)", r"\1", s)  # 1,86,405 -> 186405
    out = set()
    for w in re.findall(r"[a-z0-9]+(?:\.\d+)?", s):
        if "." in w:
            w = w.rstrip("0").rstrip(".")  # 5.50 -> 5.5
        if (len(w) >= 3 or w[:1].isdigit()) and w not in STOP and not re.fullmatch(r"20\d\d", w):
            out.add(_stem(w))
    return out


def _numbers(ws):
    """Story numbers: 5.5, 25, 734.6 (not single digits, not years)."""
    return {w for w in ws if re.fullmatch(r"\d+(?:\.\d+)?", w) and (len(w) >= 2)}


def sig(card):
    """card: dict with title, fact, question, answer, topic, published_at, cluster_id."""
    return {"all": words(" ".join(str(card.get(k) or "") for k in ("title", "fact", "question", "answer"))),
            "ans": words(card.get("answer"))}


def _ov(a, b):
    return len(a & b) / min(len(a), len(b)) if a and b else 0.0


def same_story(a, b, sa=None, sb=None):
    if a.get("cluster_id") and a.get("cluster_id") == b.get("cluster_id"):
        return True
    if abs(int(a.get("published_at") or 0) - int(b.get("published_at") or 0)) > WINDOW:
        return False
    sa, sb = sa or sig(a), sb or sig(b)
    ov = _ov(sa["all"], sb["all"])
    if a.get("topic") != b.get("topic"):
        return ov >= 0.7
    oa = _ov(sa["ans"], sb["ans"])
    if a.get("topic") == "sports":  # many different results from one Games share most words
        return ov >= 0.6 or (ov >= 0.4 and oa >= 0.5)
    if a.get("topic") in ("obituary", "important_day"):  # one person or one day: other facts about it are the same story
        return ov >= 0.25
    shared = sa["all"] & sb["all"]
    nums = _numbers(shared)
    # same story number (5.5, 25 bps) and three more shared words: the RBI repo hike told by two outlets
    return ov >= 0.5 or (ov >= 0.3 and oa >= 0.5) or (bool(nums) and len(shared - nums) >= 3)


def group(cards):
    """cards (any order) -> list of groups (lists), each one story, members in publish order."""
    groups, sigs = [], []
    for c in sorted(cards, key=lambda c: int(c.get("published_at") or 0)):
        s = sig(c)
        for g, gs in zip(groups, sigs):
            if any(same_story(c, m, s, ms) for m, ms in zip(g, gs)):
                g.append(c)
                gs.append(s)
                break
        else:
            groups.append([c])
            sigs.append([s])
    return groups
