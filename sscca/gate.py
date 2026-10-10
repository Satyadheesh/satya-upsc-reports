"""Step 1 of the SSC current-affairs runner: is this news article SSC CGL General Awareness material?

A strict model call (default no) plus code checks. An article becomes an SSC card only if:
  1. the model says ssc = true with a topic and importance >= 3;
  2. its fact is a sentence found word for word in the article;
  3. the fact contains words of that topic (an award story names an award, a sports story a result ...);
  4. the fact is not an opinion, warning, demand, allegation or forecast;
  5. (card_ok) the card asks about the story in the headline, not a side mention in the article.
"""
import re

GATE_VERSION = "sscg-4"

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
                   r"new (?:chief|head|chairman|chairperson|governor|director)|re-?appointed|nominated|selected as|elevated|"
                   r"joins? as|joined (?:\w+ ){0,4}as|md (?:&|and) ceo|chief executive|ceo",
    "award": r"award\w*|prize\w*|honour\w*|honor\w*|medal\w*|conferred|felicitated with|ratna|padma|nobel|samman|puraskar|trophy",
    "sports": r"won|wins|win|winner|medal\w*|golds?|silvers?|bronzes?|clinch\w*|title|champion\w*|trophy|cup|record|defeat\w*|beat|final|"
              r"qualif\w*|tournament|olympic\w*|games|league|series|host\w*",
    "scheme": r"scheme\w*|yojana|mission|portal|app\b|apps|application|platform|tool|dashboard|roadmap|programme|program\b|"
              r"initiative|abhiyan|launch\w*|unveil\w*|rolled out|outlay|drive|"
              r"corridor|phase|project|approv\w*|cabinet|sanction\w*",
    "law_verdict": r"bill|act\b|ordinance|amendment|notif\w*|passed|enacted|verdict|judgment|judgement|ruled|struck down|upheld|"
                   r"dismiss\w*|reject\w*|quash\w*|stay(?:ed)?|strength|rules|regulations|gazette|published|assent|"
                   r"lift\w* (?:a |the )?ban|permit\w*|guidelines|norms",
    "summit_agreement": r"summit|conference|congress|meeting|agreement|mou|memorandum|treaty|pact|accord|signed|dialogue|"
                        r"forum|host\w*|plenipotentiary|partnership",
    "defence": r"exercise|missile|test\w*|induct\w*|commission\w*|warship|submarine|aircraft|jets?|drdo|navy|naval|army|"
               r"air force|iaf|defence|defense|brahmos|agni|tejas",
    "report_index": r"report|index|rank\w*|survey|ranking|indicator\w*|released|published",
    "economy": r"rbi|reserve bank|repo|gdp|gst|forex|reserves|inflation|cpi|wpi|nso|cabinet|ministry|council|sebi|outlay|"
               r"budget|crore|lakh crore|approved|collection\w*|deficit|growth|finance commission|grants?|devolution|"
               r"notif\w*|norms|msp|minimum support price",
    "science_space": r"isro|space|satellite|launch\w*|mission|rocket|orbit|discover\w*|scientists?|developed|first|nasa|esa|"
                     r"gaganyaan|chandrayaan|technology|research|cern|competition|won|wins|telecommunication",
    "environment": r"species|reserve|sanctuary|national park|ramsar|wetland|tiger|elephant|iucn|conservation|wildlife|"
                   r"forest|biodiversity|released|climate|discover\w*|lions?|tigers?|leopards?|cheetahs?|rhinos?|"
                   r"bustards?|vultures?|population|census|estimat\w*",
    "important_day": r"day\b|diwas|week\b|observed|celebrated|commemorat\w*|theme",
    "book_author": r"author\w*|written by|penned|novel|memoir|autobiography|biography",
    "obituary": r"passed away|died|dies|demise|death|no more|breathed (?:his|her) last",
    "first_record": r"first|largest|highest|biggest|longest|tallest|youngest|oldest|fastest|driest|wettest|hottest|"
                    r"lowest|record|gi tag|geographical indication|unesco|only",
    "international": r"elected|sworn|president|prime minister|joins|joined|member\w*|withdraw\w*|treaty|united nations|un\b|"
                     r"summit|elections?|vote[sd]?|polls?|round|won|wins|beat|defeated|host\w*",
}
TOPIC_RE = {k: re.compile(r"(?<![\w-])(?:" + v + r")(?![\w])", re.I) for k, v in TOPIC_WORDS.items()}
# Opinions, warnings, demands, allegations and forecasts are not facts an SSC paper asks about.
NOT_FACT = re.compile(r"(?<![\w-])(?:warn(?:s|ed|ing)?|urge[sd]?|urging|allege[sd]?|alleging|claim(?:s|ed)?|criticis\w*|"
                      r"criticiz\w*|slam(?:s|med)?|demand(?:s|ed)?|expect(?:s|ed)?|likely to|could|might|predict\w*|"
                      r"forecast\w*|poll|analysts?|experts? (?:say|said|believe)|speculat\w*|achievable|needs? to|should|"
                      r"consider(?:s|ed|ing)?|mulls?|mulling)(?![\w])", re.I)

