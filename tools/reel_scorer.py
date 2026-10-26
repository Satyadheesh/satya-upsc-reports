"""Universal Viral Reels Scorer (Gemma 4 12B).

Scores incoming raw news articles across all topics (cinema, infrastructure, science,
curiosities, consumer hacks, defense, sports, etc.) on viral potential (0 to 10)
for Instagram Reels & YouTube Shorts, enforcing a strict zero-defamation/zero-blame gate.

Results are saved to `reel_candidates` in the UPSC DB.
"""
import argparse
import json
import os
import re
import time

from common.db import close_all, in_chunks, main_db, upsc_db
from kit.model import MODEL_NAME, Model, download

SYSTEM = """You are an expert executive producer for viral short-form news videos (Instagram Reels & YouTube Shorts) for ordinary Indian audiences.
Your goal is to evaluate news stories across ALL topics (politics & political funding/chanda, cinema/Bollywood, infrastructure, science, space, quirky/bizarre curiosities, defense, sports, consumer hacks, economy, nature) and score their viral potential.

EVALUATION CRITERIA (0 to 10):
1. Scroll-Stopping Hook (0-2): Does the story start with a fascinating contrast, question, or paradox that immediately stops someone scrolling?
2. Scale & Wow Factor (0-2): Does it feature an impressive physical scale, record, massive budget, high number, or unusual feat?
3. India Relevance (0-2): Does it directly involve India: Indian leaders, parties, institutions, public money, laws, or a clear effect on ordinary Indians? A foreign story with no India angle scores 0 here.
4. Talkability & Shareability (0-4): Would an ordinary Indian share this on WhatsApp with friends or family saying "Did you know this?" (e.g. mind-blowing political donation/chanda figures, electoral bond disclosures, declared neta assets vs reality, giant taxpayer spending, viral cinema/sports milestones, tech wonders).

CAPS:
- A foreign business, tech or celebrity story with no India angle (a US company's deal, a foreign billionaire's plan) scores at most 5 overall: our audience is Indian and follows Indian news.

WHAT TO REJECT (Score 0):
- Routine partisan name-calling, spokesperson bickering, or unverified verbal allegations without official records.
- Mundane procedural press releases or local party committee reshuffles.
- Violent crimes, murders, sexual offenses, tragic deaths, accidents with casualties, grief/mourning.
- Personal celebrity scandals, divorces, custody battles.
- Defamation hazards (claims must be grounded in official records, EC filings, CAG audits, affidavits, or established data).

Answer in JSON:
- "viral_score": Integer 0 to 10 (7+ means excellent reel material, 0 if rejection criteria met)
- "topic": Short category string (e.g. "politics_funding", "cinema", "infrastructure", "science_space", "consumer_hack", "defence", "curiosity", "sports", "economy")
- "hook_angle": A compelling opening hook or question in conversational Hindi (Devanagari)
- "wow_fact": The single most impressive number, record, or fact in the story
- "why": One short sentence explaining the score
"""

# v2 (Yash, 26 Oct 2026: "the selection is not good enough, a normal Indian who is not so intellectual won't understand"):
# the common-man test first. A minister's corruption backed by a raid/FIR/chargesheet/court/audit passes; court procedure,
# agency processes, party affairs and government systems don't. Test with --select-test; live with REEL_SELECT=v2.
SYSTEM_COMMON = """You are the executive producer of SatyaDheesh's Hindi news reels for ORDINARY Indians: a shopkeeper in
Kanpur, a farmer's son in Bihar, a nurse in Indore, a college student in Patna. Smart people who do not follow the news
closely and have no background on any story. Score how well this story will work for them as a 50-second reel (0 to 10).

FIRST, THE COMMON-MAN TEST. Write "one_line_hi": the whole story in one plain Hindi sentence that a neighbour would
understand with no background. Then ask two questions:
A. Would they understand that sentence without knowing any institution, procedure, law or earlier episode?
B. Does it touch their life or something they feel strongly about? For example: money in their pocket (prices, petrol,
   LPG, gold, taxes, salaries, pensions, loans, bank and UPI rules), jobs, exams and results, farming and crops, trains
   and travel, health and hospitals, schools, government schemes and payments, weather and floods, safety, public money
   stolen or wasted (a minister or officer accused of taking crores, backed by a raid, FIR, chargesheet, court order or
   audit), a promise made to people, cricket, films, a real human story, a record or a wonder from India.
If the answer to A or B is no, the story scores at most 4. Stories that usually fail: court procedure (appeals, hearings,
petitions about how a case was handled), agency and government processes, party organisation and internal fights,
government software and systems, reports and committees, diplomatic statements, stories that need earlier background,
and stories that matter mainly to people who follow politics or policy closely. A political story passes only when it
is about something people feel (prices, jobs, a promise, a scheme, public money, a scam backed by official action).

THEN SCORE the stories that pass (add these up):
1. Touches the viewer's life or money, or makes them angry, proud or amazed (0-4)
2. Simple to tell: one clear point, few names, no jargon needed (0-2)
3. Scroll-stopping hook: a surprising contrast, a number a viewer can picture, or a question (0-2)
4. Talkability: would they forward it on WhatsApp to family saying "देखो ये"? (0-2)

CAPS:
- A foreign story with no direct effect on ordinary Indians scores at most 4.

WHAT TO REJECT (Score 0):
- Routine partisan name-calling, spokesperson bickering, or unverified verbal allegations without official records.
- Mundane procedural press releases or local party committee reshuffles.
- Violent crimes, murders, sexual offenses, tragic deaths, accidents with casualties, grief/mourning.
- Personal celebrity scandals, divorces, custody battles.
- Defamation hazards (claims must be grounded in official records, EC filings, CAG audits, affidavits, or established data).

Answer in JSON:
- "one_line_hi": the story in one plain Hindi sentence (Devanagari)
- "viral_score": Integer 0 to 10 (7+ means excellent reel material, 0 if rejection criteria met)
- "topic": Short category string (e.g. "politics_funding", "corruption", "prices", "jobs_exams", "schemes", "cinema", "infrastructure", "science_space", "consumer_hack", "defence", "curiosity", "sports", "economy", "weather")
- "hook_angle": A compelling opening hook or question in conversational Hindi (Devanagari)
- "wow_fact": The single most impressive number, record, or fact in the story
- "why": One short sentence explaining the score
"""
SCHEMA_COMMON = {"type": "object", "properties": {"one_line_hi": {"type": "string"},
                 "viral_score": {"type": "integer", "minimum": 0, "maximum": 10}, "topic": {"type": "string"},
                 "hook_angle": {"type": "string"}, "wow_fact": {"type": "string"}, "why": {"type": "string"}},
                 "required": ["one_line_hi", "viral_score", "topic", "hook_angle", "wow_fact", "why"]}


# v3 (Yash, 26 Oct 2026: "it is not about aam aadmi... there can be a lot of news a normal person is interested in"):
# any topic a normal Indian would stop scrolling for, as long as it can be told clearly in 30 seconds.
SYSTEM_INTEREST = """You are the executive producer of SatyaDheesh's Hindi news reels. The viewer is a normal Indian
scrolling on their phone (Kanpur, Patna, Indore): smart, but not following the news closely. Score this story 0-10:
would they stop scrolling and want to know about it, and can it be told so they understand it in 30 seconds?

Any topic can work: politics and politicians, crime and scams, cricket and sport, films, ISRO and science, defence,
India and the world, money and prices, government decisions, strange or surprising events, human stories.

First write "one_line_hi": the whole story in one plain Hindi sentence a normal person would understand.

Score (add up):
1. Interest (0-4): would a normal Indian want to know this? Big names, big stakes, drama, surprise, anger, pride,
   money, something new that really happened.
2. Clear in 30 seconds (0-2): can it be told with at most one line of background, without insider knowledge?
3. Hook (0-2): a surprising contrast, a big number people can picture, or a question.
4. Talkability (0-2): would they talk about it or forward it?

Score at most 4: nothing really happened yet (a hearing adjourned, a meeting held, a committee formed, a routine
statement); insider or procedural stories that can't be made clear in 30 seconds; a foreign story with no India link.

WHAT TO REJECT (Score 0):
- Routine partisan name-calling, spokesperson bickering, or unverified verbal allegations without official records.
- Mundane procedural press releases or local party committee reshuffles.
- Violent crimes, murders, sexual offenses, tragic deaths, accidents with casualties, grief/mourning.
- Personal celebrity scandals, divorces, custody battles.
- Defamation hazards (claims must be grounded in official records, EC filings, CAG audits, affidavits, or established data).

Answer in JSON:
- "one_line_hi": the story in one plain Hindi sentence (Devanagari)
- "viral_score": Integer 0 to 10
- "topic": Short category string (e.g. "politics", "politics_funding", "corruption", "crime_scam", "sports", "cinema", "science_space", "defence", "economy", "prices", "jobs_exams", "schemes", "weather", "world", "curiosity")
- "hook_angle": A compelling opening hook or question in conversational Hindi (Devanagari)
- "wow_fact": The single most impressive number, record, or fact in the story
- "why": One short sentence explaining the score
"""
SELECT_TAG = {"v2": "+common", "v3": "+v3"}


def select_mode():
    return os.environ.get("REEL_SELECT", "v1")


def select_v2():   # any of the newer rubrics (JSON with one_line_hi)
    return select_mode() in SELECT_TAG


def select_system():
    return SYSTEM_INTEREST if select_mode() == "v3" else SYSTEM_COMMON


SCHEMA = {
    "type": "object",
    "properties": {
        "viral_score": {"type": "integer", "minimum": 0, "maximum": 10},
        "topic": {"type": "string"},
        "hook_angle": {"type": "string"},
        "wow_fact": {"type": "string"},
        "why": {"type": "string"}
    },
    "required": ["viral_score", "topic", "hook_angle", "wow_fact", "why"]
}


def decompress(blob, limit=1200):
    if not blob:
        return ""
    import zlib
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
        for wbits in (15, 47):
            try:
                return zlib.decompress(b, wbits).decode("utf-8", "replace")[:limit]
            except Exception:
                pass
        try:
            return b.decode("utf-8")[:limit]
        except Exception:
            pass
    return ""


SCRIPT_SYSTEM_CHARLIE = """You are an expert Indian short-form news storyteller who writes high-retention Instagram Reel scripts in natural, conversational Hindi.

YOUR FIRST JOB: an ordinary viewer understands the story and could retell it. Clarity beats completeness: leave out a
detail (a technical figure, a unit, an official body's full name) rather than say it in a way they won't understand.
Every other instruction below comes after this one.

TASK
Read the news article below and write a Reel narration script in Hindi (Devanagari script). The script has 4 parts: Hook, Core, Twist, Engagement. Return it as a single JSON object with the exact keys listed under OUTPUT FIELDS.

WHO YOU ARE TALKING TO (Yash, 24 Oct 2026: "the script needs to connect with the very common man")
Your viewer is an ordinary Indian scrolling on their phone: a shopkeeper in Kanpur, a farmer's son in Bihar, a nurse in
Indore, a college student in Patna. Smart, but not following this story, not an expert, and they have about 50 seconds.
They speak everyday Hindustani: Hindi mixed with the English words everyone uses (कोर्ट, पुलिस, वोट, टारगेट, जॉब…).

HOW TO WRITE FOR THEM
1. Understand the story yourself first. Write plain_story_hi: the whole story in 1-2 sentences you would tell a neighbour
   at a chai stall: who wants what, why, and what happened or was decided. Every *_say line follows that story; nothing
   that doesn't serve it goes in.
2. Talk, don't read. Say it the way you would explain it to that neighbour: short spoken sentences, "आप", the words people
   actually use. Not a news anchor, not a textbook, not a government press note. Wherever a formal or official word comes
   to mind, use the word an ordinary person would say instead.
3. Translate the system into life. Committees, authorities, legal and technical terms, units (like TMC, cusecs, MW) and
   acronyms mean nothing to this viewer: say what they DO or what they MEAN ("पानी बांटने वाली कमेटी", "रोज़ कुछ पानी").
   Explain an unavoidable term in the same breath with "यानी".
4. Numbers: only the 2-3 a viewer can picture (rupees, people, days, a percent, a date). Never rename a technical quantity
   into a vague word; compare it instead ("मांग का करीब पांचवां हिस्सा", "आधे से भी कम"). No decimals in speech.
5. In a dispute, give each side one simple line: what it wants and why.
6. Make it matter: one line on what this means for people like the viewer (prices, jobs, fees, water, safety, their
   vote), only if the article supports it.
7. Simpler words, same facts: never change a number, a tense or who did what while simplifying.
8. Read it back as that shopkeeper before you answer: could he repeat the story to a friend? Would any word or number make
   him pause? If so, rewrite that line.
- Do not use hashtags, emojis, or stage directions in any field.

EXAMPLE (an inter-state water dispute):
  Bad (an official note read aloud): "कावेरी जल विनियमन समिति ने बिलिगुंडलु पर 15 दिन तक 3,000 क्यूसेक्स पानी छोड़ने का
  निर्देश दिया। कर्नाटक के बांधों में 46.510 यूनिट पानी है।"
  Good: "कावेरी के पानी पर कर्नाटक और तमिलनाडु फिर आमने-सामने हैं। तमिलनाडु कहता है, उसके किसानों की फसल सूख रही है, उसे
  और पानी चाहिए। कर्नाटक का जवाब है, इस बार नदी में आधे से भी कम पानी आया, पहले लोगों के पीने का पानी बचाना है। अब पानी
  बांटने वाली कमेटी ने बीच का रास्ता निकाला: 15 दिन तक कर्नाटक रोज़ कुछ पानी छोड़ेगा, लेकिन ये मांग का करीब पांचवां
  हिस्सा ही है।"

VOICE / TTS ENGINE LIMITATIONS & PHONETIC RULES (Critical)
The *_say fields are synthesized directly by an AI voice model. Neural TTS engines struggle with literary grammar, complex inflections, and stacked character markers:
- Spoken Flow over Literary Grammar: Write strictly how an Indian creator speaks conversationally on camera. Avoid rare grammatical declensions, literary plural forms, or stiff bureaucratic phrasing that cause AI voices to mispronounce or slur.
- Phonetic Simplicity: Choose simple, everyday spoken vocabulary over complex consonant clusters or stacked character modifiers. If a concept can be expressed with a standard, clean colloquial word, always prefer the simpler one.
- Conversational Calls-to-Action: Keep engagement prompts conversational and natural (e.g. inviting viewers to share their thoughts or experiences in the comments), rather than abrupt or forceful single-word imperative commands.
- Symbols and Units: NEVER use symbols such as ₹, $, %, &, or abbreviations like "Rs." or "km". Always write them out as spoken Hindi words: "4000 रुपये" (not ₹4000), "20 परसेंट" (not 20%), "5 किलोमीटर" (not 5 km).
- Punctuation for Breathing: Use commas and short sentences to provide natural breath pauses for the AI voice. Avoid long, complex multi-clause sentences.
The ₹ symbol may appear ONLY in the on-screen fields: headline_hi and twist_stat.

INTRODUCE EVERY PERSON (viewers from any state may not know who anyone is)
- The FIRST time a person is named in the *_say lines, say who they are in a few words just before the name: role + party or state, e.g. "शिवसेना (UBT) के सांसद संजय राउत", "महाराष्ट्र के मुख्यमंत्री देवेंद्र फडणवीस". After that the name alone is fine.
- Everyone already knows the top offices: say "प्रधानमंत्री मोदी", "गृह मंत्री अमित शाह" (the office, no party). Party only when it matters to the story. Every named person still gets a role: people[].role_hi is never empty.
- If the person is listed in the PEOPLE block, use that role (for the top offices above, just the office is enough). If not, describe them only as the article does (e.g. "पार्टी प्रवक्ता", "याचिकाकर्ता"); never invent or guess a title.
- Name at most 3 people in the whole reel. Anyone else becomes a description without a name ("एक भाजपा नेता", "एक अधिकारी").
- Parties, agencies and acronyms get their full name once: "प्रवर्तन निदेशालय (ED)", "मतदाता सूची का विशेष गहन पुनरीक्षण (SIR)".
- Within hook_say or the start of core_say, add one short context line so a viewer from any state can follow: where this is and why it matters.

OUTPUT FIELDS
- plain_story_hi: the story in 1-2 plain sentences (step 1 of HOW TO WRITE FOR THEM). Not shown on screen.
- people: every person named anywhere in the *_say lines, in order of first mention: [{"name_hi": "संजय राउत", "role_hi": "शिवसेना (UBT) के सांसद"}]. role_hi is exactly the role you used when introducing them (from the PEOPLE block when they are listed there). Empty list if nobody is named.
- headline_hi: catchy on-screen headline, max 8 words.
- subtitle_hi: one short on-screen line under the headline (max 9 words) that adds the key fact the headline leaves out (who, where or how much). No symbols except ₹; empty string if there is nothing to add.
- hook_say: 1-2 spoken lines that grab attention immediately (a surprising fact, a question, or a contrast).
- core_title_hi: short title for the core news card, max 8 words.
- core_points_hi: exactly 2 or 3 very short on-screen bullet points in Hindi (e.g. ["22 नए सरकारी केंद्र शुरू", "किडनी के मरीज़ों को सीधा फ़ायदा", "सत्यापित डेटा"]). Max 8 words per bullet.
- core_say: 3-4 spoken lines: what actually happened, in simple and concrete terms (who, what, where, how much), plus one line of background (how we got here).
- twist_stat: the single key number or word shown on screen (e.g. "₹999" or "22 केंद्र"). It must be a DIFFERENT number or word from any in headline_hi: the viewer has already seen that one.
- twist_label: short label for that number (e.g. "डायलिसिस फ़ीस" or "नए केंद्र").
- twist_detail_hi: 1 short on-screen line in Hindi summarizing the ground reality, budget, or contrast (max 10 words, e.g. "प्राइवेट में ₹4,000 तक खर्च, सरकारी से बड़ी राहत").
- twist_say: 2-3 spoken lines: the ground reality, the key number or the contrast, and what happens next (a hearing, deadline, vote, decision or rollout), if the article says.
- question_hi: short on-screen question for the engagement card.
- engagement_title_hi: 2-4 word heading above that question, specific to this story (e.g. "पानी पर आपका फ़ैसला", "पेपर लीक: आगे क्या?"). Not a generic "आपकी राय".
- engagement_say: one natural, thought-provoking question that invites viewers to comment.

RULES
- Use only facts from the article. Do not invent numbers, names, or quotes.
- Keep the whole spoken script (hook_say + core_say + twist_say + engagement_say) to 110-140 Hindi words in total,
  roughly 45-55 seconds of speech. Never more than 140 words: count them. hook_say max 25 words, core_say max 55,
  twist_say max 40, engagement_say max 20.
- Make it rich, not padded. Every script carries: (1) one line of background, (2) at least one concrete detail a viewer
  can picture: a date, an amount in rupees, a person or a place, (3) what happens next, if the article says. Skip a point
  rather than invent it, and skip any figure the viewer couldn't picture.
- Output ONLY the JSON object. No explanation, no markdown, no code fences, no text before or after.
"""

