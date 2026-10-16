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


def unmojibake(t):
    """'El NiÃ±o' -> 'El Niño' (UTF-8 read as Latin-1 somewhere upstream)."""
    if t and re.search(r"Ã.|â€", t):
        try:
            return t.encode("cp1252").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            try:
                return t.encode("latin-1").decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                return t
    return t


def clean_title(t):
    t = re.sub(r"\*\*|\*|`", "", unmojibake(t or ""))
    return re.sub(r"\s[-|]\s[^-|]+$", "", t).strip()


def why_title(why):
    """A headline made from 'why in news': its first sentence, cut back at a clause if long (no '…')."""
    w = " ".join((why or "").split())
    m = re.search(r"[।!?]|\.(?=\s|$)", w)  # not the dot inside 87.7%
    first = w[: m.start()] if m else w
    if len(first) <= 160:  # Hindi runs ~30% longer than English
        return first
    for sep in (", ", "; ", " — "):
        k = first.rfind(sep, 0, 160)
        if k > 50:
            return first[:k]
    return first


# A person + job title, not a headline ('Sarvjeet Singh Virk, Co-founder & MD of Shoonya').
PERSON_ROLE = re.compile(r"^(?:[A-Z][\w.'-]*\s){1,4}[A-Z][\w.'-]*,\s+(?:Co-?founder|Founder|CEO|MD|Managing Director|Chairman|"
                         r"Chairperson|Director|President|Head|Chief|Partner|Economist|Analyst|Professor|Editor)\b")
LIVE_BLOG = re.compile(r"\bLIVE\b|\blive updates\b|\blive:\s", re.I)
# A lead sentence cut short and used as a headline ('On 13 September 2026, Indian High Commissioner ... met with high-level').
DATE_END = re.compile(r"\bon\s+(?:[A-Z][a-z]+day,?\s+)?(?:[A-Z][a-z]+\s+\d{1,2}|\d{1,2}\s+[A-Z][a-z]+),?\s+\d{4}$")
DATE_LEAD = re.compile(r"^On\s+\d{1,2}\s+[A-Z][a-z]+(?:\s+\d{4})?,|^On\s+[A-Z][a-z]+day,|^This\s+(?:week|weekend|morning)\b")
CUT_WORDS = {"million", "billion", "trillion", "crore", "lakh", "thousand", "high-level", "per"}
# Stock-tip and share-price stories: not UPSC material even when the model scored them high.
MARKET = re.compile(r"\b(?:shares?|stocks?)\s+(?:drop\w*|rise|rises|rose|fall|falls|fell|plummet\w*|plunge\w*|jump\w*|surge\w*|slump\w*|gain\w*|"
                    r"tumble\w*|soar\w*|sink\w*|rall\w*|up|down)\b|\bstocks?\s+to\s+(?:buy|watch)\b|\btarget price\b|"
                    r"\bbrokerage\b|Goldman Sachs|\bmultibagger\b", re.I)
REGULATOR = re.compile(r"\b(?:SEBI|Sebi|RBI|government|Govt|ministry|Cabinet|Centre|Parliament)\b")


