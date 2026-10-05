"""Step 1 of the SSC current-affairs runner: is this news article SSC CGL General Awareness material?

A strict model call (default no) plus code checks. An article becomes an SSC card only if:
  1. the model says ssc = true with a topic and importance >= 3;
  2. its fact is a sentence found word for word in the article;
  3. the fact contains words of that topic (an award story names an award, a sports story a result ...);
  4. the fact is not an opinion, warning, demand, allegation or forecast.
"""
import re

GATE_VERSION = "sscg-2"

TOPICS = {
    "appointment": ("04", "Appointments", "a person appointed, elected, sworn in or taking charge as head of a national or "
                    "international body, PSU, bank, armed force, court, commission, state (Governor/CM) or as an envoy"),
    "award": ("07", "Awards & Honours", "a national or international award, prize, honour or title given to a person, "
              "institution, film, book or place"),
    "sports": ("05", "Sports", "a result of a national or international competition: winner, medal, title, record, host, "
               "or an Indian athlete's achievement"),
    "scheme": ("03", "Government Schemes", "a central government scheme, mission, portal, app or programme launched, "
               "renamed or with an official target or outlay (a state scheme only if it is a first in India)"),
    "law_verdict": ("08", "Laws, Bills & Verdicts", "a bill passed, an Act or ordinance notified, a constitutional "
                    "amendment, or a final Supreme Court/High Court verdict that changes a rule nationally"),
    "summit_agreement": ("14", "Summits & Agreements", "an international summit or conference India attends or hosts, "
                         "or an agreement, MoU or treaty between India and another country or body"),
    "defence": ("11", "Defence", "a military exercise (name, countries, place), a missile or platform test, induction or "
                "commissioning, or a defence deal"),
    "report_index": ("02", "Reports & Rankings", "a report or index by a named official or international body, with "
                     "India's rank or a headline figure"),
    "economy": ("10", "Economy & Budget", "an official economic figure or decision by RBI, NSO, a ministry, the Cabinet, "
                "the GST Council or SEBI (repo rate, GDP, GST collection, forex reserves, inflation, an approved outlay)"),
    "science_space": ("01", "Science & Technology", "a space mission or launch, a scientific first or discovery by a named "
                      "institution, a new technology launched by a government body"),
    "environment": ("15", "Environment & Wildlife", "a new species, a protected area, Ramsar site or tiger reserve, an "
                    "IUCN listing, a conservation programme or a climate agreement"),
    "important_day": ("06", "Important Days", "a national or international day or week observed, with its theme"),
    "book_author": ("09", "Books & Authors", "a book released or launched, with its author"),
    "obituary": ("16", "Obituaries", "the death of an eminent person (with their field or post)"),
    "first_record": ("12", "National & State News", "an Indian first or record: first state, first city, largest, "
                     "highest, a GI tag, a UNESCO listing"),
    "international": ("13", "International", "a major world event: a new head of state or government, a country joining "
                      "or leaving an international body, a global treaty"),
}

TOPIC_WORDS = {
    "appointment": r"appoint\w*|became|becomes|replac\w*|elected|sworn|takes? (?:over|charge)|took (?:over|charge)|assume[sd]? (?:office|charge)|named|"
                   r"new (?:chief|head|chairman|chairperson|governor|director)|re-?appointed|nominated|selected as|elevated",
    "award": r"award\w*|prize\w*|honour\w*|honor\w*|medal\w*|conferred|felicitated with|ratna|padma|nobel|samman|puraskar|trophy",
    "sports": r"won|wins|win|winner|medal\w*|gold|silver|bronze|title|champion\w*|trophy|cup|record|defeat\w*|beat|final|"
              r"qualif\w*|tournament|olympic\w*|games|league|series|host\w*",
    "scheme": r"scheme\w*|yojana|mission|portal|app\b|programme|program\b|initiative|abhiyan|launch\w*|outlay",
    "law_verdict": r"bill|act\b|ordinance|amendment|notif\w*|passed|enacted|verdict|judgment|judgement|ruled|struck down|upheld|"
                   r"dismiss\w*|reject\w*|quash\w*|stay(?:ed)?|strength",
    "summit_agreement": r"summit|conference|meeting|agreement|mou|memorandum|treaty|pact|accord|signed|dialogue|forum",
    "defence": r"exercise|missile|test\w*|induct\w*|commission\w*|warship|submarine|aircraft|jets?|drdo|navy|naval|army|"
               r"air force|iaf|defence|defense|brahmos|agni|tejas",
    "report_index": r"report|index|rank\w*|survey|ranking|indicator\w*|released|published",
    "economy": r"rbi|reserve bank|repo|gdp|gst|forex|reserves|inflation|cpi|wpi|nso|cabinet|ministry|council|sebi|outlay|"
               r"budget|crore|lakh crore|approved|collection\w*|deficit|growth",
    "science_space": r"isro|space|satellite|launch\w*|mission|rocket|orbit|discover\w*|scientists?|developed|first|nasa|esa|"
                     r"gaganyaan|chandrayaan|technology|research",
    "environment": r"species|reserve|sanctuary|national park|ramsar|wetland|tiger|elephant|iucn|conservation|wildlife|"
                   r"forest|biodiversity|released|climate|discover\w*",
    "important_day": r"day\b|diwas|week\b|observed|celebrated|commemorat\w*|theme",
    "book_author": r"book|author\w*|written|novel|memoir|autobiography|biography|released|launched",
    "obituary": r"passed away|died|dies|demise|death|no more|breathed (?:his|her) last",
    "first_record": r"first|largest|highest|biggest|record|gi tag|geographical indication|unesco|only",
    "international": r"elected|sworn|president|prime minister|joins|joined|member\w*|withdraw\w*|treaty|united nations|un\b|"
                     r"summit|elections?|vote[sd]?|polls?|round|won|wins|beat|defeated|host\w*",
}
TOPIC_RE = {k: re.compile(r"(?<![\w-])(?:" + v + r")(?![\w])", re.I) for k, v in TOPIC_WORDS.items()}
# Opinions, warnings, demands, allegations and forecasts are not facts an SSC paper asks about.
NOT_FACT = re.compile(r"(?<![\w-])(?:warn(?:s|ed|ing)?|urge[sd]?|urging|allege[sd]?|alleging|claim(?:s|ed)?|criticis\w*|"
                      r"criticiz\w*|slam(?:s|med)?|demand(?:s|ed)?|expect(?:s|ed)?|likely to|could|might|predict\w*|"
                      r"forecast\w*|poll|analysts?|experts? (?:say|said|believe)|speculat\w*)(?![\w])", re.I)