SCRIPT_SYSTEM = SCRIPT_SYSTEM_CHARLIE

# Political reels (Yash, 22 Oct 2026: political stories get the most traction; make them sharper, but legally safe)
POLITICAL_TOPICS = {"politics", "politics_funding", "governance", "elections", "election", "parliament", "policy"}


def is_political(topic):
    t = str(topic or "").lower()
    return t in POLITICAL_TOPICS or "politic" in t or "election" in t


SCRIPT_POLITICAL_EXTRA = """
POLITICAL STORY MODE (this story is political)
Make it sharp and questioning, the way a fearless Hindi news creator talks: open on a contradiction, a broken promise,
a U-turn, a big number, or "who said what". Hold power to account with questions. But it must be legally safe:
1. Attribute every claim. core_say MUST start with "{source} की रिपोर्ट के मुताबिक". Tie each statement or accusation to
   whoever made it: "कांग्रेस का आरोप है", "भाजपा का दावा है", "मंत्री ने कहा". Never present a claim as your own.
2. An allegation stays an allegation: use "आरोप है", "दावा किया गया", "सवाल उठ रहे हैं". Never say or imply that a named
   person or party is guilty, corrupt or a criminal unless the article reports a court conviction.
3. Never use abusive or loaded labels for anyone (चोर, घोटालेबाज़, भ्रष्ट, गद्दार, जुमलेबाज़ and the like).
4. Criticise only actions, decisions, policies, public statements and public records; never anyone's family, caste,
   religion, looks or private life.
5. If the article gives the other side's reply or denial, include it in one short line ("सरकार/पार्टी का कहना है ...").
6. End with a question to the viewer, never a verdict (e.g. "क्या जनता को इसका जवाब नहीं मिलना चाहिए?").
7. Be equally sharp with every party and government; no cheering or mocking any side.
8. headline_hi may be a pointed question. Facts, numbers and names only from the article.
9. The on-screen text (headline_hi, core_points_hi, twist_stat, twist_label, twist_detail_hi) follows the same rules:
   any accusation carries "आरोप" or "दावा" ("43,000 करोड़ के भ्रष्टाचार का आरोप", never "43,000 करोड़ का भ्रष्टाचार").
10. Criminal cases (murder, assault, fraud): only what the investigation or court has done, as reported, attributed;
   never connect a named person to a crime beyond what the report itself says.
"""

SCRIPT_SOURCE_RULES = """
SOURCE TEXT
You get SUMMARY (our short rewrite) and, when available, ORIGINAL ARTICLE (the full report: quotes, who said what,
the other side's reply, numbers). Use the ORIGINAL to understand the story, for attribution, and for the few details
this viewer needs; most of its figures and official names are NOT for the script. Write everything in your own words:
never translate its sentences word for word; quote only short statements, always naming who said them.
STYLE: make the hook and the closing question specific to THIS story. Never open with "क्या आप यकीन करेंगे" and never
close with a generic "इस पूरे मामले पर आपकी क्या राय है?".
"""

JUNK_LINE = re.compile(r"^(also read|read more|read also|click here|subscribe|follow us|published|updated|copyright|"
                       r"advertisement|watch:|listen:|photo:|image:|file photo|representative image|for representational)",
                       re.I)


def clean_original(text):
    """The scraped article without its page furniture (read-more links, captions, bylines), whitespace squeezed."""
    out = []
    for line in str(text or "").splitlines():
        line = " ".join(line.split())
        if len(line) < 25 or JUNK_LINE.match(line):
            continue
        out.append(line)
    return "\n".join(out)


def fit_prompt(model, system, head, summary, original, max_tokens, margin=160):
    """The user prompt, cut so that system + prompt + the answer fit the model's context window (4,096 tokens on
    the GitHub runner; going over makes llama.cpp refuse the call). The ORIGINAL is trimmed first, at a paragraph
    end, then the SUMMARY. Token counts come from the model's own tokenizer."""
    def n(t):
        return len(model.llm.tokenize(t.encode("utf-8"), add_bos=False))
    budget = model.llm.n_ctx() - max_tokens - margin - n(system) - 40  # 40: the chat template's own tokens

    def build(sm, og):
        return head + f"SUMMARY:\n{sm}" + (f"\n\nORIGINAL ARTICLE:\n{og}" if og else "")
    sm, og = summary, original
    while og and n(build(sm, og)) > budget:
        cut = og.rfind("\n", 0, int(len(og) * 0.8))
        og = og[:cut] if cut > 400 else ""
    while n(build(sm, og)) > budget and len(sm) > 300:
        sm = sm[: int(len(sm) * 0.8)]
    return build(sm, og)


LOADED = re.compile(r"(भ्रष्टाचार|घोटाल[ाेो]|घपल[ाेो]|घूसखोरी|रिश्वतखोरी|धोखाधड़ी|हेराफेरी|लूट)")
HEDGED = re.compile(r"आरोप|दावा|दावे|कथित|जांच|जाँच|सवाल")
LABELS = {"चोर", "चोरों", "गद्दार", "जुमलेबाज़", "जुमलेबाज", "घोटालेबाज़", "घोटालेबाज", "भ्रष्ट", "लुटेरा", "लुटेरे", "देशद्रोही"}


def legal_pass(script):
    """The political rules the model doesn't always keep, applied in code (22 Oct 2026: an on-screen bullet read
    '43,000 करोड़ का भ्रष्टाचार' and the review still approved it). A field that names wrongdoing without 'आरोप/दावा/
    कथित/जांच' gets 'कथित' (alleged) in front of it; an abusive label rejects the script. -> (script, notes, ok)"""
    notes, ok = [], True

    def fix(v):
        nonlocal ok
        if not isinstance(v, str):
            return v
        words = set(re.findall(r"[\u0900-\u097F]+", v))
        if words & LABELS:
            ok = False
            notes.append(f"label {sorted(words & LABELS)} in: {v[:60]}")
        if LOADED.search(v) and not HEDGED.search(v):
            nv = LOADED.sub(lambda m: "कथित " + m.group(1), v, count=1)
            notes.append(f"'{v[:50]}' -> '{nv[:56]}'")
            return nv
        return v
    out = {k: ([fix(x) for x in v] if isinstance(v, list) else fix(v)) for k, v in script.items()}
    return out, notes, ok


# Script writer: OpenAI GPT-5.6 Luna (Yash, 24 Oct 2026, after the model test: best Hindi for the money), Gemma 12B as
# the fallback. ~Rs 0.2 per reel at medium. Rs 2 is a target, not a hard limit (Yash, 24 Oct): the only cap is a runaway
# guard (REEL_BUDGET_INR, default Rs 10 per reel, counted at Luna's launch price $1 / $6 per 1M tokens).
OPENAI_MODEL = os.environ.get("REEL_SCRIPT_MODEL", "gpt-5.6-luna")
EDIT_MODEL = os.environ.get("REEL_EDIT_MODEL") or None   # the plain-language editor pass; None = OPENAI_MODEL
OPENAI_EFFORT = os.environ.get("REEL_SCRIPT_EFFORT", "medium")  # low | medium | high
OPENAI_PRICE = {"gpt-5.6-luna": (1.0, 6.0), "gpt-5.6-terra": (2.5, 15.0), "gpt-5.6-sol": (5.0, 30.0)}  # $/1M, launch prices
REEL_BUDGET_INR = float(os.environ.get("REEL_BUDGET_INR") or "10")
USD_INR = float(os.environ.get("USD_INR", "88"))
SPENT = {"inr": 0.0}  # this reel's OpenAI spend (one dispatch = one reel)


