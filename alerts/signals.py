"""Which of the latest news stories an ordinary person in India would want to be told about: cheap signals only
(no AI here). A story = the articles of one news cluster, plus other outlets' articles with the same headline
(the pipeline's clusters rarely span outlets: 1,074 of 1,155 clusters in 48 h had one outlet, 16 Oct 2026)."""
import json
import re
import zlib

from common.db import in_chunks
from reports.data import same_headline

H = 3600
FRESH = 3 * H        # a story is a candidate while its first article is at most this old
WINDOW = 36 * H      # outlets counted over this window

# daily life: money, travel, exams and jobs, health and safety, weather, rules everyone has to follow
IMPACT = re.compile(
    r"\b(?:prices?|petrol|diesel|fuel|lpg|cylinder|cng|gst|income tax|taxe?s?|tariffs?|tolls?|fares?|rail(?:way)?s?|trains?|"
    r"irctc|flights?|airports?|airlines?|metro|upi|banks?|rbi|repo rate|emi|loans?|interest rates?|salar(?:y|ies)|pensions?|"
    r"da hike|epfo|provident fund|aadhaar|pan card|ration|subsid(?:y|ies)|holidays?|schools?|colleges?|exams?|results?|"
    r"admit cards?|neet|jee|cuet|cbse|board exams?|recruitment|vacanc(?:y|ies)|weather|rain(?:fall)?|monsoon|heat ?wave|"
    r"cold wave|cyclone|floods?|earthquake|landslide|storm|red alert|orange alert|outbreak|virus|vaccines?|hospitals?|"
    r"medicines?|electricity|power cuts?|water supply|internet|mobile|recharge|gold|silver|sensex|nifty|rupee|deadline|"
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


def score(g, now, timeline, upsc_score):
    """(score, signals) for one story. Higher = more likely an ordinary person wants to know now."""
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
    return s, dict(outlets=len(outlets), recent=len(recent), category=lead["category"], geo=lead["geo"], why=why,
                   lead_id=lead["id"], first_seen=first["at"], titles=[a["title"] for a in g[:3]],
                   sources=sorted({a["source_name"] or "?" for a in g})[:6])


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