def demotion(*titles):
    """How far down to move a story whose headline is a share-price move, a live blog or a person's name and job
    title (0 = none, 1 = one importance step). Every UPSC note is relevant, but these should not lead a report."""
    t = " ".join(x for x in titles if x)
    if (MARKET.search(t) and not REGULATOR.search(t)) or LIVE_BLOG.search(t) or any(PERSON_ROLE.match(x) for x in titles if x):
        return 1
    return 0


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
        last = re.sub(r"[^a-z0-9.-]", "", w[-1].lower())
        if last in DANGLING or last in CUT_WORDS or (len(last) <= 1 and not last.isdigit()):
            return None
        if PERSON_ROLE.match(t) or LIVE_BLOG.search(t) or DATE_LEAD.match(t) or DATE_END.search(t) or t.count('"') % 2:
            return None  # not a headline: a name + job title, a live blog, a cut lead sentence
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

        self.ssc_cards = {}
        if ids:
            try:
                for r in in_chunks(upsc, "SELECT article_id, status, question_en, answer_en, key_fact_en, static_gk_en, "
                                         "question_hi, answer_hi, key_fact_hi, static_gk_hi FROM ssc_kit WHERE article_id IN ({ph})", ids):
                    if r[1] == "done":
                        self.ssc_cards[r[0]] = {
                            "question_en": r[2], "answer_en": r[3], "key_fact_en": r[4], "static_gk_en": r[5],
                            "question_hi": r[6], "answer_hi": r[7], "key_fact_hi": r[8], "static_gk_hi": r[9],
                        }
            except Exception:
                pass

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
            "id": aid, "published_at": pub, "score": score, "demote": demotion(a[1], a[2]), "exam": exam, "paper": paper, "subject": subject, "node": node,
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
            "ssc_kit": getattr(w, "ssc_cards", {}).get(aid),
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
    return (-(x["score"] - x.get("demote", 0)), -x["related"], -x["published_at"])


COMMON_NAMES = {"india", "indian", "centre", "union", "government", "minister", "prime", "supreme", "court", "high",
                "state", "states", "national", "president", "chief", "rbi", "modi", "trump", "pakistan", "china", "us", "un"}


def _names(title):
    """Capitalised words of a headline (not its first word), lower-cased and stemmed like sscca.dedupe.words."""
    from sscca.dedupe import words
    ws = re.findall(r"[A-Za-z][\w'’-]*", title or "")
    return words(" ".join(w for w in ws[1:] if w[0].isupper() and w.lower() not in COMMON_NAMES))


def _same_story(a, b, df=None):
    if (a.get("cluster") and a.get("cluster") == b.get("cluster")) or (
            abs(a["published_at"] - b["published_at"]) <= 3 * DAY and same_headline(a["title_en"], b["title_en"])):
        return True
    if abs(a["published_at"] - b["published_at"]) <= 4 * DAY:
        # the same story from two outlets, filed under different papers: title + why-in-news overlap strongly, or
        # they share two rare names (Halzen, IceCube) and a good part of their words
        from sscca.dedupe import words, _ov
        ov = _ov(words(f"{a['title_en']} {a['why']}"), words(f"{b['title_en']} {b['why']}"))
        rare_of = lambda t: {w for w in _names(t) if df is None or df.get(w, 0) <= 3}
        ra, rb = rare_of(a["title_en"]), rare_of(b["title_en"])
        if ov >= 0.55 or (len(ra & rb) >= 2 and ov >= 0.35):
            return True
        if ra and rb and not (ra & rb) and ov < 0.55:
            return False  # different people or places in the headlines: Halzen's Nobel is not Kagan's
    else:
        ov = None
    if a["paper"] != b["paper"]:
        return False
    ka = {k.lower().strip() for k in a["keywords"]}
    kb = {k.lower().strip() for k in b["keywords"]}
    if ov is None:
        from sscca.dedupe import words, _ov
        ov = _ov(words(f"{a['title_en']} {a['why']}"), words(f"{b['title_en']} {b['why']}"))
    if a["node"] == b["node"] and len(ka & kb) >= 2 and ov >= 0.3:  # shared keywords alone ("energy security") are not a story
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
    from collections import Counter
    df = Counter(w for it in items for w in _names(it["title_en"]))
    kept = []
    for it in sorted(items, key=by_importance):
        twin = next((k for k in kept if _same_story(k, it, df)), None)
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
    pool = merge_stories([i for i in en_items if not LIVE_BLOG.search(i["title_en"])])
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



SSC_CAP = {"daily": 40, "weekly": 90, "monthly": 160}
# The SSC runner covers news from 1 Oct 2026 (IST). Periods that start earlier keep the old SSC cards (ssc_kit on
# the UPSC notes) so a month or week is never built from a few days only.
SSC_CA_FROM = 1790793000  # 2026-10-01 00:00 IST


