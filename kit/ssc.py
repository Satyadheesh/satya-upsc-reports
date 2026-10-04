"""SSC CGL General Awareness (TCS Pattern) flashcard generation using Gemma 4 12B."""
import json
import re

PROMPT_VERSION = "ssc-v1"

SYSTEM = """You are a senior SSC CGL General Awareness paper setter (TCS pattern, Tier-1/Tier-2). You convert one daily current-affairs note into ONE rapid-fire active-recall flashcard.

THINK LIKE SSC, NOT UPSC
- SSC tests direct recall: Who, What, Where, When, How many, Which. No analysis, no "with reference to", no multi-statement evaluation, no "significance" or "impact".
- Pick the single most exam-worthy entity from the note: a person, place, scheme, number, date, trophy, exercise, organisation or book.

OUTPUT: one JSON object with exactly these keys, nothing else:
- ssc_question: one direct question ending with "?". Max 120 chars. Must NOT contain or hint at the answer.
- ssc_answer: the bare answer: a name, place, number, scheme or short phrase. No full sentence, no verb. Max 50 chars.
- key_fact: one supporting fact taken from the note (duration, predecessor, target, batch, venue, edition, score). Max 120 chars.
- static_gk: one high-yield static fact linked to the answer or its organisation. Max 140 chars.

STATIC GK RULES
- Prefer: headquarters, founding/launch year, constitutional article, first person to hold the post, nodal ministry, parent body, associated river/state/capital, motto.
- Use only stable facts you are certain about. Never state who currently holds a post in static_gk.
- If you are not sure of a static fact, give a different certain one. Never guess years, articles or names.

FACTUAL BOUNDARIES
- ssc_answer and key_fact must come ONLY from the supplied note. Never add numbers, names or dates that are not in it.
- Copy numbers, spellings and units exactly. Use the ₹ symbol and "crore"/"lakh".
- If the note lacks a clean answerable fact, use the Prelims pointers or Key facts field. Do not invent one.

STYLE
- Telegraphic. No filler words, no "The government...", no explanations.
- Question patterns: "Who was appointed as...?", "In which state/city was ... held?", "What is the outlay of ...?", "Which country became ...?", "Which institution ...?"
- Do not output markdown, comments or text outside the JSON.

LANGUAGE
- Obey the Output language field. If en, write English. If hi, follow the Hindi rules below.
- Hindi rules: write the question the way Hindi exam papers do, not as a literal translation. Use patterns like "हाल ही में किसे ... नियुक्त किया गया?", "... का आयोजन कहाँ किया गया?", "किस देश ने ...?", "... योजना का कुल बजट कितना है?". Use Devanagari, with Western digits (0-9) for numbers and dates. Keep ₹ and use "करोड़". Keep acronyms in their common form (ISRO, CISF, MeitY). Use the standard Hindi form of well-known proper nouns (e.g. दिल्ली, राजस्थान). The answer must be a bare name, number or phrase, with no sentence ending in "है"."""

USER_TEMPLATE = """Output language: {lang}   (en | hi)

NOTE
Title: {title}
Paper: {paper}
Why in news: {why_in_news}
Key facts: {key_facts}
Prelims pointers:
{prelims_pointers}
Keywords: {keywords}

Create the SSC CGL flashcard JSON for this note."""

