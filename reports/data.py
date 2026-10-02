"""Notes for a report period: UPSC notes + titles/sources/events (main DB) + study kit + Hindi (translation DB).

Ported from the site's lib/upsc.ts (hydrate) and lib/upscReports.ts (buildReport) so the new PDFs pick
the same notes the site shows: same-event and near-duplicate notes collapse into one (counted in
`related`), weekly/monthly digests merge the same story across days and keep subjects balanced.
"""
import json
import math
import re

from common.db import in_chunks

IST = 19800
DAY = 86400
PAPERS = ["GS1", "GS2", "GS3", "GS4"]
CAPS = {"daily": 200, "weekly": 50, "monthly": 120}
SUBJECT_SHARE = 0.3
LIVE_BLOG = re.compile(r"\blive(\s+updates?|\s+blog)?\b\s*[:|-]|\blive updates\b", re.I)
DEVANAGARI = re.compile(r"[ऀ-ॿ]")
DANGLING = set("""a an the of to in on at for with and or but as by when while after before that which who whose its his
her their over under against amid despite during is are was were has have had will would could should may might been
being from into about than because if so not no minister chief deputy baby infant pk p.k dr mr ms""".split())
STOP_DUP = set("""about above after again against also amid among before being below between both could during each first
from further have having here into just more most other over same should some such than that their theirs them then there
these they this those through under until very were what when where which while who whom why will with would india indian
government state centre order rules issued court high said today news minister ministry affairs external official
officials department secretary""".split())
STOP_MERGE = set("""about after again against along amid among before being between could during from have into more
over said says such than that their there these they this those under were what when where which while with will would
india indian government centre state states news today live updates update year""".split())
COLS = ("a.article_id, a.published_at, a.event_id, a.upsc_score, a.exam_type, a.gs_paper, a.subject, a.syllabus_node, "
        "a.why_in_news, a.fact_box, a.prelims_pointers, a.mains_question, a.keywords, "
        "k.status, k.short_title, k.takeaway, k.brief_lead, k.brief_text, k.facts, k.mcq")


def _arr(v):
    try:
        x = json.loads(v) if v else []
        return x if isinstance(x, list) else []
    except (TypeError, ValueError):
        return []


def _obj(v):
    try:
        return json.loads(v) if v else None
    except (TypeError, ValueError):
        return None


def clean_hi(t):
    t = re.sub(r"<thought>[\s\S]*?</thought>|<\|channel>[a-zA-Z0-9_]+[\s\S]*?<channel\|?>", "", t or "", flags=re.I)
    t = re.sub(r"<\|?(?:start_of_turn|end_of_turn|eos|bos|pad|turn|mask|channel|thought|unused\d*)[^>]*\|?>\s*(?:model|user|assistant)?|</?s>", "", t, flags=re.I)
    t = re.sub(r"<\|[a-zA-Z0-9_\-\s|]+>|<channel\|?>", "", t, flags=re.I)
    return " ".join(t.split())


def clean_title(t):
    t = re.sub(r"\*\*|\*|`", "", t or "")
    return re.sub(r"\s[-|]\s[^-|]+$", "", t).strip()


def upsc_title(rephrased, original, why):
    def ok(t):
        if not t:
            return None
        t = re.sub(r"\s[-|]\s[^-|]+$", "", t.strip()).strip()
        w = t.split()
        if len(w) < 3:
            return None
        last = re.sub(r"[^a-z0-9.]", "", w[-1].lower())
        if last in DANGLING or (len(last) <= 1 and not last.isdigit()):
            return None
        return t
    return clean_title(ok(rephrased) or ok(original) or (why.strip() if why and len(why.strip()) >= 15 else "")
                       or (rephrased or original or "").strip())


def _tokens(text, stop, stem=False):
    ws = re.findall(r"[a-z0-9]{4,}", (text or "").lower())
    out = set()
    for w in ws:
        if w in stop:
            continue
        if stem and len(w) > 5:
            w = re.sub(r"(ing|ed|es|s)$", "", w)
        out.add(w)
    return out