SYSTEM = """You select news for SSC CGL General Awareness (current affairs) — the direct-recall facts SSC papers ask:
who was appointed, who won, which scheme, which exercise, which rank, which day, which book, who died, which first.

Answer ssc = true ONLY if the article itself reports one of these (topic):
""" + "\n".join(f"- {k}: {v[2]}" for k, v in TOPICS.items()) + """

Answer ssc = false for:
- market moves, share prices, company results, investments or deals between companies;
- opinions, interviews, speeches, warnings, demands, allegations, protests, political statements or party politics;
- forecasts, expert polls, estimates by private firms, think-tanks or individual researchers;
- crimes, arrests, FIRs, accidents, court hearings, notices and petitions (only final verdicts that change a rule count);
- local or district administration, municipal works, a state's routine projects, budgets or meetings;
- foreign countries' domestic news (their ministers, officials, advisers, local laws), celebrities and entertainment gossip;
  only a new head of state or government, or a world-level event, counts from abroad;
- state-level news unless it is an Indian first or record, or a state scheme with a name and an outlay that is big news;
- election observers, district officials, party posts and other minor appointments;
- science studies about risks or trends with no named first, mission or discovery.

importance: 5 = certain to be asked (national appointment, major award, big sports title, central scheme, RBI decision);
4 = likely; 3 = possible; 1-2 = unlikely (then answer ssc = false).
fact: copy ONE sentence from the article, word for word, that contains the askable fact.
scope: national, international or state.
When unsure, answer ssc = false."""

SCHEMA = {
    "type": "object",
    "properties": {
        "ssc": {"type": "boolean"},
        "topic": {"type": "string", "enum": list(TOPICS) + ["none"]},
        "importance": {"type": "integer", "enum": [0, 1, 2, 3, 4, 5]},
        "scope": {"type": "string", "enum": ["national", "international", "state"]},
        "fact": {"type": "string", "maxLength": 400},
    },
    "required": ["ssc", "topic", "importance", "scope", "fact"],
}


def _norm(s):
    s = (s or "").lower().replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", re.sub(r"[^\w%'\" .,₹$-]", " ", s)).strip(" .")


def _toks(s):
    return _norm(s).replace(",", " ").replace(".", " ").split()


def quoted(fact, title, text):
    """True if `fact` is (almost) word for word a sentence or two of the article: exact match after normalising, or
    >= 90% of its words appear in order in one stretch of the article (the model sometimes drops a comma or 'and')."""
    if _norm(fact) in _norm(f"{title}. {text}"):
        return True
    import difflib
    f = _toks(fact)
    if len(f) < 5:
        return False
    a = _toks(f"{title}. {text}")
    sm = difflib.SequenceMatcher(None, a, f, autojunk=False)
    blocks = [b for b in sm.get_matching_blocks() if b.size]
    if not blocks:
        return False
    # the matched words must sit in one stretch of the article, not be scattered
    span = blocks[-1].a + blocks[-1].size - blocks[0].a
    return sum(b.size for b in blocks) / len(f) >= 0.9 and span <= len(f) * 1.3


def check(model, title, body):
    """-> dict(keep, topic, importance, scope, fact, why)."""
    text = (body or "")[:2500]
    out = {"keep": False, "topic": "none", "importance": 0, "scope": "", "fact": "", "why": ""}
    try:
        r = model.json(SYSTEM, f"Title: {title}\nArticle:\n{text}", SCHEMA, temperature=0.0, max_tokens=220)
    except Exception as e:
        out["why"] = f"error: {str(e)[:150]}"
        return out
    topic, fact = r.get("topic"), (r.get("fact") or "").strip()
    out.update(topic=topic or "none", importance=int(r.get("importance") or 0), scope=r.get("scope") or "", fact=fact)
    if not r.get("ssc") or topic not in TOPICS:
        out["why"] = "model: no"
    elif out["importance"] < 3:
        out["why"] = f"importance {out['importance']}"
    elif out["scope"] == "state" and out["importance"] < 4:
        out["why"] = f"state news, importance {out['importance']}"
    elif len(fact.split()) < 5 or not quoted(fact, title, text):
        out["why"] = "fact not found word for word in the article"
    elif not TOPIC_RE[topic].search(fact) and not TOPIC_RE[topic].search(title or ""):
        out["why"] = f"fact has no {topic} words"
    elif NOT_FACT.search(fact):
        out["why"] = "fact is an opinion/warning/demand/forecast"
    else:
        out.update(keep=True, why="kept")
    return out