# From abroad only the big items: these topics need importance >= 4 when the scope is international.
ABROAD_STRICT = {"appointment", "defence", "international", "law_verdict", "obituary", "economy", "sports", "science_space"}
# Topics that need importance >= 4 everywhere (a "possible" appointment or economy item was mostly noise in the first days)
MIN4 = {"appointment", "economy"}
# Topics whose words must be in the fact itself, not only in the headline
FACT_WORDS_ONLY = {"appointment", "law_verdict", "book_author"}
# These topics count only with an Indian link (the model sometimes calls a US law or a Gulf meeting "national")
INDIA_REQUIRED = {"law_verdict", "scheme", "economy", "defence", "summit_agreement", "first_record"}
# At importance 3 these topics are state news when they name a state or city, even if the Centre is mentioned
# (a state's share of a central scheme, a state award, a state minister)
STATE_SENSITIVE = {"scheme", "economy", "award", "law_verdict", "appointment"}
# A sports item of importance 3 counts only from a big event
BIG_EVENT = re.compile(r"(?<![\w-])(?:olympic\w*|paralympic\w*|asian games|commonwealth|world cup|world championships?|"
                       r"khelo india|national games|grand slam|wimbledon|us open|french open|australian open|"
                       r"thomas cup|uber cup|davis cup|ranji trophy|santosh trophy|durand cup|ipl|wpl|chess olympiad|"
                       r"diamond league|hockey india|pro kabaddi|world record|national record|asian championships?)(?![\w])", re.I)
HEARING = re.compile(r"(?<![\w-])(?:hears?|hearing|issues? notice|notices? to|to examine|seeks?|sought|petition filed|"
                     r"pleas? filed|adjourn\w*|reserves? (?:its )?(?:verdict|order|judgment))(?![\w])", re.I)
MARKET = re.compile(r"(?<![\w-])(?:nifty\w*|sensex|shares?|stocks?|stock market|equities|mutual funds?|ipo)(?![\w])", re.I)
# A role the question gives the answer must be in the article (a state minister is not a "Union Minister")
ROLES = re.compile(r"(?<![\w-])(union minister|chief minister|prime minister|governor|president|chief justice|"
                   r"chief election commissioner|cabinet minister|minister of state)(?![\w])", re.I)
# A foreign appointment counts only for a top post (head of state/government, an international body, a central bank).
TOP_POST = re.compile(r"(?<![\w-])(?:president|prime minister|chancellor|premier|king|queen|monarch|pope|"
                      r"secretary[- ]general|director[- ]general|managing director|chair(?:man|person|woman)?|"
                      r"governor|chief justice|head of state|head of government)(?![\w])", re.I)
# An award from abroad is SSC material only if it is a world-level award or an Indian wins it
# (a US Presidential Medal of Freedom or National Medal of Science is not asked).
GLOBAL_AWARD = re.compile(r"(?<![\w-])(?:nobel|booker|pulitzer|oscars?|academy awards?|grammy|bafta|cannes|golden globe|"
                          r"magsaysay|abel prize|fields medal|turing award|templeton|world food prize|earthshot|"
                          r"right livelihood|wolf prize|kyoto prize|champions of the earth|ballon d'or|laureus|"
                          r"unesco|united nations|un |fifa|icc |olympic|international booker|dadasaheb|padma|bharat ratna)", re.I)