SIDE_Q = re.compile(r"^(?:who is the current|who was the .{0,40}who announced|who founded)\b", re.I)
DEATH_Q = re.compile(r"\b(?:died|dies|passed away|death|demise)\b", re.I)  # an obituary card should ask who died
SSC_LOOKBACK = 6 * DAY
SSC_CARD_FILTER = None  # a daily PDF leaves out stories already carded in the six days before it
GENERIC_KEY = {"sanction", "sanctioned", "amount", "award", "awarded", "appointed", "appoint", "development", "develop",
               "modernization", "modernisation", "recent", "recently", "announced", "approved", "total"}


def key_adds(q, a, key):
    """A KEY line must add something the question and answer don't already say ('Sanctioned amount is ₹45 crore'
    under 'Under which scheme was ₹45 crore sanctioned?' adds nothing)."""
    from sscca.dedupe import _stem
    tok = lambda s: {_stem(w) for w in re.findall(r"[a-z0-9]+", (s or "").lower()) if len(w) >= 3 or w.isdigit()}
    from sscca.dedupe import STOP
    new = tok(key) - tok(f"{q} {a}") - {_stem(w) for w in STOP} - {_stem(w) for w in GENERIC_KEY}
    return bool(new)


class SscCards(list):
    """The PDF's cards, plus .pool: every card of the window (wrong options for the quiz)."""
    pool = ()


def ssc_items(upsc, p):
    """SSC cards of the period from the SSC runner (ssc_ca, judged from the raw news), one per story
    (sscca.dedupe: same cluster, or the same story from another outlet or day), best first.
    A daily PDF skips stories already carded in the six days before; the weekly and monthly have each story once.
    Static GK comes from the current verified table (kit.ssc_guard) and is shown once per PDF; a KEY line that only
    repeats the question is left out. None for periods before the runner's start (build the SSC PDF the old way)."""
    from kit.ssc_guard import choose_static_gk
    from sscca.dedupe import group, sig, _ov
    from sscca.gate import TOPICS
    if p["start"] < SSC_CA_FROM:
        return None
    since = max(SSC_CA_FROM, p["start"] - (SSC_LOOKBACK if p["kind"] == "daily" else 0))
    try:
        rows = upsc.execute(
            "SELECT article_id, published_at, cluster_id, topic, importance, title, question, answer, key_fact, static_gk, fact "
            "FROM ssc_ca INDEXED BY idx_ssc_ca_status WHERE status = 'card' AND published_at >= ? AND published_at < ?",
            [since, p["end"]]).rows
    except Exception as ex:  # table not created yet
        print(f"SSC cards not available: {type(ex).__name__}")
        return []
    cards = [dict(zip(("article_id", "published_at", "cluster_id", "topic", "importance", "title", "question", "answer",
                       "key_fact", "static_gk", "fact"), r)) for r in rows]
    cards = [c for c in cards if c["topic"] in TOPICS and c["question"] and c["answer"]]
    if SSC_CARD_FILTER:  # previews only: drop cards the current code checks would drop (as sscca.recheck --apply would)
        cards = [c for c in cards if SSC_CARD_FILTER(c)]
    picks = []
    for g in group(cards):
        if int(g[0]["published_at"] or 0) < p["start"]:
            continue  # the story was in an earlier daily PDF
        inside = [c for c in g if c["published_at"] >= p["start"]]
        sigs = [sig(c)["all"] for c in inside]
        # the best telling: not a side question ("who is the current Governor", an obituary card that doesn't ask who
        # died), most important, then the one closest
        # to the others (the consensus answer), then earliest
        central = [sum(_ov(s, o) for o in sigs) for s in sigs]
        side = [bool(SIDE_Q.match(c["question"] or "")) or (
            c["topic"] == "obituary" and not DEATH_Q.search(c["question"] or "")) for c in inside]
        best = max(range(len(inside)), key=lambda k: (not side[k], int(inside[k]["importance"] or 0), central[k],
                                                      -inside[k]["published_at"]))
        picks.append({**inside[best], "importance": max(int(c["importance"] or 0) for c in inside)})  # the story's rank
    picks.sort(key=lambda c: (-c["importance"], -c["published_at"]))
    picks = picks[:SSC_CAP.get(p["kind"], 40)]
    # in the PDF: by module, and within a module most important first
    picks.sort(key=lambda c: (TOPICS[c["topic"]][0], -c["importance"], -c["published_at"]))
    out, seen_gk = SscCards(), set()
    out.pool = [(c["question"], c["answer"], TOPICS[c["topic"]][0]) for c in cards]  # quiz options (render.ssc_quiz)
    out.pool_src = [(c["article_id"], c["question"], TOPICS[c["topic"]][0]) for c in cards]  # same cards, for the Hindi pool
    for c in picks:
        q, ans, key = c["question"], c["answer"], c["key_fact"] or ""
        sgk, _ = choose_static_gk({"ssc_question": q, "ssc_answer": ans, "key_fact": key})
        if sgk in seen_gk:
            sgk = ""
        seen_gk.add(sgk)
        if key and not key_adds(q, ans, key):
            key = ""
        code, name, _ = TOPICS[c["topic"]]
        aid = c["article_id"]
        out.append({"id": aid, "published_at": c["published_at"], "title": c["title"] or "", "why": c["fact"] or "",
                    "fact_box": "", "pointers": [], "related": 0, "paper": "SSC", "subject": c["topic"],
                    "importance": c["importance"], "ssc_topic": (code, name), "src_url": f"https://satyadheesh.in/news/{aid}",
                    "ssc_kit": {"question_en": q, "answer_en": ans, "key_fact_en": key, "static_gk_en": sgk}})
    return out