def openai_script(system, user, model=None, schema_=None):
    """The reel script from OpenAI, or (None, why). The answer may use up to 8,000 tokens (room for high reasoning);
    only a runaway is stopped (REEL_BUDGET_INR per reel)."""
    import urllib.error
    import urllib.request
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        return None, "no OPENAI_API_KEY"
    model = model or OPENAI_MODEL
    pin, pout = OPENAI_PRICE.get(model, (5.0, 30.0))
    left_usd = (REEL_BUDGET_INR - SPENT["inr"]) / USD_INR
    in_tokens = len(system + user) / 2.5  # generous estimate (Hindi/English mix)
    max_out = int((left_usd - in_tokens * pin / 1e6) / (pout / 1e6))
    if max_out < 1500:
        return None, f"reel budget used (Rs {SPENT['inr']:.2f} of {REEL_BUDGET_INR})"
    schema = json.loads(json.dumps(schema_ or SCRIPT_SCHEMA))
    schema["additionalProperties"], schema["required"] = False, list(schema["properties"])
    body = {"model": model, "reasoning_effort": OPENAI_EFFORT, "max_completion_tokens": min(max_out, 8000),
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_schema", "json_schema": {"name": "reel_brief" if schema_ else "reel_script", "schema": schema, "strict": True}}}
    req = urllib.request.Request("https://api.openai.com/v1/chat/completions", data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            out = json.loads(r.read())
    except urllib.error.HTTPError as e:
        return None, f"OpenAI HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:200]}"
    except Exception as e:
        return None, f"OpenAI {type(e).__name__}"
    u = out.get("usage") or {}
    cost = (u.get("prompt_tokens", 0) * pin + u.get("completion_tokens", 0) * pout) / 1e6 * USD_INR
    SPENT["inr"] += cost
    print(f"  OpenAI {model} ({OPENAI_EFFORT}): {u.get('prompt_tokens')} in, {u.get('completion_tokens')} out "
          f"({(u.get('completion_tokens_details') or {}).get('reasoning_tokens')} thinking), at most Rs {cost:.2f} "
          f"(reel so far Rs {SPENT['inr']:.2f})", flush=True)
    try:
        return json.loads(out["choices"][0]["message"]["content"]), None
    except Exception as e:
        return None, f"OpenAI answer unreadable: {type(e).__name__}"


FEEDBACK = ""  # filled once per run by main() (audience_feedback)


def audience_feedback(u_db, n=4):
    """What our audience actually watched: the first line of our recent Instagram reels with their reach (best and
    worst n), for the scoring prompt (Yash, 24 Oct 2026: learn from results). '' if Instagram can't be read."""
    try:
        import urllib.parse
        import urllib.request
        tok = {r[0]: r[1] for r in u_db.execute("SELECT k, token FROM ig_auth").rows}.get("long_lived")
        if not tok:
            return ""
        base = "https://graph.instagram.com/v23.0"
        get = lambda path, **q: json.loads(urllib.request.urlopen(f"{base}/{path}?" + urllib.parse.urlencode({**q, "access_token": tok}), timeout=30).read())
        me = get("me", fields="user_id")
        media = get(f"{me.get('user_id') or me.get('id')}/media", fields="id,caption,media_product_type,timestamp", limit=40).get("data", [])
        rows = []
        for m in media:
            if m.get("media_product_type") != "REELS" or not m.get("caption"):
                continue
            try:
                reach = get(f"{m['id']}/insights", metric="reach")["data"][0]["values"][0]["value"]
            except Exception:
                continue
            line = m["caption"].strip().splitlines()[0].lstrip("🚨 ").strip()[:90]
            rows.append((reach, line))
        if len(rows) < 6:
            return ""
        rows.sort(reverse=True)
        top = "\n".join(f"  + reach {r}: {t}" for r, t in rows[:n])
        low = "\n".join(f"  - reach {r}: {t}" for r, t in rows[-n:])
        return ("\nWHAT OUR AUDIENCE ACTUALLY WATCHED (Instagram reach of our recent reels; learn the pattern, don't copy the topics):\n"
                f"Did well:\n{top}\nDid poorly:\n{low}\n")
    except Exception as e:
        print(f"  (audience feedback unavailable: {type(e).__name__})")
        return ""


NAME = re.compile(r"\b[A-Z][a-zA-Z.'-]{3,}\b")
COMMON = {"India", "Indian", "Indians", "Government", "Centre", "Central", "State", "States", "Minister", "Chief", "Prime",
          "Supreme", "Court", "High", "Union", "National", "Party", "Congress", "Lok", "Sabha", "Rajya", "President", "Bank",
          "Report", "Committee", "Commission", "Election", "Police", "Delhi", "Mumbai", "World", "First", "After", "With",
          "Over", "From", "Says", "Said", "Will", "Amid", "Rs", "Crore", "Lakh", "Billion", "Trillion", "Million", "This", "That"}


def names_in(title):
    """Proper names in an English headline (people, companies, places), minus the very common ones."""
    return {w.strip(".'-") for w in NAME.findall(title or "")} - COMMON


SUITABILITY_POLITICAL_EXTRA = """
5. LEGAL SAFETY (this is a political story; reject_story if ANY point fails):
   - core_say starts with the source attribution ("... की रिपोर्ट के मुताबिक") and every accusation is tied to whoever made it;
   - no named person or party is called or implied guilty, corrupt or criminal (unless the script says a court convicted them),
     in the spoken lines AND the on-screen text (headline, points, stat label, detail line);
   - no abusive or loaded labels; nothing about anyone's family, caste, religion or private life;
   - it ends on a question, not a verdict, and does not cheer or mock a party.
"""

# On-screen source label from the article's host (it said TheHindu for every non-Indian-Express story).
SOURCE_LABELS = {
    "thehindu": "TheHindu", "indianexpress": "TheIndianExpress", "ndtv": "NDTV", "timesofindia": "TimesOfIndia",
    "indiatimes": "TimesOfIndia", "economictimes": "EconomicTimes", "hindustantimes": "HindustanTimes",
    "livemint": "Mint", "indiatoday": "IndiaToday", "deccanherald": "DeccanHerald", "tribuneindia": "TheTribune",
    "telegraphindia": "TheTelegraph", "bbc": "BBC", "aljazeera": "AlJazeera", "reuters": "Reuters",
    "onmanorama": "Onmanorama", "greaterkashmir": "GreaterKashmir", "odishabytes": "OdishaBytes",
    "thesouthfirst": "TheSouthFirst", "telanganatoday": "TelanganaToday", "wired": "Wired", "techcrunch": "TechCrunch",
    "theguardian": "TheGuardian", "scmp": "SCMP", "dawn": "Dawn",
}


def source_label_for(url):
    from urllib.parse import urlparse
    host = (urlparse(url or "").hostname or "").lower()
    if host.startswith("economictimes."):
        return "EconomicTimes"
    for key, label in SOURCE_LABELS.items():
        if key in host.split("."):
            return label
    parts = [p for p in host.split(".") if p and p not in ("www", "m", "amp", "com", "in", "co", "org", "net", "uk")]
    return parts[0].capitalize() if parts else "TheHindu"


_NUMS = re.compile(r"\d[\d,.]*")


def distinct_stat(headline, stat, label, detail, points):
    """Card 3's big number must not repeat the hook's (the 24 Oct reel showed '50,000 रुपये' on cards 1, 2 and 3).
    If it does, use another number from the detail line or the bullet points (with the word after it), else the
    label itself as the big word."""
    seen = {n.replace(",", "") for n in _NUMS.findall(headline or "")}
    mine = {n.replace(",", "") for n in _NUMS.findall(stat or "")}
    if not mine or not (mine & seen):
        return stat, label
    for text_ in [detail or ""] + list(points or []):
        for m in re.finditer(r"(₹?\d[\d,.]*)\s*(\S+)?", text_):
            if m.group(1).lstrip("₹").replace(",", "") not in seen:
                return " ".join(x for x in (m.group(1), m.group(2)) if x), ""  # the old label described the old number
    return (label or stat), ""

# People in a reel are introduced (Yash, 24 Oct 2026: "the audience might not even be aware of them"). Roles come
# from the entity library the promise tracker uses (raam-07/satya-entity-library, public, refreshed by its own
# pipeline), Hindi file: name_hi / role_hi / party. Fetched once per run; no library = no PEOPLE block, rules still apply.
ENTITIES_HI_URL = "https://raw.githubusercontent.com/raam-07/satya-entity-library/main/entities_hi.json"
PEOPLE_CATS = ("cabinet_ministers", "state_chief_ministers", "opposition_leaders", "generic_politicians")
_PEOPLE = None


def library_people():
    """[{name, name_hi, role_hi, party, keys}] from the entity library; the first entry per name wins (cabinet
    before chief ministers etc.: the library repeats a few names with an older role)."""
    global _PEOPLE
    if _PEOPLE is not None:
        return _PEOPLE
    _PEOPLE = []
    try:
        import urllib.request
        with urllib.request.urlopen(ENTITIES_HI_URL, timeout=20) as r:
            data = json.loads(r.read())
    except Exception as e:
        print(f"  entity library not loaded ({type(e).__name__}): people are introduced from the article only")
        return _PEOPLE
    seen = set()
    for cat in PEOPLE_CATS:
        for p in (data.get("india") or {}).get(cat) or []:
            name = (p.get("name") or "").strip()
            if not name or name.lower() in seen or not (p.get("role_hi") or p.get("role")):
                continue
            seen.add(name.lower())
            aliases = p.get("aliases") or []
            if isinstance(aliases, str):
                aliases = re.findall(r"'([^']+)'", aliases)
            # match on the full name, or an alias that is one of the name's own words (Naidu, Fadnavis), never on
            # descriptive aliases ("Leader of Opposition", "Bengaluru Development")
            words = {w.lower() for w in re.findall(r"[A-Za-z]+", name) if len(w) >= 4}
            keys = {name.lower()} | {a.lower() for a in aliases if a.lower() in words}
            _PEOPLE.append({"name": name, "name_hi": p.get("name_hi") or name, "role_hi": p.get("role_hi") or p.get("role"),
                            "party": p.get("party_hi") or p.get("party") or "", "keys": keys})
    return _PEOPLE


def people_block(*texts):
    """The PEOPLE block for the script writer: library people named in the article, with their recorded roles."""
    text_ = " ".join(t for t in texts if t).lower()
    found = []
    for p in library_people():
        if any(re.search(r"\b" + re.escape(k) + r"\b", text_) for k in p["keys"]):
            found.append(p)
    if not found:
        return "", []
    lines = [f"- {p['name_hi']} ({p['name']}): {p['role_hi']}" + (f"  [party: {p['party']}]" if p['party'] and p['party'] not in p['role_hi'] else "")
             for p in found[:6]]
    return ("PEOPLE (from our records: introduce them with this role, said naturally; mention the party only when it "
            "matters to the story; anyone else only as the article describes them)\n" + "\n".join(lines) + "\n"), found


SAY_FIELDS = ("hook_say", "core_say", "twist_say", "engagement_say")
_ROLE_STOP = {"के", "की", "का", "और", "में", "से", "पर", "एक", "तथा", "ने"}


def _role_words(role):
    return {w for w in re.findall(r"[ऀ-ॿ]+|[A-Za-z]+", role or "") if w not in _ROLE_STOP and len(w) >= 2}


def intro_problems(script, known=()):
    """Every person in the voice script must be introduced on first mention: some word of their role within a few
    words before (or right after) the name. Also: at most 3 named people. -> list of problems ([] = fine).
    `known`: library people found in the article; one named in the script but missing from `people` counts too."""
    say = " ".join(str(script.get(k) or "") for k in SAY_FIELDS)
    people = [p for p in (script.get("people") or []) if isinstance(p, dict) and (p.get("name_hi") or "").strip()]
    listed = {p["name_hi"].strip() for p in people}
    lib = {k["name_hi"]: k["role_hi"] for k in known}
    for p in people:   # a listed person with an empty role is checked against the library role (or any role word)
        if not (p.get("role_hi") or "").strip():
            p["role_hi"] = lib.get(p["name_hi"].strip(), "")
    for k in known:   # a library person the script didn't list: full name spoken, or a surname no listed person shares
        sur = k["name_hi"].split()[-1]                             # (Brijesh Goyal's "गोयल" must not flag Piyush Goyal)
        if k["name_hi"] not in listed and (k["name_hi"] in say or (sur in say and not any(sur in n for n in listed))):
            people.append({"name_hi": k["name_hi"], "role_hi": k["role_hi"]})
    out = []
    named = 0
    for p in people:
        name = p["name_hi"].strip()
        variants = [name] + ([name.split()[-1]] if len(name.split()) > 1 else [])
        hits = [say.find(v) for v in variants if v in say]
        if not hits:
            continue
        named += 1
        i = min(hits)
        window = say[max(0, i - 70):i] + " " + say[i + len(name):i + len(name) + 40]
        role = (p.get("role_hi") or "").strip()
        if not role or not (_role_words(role) & _role_words(window)):
            out.append(f"{name} is not introduced on first mention (say: '{p.get('role_hi') or 'role'} {name}')")
    cap = 2 if {"b5", "g1"} & {os.environ.get("REEL_PROMPT_VARIANT", ""), os.environ.get("REEL_PIPELINE", "b4r")} else 3
    if named > cap:
        out.append(f"{named} people are named: keep at most {cap}, describe the rest without a name")
    return out


def tags_for_cards(script):
    """{'hook'|'core'|'twist'|'engagement': [{name, role}]}: the card where each person is first named (max 2 per card)."""
    cards = {}
    for p in script.get("people") or []:
        name = (p.get("name_hi") or "").strip() if isinstance(p, dict) else ""
        if not name:
            continue
        variants = [name] + ([name.split()[-1]] if len(name.split()) > 1 else [])
        for field, card in zip(SAY_FIELDS, ("hook", "core", "twist", "engagement")):
            if any(v in str(script.get(field) or "") for v in variants):
                if len(cards.setdefault(card, [])) < 2:
                    cards[card].append({"name": name, "role": (p.get("role_hi") or "").strip()})
                break
    return cards

SCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "people": {
            "type": "array",
            "items": {"type": "object", "properties": {"name_hi": {"type": "string"}, "role_hi": {"type": "string"}},
                      "required": ["name_hi", "role_hi"], "additionalProperties": False}
        },
        "headline_hi": {"type": "string"},
        "plain_story_hi": {"type": "string"},
        "engagement_title_hi": {"type": "string"},
        "subtitle_hi": {"type": "string"},
        "hook_say": {"type": "string"},
        "core_title_hi": {"type": "string"},
        "core_points_hi": {
            "type": "array",
            "items": {"type": "string"}
        },
        "core_say": {"type": "string"},
        "twist_stat": {"type": "string"},
        "twist_label": {"type": "string"},
        "twist_detail_hi": {"type": "string"},
        "twist_say": {"type": "string"},
        "question_hi": {"type": "string"},
        "engagement_say": {"type": "string"}
    },
    "required": [
        "plain_story_hi", "people", "headline_hi", "subtitle_hi", "engagement_title_hi", "hook_say", "core_title_hi", "core_points_hi", "core_say",
        "twist_stat", "twist_label", "twist_detail_hi", "twist_say", "question_hi", "engagement_say"
    ]
}

SUITABILITY_SYSTEM = """You are the Senior Editorial Quality Director at SatyaDheesh, an elite Indian news channel.
Your task is to critically review a generated Hindi news Reel script and its selected voice persona before it is produced.

VOICE PERSONAS:
- 'charlie' (Male): Energetic, confident, modern, authoritative Hindi creator. Best for: national news, defense, economy, infrastructure, science, space, geopolitics.
- 'matilda' (Female): Warm, articulate, engaging, knowledgeable Hindi creator. Best for: consumer rights, health, public schemes, civic alerts, environment, culture.

EVALUATION CRITERIA:
1. Tone & Credibility: Is the script professional, engaging, and worthy of a credible news brand? Reject ANY script with cheap movie catchphrases, slapstick humor, clownish slang, or cringe drama.
2. Voice Match: Is the language, pacing, and vibe genuinely suitable for the assigned voice persona?
3. Story Fit: Is this story actually worth a 30-40s video reel, or does it sound awkward, trivial, or forced?
4. TTS Phonetic Naturalness: Does the spoken narration flow naturally without awkward grammatical phrasing, stiff literary inflections, or tongue-twisters that would sound robotic or mispronounced on an AI voice?

Return a JSON object:
{
  "is_suitable": true or false,
  "verdict": "Clear 1-sentence assessment of tone and voice match",
  "action": "approve" or "change_voice" or "reject_story",
  "suggested_voice": "charlie" or "matilda"
}
"""

SUITABILITY_COMMON_EXTRA = """
5. Common man (Yash, 26 Oct 2026: "not fine with something that a normal typical common man could not understand"):
   would a shopkeeper in Kanpur or a farmer's son in Bihar, who doesn't follow the news, understand what happened and why
   it matters on first hearing? An unexplained office, abbreviation, procedure or a number they can't picture fails it.
   If it fails, is_suitable is false and action is "reject_story".
"""

SUITABILITY_SCHEMA = {
    "type": "object",
    "properties": {
        "is_suitable": {"type": "boolean"},
        "verdict": {"type": "string"},
        "action": {"type": "string", "enum": ["approve", "change_voice", "reject_story"]},
        "suggested_voice": {"type": "string", "enum": ["charlie", "matilda"]}
    },
    "required": ["is_suitable", "verdict", "action", "suggested_voice"]
}

CATEGORY_HI = {
    "politics": "राजनीति",
    "politics_funding": "चुनावी चंदा",
    "infrastructure": "इंफ्रास्ट्रक्चर",
    "economy": "अर्थव्यवस्था",
    "cinema": "सिनेमा",
    "bollywood": "सिनेमा",
    "curiosity": "रोचक पड़ताल",
    "science": "विज्ञान",
    "science_space": "विज्ञान और स्पेस",
    "space": "अंतरिक्ष",
    "defence": "रक्षा",
    "defense": "रक्षा",
    "sports": "खेल",
    "consumer_hack": "काम की खबर",
    "crime": "विशेष रिपोर्ट",
    "judiciary": "अदालत और कानून",
    "education": "शिक्षा",
    "environment": "पर्यावरण",
    "nature": "पर्यावरण और प्रकृति",
}


