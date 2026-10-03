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
        "k.status, k.short_title, k.takeaway, k.brief_lead, k.brief_text, k.facts, k.mcq, a.cluster_id")
NUM_STORY = re.compile(r"\b\d{2,}\b")
CUT_SEPS = (". ", "; ", ": ", " — ", ", ")


def uncut(t):
    """Older notes were clipped mid-word with '…' (fixed in the UPSC service, v2.7): trim back to the last full clause."""
    t = t or ""
    if not t.rstrip().endswith("…"):
        return t
    head = t.rstrip()[:-1]
    for sep in CUT_SEPS:
        k = head.rfind(sep)
        if k >= len(head) // 2:
            return head[:k].rstrip(" ,;:—") + ("." if sep == ". " else "")
    return t


def story_numbers(text):
    return {n for n in NUM_STORY.findall(text or "") if not re.fullmatch(r"(19|20)\d\d", n)}


def same_headline(a_title, b_title):
    """The same story told twice (two outlets, often filed under different papers): the headlines share 4+ words
    (Jaccard >= 0.3), or a story number (not a year) plus 2 words. Same rule as the site's feed."""
    ta, tb = _tokens(a_title, STOP_DUP), _tokens(b_title, STOP_DUP)
    sh = len(ta & tb)
    u = len(ta) + len(tb) - sh
    return (sh >= 4 and (sh / u if u else 0) >= 0.3) or (bool(story_numbers(a_title) & story_numbers(b_title)) and sh >= 2)


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


def why_title(why):
    """A headline made from 'why in news': its first sentence, cut back at a clause if long (no '…')."""
    w = " ".join((why or "").split())
    m = re.search(r"[।!?]|\.(?=\s|$)", w)  # not the dot inside 87.7%
    first = w[: m.start()] if m else w
    if len(first) <= 130:
        return first
    for sep in (", ", "; ", " — "):
        k = first.rfind(sep, 0, 130)
        if k > 50:
            return first[:k]
    return first[: first.rfind(" ", 0, 130)]


def upsc_title(rephrased, original, why, with_source=False):
    """The note's headline, and where it came from: 'headline' (the news headline), 'original' (the source's own
    title) or 'why' (made from why-in-news). A headline about something else than the note (e.g. 'Sarvjeet Singh
    Virk, Co-founder & MD of Shoonya' on a SEBI F&O study) shares no key word with why-in-news and is not used."""
    why_toks = _tokens(why, STOP_DUP)

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
        if why_toks and len(_tokens(t, STOP_DUP) & why_toks) < 1:
            return None  # about something else
        return t
    for src, t in (("headline", ok(rephrased)), ("original", ok(original)), ("why", why_title(why) if why and len(why.strip()) >= 15 else None)):
        if t:
            return (clean_title(t), src) if with_source else clean_title(t)
    t = clean_title((rephrased or original or "").strip())
    return (t, "headline") if with_source else t


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
        self.hi_title, self.hi_note, self.hi_kit = {}, {}, {}
        if trans is not None and ids:
            self.hi_title = {r[0]: clean_hi(r[1]) for r in in_chunks(
                trans, "SELECT article_id, rephrased_title_hi FROM translations WHERE article_id IN ({ph})", ids) if r[1]}
            for r in in_chunks(trans, "SELECT article_id, why_in_news_hi, fact_box_hi, prelims_pointers_hi, mains_question_hi "
                                      "FROM upsc_translations WHERE article_id IN ({ph})", ids):
                ptrs = [{**q, "text": clean_hi(q.get("text"))} for q in _arr(r[3]) if isinstance(q, dict) and clean_hi(q.get("text"))]
                self.hi_note[r[0]] = {"why": clean_hi(r[1]), "fact": clean_hi(r[2]), "pointers": ptrs, "mains": clean_hi(r[4])}
            try:  # the note's own Hindi headline, for notes whose news article has none (Hindi service)
                for r in in_chunks(trans, "SELECT article_id, title_hi FROM upsc_translations "
                                          "WHERE article_id IN ({ph}) AND title_hi IS NOT NULL", ids):
                    if clean_hi(r[1]) and r[0] not in self.hi_title:
                        self.hi_title[r[0]] = clean_hi(r[1])
            except Exception as ex:
                print(f"Note Hindi headlines not available: {type(ex).__name__}")
            self.hi_kit = {}
            try:  # Hindi study kit (written by the Hindi service); absent until it has run
                for r in in_chunks(trans, "SELECT article_id, short_title_hi, takeaway_hi, brief_lead_hi, brief_text_hi, facts_hi, mcq_hi "
                                          "FROM upsc_kit_translations WHERE article_id IN ({ph})", ids):
                    self.hi_kit[r[0]] = {"short_title": clean_hi(r[1]), "takeaway": clean_hi(r[2]), "brief_lead": clean_hi(r[3]),
                                         "brief_text": clean_hi(r[4]), "facts": _arr(r[5]), "mcq": _obj(r[6])}
            except Exception as ex:
                print(f"Hindi study kit not available: {type(ex).__name__}")

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
        k = (f"e:{it['event']['slug']}" if it.get("event") else f"c:{it['cluster']}" if it.get("cluster")
             else f"a:{it['id']}")
        prev = by_key.get(k)
        if not prev:
            by_key[k] = dict(it)
            continue
        keep = dict(it) if (it["score"] > prev["score"] or (it["score"] == prev["score"] and it["published_at"] > prev["published_at"])) else prev
        keep["related"] = prev["related"] + it["related"] + 1
        by_key[k] = keep
    return list(by_key.values())


