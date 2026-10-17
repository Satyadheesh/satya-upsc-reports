"""Which of the latest news stories an ordinary person in India would want to be told about: cheap signals only
(no AI here). A story = the articles of one news cluster, plus other outlets' articles with the same headline
(the pipeline's clusters rarely span outlets: 1,074 of 1,155 clusters in 48 h had one outlet, 16 Oct 2026)."""
import json
import re
import zlib
from collections import Counter, defaultdict

from common.db import in_chunks
from reports.data import same_headline

H = 3600
FRESH = 3 * H        # a story is a candidate while its first article is at most this old
WINDOW = 36 * H      # outlets counted over this window

# daily life: money, travel, exams and jobs, health and safety, weather, rules everyone has to follow
IMPACT = re.compile(
    r"\b(?:price (?:hike|cut|rise)s?|prices? (?:of|to|hiked|cut|rise|rises|rose|fall|fell|increase[sd]?|reduced)|costlier|"
    r"cheaper|petrol|diesel|fuel|lpg|cylinder|cng|gst|income tax|tax (?:slab|rebate|relief|rate)s?|toll|fares?|railways?|"
    r"trains?|irctc|flights?|airports?|airlines?|metro|upi|bank holidays?|bank accounts?|atms?|rbi|repo rate|emi|"
    r"home loans?|interest rates?|salar(?:y|ies)|pensions?|da hike|epfo|provident fund|aadhaar|pan card|ration|"
    r"subsid(?:y|ies)|holidays?|schools?|colleges?|exams?|results? (?:declared|announced|out)|admit cards?|neet|jee|cuet|"
    r"cbse|board exams?|recruitment|vacanc(?:y|ies)|weather|rain(?:fall)?|monsoon|heat ?wave|cold wave|cyclone|floods?|"
    r"earthquake|landslide|storm|red alert|orange alert|outbreak|virus|vaccines?|hospitals?|medicines?|electricity|"
    r"power cuts?|water supply|internet shutdown|mobile tariffs?|recharge|gold price|silver price|sensex|nifty|deadline|"
    r"new rules?|banned|ban on)\b", re.I)
NATIONAL = re.compile(r"\b(?:nationwide|across india|all states|union cabinet|cabinet approves|supreme court|parliament|"
                      r"lok sabha|rajya sabha|prime minister|pm modi|centre|central government|election commission|"
                      r"president murmu)\b", re.I)
DISASTER = re.compile(r"\b(?:killed|dead|deaths?|died|injured|collapse[sd]?|blast|explosion|earthquake|cyclone|flood|"
                      r"landslide|derail(?:ed|ment)|crash(?:ed)?|stampede|fire)\b", re.I)
INDIA = re.compile(r"\b(?:india|indian|indians|delhi|mumbai|centre|modi)\b", re.I)


def text_of(blob, limit=900):
    """The rephrased article (zlib or gzip compressed; a string may be base64 or plain text) cut to `limit` characters."""
    if not blob:
        return ""
    raw = []
    if isinstance(blob, (bytes, bytearray, memoryview)):
        raw.append(bytes(blob))
    else:
        import base64
        try:
            raw.append(base64.b64decode(str(blob), validate=True))
        except Exception:
            return str(blob)[:limit]
    for b in raw:
        for wbits in (15, 47):  # zlib, gzip (or zlib) auto-detect
            try:
                return zlib.decompress(b, wbits).decode("utf-8", "replace")[:limit]
            except Exception:
                pass
        try:
            return b.decode("utf-8")[:limit]
        except Exception:
            pass
    return ""


def load(main, upsc, now):
    """Processed articles of the last WINDOW, with their source, cluster, category and the signals we need."""
    rows = main.execute(
        "SELECT a.id, a.cluster_id, a.source_id, a.scraped_at, a.category, a.geo_focus, a.civic_flag, "
        "COALESCE(a.rephrased_title, a.title), a.url, a.party_mentioned, a.ministers_mentioned, a.states_mentioned, "
        "a.cities_mentioned, s.name FROM articles a INDEXED BY idx_articles_scraped LEFT JOIN sources s ON s.id = a.source_id "
        "WHERE a.scraped_at >= ? AND a.status IN ('classified', 'entity_processed', 'processed')", [now - WINDOW]).rows
    arts = [dict(id=r[0], cluster=r[1], source=r[2], at=r[3], category=r[4] or "", geo=r[5], civic=r[6] == 1,
                 title=r[7] or "", url=r[8], india_ents=any((x or "[]") not in ("[]", "") for x in r[9:13]), source_name=r[13])
            for r in rows]
    return arts


def stories(arts):
    """Group articles into stories: same cluster, or the same headline from another outlet."""
    arts = sorted(arts, key=lambda a: a["at"])
    groups, by_cluster = [], {}
    for a in arts:
        g = by_cluster.get(a["cluster"]) if a["cluster"] else None
        if g is None:
            g = next((g for g in groups if abs(g[0]["at"] - a["at"]) < 24 * H and any(same_headline(x["title"], a["title"])
                                                                                    for x in g[-6:])), None)
        if g is None:
            g = []
            groups.append(g)
        g.append(a)
        if a["cluster"]:
            by_cluster[a["cluster"]] = g
    return groups