def send_telegram_alert(text):
    """Sends an error alert directly to Telegram."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN") or "8553388061:AAGzoTrdaUABEj8QbPidn6wT1R9Q8oREqNI"
    chat_id = os.environ.get("TELEGRAM_CHAT_ID") or os.environ.get("TELEGRAM_TEST_CHAT_ID") or os.environ.get("CHAT_ID") or "6634664206"
    try:
        import urllib.request
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"  Telegram alert error: {e}")
        return False


def dispatch_daily_reel(u_db, m_db, model=None, force=False):
    SPENT["inr"] = 0.0
    """Dispatches the top viral story of the day to Satyadheesh/reels via repository_dispatch."""
    token = os.environ.get("CORE_TOKEN") or os.environ.get("GITHUB_PAT") or os.environ.get("GITHUB_PAT_CLASSIC")
    if not token:
        print("  Notice: No GitHub PAT found (CORE_TOKEN); skipping reel dispatch.")
        return

    now = int(time.time())
    # Ensure at most 1 reel per 6 hours unless force=True
    if not force:
        # Check 1: Turso DB reel_posts
        try:
            recent = u_db.execute("SELECT max(dispatched_at) FROM reel_posts").rows
            if recent and recent[0][0] and (now - int(recent[0][0])) < 6 * 3600:
                last_ago_hrs = (now - int(recent[0][0])) / 3600
                print(f"  Daily reel already dispatched {last_ago_hrs:.1f}h ago (< 6 hours). Skipping duplicate dispatch.")
                return
        except Exception:
            pass

        # Check 2: Satyadheesh/reels GitHub Actions runs (in case run was triggered directly)
        try:
            import datetime
            import urllib.request
            gh_url = "https://api.github.com/repos/Satyadheesh/reels/actions/workflows/daily-reel.yml/runs?status=success&per_page=1"
            req = urllib.request.Request(gh_url, headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "satya-reel-scorer"
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
                runs = data.get("workflow_runs", [])
                if runs:
                    updated = datetime.datetime.fromisoformat(runs[0]["updated_at"].replace("Z", "+00:00"))
                    diff_hrs = (datetime.datetime.now(datetime.timezone.utc) - updated).total_seconds() / 3600.0
                    if diff_hrs < 6.0:
                        print(f"  Reel already posted to Telegram {diff_hrs:.1f}h ago (< 6 hours). Skipping dispatch.")
                        return
        except Exception as e:
            print(f"  Note: GitHub Actions run check: {e}")

    # Find the top viral score candidates (>= 7) from the last 24h not yet reeled
    since = now - 24 * 3600
    try:
        candidates = u_db.execute(
            "SELECT c.article_id, c.topic, c.viral_score, c.hook_angle, c.wow_fact, c.why, c.published_at "
            "FROM reel_candidates c "
            "WHERE c.viral_score >= 6 AND c.created_at >= ? AND c.model LIKE ? "
            "  AND c.article_id NOT IN (SELECT article_id FROM reel_posts) "
            "ORDER BY c.viral_score DESC, c.published_at DESC "
            "LIMIT 40",
            [since, "%" + SELECT_TAG.get(select_mode(), "")]   # v2/v3: only stories scored by those rules
        ).rows
        # political stories get the most traction (Yash, 22 Oct 2026): +1 when ranking, and they qualify from 6
        candidates = [c for c in candidates if int(c[2]) >= 7 or (is_political(c[1]) and int(c[2]) >= 6)]
        candidates.sort(key=lambda c: (int(c[2]) + (1 if is_political(c[1]) else 0), c[6] or 0), reverse=True)
        # no repeat of the same person or company within 48 h (Musk got 3 reels in 3 days, 22-24 Oct 2026)
        recent = [int(r[0]) for r in u_db.execute("SELECT article_id FROM reel_posts WHERE dispatched_at >= ?", [now - 48 * 3600]).rows]
        ids = recent + [int(c[0]) for c in candidates[:20]]
        titles = {}
        if ids:
            ph = ",".join("?" * len(ids))
            titles = {int(r[0]): (r[1] or r[2] or "") for r in m_db.execute(f"SELECT id, title, rephrased_title FROM articles WHERE id IN ({ph})", ids).rows}
        seen = set().union(*[names_in(titles.get(a, "")) for a in recent]) if recent else set()
        fresh = []
        for c in candidates[:20]:
            overlap = names_in(titles.get(int(c[0]), "")) & seen
            if overlap:
                print(f"  #{c[0]} skipped: {sorted(overlap)} already had a reel in the last 48 h")
                continue
            fresh.append(c)
        candidates = [c[:6] for c in fresh[:5]]
    except Exception as e:
        print(f"  Error querying reel_candidates for dispatch: {e}")
        return

    if not candidates:
        print("  No new high viral candidate (score >= 7) available to dispatch right now.")
        return

    if model is None and os.environ.get("REEL_PIPELINE", "b4r") != "luna":
        model = gemma_model()   # B4r needs Gemma anyway; the quality gate then runs too
    approved_candidate = None
    approved_script = None
    approved_persona = None
    approved_row = None

    female_topics = {"consumer_hack", "education", "environment", "nature", "health", "cinema", "lifestyle"}

    for cand in candidates:
        aid, topic, score, hook, fact, why = int(cand[0]), str(cand[1]), int(cand[2]), str(cand[3]), str(cand[4]), str(cand[5])
        SPENT["inr"] = 0.0   # the runaway guard is per reel: each candidate is its own reel (B4r costs ~Rs 2-4)
        art_rows = m_db.execute(
            "SELECT title, rephrased_title, rephrased_article, category, image_url, url, content "
            "FROM articles WHERE id = ?",
            [aid]
        ).rows
        if not art_rows:
            continue

        r = art_rows[0]
        political = is_political(topic)

        # Initial persona selection based on topic
        persona = "matilda" if str(topic).lower() in female_topics else "charlie"

        last_openai = None
        for voice_attempt in range(2):
            print(f"  Evaluating candidate #{aid} [{topic}] with persona: {persona} (attempt {voice_attempt + 1})...")
            script_data = None
            inp = script_inputs(r, topic, fact, persona)
            title, body, original = inp["title"], inp["body"], inp["original"]
            system, head, known = inp["system"], inp["head"], inp["known"]
            if last_openai:  # only the voice changed: the OpenAI script stays (no second payment)
                script_data = last_openai
            else:
                script_data, why, problems = live_script(inp, aid)
                if script_data:
                    if problems:
                        print(f"::warning title=Reel #{aid}: script problems left::{'; '.join(problems)[:400]}")
                    last_openai = script_data
                else:
                    print(f"  OpenAI script not used ({why}); Gemma writes it")
            if not script_data and model:
                try:
                    sprompt = fit_prompt(model, system, head, body[:1500], original, max_tokens=800)
                    script_data = model.json(system, sprompt, SCRIPT_SCHEMA, temperature=0.25, max_tokens=800)
                    problems = intro_problems(script_data, known)
                    if problems:
                        print(f"::warning title=Reel #{aid} (Gemma script): people not introduced::{'; '.join(problems)[:400]}")
                except Exception as e:
                    print(f"  Script generation warning: {e}")
            if script_data:
                try:
                    if political and script_data:
                        script_data, notes, legal_ok = legal_pass(script_data)
                        for note in notes:
                            print(f"  legal pass #{aid}: {note}")
                        if not legal_ok:
                            print(f"  Story #{aid}: abusive label in the script, trying next candidate...")
                            script_data = None
                except Exception as e:
                    print(f"  Script generation warning: {e}")

            if not script_data:
                break

            # Editorial & Voice Suitability Evaluation (Gemma Quality Gate)
            if model:
                try:
                    eval_prompt = (
                        f"NEWS ARTICLE: {title}\n"
                        f"TOPIC: {topic}{' (POLITICAL: apply the legal safety check)' if political else ''}\n"
                        f"ASSIGNED VOICE: {persona}\n"
                        f"HEADLINE: {script_data.get('headline_hi')}\n"
                        f"ON-SCREEN: {script_data.get('core_title_hi')} | {' | '.join(script_data.get('core_points_hi') or [])} | "
                        f"{script_data.get('twist_stat')} {script_data.get('twist_label')} | {script_data.get('twist_detail_hi')}\n"
                        f"HOOK: {script_data.get('hook_say')}\n"
                        f"CORE: {script_data.get('core_say')}\n"
                        f"TWIST: {script_data.get('twist_say')}\n"
                        f"ENGAGEMENT: {script_data.get('engagement_say')}"
                    )
                    suitability = model.json(SUITABILITY_SYSTEM + (SUITABILITY_POLITICAL_EXTRA if political else "")
                                             + (SUITABILITY_COMMON_EXTRA if os.environ.get("REEL_PIPELINE") == "b5" else ""), eval_prompt,
                                             SUITABILITY_SCHEMA, temperature=0.1, max_tokens=200)
                    is_ok = suitability.get("is_suitable") is True or suitability.get("action") == "approve"
                    verdict = suitability.get("verdict", "")
                    action = suitability.get("action", "")
                    print(f"  Gemma review for #{aid} ({persona}): suitable={is_ok}, action={action} -> {verdict}")

                    if is_ok:
                        approved_candidate = cand
                        approved_script = script_data
                        approved_persona = persona
                        approved_row = r
                        break
                    elif action == "change_voice" and voice_attempt == 0:
                        suggested = suitability.get("suggested_voice")
                        if suggested and suggested != persona:
                            print(f"  Gemma suggested voice change: switching {persona} -> {suggested}...")
                            persona = suggested
                            continue
                    else:
                        print(f"  Story #{aid} rejected by Gemma editorial review ({verdict}). Trying next candidate...")
                        break
                except Exception as e:
                    print(f"  Suitability check note: {e}")
                    if political:  # a political script is never made without its legal check
                        print(f"  Story #{aid}: political and unchecked, trying next candidate...")
                        break
                    approved_candidate = cand
                    approved_script = script_data
                    approved_persona = persona
                    approved_row = r
                    break
            else:
                approved_candidate = cand
                approved_script = script_data
                approved_persona = persona
                approved_row = r
                break

        if approved_candidate:
            break

    if not approved_candidate or not approved_script:
        err_msg = (
            "⚠️ *SatyaDheesh Reel Alert: No Candidate Approved*\n\n"
            f"• *Evaluated*: {len(candidates)} high-viral candidates\n"
            "• *Reason*: None passed Gemma's brand dignity & voice fit review.\n"
            "• *Action*: Reel dispatch halted to protect brand quality."
        )
        print(f"❌ {err_msg}")
        send_telegram_alert(err_msg)
        return

    aid, topic, score, hook, fact, why = int(approved_candidate[0]), str(approved_candidate[1]), int(approved_candidate[2]), str(approved_candidate[3]), str(approved_candidate[4]), str(approved_candidate[5])
    r = approved_row
    title = r[1] or r[0]
    cat = r[3] or topic
    img = r[4] or ""
    source_url = r[5] or ""
    persona = approved_persona
    script_data = approved_script

    headline_hi = script_data.get("headline_hi") or title[:40]
    hook_say = script_data.get("hook_say") or hook
    core_title = script_data.get("core_title_hi") or "पूरी जानकारी"
    core_say = script_data.get("core_say") or f"इस मामले की पूरी जानकारी ये है कि {fact}।"
    twist_stat = script_data.get("twist_stat") or "बड़ा बदलाव"
    twist_label = script_data.get("twist_label") or "का असर"
    twist_say = script_data.get("twist_say") or f"ज़मीनी सच्चाई ये है कि {fact}।"
    q_hi = script_data.get("question_hi") or "आपकी क्या राय है?"
    eng_say = script_data.get("engagement_say") or "इस पूरे मामले पर आपकी क्या सोच है? कमेंट में बताइए और फ़ॉलो कीजिए सत्याधीश।"

    category_hi = CATEGORY_HI.get(str(topic).lower(), "विशेष पड़ताल")

    # Clean Hindi core bullet points for Card 2
    raw_pts = script_data.get("core_points_hi")
    if raw_pts and isinstance(raw_pts, list) and len(raw_pts) > 0:
        core_points = [str(p).strip() for p in raw_pts if str(p).strip()][:3]
        if len(core_points) == 1:
            core_points.append("सत्यापित सरकारी डेटा")
    else:
        core_points = ["सटीक सरकारी रिपोर्ट", "सत्यापित डेटा"]

    # Clean Hindi detail line under big stat for Card 3
    twist_detail = script_data.get("twist_detail_hi")
    if not twist_detail:
        twist_detail = "सत्यापित ज़मीनी रिपोर्ट"

    source_label = source_label_for(source_url)
    subtitle_hi = " ".join(str(script_data.get("subtitle_hi") or "").split())
    twist_stat, twist_label = distinct_stat(headline_hi, twist_stat, twist_label, twist_detail, core_points)

    hook_badge = "ताज़ा पड़ताल"
    twist_badge = "ज़मीनी हक़ीक़त"

    tags = tags_for_cards(script_data)
    payload = {
        "article_id": aid,
        "persona": persona,
        "force": force,
        "category": category_hi,
        "headline": headline_hi,
        "image_url": img,
        "hook": {
            "badge": hook_badge,
            "title": headline_hi,
            "subtitle": subtitle_hi,
            "people": tags.get("hook", []),
            "say": hook_say
        },
        "core": {
            "badge": "मुख्य जानकारी",
            "title": core_title,
            "points": core_points,
            "source": source_label,
            "people": tags.get("core", []),
            "say": core_say
        },
        "twist": {
            "badge": twist_badge,
            "big_stat": twist_stat,
            "stat_label": twist_label,
            "detail": twist_detail,
            "people": tags.get("twist", []),
            "say": twist_say
        },
        "engagement": {
            "headline": (" ".join(str(script_data.get("engagement_title_hi") or "").split())[:40] or "आपकी राय"),
            "question": q_hi,
            "cta": "कमेंट में अपनी राय ज़रूर लिखें!",
            "people": tags.get("engagement", []),
            "say": eng_say
        }
    }

    # the final script as an annotation (job logs aren't readable from outside): who is introduced how, and the voice lines
    _txt = ("PEOPLE: " + "; ".join(f"{p.get('name_hi')} = {p.get('role_hi')}" for p in script_data.get("people") or []) + "\n"
            + f"HEADLINE: {headline_hi} | SUB: {subtitle_hi}\n"
            + "\n".join(f"{k.upper()}: {script_data.get(k)}" for k in SAY_FIELDS))
    print(f"::notice title=Reel script #{aid}::" + _txt.replace("%", "%25").replace("\r", "").replace("\n", "%0A")[:6000])
    print(f"\n🚀 Dispatching top viral reel to Satyadheesh/reels:")
    print(f"   Article #{aid} (Score {score}/10) [{topic}]")
    print(f"   Hook: {hook_say[:70]}")

    import urllib.request
    req = urllib.request.Request(
        "https://api.github.com/repos/Satyadheesh/reels/dispatches",
        data=json.dumps({"event_type": "generate_reel", "client_payload": payload}).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "satya-reel-scorer"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status in (200, 204):
                print(f"✅ Successfully dispatched reel event for #{aid} to Satyadheesh/reels!")
                u_db.execute(
                    "INSERT OR REPLACE INTO reel_posts (article_id, title, topic, viral_score, hook_angle, dispatched_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    [aid, title, topic, score, hook, now]
                )
            else:
                err_msg = f"⚠️ *Reel Dispatch Warning*: Satyadheesh/reels returned HTTP status {resp.status} for article #{aid}"
                print(err_msg)
                send_telegram_alert(err_msg)
    except Exception as e:
        err_msg = (
            "🚨 *SatyaDheesh Reel Dispatch Error*\n\n"
            f"• *Article*: #{aid} ({title[:60]})\n"
            f"• *Voice*: {persona}\n"
            f"• *Error*: `{str(e)[:250]}`"
        )
        print(f"❌ Failed to dispatch to Satyadheesh/reels: {e}")
        send_telegram_alert(err_msg)


def script_inputs(r, topic, fact, persona):
    """The exact prompt the live reel uses. r = (title, rephrased_title, rephrased_article, category, image_url, url,
    content) from articles. -> dict(system, head, user_msg, body, original, known, political, title)."""
    title = r[1] or r[0]
    body = decompress(r[2], limit=4000)
    original = clean_original(decompress(r[6], limit=12000))[:4000]  # ~1,000 tokens: richer context, runner time in check
    political = is_political(topic)
    src_name = "इंडियन एक्सप्रेस" if "indianexpress" in str(r[5] or "").lower() else "द हिंदू"
    variant = os.environ.get("REEL_PROMPT_VARIANT", "")   # experiments only: "short", "no_original"
    if variant == "short":
        system = SCRIPT_SYSTEM_SHORT.replace("<source>", src_name)
    else:
        system = SCRIPT_SYSTEM_CHARLIE + SCRIPT_SOURCE_RULES + (SCRIPT_POLITICAL_EXTRA.replace("{source}", src_name) if political else "")
    pblock, known = people_block(r[0], title, body, original)
    head = (f"NEWS ARTICLE\nTitle: {title}\nTopic: {topic}\nSource: {src_name}\n"
            + (f"Key Fact: {fact}\n" if variant != "no_original" else "") + f"Voice Persona: {persona}\n" + pblock)
    user_msg = head + f"SUMMARY:\n{body[:1500]}" + (f"\n\nORIGINAL ARTICLE:\n{original}" if original and variant != "no_original" else "")
    return dict(system=system, head=head, user_msg=user_msg, body=body, original=original, known=known,
                political=political, title=title)


# Experiment (Yash, 24 Oct 2026: "I am not convinced Luna can't write a simple script"): a short, focused prompt.
SCRIPT_SYSTEM_SHORT = """Write a 45-55 second Hindi news reel script for SatyaDheesh.