def ssc_items_hi(en_items, trans, ready=0.8):
    """The Hindi SSC PDF: the English edition's cards in Hindi (Hindi service, ssc_ca_translations; static GK from the
    checked Hindi table). -> (items or None, share translated). None until `ready` of the cards have Hindi, so the
    Hindi PDF never carries only half the day."""
    from kit.ssc_guard import static_gk_hi
    if not en_items or trans is None:
        return None, 0.0
    ids = [i["id"] for i in en_items]
    pool_src = getattr(en_items, "pool_src", ())  # every card of the window: wrong options for the Hindi quiz too
    pool_ids = list({*ids, *(x[0] for x in pool_src)})
    try:
        rows = in_chunks(trans, "SELECT article_id, question_hi, answer_hi, key_fact_hi, question_en FROM ssc_ca_translations "
                                "WHERE article_id IN ({ph})", pool_ids)
    except Exception as ex:  # table not there until the Hindi service has run
        print(f"Hindi SSC cards not available: {type(ex).__name__}")
        return None, 0.0
    hi = {r[0]: r for r in rows if r[1] and r[2] and DEVANAGARI.search(r[1])}
    out = SscCards()
    for it in en_items:
        k = it["ssc_kit"]
        h = hi.get(it["id"])
        if not h or (h[4] and h[4] != k["question_en"]):  # translated before the card was rewritten
            continue
        key_hi = (h[3] or "") if k.get("key_fact_en") else ""
        out.append({**it, "ssc_kit": {**k, "question_hi": h[1], "answer_hi": h[2], "key_fact_hi": key_hi,
                                      "static_gk_hi": static_gk_hi(k.get("static_gk_en") or "")}})
    share = len(out) / len(en_items)
    if share < ready:
        return None, share
    # quiz options: the Hindi of every card of the window, like the English pool (it was only this PDF's own cards, so
    # the Hindi quiz rarely found 3 wrong options of the same kind: Instagram's Hindi SSC quiz never had 5 questions)
    out.pool = [(i["ssc_kit"]["question_hi"], i["ssc_kit"]["answer_hi"], i["ssc_topic"][0]) for i in out]
    for aid, q_en, module in pool_src:
        h = hi.get(aid)
        if h and (not h[4] or h[4] == q_en):
            out.pool.append((h[1], h[2], module))
    return out, share