# Winner not known yet: "will announce", "to be announced", "nominated for", "shortlisted" ("X to be conferred
# the Phalke award" is fine: the winner is named)
NOT_YET = re.compile(r"(?<![\w-])(?:will (?:be )?announce\w*|to be announced|nominated for|shortlist\w*|longlist\w*|"
                     r"finalists?|in the running|frontrunners?)(?![\w])", re.I)
INDIA = re.compile(r"(?<![\w-])(?:india|indian|indo|bharat)(?![\w])", re.I)
# A low-importance "national" item that names an Indian state or city and nothing national is state news.
PLACES = re.compile(r"(?<![\w-])(?:andhra|arunachal|assam|bihar|chhattisgarh|goa|gujarat|haryana|himachal|jharkhand|"
                    r"karnataka|kerala|madhya pradesh|maharashtra|manipur|meghalaya|mizoram|nagaland|odisha|punjab|"
                    r"rajasthan|sikkim|tamil nadu|telangana|tripura|uttar pradesh|uttarakhand|west bengal|"
                    r"jammu|kashmir|ladakh|puducherry|chandigarh|delhi|mumbai|chennai|kolkata|bengaluru|bangalore|"
                    r"hyderabad|ahmedabad|pune|lucknow|jaipur|bhopal|patna|vijayawada|visakhapatnam|amaravati|guntur|"
                    r"tirupati|kochi|kottayam|thiruvananthapuram|kozhikode|malappuram|wayanad|madurai|coimbatore|"
                    r"mysuru|mysore|mangaluru|warangal|nagpur|indore|surat|vadodara|kanpur|varanasi|guwahati|"
                    r"bhubaneswar|ranchi|raipur|dehradun|shimla|srinagar|district|taluk|mandal|municipal\w*|"
                    r"corporation|panchayat|constituency)(?![\w])", re.I)
NATIONAL = re.compile(r"(?<![\w-])(?:centre|central|union|national|india'?s?|indian|ministry|prime minister|pm|"
                      r"president|supreme court|parliament|niti|isro|drdo|rbi|iaf|army|navy|cabinet|nationwide|"
                      r"all-india|first)(?![\w])", re.I)

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

RBI's weekly forex reserves, GST collections, GDP, inflation, IIP and core-sector data count as economy.

importance: 5 = certain to be asked (national appointment, major award, big sports title, central scheme, RBI decision);
4 = likely; 3 = possible; 1-2 = unlikely (then answer ssc = false).
fact: copy ONE sentence from the article, word for word, that contains the askable fact. The fact must be the
story of the headline itself. If the article only mentions an askable fact on the side (a Nobel Prize in a story
about a logo, a medal in a story about a speech), answer ssc = false.
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


INDIA_LINK = re.compile(r"(?<![\w-])(?:lok sabha|rajya sabha|niti aayog|rbi|reserve bank of india|isro|drdo|sebi|"
                        r"union (?:cabinet|government|minister|ministry|budget)|centre|central government|crore|lakh|"
                        r"rs\.?|inr|iaf|indian army|indian navy|modi|delhi|union \w+ ministry|ministry of \w+|national|"
                        r"pm[- ]\w+|pradhan mantri|swadesh darshan|jal jeevan|ayushman|guinness)(?![\w])|₹", re.I)


FOREIGN = re.compile(r"(?<![\w-])(?:u\.?s\.?|usa|united states|american|america|white house|pentagon|congress(?:man|woman)|"
                     r"britain|british|u\.?k\.?|england|china|chinese|beijing|pakistan\w*|russia\w*|ukrain\w*|"
                     r"israel\w*|iran\w*|saudi|europe\w*|eu|canada|canadian|australia\w*|japan\w*)(?![\w])", re.I)