Your viewer: an ordinary Indian scrolling on their phone (a shopkeeper in Kanpur, a farmer's son in Bihar). Not following
this story, not an expert. Talk to them like a friend explaining the news at a chai stall: everyday Hindustani, short
spoken sentences, English words people actually use (in Devanagari). If a figure, unit, official body or term would make
them pause, leave it out or say what it means. They must be able to retell the story after watching: who wants what, why,
and what happened.

Example of the voice:
"कावेरी के पानी पर कर्नाटक और तमिलनाडु फिर आमने-सामने हैं। तमिलनाडु कहता है, उसके किसानों की फसल सूख रही है, उसे और पानी
चाहिए। कर्नाटक का जवाब है, इस बार नदी में आधे से भी कम पानी आया, पहले लोगों के पीने का पानी बचाना है।"

Must do:
- core_say starts with "<source> की रिपोर्ट के मुताबिक". Claims are attributed ("X का कहना है", "आरोप है"); never call
  anyone guilty. Facts only from the article; never change a number or who did what.
- The first time you name a person, say who they are ("कर्नाटक के मुख्यमंत्री डी.के. शिवकुमार"). At most 3 named people.
- No symbols in the *_say lines (write रुपये, परसेंट). ₹ only on screen.
- Lengths: whole voice 110-140 words; hook_say <=25, core_say <=55, twist_say <=40, engagement_say <=20 words.
  headline_hi <=8 words, subtitle_hi <=9, core_points_hi 2-3 bullets <=8 words, twist_detail_hi <=10.

Fields: plain_story_hi (the story in 1-2 plain sentences, not shown), people [{name_hi, role_hi}], headline_hi,
subtitle_hi, hook_say (grab attention), core_title_hi, core_points_hi, core_say (what happened, each side in a dispute),
twist_stat (a number or word different from the headline's), twist_label, twist_detail_hi, twist_say (ground reality and
what happens next), question_hi, engagement_title_hi (2-4 words), engagement_say (one natural question).
Output only the JSON object.
"""

_GEMMA = {}

# Yash, 24 Oct 2026: "Gemma summarises the news in 150-200 crisp words, then the script model writes from that".
GEMMA_REEL_SUMMARY_SYSTEM = """You write the story summary a reel scriptwriter will work from. Read the article and write
150-200 words of plain, simple English (short sentences), so that an ordinary viewer could follow the story:
1. Who is involved: each person with who they are (role, party or state), each organisation with what it does.
2. What happened, and what each side says or wants, and why.
3. The single most surprising or human detail in the article.
4. What happens next, if the article says.
Numbers: keep money in rupees, people, days, dates and percentages. Turn technical quantities (TMC, cusecs, megawatts,
tonnes) into comparisons a viewer can picture ("about a fifth of what Tamil Nadu asked for", "less than half the usual
inflow") instead of the figure. No decimals. Say what an official body does instead of its full name.
Keep attributions exactly (who said or alleged what); facts only from the article; change nothing.
Return JSON: {"summary": "..."}"""
GEMMA_REEL_SUMMARY_SCHEMA = {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]}


GEMMA_REEL_SUMMARY_SYSTEM_HI = GEMMA_REEL_SUMMARY_SYSTEM.replace(
    "150-200 words of plain, simple English (short sentences)",
    "150-200 words of plain, everyday spoken Hindi in Devanagari (बोलचाल की हिंदी, short sentences; English words people "
    "use every day are fine, written in Devanagari; never formal or official Hindi)")


def gemma_model():
    if "m" not in _GEMMA:
        _GEMMA["m"] = Model(download(), n_ctx=8192)
    return _GEMMA["m"]


# B4 (Yash, 24 Oct 2026): one simple job per Gemma call: shorten (English) → translate (Hindi) → simplify (Hindi).
GEMMA_TRANSLATE_SYSTEM = """Translate this news summary into Hindi (Devanagari) faithfully: every fact, name, number, date
and attribution exactly as in the English. Natural Hindi sentences. Return JSON: {"text": "..."}"""
GEMMA_SIMPLIFY_SYSTEM = """Rewrite this Hindi news summary so an ordinary Indian viewer understands it the first time
(a shopkeeper in Kanpur, a farmer's son in Bihar): everyday spoken Hindi (बोलचाल की हिंदी), short sentences; English words
people use every day are fine, in Devanagari. Replace technical units, decimals, jargon and official bodies' names with
what they mean or a comparison a viewer can picture ("मांग का करीब पांचवां हिस्सा", "आधे से भी कम", "पानी बांटने वाली
कमेटी"). Formal or official Hindi becomes the way people talk. Keep EVERY fact, name, money amount, date and attribution
(who said or alleged what); add nothing; keep it 150-200 words. Return JSON: {"text": "..."}"""
TEXT_SCHEMA = {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}


# B5 (Yash, 26 Oct 2026: scripts too dense for a common man): one story, one point. Same steps as B4r; the prompts
# keep only what the viewer needs (B4's "keep every fact" made each step add detail).
GEMMA_B5_STORY_SYSTEM = """You tell a news story to an ordinary Indian who does not follow the news (a shopkeeper in
Kanpur, a farmer's son in Bihar). Read the article and write 100-150 words of plain, simple English (short sentences) for
a reel scriptwriter:
1. The one main thing that happened, in the first sentence.
2. Why it matters to an ordinary person, only if the article shows it or it is plainly true (a price, a job, money,
   safety, a promise). Never invent.
3. The one or two details that make it real: one number a viewer can picture, one human detail.
4. What happens next, if the article says.
Rules: name at most 2 people; everyone else by their role ("a minister", "the officer"). No abbreviations and no names of
offices, departments, laws, systems or schemes people don't already know (police, CBI, ED, Supreme Court, RBI are known):
say what they do instead. Numbers only if a viewer can picture them, rounded, money in rupees. Leave out procedure,
background, side stories and who-said-what that doesn't change the story. Keep every attribution exact (who said or
alleged what); an allegation stays an allegation. Facts only from the article; change nothing.
Return JSON: {"summary": "..."}"""
GEMMA_B5_SIMPLIFY_SYSTEM = GEMMA_SIMPLIFY_SYSTEM.replace(
    "Keep EVERY fact, name, money amount, date and attribution\n(who said or alleged what); add nothing; keep it 150-200 words.",
    "Keep the facts that are in it exactly right and every\nattribution (who said or alleged what); add nothing; drop any "
    "detail an ordinary viewer doesn't need; 100-150 words.")
B5_WRITER_EXTRA = """
THIS REEL: ONE STORY, ONE POINT (the viewer is an ordinary Indian who does not follow the news)
- Open with what happened and why the viewer should care, in the words they use at home.
- Name at most 2 people; everyone else by their role.
- No abbreviations and no names of offices, departments, laws or systems the viewer wouldn't know: say what they do
  ("चुनाव कराने वाली संस्था", "जांच एजेंसी"). Police, CBI, ED, Supreme Court are fine.
- At most two numbers in the whole reel, rounded the way people say them, ones a viewer can picture: no decimals
  anywhere, on screen either ("1.69 करोड़" is said "करीब पौने दो करोड़").
- Say whose loss or gain it is in everyday terms when the story shows it (whose money, whose rice, whose ticket).
- Leave out procedure, background and side details. If a line needs explaining, it doesn't belong in the reel.
- Every line adds something new: never say the same point twice.
- engagement_say: one short question an ordinary viewer can answer from their own life or opinion in a word or two,
  never about procedure or timelines, and only one question.
- Never add anything that isn't in the story.
"""
GEMMA_B5_REVIEW_EXTRA = """
This reel is for an ordinary Indian who does not follow the news, and tells ONE story with ONE point. Also report:
- too_much: a name, office, abbreviation, number, procedure or side detail the viewer does not need to follow the main
  point. The fix is to cut it (say what to cut).
A repeated point is too_much. A fix never brings in a name, office, fund or abbreviation the viewer wouldn't know: say
what it is in plain words instead.
Report "story" only when the main point (what happened and why it matters to the viewer) is unclear, never because a
detail from the article is missing.
Allowed problem types: fact|unclear|formal|legal|story|too_much. Write "fix" in simple English (what to change), not
new Hindi wording."""


LEN_RULE = """- Keep the whole spoken script (hook_say + core_say + twist_say + engagement_say) to 110-140 Hindi words in total,
  roughly 45-55 seconds of speech. Never more than 140 words: count them. hook_say max 25 words, core_say max 55,
  twist_say max 40, engagement_say max 20."""
B5_LEN_RULE = """- SHORT REEL (Yash: 30-40 seconds is fine; a viewer who doesn't understand is not): the whole spoken script
  (hook_say + core_say + twist_say + engagement_say) is 70-100 Hindi words, about 30-40 seconds. hook_say max 18 words,
  core_say max 40, twist_say max 25, engagement_say max 15. Shorter and clear beats longer and complete."""
RICH_RULE = """- Make it rich, not padded. Every script carries: (1) one line of background, (2) at least one concrete detail a viewer
  can picture: a date, an amount in rupees, a person or a place, (3) what happens next, if the article says."""
B5_RICH_RULE = """- One clear point, told simply. Background only if the viewer can't follow without it (one short line). At most one
  or two concrete details a viewer can picture: an amount in rupees, a person or a place; what happens next, if the
  article says."""


def b5_system(system):
    """The writer's prompt for B5: short (30-40 s) and one point, instead of 45-55 s and 'rich'."""
    for old, new in ((LEN_RULE, B5_LEN_RULE), (RICH_RULE, B5_RICH_RULE)):
        if old in system:
            system = system.replace(old, new)
        else:
            print("  (b5_system: a rule to replace was not found; the B5 rules still apply)")
    return system + B5_WRITER_EXTRA


def gemma_b4_story(model, inp, v="b4"):
    """English summary → Hindi translation → plain-Hindi simplification; each step logged. '' on failure."""
    en = gemma_reel_summary(model, inp, system=GEMMA_B5_STORY_SYSTEM if v == "b5" else None)
    if not en:
        return ""
    out = en
    if v == "b5":
        # B5 keeps Gemma in English: its Hindi (translate/simplify) dropped words, mostly names, leaving "। ने कहा",
        # "कि को लीक" (24-26 Oct 2026); Luna writes the Hindi.
        return en
    for step, system in (("translate", GEMMA_TRANSLATE_SYSTEM),
                         ("simplify", GEMMA_B5_SIMPLIFY_SYSTEM if v == "b5" else GEMMA_SIMPLIFY_SYSTEM)):
        try:
            t = time.time()
            nxt = ((model.json(system, out, TEXT_SCHEMA, temperature=0.2, max_tokens=900) or {}).get("text") or "").strip()
        except Exception as e:
            print(f"  B4 {step} failed: {type(e).__name__}; keeping the previous step")
            break
        if len(nxt.split()) < 60:   # a step that lost most of the story is not used
            print(f"  B4 {step}: too short ({len(nxt.split())} words), keeping the previous step")
            break
        out = nxt
        print(f"  B4 {step} ({len(out.split())} words, {time.time() - t:.0f}s): {out}", flush=True)
    return out


def gemma_reel_summary(model, inp, system=None):
    system = system or (GEMMA_REEL_SUMMARY_SYSTEM_HI if os.environ.get("REEL_PROMPT_VARIANT") in ("gemma_brief_hi", "b3")
                        else GEMMA_REEL_SUMMARY_SYSTEM)   # b4 starts from the English summary
    user = (f"Title: {inp['title']}\n\nSHORT SUMMARY:\n{inp['body'][:1200]}\n\n"
            + (f"FULL ARTICLE:\n{inp['original'][:3500]}" if inp["original"] else ""))
    try:
        return (model.json(system, user, GEMMA_REEL_SUMMARY_SCHEMA, temperature=0.2,
                           max_tokens=700) or {}).get("summary", "").strip()
    except Exception as e:
        print(f"  Gemma reel summary failed: {type(e).__name__}")
        return ""


# B3 (Yash, 24 Oct 2026: "time doesn't matter, quality does"): Gemma reviews the script against the full article and
# lists problems; it never rewrites (its rewrites dropped words). Luna fixes exactly the listed problems.
GEMMA_REVIEW_SYSTEM = """You are the fact and clarity checker for a Hindi news reel. You get the FULL ORIGINAL ARTICLE
and the reel SCRIPT (JSON). Check every spoken line (hook_say, core_say, twist_say, engagement_say) and every on-screen
field. Report a problem only when it is real:
- fact: a number, name, date, place, tense or "who said / did / alleged what" that differs from the article, or a claim
  not in the article.
- unclear: a line an ordinary Indian viewer (a shopkeeper, a farmer's son) would not understand the first time they hear
  it: a technical unit, an official body's name, jargon, a decimal, a vague number like "46 यूनिट", or a confusing sentence.
- formal: wording that sounds like a news anchor, a textbook or a government note instead of how people talk.
- legal: an allegation stated as fact, or a claim without who made it.
- story: after the reel, could the viewer retell who wants what, why, and what happened? If not, say what is missing.
For each problem give: field, the exact words, the problem type, and a short suggestion (in Hindi where it is wording).
"<newspaper> की रिपोर्ट के मुताबिक" (e.g. "द हिंदू की रिपोर्ट के मुताबिक") is the channel's required credit to the newspaper
the story comes from, even though the article does not name itself: never report it. Never suggest an explanation in
brackets; suggest the plain word or phrase people use instead.
Do not report style preferences or things that are fine. If everything is fine, return an empty list.
Return JSON: {"problems": [{"field": "...", "quote": "...", "type": "fact|unclear|formal|legal|story", "fix": "..."}]}"""
GEMMA_REVIEW_SCHEMA = {"type": "object", "properties": {"problems": {"type": "array", "items": {"type": "object",
                       "properties": {"field": {"type": "string"}, "quote": {"type": "string"}, "type": {"type": "string"},
                                      "fix": {"type": "string"}}, "required": ["field", "quote", "type", "fix"]}}},
                       "required": ["problems"]}


def gemma_review(model, inp, script, extra=""):
    user = (f"FULL ORIGINAL ARTICLE:\nTitle: {inp['title']}\n{(inp['original'] or inp['body'])[:3500]}\n\n"
            "SCRIPT:\n" + json.dumps({k: v for k, v in script.items() if k != 'plain_story_hi'}, ensure_ascii=False))
    try:
        out = model.json(GEMMA_REVIEW_SYSTEM + extra, user, GEMMA_REVIEW_SCHEMA, temperature=0.1, max_tokens=900) or {}
        return [p for p in out.get("problems") or [] if isinstance(p, dict) and p.get("quote")]
    except Exception as e:
        print(f"  Gemma review failed: {type(e).__name__}")
        return []


def review_loop(inp, aid, script, rounds=2, extra=""):
    """Gemma checks, Luna fixes exactly the listed problems; up to `rounds` rounds or until Gemma finds nothing."""
    for rnd in range(1, rounds + 1):
        probs = gemma_review(gemma_model(), inp, script, extra)
        print(f"  B3 review #{aid} round {rnd}: {len(probs)} problem(s)"
              + "".join(f"\n    - [{p.get('type')}] {p.get('field')}: «{str(p.get('quote'))[:90]}» → {str(p.get('fix'))[:120]}" for p in probs[:8]),
              flush=True)
        if not probs:
            break
        fixed, why = openai_script(inp["system"], inp["user_msg"] + "\n\nYOUR PREVIOUS SCRIPT:\n"
                                   + json.dumps(script, ensure_ascii=False)
                                   + "\n\nA CHECKER FOUND THESE PROBLEMS. Fix exactly these and keep everything else as it is "
                                   "(same facts, attribution, introductions and limits). The checker's quotes may be slightly "
                                   "garbled: find the line it means and write the fix in your own words; never leave a "
                                   "sentence without its subject; if a fix brings in an office, fund or abbreviation, say what "
                                   "it is in plain words, not its short form (police, CBI, ED, CID, Supreme Court are known):\n- "
                                   + "\n- ".join(f"[{p.get('type')}] {p.get('field')}: \"{p.get('quote')}\" → {p.get('fix')}" for p in probs[:10]))
        if not fixed:
            print(f"  B3 fix #{aid} failed ({why}); keeping the last script")
            break
        script = fixed
    return script


BRIEF_SYSTEM = """You prepare a story brief for a Hindi news reel writer. Read the article and write, in simple
everyday Hindi (the way you would explain it to a neighbour), what an ordinary viewer needs to understand this story:
- story_hi: the whole story in 2-3 plain sentences: who wants what, why, and what happened or was decided.
- facts_hi: 4-6 short facts the reel can use, each in plain Hindi: names with who they are, what each side says, money in
  rupees, dates, what happens next. Translate figures into something a viewer can picture ("मांग का करीब पांचवां हिस्सा",
  "आधे से भी कम", "करीब डेढ़ करोड़ रुपये") and leave out technical units, decimals and official body names a viewer
  wouldn't know (say what the body does instead). Keep attributions: who said or alleged what.
- Facts only from the article. Do not change any fact.
Output only the JSON object."""
BRIEF_SCHEMA = {"type": "object", "properties": {"story_hi": {"type": "string"},
                "facts_hi": {"type": "array", "items": {"type": "string"}}},
                "required": ["story_hi", "facts_hi"]}

EDITOR_SYSTEM = """You are the final editor of SatyaDheesh's Hindi news reels. A writer has drafted the script below.
Your ONLY job: make it land with an ordinary Indian viewer scrolling on their phone, a shopkeeper in Kanpur, a farmer's son
in Bihar, a nurse in Indore: smart, but not following this story, and with about 50 seconds to spare.

Go line by line and ask: would that viewer understand this the first time they hear it, and would a friend talk like this?
- If a line sounds like a news anchor, a textbook or an official press note, say it the way people actually talk:
  everyday Hindustani, short sentences, "आप"; everyday English words people use are welcome (in Devanagari).
- If a number, unit, official body, legal or technical term would make the viewer pause, drop it, compare it to
  something they can picture, or say what it means. A number nobody can picture is worse than no number.
- Make sure the story is clear: who wants what, why, and what happened or was decided. In a dispute, each side's position
  in one simple line.
- Keep every fact true and unchanged: numbers you keep, tenses, who said or did what. Add nothing that isn't in the draft
  or the article.
- Keep, exactly: "<source> की रिपोर्ट के मुताबिक" and every "आरोप"/"दावा"/attribution (legal safety); each person's
  introduction on first mention; the length limits; the JSON keys. Keep plain_story_hi consistent with the new lines.
- On-screen fields (headline, subtitle, points, stat, labels, question, card titles) follow the same test.

How the edit should sound (real lines from drafts that missed):
  Draft: "कावेरी जल विनियमन समिति ने बिलिगुंडलु पर 15 दिन तक 3,000 क्यूसेक्स पानी छोड़ने का निर्देश दिया।"
  Edited: "अब पानी बांटने वाली कमेटी ने बीच का रास्ता निकाला: 15 दिन तक कर्नाटक रोज़ कुछ पानी छोड़ेगा, लेकिन ये तमिलनाडु
  की मांग का करीब पांचवां हिस्सा ही है।"
  Draft: "दोनों देशों ने 2030 तक व्यापार को 100 अरब डॉलर तक पहुंचाने का लक्ष्य निर्धारित किया है। संबंधित मंत्रालय सहयोग आगे बढ़ाएंगे।"
  Edited: "भारत और रूस ने टारगेट रखा है, 2030 तक आपस में 100 बिलियन डॉलर का कारोबार। अब सवाल ये है, ये होगा कैसे?"

Return the full edited script as the same JSON object. If a line is already right, keep it.
"""


def luna_edit(inp, draft):
    """Second pass: the plain-language editor (a separate, single-purpose prompt). -> (edited or None, why)."""
    user = ("ARTICLE (for facts only):\n" + inp["head"] + f"SUMMARY:\n{inp['body'][:1500]}\n\n"
            "DRAFT SCRIPT:\n" + json.dumps(draft, ensure_ascii=False))
    return openai_script(EDITOR_SYSTEM, user, model=EDIT_MODEL)


def luna_brief(inp):
    """Step 1 (Yash, 24 Oct 2026): Luna reads the full original and writes a plain-Hindi brief; the writer then works from
    the brief, not the dense English report (which pulled the script into its figures and official register)."""
    user = inp["head"] + f"SUMMARY:\n{inp['body'][:1500]}" + (f"\n\nORIGINAL ARTICLE:\n{inp['original']}" if inp["original"] else "")
    return openai_script(BRIEF_SYSTEM, user, schema_=BRIEF_SCHEMA)


def luna_script(inp, aid, edit=None):
    """OpenAI (Luna) script + the people-intro check with one rewrite. -> (script or None, why, problems)."""
    if os.environ.get("REEL_PROMPT_VARIANT") == "brief":
        brief, why_b = luna_brief(inp)
        if brief:
            head = inp["head"].replace(next((l for l in inp["head"].splitlines() if l.startswith("Key Fact:")), "\x00"), "")
            inp = dict(inp, user_msg=head + "STORY BRIEF (plain Hindi, from the full article):\n" + brief["story_hi"]
                       + "\n- " + "\n- ".join(brief.get("facts_hi") or []))
            print(f"  brief #{aid}: {brief['story_hi'][:200]}")
        else:
            print(f"  brief #{aid} failed ({why_b}); writing from the article")
    script_data, why = openai_script(inp["system"], inp["user_msg"])
    problems = []
    if script_data:
        problems = intro_problems(script_data, inp["known"])
        if problems:  # one rewrite: fix exactly these, change nothing else
            print(f"  intro check #{aid}: {'; '.join(problems)} -> one rewrite")
            fixed, why2 = openai_script(inp["system"], inp["user_msg"] + "\n\nYOUR PREVIOUS SCRIPT:\n"
                                        + json.dumps(script_data, ensure_ascii=False)
                                        + "\n\nFIX ONLY THIS, keep everything else as it is:\n- " + "\n- ".join(problems))
            if fixed:
                script_data = fixed
                problems = intro_problems(script_data, inp["known"])
        edit = edit or os.environ.get("REEL_EDIT_PASS", "on")
        if edit == "off":
            return script_data, why, problems
        if edit == "gemma":
            try:
                user = ("ARTICLE (for facts only):\n" + inp["head"] + f"SUMMARY:\n{inp['body'][:1500]}\n\n"
                        "DRAFT SCRIPT:\n" + json.dumps(script_data, ensure_ascii=False))
                edited, why_e = gemma_model().json(EDITOR_SYSTEM, user, SCRIPT_SCHEMA, temperature=0.2, max_tokens=1400), "gemma"
            except Exception as e:
                edited, why_e = None, f"gemma edit failed: {type(e).__name__}"
        else:
            edited, why_e = luna_edit(inp, script_data)
        if edited and len(intro_problems(edited, inp["known"])) <= len(problems):
            script_data, problems = edited, intro_problems(edited, inp["known"])
            print(f"  plain-language edit #{aid}: applied")
        else:
            print(f"  plain-language edit #{aid}: kept the draft ({why_e or 'the edit lost a person introduction'})")
    return script_data, why, problems


# Spoken and on-screen lines are Hindi: an English word in Latin letters ("deadline", "wetlands") is a slip of the writer.
# All-caps short forms (ED, CID, KPSC) are fine. No word is banned: Luna writes the word in Devanagari or says it plainly.
LATIN_WORD = re.compile(r"\b[A-Za-z][a-z]{2,}\b")


BROKEN = re.compile(r"(?:^|[।?!]\s*|कि\s+)(ने|को|से|का|की|के)\s")


def broken_problems(script):
    """A sentence that starts with a postposition ("। ने कहा", "कि को लीक") lost its subject; U+FFFD is a broken
    character. Both came from Gemma's Hindi steps (24-26 Oct 2026)."""
    out = []
    for k, v in (script or {}).items():
        for s_ in (v if isinstance(v, list) else [v]):
            if isinstance(s_, str) and ("\ufffd" in s_ or BROKEN.search(s_)):
                out.append(f"{k}: a sentence is broken (missing its subject or a broken character): \"{s_[:80]}\" - rewrite it whole")
                break
    return out


def latin_problems(script):
    out = []
    for k, v in (script or {}).items():
        if k == "people":
            continue
        words = sorted({w for s in (v if isinstance(v, list) else [v]) if isinstance(s, str) for w in LATIN_WORD.findall(s)})
        if words:
            out.append(f"{k}: {', '.join(words)} written in English letters: write it in Devanagari (or the plain Hindi word people use)")
    return out


def b4r_script(inp, aid, v="b4r"):
    """LIVE reel script (Yash picked it on 24 Oct 2026 after testing B2/B3/B4/B4r on the same stories): Gemma shortens
    the article in English → translates to Hindi → simplifies the Hindi; Luna writes the script from that story only (no
    editor pass); Gemma checks it against the full article and Luna fixes exactly the listed problems (up to 2 rounds);
    then the English-letters check with one rewrite. -> (script or None, why, problems)"""
    tg = time.time()
    if v == "b5":
        inp = dict(inp, system=b5_system(inp["system"]))
    gs = gemma_b4_story(gemma_model(), inp, v="b5" if v == "b5" else "b4")
    print(f"  {v.upper()} story #{aid} ({len(gs.split())} words, {time.time() - tg:.0f}s): {gs}", flush=True)
    if gs:
        # Only Gemma's plain story: no English headline or "Key Fact" (the headline "…18.402 tmcft…" leaked its figure).
        head = "\n".join(l for l in inp["head"].splitlines() if not l.startswith(("Key Fact:", "Title:"))) + "\n"
        inp = dict(inp, user_msg=head + ("STORY (simple English, everything you need; write the reel in everyday spoken "
                                         "Hindi):\n" if v == "b5" else "STORY (150-200 words, everything you need):\n") + gs)
    else:
        print(f"  B4 story #{aid} failed: Luna writes from the article")
    sc, why, problems = luna_script(inp, aid, edit="off")
    if not sc:
        return None, why, problems
    sc = review_loop(inp, aid, sc, extra=GEMMA_B5_REVIEW_EXTRA if v == "b5" else "")
    latin = latin_problems(sc) + broken_problems(sc)
    if latin:
        print(f"  English-letters / broken-sentence check #{aid}: {'; '.join(latin)} -> one rewrite")
        fixed, _ = openai_script(inp["system"], inp["user_msg"] + "\n\nYOUR PREVIOUS SCRIPT:\n"
                                 + json.dumps(sc, ensure_ascii=False)
                                 + "\n\nFIX ONLY THIS, keep everything else as it is:\n- " + "\n- ".join(latin))
        if fixed and len(intro_problems(fixed, inp["known"])) <= len(intro_problems(sc, inp["known"])):
            sc = fixed
    sc = fix_credit(inp, aid, sc)
    return sc, why, intro_problems(sc, inp["known"]) + latin_problems(sc) + broken_problems(sc)


def fix_credit(inp, aid, sc):
    """Political reels: core_say opens with the newspaper credit (legal safety). A rewrite once replaced it with
    "तेलंगाना सीआईडी की रिपोर्ट के मुताबिक" (26 Oct 2026); put the paper's credit back in code."""
    if not inp.get("political") or not sc.get("core_say"):
        return sc
    src = next((l.split(":", 1)[1].strip() for l in inp["head"].splitlines() if l.startswith("Source:")), "द हिंदू")
    credit, say = f"{src} की रिपोर्ट के मुताबिक", sc["core_say"].strip()
    if say.startswith(credit):
        return sc
    m = re.match(r"^[^,।]{0,40}की रिपोर्ट के मुताबिक,?\s*", say)
    new = credit + ", " + (say[m.end():] if m else say)
    print(f"  credit #{aid}: core_say now opens with '{credit}'" + (f" (was '{m.group(0).strip()}')" if m else ""))
    return dict(sc, core_say=new)


# G1 (Yash, 26 Oct 2026: "lets only gemma now, no luna"): Gemma only, two steps. 1) English notes (Gemma's English is
# reliable). 2) The Hindi reel as plain labelled lines, NOT grammar-constrained JSON (Gemma's Hindi through the JSON
# grammar dropped words, mostly names). Then code checks; one Gemma rewrite for exactly the problems found.
G1_NOTES_SYSTEM = """Read the news article. Write notes in simple English for a 30-second Hindi reel. The viewer is a
normal Indian who doesn't follow the news and has no background on this story.
- background: the one line the viewer needs to follow the story (who is who, what the issue is), or "" if none needed.
- what_happened: 2-3 short sentences.
- people: at most 2 people worth naming, each with who they are in a few simple words (role + party or state).
  Everyone else by role only.
- interesting: why a normal person would find this interesting (the surprise, the stakes, the drama).
- details: 1-2 details a viewer can picture: rounded numbers in rupees or people, places, dates.
- allegations: who accuses whom of what, exactly as in the article ("" if none). An allegation stays an allegation.
- next: what happens next, if the article says ("" otherwise).
No abbreviations or office names a normal person wouldn't know: say what they do (police, CBI, ED, Supreme Court, RBI
are known). Facts only from the article; change nothing."""
G1_NOTES_SCHEMA = {"type": "object", "properties": {
    "background": {"type": "string"}, "what_happened": {"type": "string"},
    "people": {"type": "array", "items": {"type": "object", "properties": {"name": {"type": "string"}, "who": {"type": "string"}},
                                          "required": ["name", "who"]}},
    "interesting": {"type": "string"}, "details": {"type": "string"}, "allegations": {"type": "string"},
    "next": {"type": "string"}},
    "required": ["background", "what_happened", "people", "interesting", "details", "allegations", "next"]}

G1_SCRIPT_SYSTEM = """You write SatyaDheesh's Hindi news reels. The viewer is a normal Indian scrolling on their phone
(Kanpur, Patna, Indore): smart, but not following the news, with no background on this story. Your one job: they
understand the story the first time they hear it, and find it interesting.

HOW TO WRITE
- Everyday spoken Hindi, the way people talk at home. Short sentences. English words people use every day are fine,
  written in Devanagari (पुलिस, कोर्ट, टिकट, सरकार).
- If the viewer needs background, give it first, in one simple line.
- The first time a person is named, say who they are in a few simple words just before the name ("तेलंगाना के
  मुख्यमंत्री रेवंत रेड्डी"). Name at most 2 people; everyone else by role.
- No abbreviations or office names a normal person doesn't know: say what they do. Police, CBI, ED, Supreme Court,
  RBI are known.
- Numbers only if a viewer can picture them, said the way people say them ("करीब पौने दो करोड़", never "1.69 करोड़").
- An allegation stays an allegation: "आरोप है", "पुलिस के मुताबिक", "X का कहना है". Never state a crime as a fact.
- Facts only from the notes. Add nothing. Every line adds something new.
- Spoken lines (HOOK + CORE + TWIST + END) together: 70-100 Hindi words, about 30-40 seconds.

WRITE EXACTLY THESE LINES, each starting with its label, nothing else:
HEADLINE: on screen, max 7 words
SUBTITLE: on screen, max 9 words
HOOK: spoken, max 18 words: the most interesting thing, the way you'd tell a friend
CORE_TITLE: on screen, max 5 words
CORE_POINTS: on screen, 2-3 short points separated by |, each max 7 words
CORE: spoken, max 45 words: background if needed, who, what happened
STAT: on screen, one number or very short phrase
STAT_LABEL: on screen, max 4 words
STAT_DETAIL: on screen, max 9 words
TWIST: spoken, max 25 words: the surprise, the stakes, or what happens next
END_TITLE: on screen, 2-4 words
QUESTION: on screen, max 8 words
END: spoken, one short question a viewer can answer in a word or two
STORY: the whole story in one plain Hindi sentence
PEOPLE: each named person as नाम = कौन हैं, separated by ; (or कोई नहीं)

STYLE EXAMPLE (a different story, for the voice only):
HEADLINE: कावेरी के पानी पर फिर झगड़ा
SUBTITLE: तमिलनाडु को मांग का छोटा हिस्सा
HOOK: कर्नाटक और तमिलनाडु एक बार फिर नदी के पानी पर आमने-सामने हैं।
CORE_TITLE: पानी का बंटवारा
CORE_POINTS: दोनों राज्यों के किसान कावेरी पर निर्भर | तमिलनाडु ने ज्यादा पानी मांगा | कमेटी ने थोड़ा पानी तय किया
CORE: कावेरी नदी दोनों राज्यों से होकर बहती है, और दोनों तरफ के किसान इसी पानी से खेती करते हैं। तमिलनाडु ने ज्यादा पानी मांगा था, लेकिन पानी बांटने वाली कमेटी ने कहा, कर्नाटक पंद्रह दिन तक रोज़ थोड़ा पानी छोड़ेगा।
STAT: पांचवां हिस्सा
STAT_LABEL: मांग का
STAT_DETAIL: तमिलनाडु को मांग का करीब पांचवां हिस्सा
TWIST: यानी तमिलनाडु को जितना चाहिए था, उसका करीब पांचवां हिस्सा ही मिलेगा। अब वहां के किसान नाराज़ हैं।
END_TITLE: पानी पर फैसला
QUESTION: क्या ये बंटवारा सही है?
END: आपके हिसाब से ये बंटवारा सही है?
STORY: कावेरी के पानी पर कमेटी ने तमिलनाडु को उसकी मांग का करीब पांचवां हिस्सा ही दिया है।
PEOPLE: कोई नहीं"""

G1_KEYS = {"HEADLINE": "headline_hi", "SUBTITLE": "subtitle_hi", "HOOK": "hook_say", "CORE_TITLE": "core_title_hi",
           "CORE_POINTS": "core_points_hi", "CORE": "core_say", "STAT": "twist_stat", "STAT_LABEL": "twist_label",
           "STAT_DETAIL": "twist_detail_hi", "TWIST": "twist_say", "END_TITLE": "engagement_title_hi",
           "QUESTION": "question_hi", "END": "engagement_say", "STORY": "plain_story_hi", "PEOPLE": "people"}
G1_LINE = re.compile(r"^\s*\**\s*(HEADLINE|SUBTITLE|HOOK|CORE_TITLE|CORE_POINTS|CORE|STAT_LABEL|STAT_DETAIL|STAT|TWIST|"
                     r"END_TITLE|QUESTION|END|STORY|PEOPLE)\s*\**\s*[:：]\s*(.*)$")


def parse_g1(text):
    """Gemma's labelled lines -> the script dict the reels repo uses. -> (script, missing labels)"""
    sc = {}
    for line in (text or "").splitlines():
        m = G1_LINE.match(line)
        if m and m.group(2).strip():
            sc.setdefault(G1_KEYS[m.group(1)], m.group(2).strip().strip("*").strip())
    pts = sc.get("core_points_hi", "")
    sc["core_points_hi"] = [x.strip() for x in pts.split("|") if x.strip()][:3]
    people = []
    for part in str(sc.get("people", "")).split(";"):
        if "=" in part:
            n, r = part.split("=", 1)
            if n.strip() and "कोई नहीं" not in n:
                people.append({"name_hi": n.strip(), "role_hi": r.strip()})
    sc["people"] = people
    missing = [k for k, f in G1_KEYS.items() if f not in ("people",) and not sc.get(f)]
    return sc, missing


def parse_g1_missing(sc):
    return [k for k, f in G1_KEYS.items() if f != "people" and not sc.get(f)]


def g1_text_problems(sc, inp):
    words = sum(len(str(sc.get(k, "")).split()) for k in ("hook_say", "core_say", "twist_say", "engagement_say"))
    out = []
    if words > 110:
        out.append(f"the spoken lines have {words} words: cut to 70-100 (HOOK + CORE + TWIST + END)")
    if words < 55:
        out.append(f"the spoken lines have only {words} words: the viewer needs a little more to follow (70-100)")
    if re.search(r"\d+\.\d+", " ".join(str(v) for v in sc.values() if isinstance(v, str))):
        out.append("a number has a decimal: say it the way people do (करीब पौने दो करोड़)")
    return out + intro_problems(sc, inp["known"]) + latin_problems(sc) + broken_problems(sc)


def g1_notes_text(notes):
    ppl = "; ".join(f"{p.get('name')} = {p.get('who')}" for p in notes.get("people") or [])
    return "\n".join(f"{k.upper()}: {v}" for k, v in (("background", notes.get("background")),
                     ("what happened", notes.get("what_happened")), ("people", ppl or "none"),
                     ("why it's interesting", notes.get("interesting")), ("details", notes.get("details")),
                     ("allegations", notes.get("allegations")), ("next", notes.get("next"))) if v)


def g1_script(inp, aid, model=None, direct=False):
    """Gemma-only reel script. direct=True (variant g1d, experiment): no notes step, the script is written straight from
    the article. -> (script or None, why, problems)"""
    model = model or gemma_model()
    t0 = time.time()
    if direct:
        ntext = (f"Title: {inp['title']}\n\nSUMMARY:\n{inp['body'][:1200]}\n\n"
                 + (f"FULL ARTICLE:\n{inp['original'][:3000]}" if inp["original"] else ""))
    try:
        if direct:
            raise StopIteration
        notes = model.json(G1_NOTES_SYSTEM, f"Title: {inp['title']}\n\nSUMMARY:\n{inp['body'][:1200]}\n\n"
                           + (f"FULL ARTICLE:\n{inp['original'][:3500]}" if inp["original"] else ""),
                           G1_NOTES_SCHEMA, temperature=0.2, max_tokens=600) or {}
    except StopIteration:
        notes = None
    except Exception as e:
        return None, f"G1 notes failed: {type(e).__name__}", []
    if notes is not None:
        ntext = g1_notes_text(notes)
        print(f"  G1 notes #{aid} ({time.time() - t0:.0f}s):\n{ntext}", flush=True)
    src = next((l.split(":", 1)[1].strip() for l in inp["head"].splitlines() if l.startswith("Source:")), "द हिंदू")
    user = (("THE ARTICLE:\n" if direct else "NOTES (everything you need):\n") + ntext
            + (f"\n\nThis is a political story: CORE starts with \"{src} की रिपोर्ट के मुताबिक\"." if inp["political"] else ""))
    sc, problems = None, []
    for attempt in range(2):
        t = time.time()
        try:
            prompt = user if attempt == 0 else (user + "\n\nYOUR SCRIPT:\n" + raw + "\n\nFIX ONLY THESE, keep everything else; "
                                                 "write all the lines again:\n- " + "\n- ".join(problems))
            raw = model.text(G1_SCRIPT_SYSTEM, prompt, temperature=0.4, max_tokens=900)
        except Exception as e:
            return sc, f"G1 script failed: {type(e).__name__}", problems
        new, missing = parse_g1(raw)
        if missing and sc and attempt:
            print(f"  G1 rewrite #{aid} lost {missing}; keeping the first script")
            break
        sc = new
        problems = ([f"missing the line(s): {', '.join(missing)}"] if missing else []) + g1_text_problems(sc, inp)
        print(f"  G1 script #{aid} try {attempt + 1} ({time.time() - t:.0f}s): {len(problems)} problem(s)"
              + "".join(f"\n    - {p}" for p in problems), flush=True)
        if not problems:
            break
    if not sc or parse_g1_missing(sc):   # the reel needs every card's text
        return None, f"G1 script incomplete: {parse_g1_missing(sc) if sc else 'no script'}", problems
    sc, notes_l, ok = legal_pass(sc)   # every story (not only political): "कथित" before a named wrongdoing
    for n in notes_l:
        print(f"  legal #{aid}: {n}")
    sc = fix_credit(inp, aid, sc)
    return sc, ("G1" if ok else "G1: abusive label"), g1_text_problems(sc, inp)


def json_vs_text_check(inp, aid, model=None):
    """Step 0 (26 Oct 2026): does Gemma's Hindi drop words only through the JSON grammar? Same request both ways."""
    model = model or gemma_model()
    src = f"Title: {inp['title']}\n\n{inp['body'][:1200]}"
    ask = "Tell this news in 4-5 simple spoken Hindi sentences (Devanagari), naming the people in it with who they are."
    try:
        j = (model.json(ask, src, TEXT_SCHEMA, temperature=0.2, max_tokens=500) or {}).get("text", "")
        t = model.text(ask + " Write only the sentences.", src, temperature=0.2, max_tokens=500)
    except Exception as e:
        print(f"  json/text check #{aid} failed: {type(e).__name__}")
        return
    bj, bt = broken_problems({"x": j}), broken_problems({"x": t})
    block = f"JSON mode ({'BROKEN' if bj else 'ok'}): {j}\nTEXT mode ({'BROKEN' if bt else 'ok'}): {t}"
    print(f"== json vs text #{aid}\n{block}", flush=True)
    notice(f"Gemma json vs text #{aid}", block)


def live_script(inp, aid):
    """The live script pipeline: B4r; REEL_PIPELINE=luna (repo variable) goes back to Luna alone without a code change."""
    pipe = os.environ.get("REEL_PIPELINE", "b4r")
    if pipe == "g1":
        return g1_script(inp, aid)
    if pipe == "luna":
        return luna_script(inp, aid)
    return b4r_script(inp, aid, v="b5" if pipe == "b5" else "b4r")


def luna_test(m_db, u_db, ids):
    """Fast check of the LIVE script writer (Luna) on real stories: same prompt, intro check and legal pass as a real
    reel, no Gemma, nothing saved, dispatched or posted. ids empty -> the 3 newest reel candidates."""
    if not ids:
        ids = [int(r[0]) for r in u_db.execute(
            "SELECT article_id FROM reel_candidates WHERE viral_score >= 6 ORDER BY created_at DESC LIMIT 3").rows]
    for aid in ids:
        c = u_db.execute("SELECT topic, wow_fact FROM reel_candidates WHERE article_id = ?", [aid]).rows
        topic, fact = (str(c[0][0]), str(c[0][1])) if c else ("politics", "")
        r = m_db.execute("SELECT title, rephrased_title, rephrased_article, category, image_url, url, content "
                         "FROM articles WHERE id = ?", [aid]).rows
        if not r:
            print(f"## {aid}: not found")
            continue
        inp = script_inputs(r[0], topic, fact, "charlie")
        SPENT["inr"] = 0.0   # the budget is per reel: each test story is its own reel
        if os.environ.get("REEL_PROMPT_VARIANT") == "b3":
            os.environ["REEL_PROMPT_VARIANT_B3"] = "1"
        if os.environ.get("REEL_PROMPT_VARIANT") in ("gemma_brief", "gemma_brief_hi", "gemma_only", "b3", "b4"):
            tg = time.time()
            gs = (gemma_b4_story(gemma_model(), inp) if os.environ.get("REEL_PROMPT_VARIANT") == "b4"
                  else gemma_reel_summary(gemma_model(), inp))
            print(f"## GEMMA SUMMARY #{aid} ({len(gs.split())} words, {time.time() - tg:.0f}s): {gs}", flush=True)
            if gs:
                # Only Gemma's plain summary: no English headline or "Key Fact" (the headline "…18.402 tmcft…" leaked
                # its figure into the script).
                head = "\n".join(l for l in inp["head"].splitlines() if not l.startswith(("Key Fact:", "Title:"))) + "\n"
                inp = dict(inp, user_msg=head + "STORY (150-200 words, everything you need):\n" + gs)
        t0 = time.time()
        if os.environ.get("REEL_PROMPT_VARIANT", "") in ("", "b4r"):   # the live pipeline, exactly
            sc, why, problems = live_script(inp, aid)
        elif os.environ.get("REEL_PROMPT_VARIANT") == "b5":
            sc, why, problems = b4r_script(inp, aid, v="b5")
        elif os.environ.get("REEL_PROMPT_VARIANT") == "g1":
            json_vs_text_check(inp, aid)
            sc, why, problems = g1_script(inp, aid)
        elif os.environ.get("REEL_PROMPT_VARIANT") == "g1d":
            sc, why, problems = g1_script(inp, aid, direct=True)
        elif os.environ.get("REEL_PROMPT_VARIANT") == "gemma_only":   # Gemma writes the script itself (comparison)
            try:
                sc, why = gemma_model().json(inp["system"], inp["user_msg"], SCRIPT_SCHEMA, temperature=0.25, max_tokens=1400), "gemma"
            except Exception as e:
                sc, why = None, f"gemma script failed: {type(e).__name__}"
            problems = intro_problems(sc, inp["known"]) if sc else []
        else:
            sc, why, problems = luna_script(inp, aid)
            if sc and os.environ.get("REEL_PROMPT_VARIANT") == "b3":
                sc = review_loop(inp, aid, sc)
                problems = intro_problems(sc, inp["known"])
        if not sc:
            print(f"## {aid}: Luna gave no script ({why})")
            continue
        legal = ""
        if inp["political"]:
            sc, notes, ok = legal_pass(sc)
            legal = f" | legal ok={ok} {notes or ''}"
        block = (f"## #{aid} [{topic}] {os.environ.get('REEL_PROMPT_VARIANT') or 'live'}/{os.environ.get('REEL_EDIT_PASS') or 'edit'} {OPENAI_MODEL}{' + edit ' + EDIT_MODEL if EDIT_MODEL else ''} {inp['title'][:50]}\n({time.time() - t0:.0f}s, Rs {SPENT['inr']:.2f}){legal}"
              f"{' | PROBLEMS LEFT: ' + '; '.join(problems) if problems else ''}\n"
              f"STORY: {sc.get('plain_story_hi')}\n"
              f"PEOPLE: {'; '.join(p.get('name_hi', '') + ' = ' + p.get('role_hi', '') for p in sc.get('people') or [])}\n"
              f"ON SCREEN: {sc.get('headline_hi')} | {sc.get('subtitle_hi')}\n"
              f"HOOK: {sc.get('hook_say')}\nCORE: {sc.get('core_say')}\nTWIST: {sc.get('twist_say')}\n"
              f"CARD 3: {sc.get('twist_stat')} {sc.get('twist_label')} | {sc.get('twist_detail_hi')}\n"
              f"CARD 4: {sc.get('engagement_title_hi')} | {sc.get('question_hi')}\n"
              f"END: {sc.get('engagement_say')}\n")
        print(block, flush=True)
        notice(f"Script #{aid}", block)


def script_test(m_db, u_db, ids):
    """Write (and review) the reel script for these article ids and print it, with prompt sizes and timings.
    Nothing is saved or dispatched."""
    model = Model(download())
    for aid in ids:
        c = u_db.execute("SELECT topic, wow_fact FROM reel_candidates WHERE article_id = ?", [aid]).rows
        topic, fact = (str(c[0][0]), str(c[0][1])) if c else ("politics", "")
        r = m_db.execute("SELECT title, rephrased_title, rephrased_article, url, content FROM articles WHERE id = ?", [aid]).rows
        if not r:
            print(f"## {aid}: not found")
            continue
        r = r[0]
        title, political = r[1] or r[0], is_political(topic)
        src_name = "इंडियन एक्सप्रेस" if "indianexpress" in str(r[3] or "").lower() else "द हिंदू"
        body, original = decompress(r[2], limit=4000), clean_original(decompress(r[4], limit=12000))[:4000]
        system = SCRIPT_SYSTEM_CHARLIE + SCRIPT_SOURCE_RULES + (SCRIPT_POLITICAL_EXTRA.replace("{source}", src_name) if political else "")
        head = f"NEWS ARTICLE\nTitle: {title}\nTopic: {topic}\nSource: {src_name}\nKey Fact: {fact}\nVoice Persona: charlie\n"
        prompt = fit_prompt(model, system, head, body[:1500], original, max_tokens=550)
        n = lambda t: len(model.llm.tokenize(t.encode("utf-8"), add_bos=False))
        print(f"## {aid} [{topic}] political={political}: original {len(original)} chars, prompt {n(system)} + {n(prompt)} tokens "
              f"(context {model.llm.n_ctx()}), original kept: {'ORIGINAL ARTICLE' in prompt}", flush=True)
        t0 = time.time()
        sc = model.json(system, prompt, SCRIPT_SCHEMA, temperature=0.25, max_tokens=550)
        if political:
            sc, notes, legal_ok = legal_pass(sc)
            print(f"legal pass: ok={legal_ok} {notes}", flush=True)
        print(f"script in {time.time() - t0:.0f}s:\n{json.dumps(sc, ensure_ascii=False, indent=1)}", flush=True)
        ev = (f"NEWS ARTICLE: {title}\nTOPIC: {topic}{' (POLITICAL: apply the legal safety check)' if political else ''}\n"
              f"ASSIGNED VOICE: charlie\nHEADLINE: {sc.get('headline_hi')}\n"
              f"ON-SCREEN: {sc.get('core_title_hi')} | {' | '.join(sc.get('core_points_hi') or [])} | {sc.get('twist_stat')} "
              f"{sc.get('twist_label')} | {sc.get('twist_detail_hi')}\nHOOK: {sc.get('hook_say')}\nCORE: {sc.get('core_say')}\n"
              f"TWIST: {sc.get('twist_say')}\nENGAGEMENT: {sc.get('engagement_say')}")
        rv = model.json(SUITABILITY_SYSTEM + (SUITABILITY_POLITICAL_EXTRA if political else ""), ev, SUITABILITY_SCHEMA,
                        temperature=0.1, max_tokens=200)
        print(f"review: {json.dumps(rv, ensure_ascii=False)}\n", flush=True)


def notice(title, text):
    """With REEL_STREAM_NOTICES set (Actions), print the block as an annotation right away, so a run that is cut off by
    its time limit still shows what it finished (logs can't be read from outside)."""
    if os.environ.get("REEL_STREAM_NOTICES"):
        enc = text[:2200].replace("%", "%25").replace("\r", "").replace("\n", "%0A")
        print(f"::notice title={title[:60]}::{enc}", flush=True)


def rank(rows):
    """rows: (aid, topic, score, published_at) -> the dispatch order (qualifying stories only)."""
    q = [r for r in rows if int(r[2]) >= 7 or (is_political(r[1]) and int(r[2]) >= 6)]
    return sorted(q, key=lambda r: (int(r[2]) + (1 if is_political(r[1]) else 0), r[3] or 0), reverse=True)


def select_test(m_db, u_db, n=45, scripts=int(os.environ.get("SELECT_TEST_SCRIPTS") or 3)):
    """Read-only: re-score the last 24 h's scored stories with the common-man rubric (v2), show the old vs new picks,
    then write B5 scripts for the new top `scripts`. Nothing is saved, dispatched or posted."""
    now = int(time.time())
    old = u_db.execute("SELECT article_id, topic, viral_score, published_at FROM reel_candidates WHERE created_at >= ? "
                       "ORDER BY (viral_score >= 6) DESC, created_at DESC LIMIT ?", [now - 24 * 3600, n]).rows   # every old contender + the newest others
    posted = {int(r[0]) for r in u_db.execute("SELECT article_id FROM reel_posts").rows}
    ids = [int(r[0]) for r in old]
    arts = {}
    for chunk in [ids[i:i + 50] for i in range(0, len(ids), 50)]:
        ph = ",".join("?" * len(chunk))
        for r in m_db.execute(f"SELECT id, title, rephrased_title, rephrased_article, category FROM articles WHERE id IN ({ph})", chunk).rows:
            arts[int(r[0])] = r
    model = gemma_model()
    fb = audience_feedback(u_db, n=6)   # real Instagram reach of our recent reels
    print(f"== REACH{fb or ' (Instagram reach not readable)'}", flush=True)
    notice("Instagram reach of our reels", fb or "not readable")
    new, line = [], {}
    t0 = time.time()
    for o in old:
        a = arts.get(int(o[0]))
        if not a:
            continue
        prompt = f"Title: {a[2] or a[1]}\nCategory: {a[4]}\nArticle Body:\n{decompress(a[3])[:1000]}\n"
        try:
            res = model.json(select_system() if select_v2() else SYSTEM_INTEREST, prompt, SCHEMA_COMMON, temperature=0.1, max_tokens=400)
        except Exception as e:
            print(f"  #{o[0]} rescore failed: {type(e).__name__}")
            continue
        new.append((int(o[0]), str(res.get("topic") or o[1]), int(res.get("viral_score") or 0), o[3]))
        line[int(o[0])] = (str(res.get("one_line_hi") or ""), str(res.get("why") or ""))
    print(f"(re-scored {len(new)} stories in {time.time() - t0:.0f}s)")
    title = lambda aid: ((arts.get(aid) or [0, "", ""])[2] or (arts.get(aid) or [0, ""])[1] or "")[:80]
    oldr, newr = [r for r in rank(old) if int(r[0]) not in posted], [r for r in rank(new) if r[0] not in posted]
    oldsc = {int(r[0]): int(r[2]) for r in old}
    newsc = {r[0]: r[2] for r in new}
    secs = [("SELECT old picks", "\n".join(f"#{r[0]} old {r[2]} [{r[1]}] {title(int(r[0]))}" for r in oldr[:8])),
            ("SELECT new picks", "\n".join(f"#{r[0]} new {r[2]} (old {oldsc.get(r[0])}) [{r[1]}] {title(r[0])}\n   = {line[r[0]][0]}"
                                           for r in newr[:8])),
            ("SELECT dropped", "\n".join(f"#{r[0]} old {r[2]} → new {newsc.get(int(r[0]))}: {title(int(r[0]))}\n   why: "
                                        f"{line.get(int(r[0]), ('', ''))[1]}" for r in oldr[:8]
                                        if int(r[0]) not in [x[0] for x in newr[:8]]))]
    for t, body in secs:
        print(f"== {t}\n{body}", flush=True)   # not "## ": the workflow's end-of-run split is only for scripts
        notice(t, body)
    top = [r[0] for r in newr[:scripts]]
    if top:
        os.environ["REEL_PROMPT_VARIANT"] = os.environ.get("REEL_PROMPT_VARIANT") or "b5"
        luna_test(m_db, u_db, top)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=30, help="Number of unscored articles to evaluate")
    ap.add_argument("--dry-run", action="store_true", help="Print scores without writing to DB")
    ap.add_argument("--dispatch", action="store_true", help="Force dispatch of top candidate")
    ap.add_argument("--no-dispatch", action="store_true", help="Do not trigger reels repo")
    ap.add_argument("--select-test", action="store_true", help="re-score the last 24 h with the common-man rules, "
                    "show old vs new picks and B5 scripts for the new top 3; print only")
    ap.add_argument("--script-test", default="", help="comma-separated article ids: write and review their scripts, print only")
    ap.add_argument("--luna-test", default=None, help="article ids (comma-separated, or empty = 3 newest candidates): "
                                                      "the live Luna script only, fast, print only")
    args = ap.parse_args()
    if args.select_test:
        select_test(main_db(), upsc_db())
        return
    if args.luna_test is not None:
        luna_test(main_db(), upsc_db(), [int(x) for x in args.luna_test.split(",") if x.strip().isdigit()])
        return
    if args.script_test:
        script_test(main_db(), upsc_db(), [int(x) for x in args.script_test.split(",") if x.strip().isdigit()])
        return

    now = int(time.time())
    m_db = main_db()
    u_db = upsc_db()

    # Find articles from the last 24 hours not yet scored in reel_candidates
    since = now - 24 * 3600
    # v2: a story scored by the old rules is scored again by the common-man rules (INSERT OR REPLACE)
    already = {r[0] for r in u_db.execute("SELECT article_id FROM reel_candidates WHERE created_at >= ? AND model LIKE ?",
                                          [since - 86400, "%" + SELECT_TAG.get(select_mode(), "")]).rows}

    # Fetch candidate articles across all categories
    rows = m_db.execute(
        "SELECT id, title, rephrased_title, rephrased_article, category, scraped_at "
        "FROM articles WHERE scraped_at >= ? ORDER BY id DESC LIMIT 150",
        [since]
    ).rows

    candidates = []
    for r in rows:
        aid = int(r[0])
        if aid not in already:
            candidates.append({
                "id": aid,
                "title": r[2] or r[1],
                "body": decompress(r[3]),
                "category": r[4],
                "scraped_at": int(r[5])
            })
        if len(candidates) >= args.batch:
            break

    if not candidates:
        print(f"No new unscored articles found in the last 24h.")
        if not args.no_dispatch and not args.dry_run:
            dispatch_daily_reel(u_db, m_db, force=args.dispatch)
        return

    print(f"Evaluating {len(candidates)} new articles with Gemma 4 12B ({MODEL_NAME})...")
    model = gemma_model()   # one Gemma (8k context) for scoring, the B4r script steps and the quality gate
    global FEEDBACK
    FEEDBACK = audience_feedback(u_db)
    if FEEDBACK:
        print(FEEDBACK)

    scored_count = 0
    high_score_count = 0

    for idx, art in enumerate(candidates, start=1):
        prompt = (
            f"Title: {art['title']}\n"
            f"Category: {art['category']}\n"
            f"Article Body:\n{art['body'][:1000]}\n"
        )
        try:
            res = (model.json(select_system() + FEEDBACK, prompt, SCHEMA_COMMON, temperature=0.1, max_tokens=400) if select_v2()
                   else model.json(SYSTEM + FEEDBACK, prompt, SCHEMA, temperature=0.1, max_tokens=250))
            score = int(res.get("viral_score") or 0)
            topic = str(res.get("topic") or art["category"])
            hook = str(res.get("hook_angle") or "")
            fact = str(res.get("wow_fact") or "")
            why = str(res.get("why") or "")

            print(f"[{idx}/{len(candidates)}] ID {art['id']} -> Score {score}/10 [{topic}] {art['title'][:70]}")
            if score >= 7:
                print(f"    🌟 High Viral Score: {hook}")
                high_score_count += 1

            if not args.dry_run:
                u_db.execute(
                    "INSERT OR REPLACE INTO reel_candidates "
                    "(article_id, published_at, topic, viral_score, hook_angle, wow_fact, why, model, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [art["id"], art["scraped_at"], topic, score, hook, fact, why, MODEL_NAME + SELECT_TAG.get(select_mode(), ""), now]
                )
            scored_count += 1
        except Exception as e:
            print(f"  Error scoring article {art['id']}: {e}")

    print(f"\nDone: {scored_count} articles scored ({high_score_count} with viral score >= 7).")

    if not args.no_dispatch and not args.dry_run:
        dispatch_daily_reel(u_db, m_db, model=model, force=args.dispatch)


if __name__ == "__main__":
    try:
        main()
    finally:
        close_all()