def hydrate(rows, w, lang="en"):
    out, seen_ev, seen_cl, recent = [], {}, {}, []
    for r in rows:
        (aid, pub, ev, score, exam, paper, subject, node, why, fact, ptrs, mains, kws,
         kstatus, ktitle, ktake, klead, ktext, kfacts, kmcq, cluster) = r
        a = w.arts.get(aid)
        if not a:
            continue
        twin = (seen_ev.get(ev) if ev is not None else None) or (seen_cl.get(cluster) if cluster else None)
        if twin:  # same event or same news cluster
            twin["related"] += 1
            continue
        why = uncut(why)
        title_en, title_src = upsc_title(a[1], a[2], why, with_source=True)
        h = w.hi_note.get(aid) or {}
        hi = lang == "hi"
        item = {
            "id": aid, "published_at": pub, "score": score, "exam": exam, "paper": paper, "subject": subject, "node": node,
            # Hindi headline only when it translates the headline English uses; otherwise made from the Hindi why-in-news
            "title_en": title_en, "title": (w.hi_title.get(aid) if hi and title_src == "headline" else None) or title_en,
            "why": (h.get("why") if hi else None) or why or "",
            "fact_box": (h.get("fact") if hi else None) or fact or "",
            "pointers": (h.get("pointers") if hi and h.get("pointers") else None)
                        or [q for q in _arr(ptrs) if isinstance(q, dict) and q.get("text")],
            "mains": (h.get("mains") if hi else None) or mains,
            "keywords": [k for k in _arr(kws) if isinstance(k, str)],
            "source": a[4], "url": a[3], "event": w.events.get(ev), "event_id": ev, "cluster": cluster, "related": 0,
            "hi": bool(h.get("why")),
            "kit_hi": w.hi_kit.get(aid) if hi else None,
            "kit": ({"short_title": ktitle, "takeaway": ktake, "brief_lead": klead, "brief_text": ktext,
                     "facts": _arr(kfacts), "mcq": _obj(kmcq)} if kstatus == "done" else None),
        }
        toks = _tokens(f"{title_en} {why or ''}", STOP_DUP)  # English in both languages, like the site
        dup = False
        for q, qtoks in recent:  # same headline across papers (72 h), or near-duplicate in the same paper + subject (48 h)
            if abs(q["published_at"] - pub) <= 3 * DAY and same_headline(q["title_en"], title_en):
                q["related"] += 1
                dup = True
                break
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
        if cluster:
            seen_cl[cluster] = item
        recent.append((item, toks))
        out.append(item)
    return out


def by_importance(x):
    return (-x["score"], -x["related"], -x["published_at"])


def _same_story(a, b):
    if (a.get("cluster") and a.get("cluster") == b.get("cluster")) or (
            abs(a["published_at"] - b["published_at"]) <= 3 * DAY and same_headline(a["title_en"], b["title_en"])):
        return True
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
    return why_title(it["why"])


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
            out.append({**h, "title": hindi_title(h), "related": en["related"], "kit": en["kit"], "kit_hi": h.get("kit_hi")})
    return out, total, (len(out) / len(chosen) if chosen else 0.0)


KIT_FIELDS = ("takeaway", "brief_lead", "brief_text", "mcq")


def same_kit(en_kit, hi_kit):
    """The study-kit parts both languages have, as (english, hindi) — or (None, None).
    A part only one language has is dropped from both, so the two reports say the same things."""
    if not (en_kit and hi_kit and en_kit.get("short_title") and hi_kit.get("short_title")):
        return None, None
    e, h = dict(en_kit), dict(hi_kit)
    for f in KIT_FIELDS:
        if not (e.get(f) and h.get(f)):
            e[f] = h[f] = None
    if not (e.get("brief_lead") and e.get("brief_text") and h.get("brief_lead") and h.get("brief_text")):
        e["brief_lead"] = e["brief_text"] = h["brief_lead"] = h["brief_text"] = None
    fe, fh = e.get("facts") or [], h.get("facts") or []
    if len(fe) == len(fh) and fe:
        h["facts"] = [{**fh[i], "label": fe[i].get("label")} for i in range(len(fe))]  # same order, same labels
    else:
        e["facts"] = h["facts"] = None  # can't be matched one-to-one: both use the note's own pointers
    return e, h


def editions(period, en_items, hi_items, ready=0.8):
    """The English and Hindi editions of one report, built to carry exactly the same stories in the same order
    with the same parts (headline, why it matters, facts, quiz, In-brief line). Returns (en, hi, total, share):
    share = how much of the English selection has Hindi; the Hindi edition is only built when it is high enough,
    and then both editions use only the stories that have Hindi (chosen again from that pool)."""
    chosen, total, share = select(period, en_items, hi_items)
    if hi_items is None:
        return chosen, None, total, 1.0
    hi_by_id = {i["id"]: i for i in hi_items if i.get("hi")}
    if not chosen or share < ready:
        en_only, total, _ = select(period, en_items)
        return en_only, None, total, share
    en_sel, total, _ = select(period, [i for i in en_items if i["id"] in hi_by_id])
    en_out, hi_out = [], []
    for en in en_sel:
        h = hi_by_id[en["id"]]
        ke, kh = same_kit(en.get("kit"), h.get("kit_hi"))
        en_out.append({**en, "kit": ke})
        hi_out.append({**h, "title": hindi_title(h), "related": en["related"], "kit": ke, "kit_hi": kh})
    return en_out, hi_out, total, share