FEW_SHOTS_EN = [
    (
        """Output language: en

NOTE
Title: Neena Singh appointed first woman Director General of CISF
Paper: GS2 · Governance
Why in news: Senior IPS officer Neena Singh was appointed DG of the Central Industrial Security Force, the first woman to head the force.
Key facts: 1989-batch IPS officer, Rajasthan cadre; earlier served in CBI and as Special DG in CISF.
Prelims pointers:
- person: Neena Singh
- institution: CISF
Keywords: ["CISF", "Neena Singh", "Director General"]

Create the SSC CGL flashcard JSON for this note.""",
        {
            "ssc_question": "Who became the first woman Director General of CISF?",
            "ssc_answer": "Neena Singh",
            "key_fact": "1989-batch IPS officer of Rajasthan cadre.",
            "static_gk": "CISF raised 1969 under CISF Act 1968; HQ: New Delhi; works under MHA.",
        },
    ),
    (
        """Output language: en

NOTE
Title: Government approves ₹10,372 crore IndiaAI Mission to bolster compute capacity
Paper: GS3 · Science & Technology
Why in news: The Union Cabinet chaired by PM Modi approved the IndiaAI Mission with a budget outlay of ₹10,372 crore over 5 years to establish 10,000 GPUs.
Key facts: Outlay ₹10,372 crore for 5 years; AI compute capacity of 10,000+ GPUs; IndiaAI Innovation Centre; IndiaAI Datasets Platform; implemented by Independent Business Division under Digital India Corporation.
Prelims pointers:
- scheme: IndiaAI Mission
- institution: Digital India Corporation (DIC) under MeitY
- data_fact: 10,000 GPUs compute capacity
Keywords: ["IndiaAI Mission", "MeitY", "GPUs"]

Create the SSC CGL flashcard JSON for this note.""",
        {
            "ssc_question": "What is the total financial outlay approved for the IndiaAI Mission?",
            "ssc_answer": "₹10,372 crore",
            "key_fact": "Spread over 5 years; target of 10,000+ GPUs of compute capacity.",
            "static_gk": "Nodal ministry: MeitY; Digital India launched on 1 July 2015.",
        },
    ),
    (
        """Output language: en

NOTE
Title: India-US joint military exercise Yudh Abhyas 2024 begins in Alaska
Paper: GS3 · Internal Security
Why in news: The 20th edition of Exercise Yudh Abhyas began at Fort Wainwright, Alaska, with Indian Army and US Army contingents.
Key facts: 20th edition; venue Fort Wainwright, Alaska; September 2024; focus on interoperability and joint operations.
Prelims pointers:
- exercise: Yudh Abhyas
- place: Alaska, USA
Keywords: ["Yudh Abhyas", "Indian Army", "US Army", "Alaska"]

Create the SSC CGL flashcard JSON for this note.""",
        {
            "ssc_question": "In which US state was the 20th edition of Exercise Yudh Abhyas held?",
            "ssc_answer": "Alaska",
            "key_fact": "Held at Fort Wainwright in Sept 2024; India-US Army exercise.",
            "static_gk": "Alaska was bought from Russia in 1867; Yudh Abhyas has been held since 2004.",
        },
    ),
]

FEW_SHOTS_HI = [
    (
        """Output language: hi

NOTE
Title: D Gukesh becomes youngest World Chess Champion
Paper: Miscellaneous · Sports
Why in news: Indian Grandmaster D Gukesh defeated China's Ding Liren in the World Chess Championship final in Singapore at age 18.
Key facts: Won 7.5-6.5 in the final game decider; youngest undisputed world champion; venue Singapore; December 2024.
Prelims pointers:
- person: D Gukesh
- event: FIDE World Chess Championship 2024
Keywords: ["Gukesh", "Ding Liren", "FIDE", "Singapore"]

Create the SSC CGL flashcard JSON for this note.""",
        {
            "ssc_question": "हाल ही में विश्व शतरंज चैंपियनशिप 2024 किस भारतीय खिलाड़ी ने जीती?",
            "ssc_answer": "डी. गुकेश",
            "key_fact": "सिंगापुर में चीन के डिंग लिरेन को हराया; 18 वर्ष में सबसे युवा चैंपियन।",
            "static_gk": "FIDE की स्थापना 1924, मुख्यालय: लुसाने (स्विट्जरलैंड); पहले भारतीय विश्व चैंपियन: विश्वनाथन आनंद।",
        },
    )
]

SCHEMA_EN = {
    "type": "object",
    "properties": {
        "ssc_question": {"type": "string", "minLength": 15, "maxLength": 120, "pattern": r"^[^\n]*\?$"},
        "ssc_answer":   {"type": "string", "minLength": 1,  "maxLength": 50,  "pattern": r"^[^\n]*$"},
        "key_fact":     {"type": "string", "minLength": 5,  "maxLength": 120, "pattern": r"^[^\n]*$"},
        "static_gk":    {"type": "string", "minLength": 5,  "maxLength": 140, "pattern": r"^[^\n]*$"},
    },
    "required": ["ssc_question", "ssc_answer", "key_fact", "static_gk"],
    "additionalProperties": False,
}