def score(g, now, timeline, upsc_score, related=0):
    """(score, signals) for one story. Higher = more likely an ordinary person wants to know now.
    related: other reports in the window about the same thing (coverage())."""
    first = g[0]
    lead = max(g, key=lambda a: (a["category"] != "international", len(a["title"])))
    title = " ".join(a["title"] for a in g[:4])
    outlets = {a["source"] for a in g}
    recent = {a["source"] for a in g if a["at"] >= now - FRESH}
    india = (lead["category"] != "international") or lead["india_ents"] or bool(INDIA.search(title))
    s, why = 0.0, []
    s += 2 * min(len(outlets) - 1, 4)
    if len(outlets) > 1:
        why.append(f"{len(outlets)} outlets ({len(recent)} in the last 3 h)")
    if related >= 3:
        s += 2 if related < 6 else 4 if related < 12 else 6
        why.append(f"widely reported ({related} related reports in {WINDOW // H} h)")
    imp = sorted({m.lower() for m in IMPACT.findall(title)})
    if imp:
        s += 4
        why.append("daily life: " + ", ".join(imp[:4]))
    if NATIONAL.search(title):
        s += 2
        why.append("national")
    if DISASTER.search(title) and india:
        s += 2
        why.append("safety / disaster")
    ev = max((timeline.get(a["id"], 0) for a in g), default=0)
    if ev >= 2:
        s += 2
        why.append(f"update to a running story ({ev} earlier updates)")
    us = max((upsc_score.get(a["id"], 0) for a in g), default=0)
    if us >= 4:
        s += 2
        why.append(f"UPSC importance {us}/5")
    if any(a["civic"] for a in g):
        s += 1
        why.append("civic flag")
    if not india:
        s -= 6
        why.append("foreign, no India link")
    if lead["category"] == "crime" and len(outlets) < 3 and not NATIONAL.search(title):
        s -= 3
        why.append("local crime")
    if lead["category"] in ("sports", "other") and len(outlets) < 3:
        s -= 1
    return s, dict(outlets=len(outlets), recent=len(recent), related=related, category=lead["category"], geo=lead["geo"], why=why,
                   lead_id=lead["id"], first_seen=first["at"], titles=[a["title"] for a in g[:3]],
                   sources=sorted({a["source_name"] or "?" for a in g})[:6])


# Words that say nothing about which story it is (plus anything in more than COMMON_DF headlines of the window)
STOP = set("""after again against amid also among been before being between both could during from have having into
just more most much over said says than that their them then there these they this those through under until upon very
were what when where which while will with without would your about across first last next year years week today
india indian indians state states government govt centre central minister ministers chief party leaders leader police
court news report reports amid","""
           .replace(",", " ").split())
WORD = re.compile(r"[a-z][a-z'-]{3,}")
COMMON_DF = 25   # a word in more headlines than this is too common to tie two stories together
RARE_DF = 12     # ...and at least one shared word must be this specific


def words(title):
    return {w.strip("'-") for w in WORD.findall(title.lower())} - STOP


def coverage(groups):
    """story index -> how many other reports in the window are about the same thing (they share at least two
    distinctive headline words, one of them rare). The scraper drops near-duplicate articles at the source, so
    'how many outlets carry it' is mostly 1; this is the stand-in for 'everyone is reporting this' (17 Oct 2026)."""
    ws = [set().union(*(words(a["title"]) for a in g)) for g in groups]
    df = Counter(w for x in ws for w in x)
    index = defaultdict(set)
    for i, x in enumerate(ws):
        for w in x:
            if 2 <= df[w] <= COMMON_DF:
                index[w].add(i)
    out = {}
    for i, x in enumerate(ws):
        shared, rare = Counter(), set()
        for w in x:
            for j in index.get(w, ()):
                if j != i:
                    shared[j] += 1
                    if df[w] <= RARE_DF:
                        rare.add(j)
        related = [j for j, n in shared.items() if n >= 2 and j in rare]
        out[i] = sum(len(groups[j]) for j in related)
    return out


def timeline_depth(main, ids):
    """article id -> number of earlier updates on its timeline (event_articles)."""
    ev = {r[0]: r[1] for r in in_chunks(main, "SELECT article_id, event_id FROM event_articles WHERE article_id IN ({ph})", ids)}
    out = {}
    if ev:
        cnt = {r[0]: r[1] for r in in_chunks(main, "SELECT event_id, COUNT(*) FROM event_articles WHERE event_id IN ({ph}) "
                                                  "GROUP BY event_id", sorted(set(ev.values())))}
        out = {a: max(cnt.get(e, 1) - 1, 0) for a, e in ev.items()}
    return out


def upsc_scores(upsc, ids):
    return {r[0]: r[1] or 0 for r in in_chunks(upsc, "SELECT article_id, upsc_score FROM upsc_articles WHERE article_id IN ({ph})", ids)}


def story_key(g):
    c = next((a["cluster"] for a in g if a["cluster"]), None)
    return f"c:{c}" if c else f"a:{g[0]['id']}"


def dumps(sig):
    return json.dumps(sig, ensure_ascii=False)