class Window:
    """Every note in [start, end) plus its titles, events, study kit and (optionally) Hindi text,
    fetched once; reports for the periods inside are then built from memory."""

    def __init__(self, upsc, main, start, end, trans=None):
        self.rows = upsc.execute(f"SELECT {COLS} FROM upsc_articles a INDEXED BY idx_upsc_pub "
                                 "LEFT JOIN upsc_kit k ON k.article_id = a.article_id "
                                 "WHERE a.published_at >= ? AND a.published_at < ? "
                                 "ORDER BY a.upsc_score DESC, a.published_at DESC", [start, end]).rows
        ids = [r[0] for r in self.rows]
        self.arts = {r[0]: r for r in in_chunks(main, "SELECT a.id, a.rephrased_title, a.title, a.url, s.name FROM articles a "
                                                      "LEFT JOIN sources s ON s.id = a.source_id WHERE a.id IN ({ph})", ids)}
        ev_ids = sorted({r[2] for r in self.rows if r[2] is not None})
        self.events = {r[0]: {"slug": r[1], "title": r[2]} for r in in_chunks(
            main, "SELECT id, slug, title FROM events WHERE id IN ({ph}) AND slug IS NOT NULL AND title IS NOT NULL", ev_ids)}
        self.hi_title, self.hi_note = {}, {}
        if trans is not None and ids:
            self.hi_title = {r[0]: clean_hi(r[1]) for r in in_chunks(
                trans, "SELECT article_id, rephrased_title_hi FROM translations WHERE article_id IN ({ph})", ids) if r[1]}
            for r in in_chunks(trans, "SELECT article_id, why_in_news_hi, fact_box_hi, prelims_pointers_hi, mains_question_hi "
                                      "FROM upsc_translations WHERE article_id IN ({ph})", ids):
                ptrs = [{**q, "text": clean_hi(q.get("text"))} for q in _arr(r[3]) if isinstance(q, dict) and clean_hi(q.get("text"))]
                self.hi_note[r[0]] = {"why": clean_hi(r[1]), "fact": clean_hi(r[2]), "pointers": ptrs, "mains": clean_hi(r[4])}

    def day(self, day_start, lang="en"):
        """One IST day's notes, best first, de-duplicated like the site's day lists."""
        return hydrate([r for r in self.rows if day_start <= r[1] < day_start + DAY], self, lang)

    def period(self, p, lang="en"):
        days = []
        d = p["start"]
        while d < p["end"]:
            days.append(self.day(d, lang))
            d += DAY
        items = [i for day in days for i in day]
        return items if p["kind"] == "daily" else dedupe_across_days(items)


def dedupe_across_days(items):
    by_key = {}
    for it in items:
        k = f"e:{it['event']['slug']}" if it.get("event") else f"a:{it['id']}"
        prev = by_key.get(k)
        if not prev:
            by_key[k] = dict(it)
            continue
        keep = dict(it) if (it["score"] > prev["score"] or (it["score"] == prev["score"] and it["published_at"] > prev["published_at"])) else prev
        keep["related"] = prev["related"] + it["related"] + 1
        by_key[k] = keep
    return list(by_key.values())


def hydrate(rows, w, lang="en"):
    out, seen_ev, recent = [], {}, []
    for r in rows:
        (aid, pub, ev, score, exam, paper, subject, node, why, fact, ptrs, mains, kws,
         kstatus, ktitle, ktake, klead, ktext, kfacts, kmcq) = r
        a = w.arts.get(aid)
        if not a:
            continue
        if ev is not None and ev in seen_ev:
            seen_ev[ev]["related"] += 1
            continue
        title_en = upsc_title(a[1], a[2], why)
        h = w.hi_note.get(aid) or {}
        hi = lang == "hi"
        item = {
            "id": aid, "published_at": pub, "score": score, "exam": exam, "paper": paper, "subject": subject, "node": node,
            "title_en": title_en, "title": (w.hi_title.get(aid) if hi else None) or title_en,
            "why": (h.get("why") if hi else None) or why or "",
            "fact_box": (h.get("fact") if hi else None) or fact or "",
            "pointers": (h.get("pointers") if hi and h.get("pointers") else None)
                        or [q for q in _arr(ptrs) if isinstance(q, dict) and q.get("text")],
            "mains": (h.get("mains") if hi else None) or mains,
            "keywords": [k for k in _arr(kws) if isinstance(k, str)],
            "source": a[4], "url": a[3], "event": w.events.get(ev), "event_id": ev, "related": 0,
            "hi": bool(h.get("why")),
            "kit": ({"short_title": ktitle, "takeaway": ktake, "brief_lead": klead, "brief_text": ktext,
                     "facts": _arr(kfacts), "mcq": _obj(kmcq)} if kstatus == "done" else None),
        }
        toks = _tokens(f"{item['title']} {item['why']}", STOP_DUP)
        dup = False
        for q, qtoks in recent:  # near-duplicate within 48 h, same paper + subject (site rule)
            if abs(q["published_at"] - pub) <= 2 * DAY and q["paper"] == paper and q["subject"] == subject:
                sh = len(toks & qtoks)
                u = len(toks) + len(qtoks) - sh
                j = sh / u if u else 0
                if sh >= 5 or (sh >= 4 and j >= 0.2) or (sh >= 3 and j >= 0.35):
                    q["related"] += 1
                    dup = True
                    break
        if dup:
            continue
        if ev is not None:
            seen_ev[ev] = item
        recent.append((item, toks))
        out.append(item)
    return out