def rules(topic, importance, scope, fact, title, text):
    """Code checks on the model's answer. -> reason it fails, or "" if it passes."""
    where = f"{title} {fact}"
    if importance < 3:
        return f"importance {importance}"
    if scope == "state" and importance < 4:
        return f"state news, importance {importance}"
    if topic in MIN4 and importance < 4:
        return f"{topic} needs importance 4"
    if scope == "international" and topic in ABROAD_STRICT and importance < 4 and not (
            topic in ("sports", "science_space") and INDIA.search(where)):
        return f"foreign news, importance {importance}"
    if topic in INDIA_REQUIRED and not (INDIA.search(where) or PLACES.search(where) or INDIA_LINK.search(where)):
        return "no Indian link"
    if topic in INDIA_REQUIRED and FOREIGN.search(where) and not INDIA.search(where):
        return "foreign news, no Indian link"
    if MARKET.search(title or ""):
        return "market news"
    if len(fact.split()) < 5 or not quoted(fact, title, text):
        return "fact not found word for word in the article"
    if not TOPIC_RE[topic].search(fact) and (topic in FACT_WORDS_ONLY or not TOPIC_RE[topic].search(title or "")):
        return f"fact has no {topic} words"
    if topic != "law_verdict" and (NOT_FACT.search(fact) or NOT_FACT.search(title or "")):
        return "fact is an opinion/warning/demand/forecast"  # verdicts may quote what a side claimed or demanded
    if topic == "law_verdict" and HEARING.search(where):
        return "court hearing or notice, not a verdict"
    if topic == "appointment" and scope == "international" and not INDIA.search(where) and not TOP_POST.search(fact):
        return "foreign appointment, not a top post"
    if topic == "defence" and scope == "international" and not INDIA.search(where):
        return "foreign military news, India not involved"
    if topic == "award" and NOT_YET.search(fact):
        return "award not given yet"
    if topic == "award" and not INDIA.search(where) and not GLOBAL_AWARD.search(where) and (
            scope == "international" or FOREIGN.search(where)):
        return "foreign national award"
    if topic == "sports" and importance < 4 and not BIG_EVENT.search(where):
        return "sports, not a big event"
    if importance < 4 and PLACES.search(where) and (topic in STATE_SENSITIVE or not NATIONAL.search(where)):
        return f"local news, importance {importance}"
    return ""


def _words(s):
    return [w.strip("'\"") for w in _toks(s) if w.strip("'\"") not in {"the", "a", "an", "of", "and", "in", "at", "on", "for", "to", "by"}]


def on_story(card, fact, title):
    """The card is about the headline's story: the question and answer share a word with the headline, and with the
    gate's fact they share two (stemmed, without stop words). Catches a Nobel card from a story about a logo."""
    from .dedupe import words
    t = words(title)
    if len(t) < 3 or _norm(title)[:60] in _norm(fact):  # too short to judge, or the "headline" is the fact sentence
        return True
    qa = words(f"{card.get('ssc_question') or ''} {card.get('ssc_answer') or ''}")
    return bool(t & qa) and len(t & (qa | words(fact))) >= 2


def card_ok(card, fact, title, text):
    """The card must ask about this news: its answer is in the gate's fact or the headline (not static trivia such as
    'who founded the Nobel Prize'), it is about the headline's story, and any role the question gives
    ('Union Minister') is in the article."""
    ans = _words(card.get("ssc_answer") or "")
    if not ans:
        return "card has no answer"
    if not on_story(card, fact, title):
        return "card is not about the headline story"
    hay = {w.strip("'\"") for w in _toks(f"{title} {fact}")}
    if sum(w in hay for w in ans) < -(-len(ans) * 3 // 5):  # at least 60%, rounded up
        return "card answer is not in the news fact"
    low = _norm(f"{title} {text}")
    for role in ROLES.findall(card.get("ssc_question") or ""):
        if _norm(role) not in low:
            return f"card question says '{role}', the article does not"
    return ""


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
    else:
        out["why"] = rules(topic, out["importance"], out["scope"], fact, title, text) or "kept"
        out["keep"] = out["why"] == "kept"
    return out