SCHEMA_HI = {
    "type": "object",
    "properties": {
        "ssc_question": {"type": "string", "minLength": 15, "maxLength": 150, "pattern": r"^[^\n]*[?？]$"},
        "ssc_answer":   {"type": "string", "minLength": 1,  "maxLength": 70,  "pattern": r"^[^\n]*$"},
        "key_fact":     {"type": "string", "minLength": 5,  "maxLength": 170, "pattern": r"^[^\n]*$"},
        "static_gk":    {"type": "string", "minLength": 5,  "maxLength": 190, "pattern": r"^[^\n]*$"},
    },
    "required": ["ssc_question", "ssc_answer", "key_fact", "static_gk"],
    "additionalProperties": False,
}


def schema(lang="en"):
    return SCHEMA_HI if lang == "hi" else SCHEMA_EN


def user_prompt(note, lang="en", feedback=None):
    ptrs = "\n".join(
        f"- {p.get('type', '')}: {p.get('text', '')}"
        for p in (note.get("prelims_pointers") or [])
        if isinstance(p, dict)
    )
    if not ptrs:
        ptrs = "- none"

    keywords = json.dumps(note.get("keywords") or [])
    text = USER_TEMPLATE.format(
        lang=lang,
        title=note.get("title") or note.get("original_title") or "",
        paper=f"{note.get('gs_paper') or 'GS'} · {note.get('subject') or 'General'}",
        why_in_news=note.get("why_in_news") or "",
        key_facts=note.get("fact_box") or "",
        prelims_pointers=ptrs,
        keywords=keywords,
    )
    if feedback:
        text += f"\n\nYour previous answer was rejected: {feedback}. Please rewrite and fix that."
    return text


def build_messages(note, lang="en", feedback=None):
    shots = FEW_SHOTS_HI if lang == "hi" else FEW_SHOTS_EN
    msgs = [{"role": "system", "content": SYSTEM}]
    for u, a in shots:
        msgs.append({"role": "user", "content": u})
        msgs.append({"role": "assistant", "content": json.dumps(a, ensure_ascii=False)})
    msgs.append({"role": "user", "content": user_prompt(note, lang, feedback)})
    return msgs


class SscInvalid(ValueError):
    pass


def validate_ssc_card(card, note, lang="en"):
    if not isinstance(card, dict):
        raise SscInvalid("Output must be a JSON object")

    for k in ("ssc_question", "ssc_answer", "key_fact", "static_gk"):
        val = card.get(k)
        if not val or not isinstance(val, str) or not val.strip():
            raise SscInvalid(f"Missing or empty field: {k}")
        card[k] = val.strip()

    q = card["ssc_question"]
    ans = card["ssc_answer"]
    kf = card["key_fact"]

    # 1. Must end in ? or ？
    if not (q.endswith("?") or q.endswith("？")):
        raise SscInvalid("Question must end with '?'")

    # 2. Leakage check: answer should not appear inside question
    if len(ans) >= 4 and ans.lower() in q.lower():
        raise SscInvalid(f"Answer '{ans}' leaked inside question '{q}'")

    # 3. Hindi check: answer must not end in auxiliary verbs (है, हैं, था, थी, थे)
    if lang == "hi":
        trimmed = ans.rstrip(".।! ")
        if trimmed.endswith(("है", "हैं", "था", "थी", "थे")):
            raise SscInvalid(f"Hindi answer must be bare entity, cannot end in verb '{trimmed}': {ans}")

    # 4. Digit grounding: any 2+ digit numbers in answer and key_fact must appear in source note
    note_text = " ".join([
        str(note.get("title") or ""),
        str(note.get("original_title") or ""),
        str(note.get("why_in_news") or ""),
        str(note.get("fact_box") or ""),
        str(note.get("mains_question") or ""),
        str(note.get("prelims_pointers") or ""),
    ])
    note_digits = set(re.findall(r"\d+", note_text))
    for field_name, text in (("ssc_answer", ans), ("key_fact", kf)):
        for d in re.findall(r"\d+", text):
            if len(d) >= 2 and d not in note_digits:
                raise SscInvalid(f"Digit '{d}' in {field_name} not found in source note")

    return card