def by_importance(x):
    return (-x["score"], -x["related"], -x["published_at"])


def _same_story(a, b):
    if a["paper"] != b["paper"]:
        return False
    ka = {k.lower().strip() for k in a["keywords"]}
    kb = {k.lower().strip() for k in b["keywords"]}
    if a["node"] == b["node"] and len(ka & kb) >= 2:
        return True

    def jac(x, y):
        s = len(x & y)
        u = len(x) + len(y) - s
        return s, (s / u if u else 0)
    s, j = jac(_tokens(a["title_en"], STOP_MERGE, True), _tokens(b["title_en"], STOP_MERGE, True))
    if s >= 3 and j >= 0.3:
        return True
    if abs(a["published_at"] - b["published_at"]) > 4 * DAY:
        return False
    s, j = jac(_tokens(f"{a['title_en']} {a['why']}", STOP_MERGE, True), _tokens(f"{b['title_en']} {b['why']}", STOP_MERGE, True))
    return s >= 5 and j >= 0.22


def merge_stories(items):
    kept = []
    for it in sorted(items, key=by_importance):
        twin = next((k for k in kept if _same_story(k, it)), None)
        if twin:
            twin["related"] += it["related"] + 1
        else:
            kept.append(dict(it))
    return kept


def pick_balanced(items, cap):
    per_subject = max(3, math.ceil(cap * SUBJECT_SHARE))
    count, picked, rest = {}, [], []
    for it in sorted(items, key=by_importance):
        n = count.get(it["subject"], 0)
        if len(picked) < cap and n < per_subject:
            picked.append(it)
            count[it["subject"]] = n + 1
        else:
            rest.append(it)
    for it in rest:
        if len(picked) >= cap:
            break
        picked.append(it)
    return picked


def hindi_title(it):
    """Hindi report: a note whose headline has no Hindi translation gets the start of its Hindi 'why in news'."""
    if DEVANAGARI.search(it["title"]) or not DEVANAGARI.search(it["why"]):
        return it["title"]
    w = it["why"].strip()
    m = re.search(r"[।.!?]", w)
    if m and 20 < m.start() <= 120:
        return w[:m.start()]
    if len(w) <= 110:
        return w
    cut = w.rfind(" ", 0, 100)
    return w[: cut if cut > 40 else 100] + "…"


def select(period, en_items, hi_items=None):
    """The notes a report carries (selection always on English, so both languages carry the same digest).
    Returns (chosen, total, hi_share)."""
    pool = list(en_items)
    if period["kind"] != "daily":
        pool = merge_stories([i for i in pool if not LIVE_BLOG.search(i["title_en"])])
    total = len(pool)
    if not total:
        return [], 0, 0.0
    chosen = sorted(pool, key=by_importance) if period["kind"] == "daily" else pick_balanced(pool, CAPS[period["kind"]])
    if hi_items is None:
        return chosen, total, 1.0
    hi_by_id = {i["id"]: i for i in hi_items}
    out = []
    for en in chosen:
        h = hi_by_id.get(en["id"])
        if h and h["hi"]:
            out.append({**h, "title": hindi_title(h), "related": en["related"], "kit": en["kit"]})
    return out, total, (len(out) / len(chosen) if chosen else 0.0)
