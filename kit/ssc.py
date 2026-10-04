"""SSC CGL General Awareness (TCS Pattern) flashcard generation using Gemma 4 12B."""
import json
import re

PROMPT_VERSION = "ssc-v3"

PROMPT_TEMPLATE = """You are a senior SSC CGL General Awareness paper setter (TCS pattern, Tier-1/Tier-2). You convert one daily current-affairs note into ONE rapid-fire active-recall flashcard.

THINK LIKE SSC, NOT UPSC
- SSC tests direct recall: Who, What, Where, When, How many, Which. No analysis, no "with reference to", no multi-statement evaluation, no "significance" or "impact".
- Pick the single most exam-worthy entity from the note: a person, place, scheme, number, date, trophy, exercise, organisation or book.

OUTPUT: one JSON object with exactly these keys, nothing else:
- ssc_question: one direct question ending with "?". Max 120 chars. Must NOT contain or hint at the answer.
- ssc_answer: the bare answer: a name, place, number, scheme or short phrase. No full sentence, no verb. Max 50 chars.
- key_fact: one supporting fact taken from the note (duration, predecessor, target, batch, venue, edition, score). Max 120 chars.
- static_gk: one high-yield static fact directly linked to the answer or its parent body. Max 140 chars.

CRITICAL: NEVER OUTPUT A HEADLINE OR STORY SUMMARY
- The ssc_question MUST be a genuine question that a student can answer from recall. It MUST start with Who, What, Where, When, How, Which, Name, In which, Under which, or a similar interrogative.
- NEVER paste a news headline, story title, or descriptive sentence as the question. Headlines like "India releases Great Indian Bustards..." or "Telangana launches cashless treatment scheme" are NOT questions.
- The ssc_answer MUST be a short entity: a name, number, place, scheme name, or date. NEVER a clause or sentence. No verbs, no articles ("The"), no explanations. 1–5 words maximum.
- key_fact and static_gk MUST each add DIFFERENT information. NEVER repeat or rephrase the question or the answer in these fields.

STATE & JURISDICTION RULE (CRITICAL)
- If an event, election, policy, court order or scheme applies to a specific Indian state or territory, the question MUST name that state (e.g. "In Rajasthan, what is the...?", "Under Tamil Nadu's scheme...?").
- Never frame a state-level matter as an unqualified national rule.

FACTUAL BOUNDARIES
- ssc_answer and key_fact must come ONLY from the note. Never add numbers, names or dates that are not in it.
- Copy numbers, spellings and units exactly. Use the ₹ symbol and "crore"/"lakh".
- If a figure is an independent estimate or third-party report (think-tank, university study), attribute it in the question or key_fact.
- If the note lacks a clean answerable fact, use its Prelims pointers or Key facts. Do not invent one.

STATIC GK (ANTI-HALLUCINATION)
- First preference: an existing static hook in the note's Prelims pointers or Key facts (Act, Article, Body, Ministry, River).
- Otherwise, from memory, use ONLY high-confidence anchors for the subject entity itself:
  1. Headquarters city (e.g. "HQ: New Delhi")
  2. Nodal Ministry or parent body (e.g. "Under Ministry of Power")
  3. Constitutional Article or statutory Act (e.g. "Article 243D", "IT Act, 2000")
  4. Directly associated river, state capital or international border
- NEVER state who currently holds an office.
- NEVER guess founding years, exact dates or superlatives ("oldest", "first", "largest"). If not 100% certain, use a headquarters or ministry anchor instead.
- NEVER hook an unrelated third country or entity to the story.
- If you have no high-confidence anchor, use another supporting fact from the note rather than guessing.

STYLE
- Telegraphic. No filler, no "The government...", no explanations.
- Question patterns: "Who was appointed as...?", "In which state/city was ... held?", "What is the outlay of ...?", "Which country became ...?", "Which institution ...?"
- Write in English.

QUESTION CHECK
- Bad (headline as Q): "India and France conduct Shakti exercise in Rajasthan?" → This is a headline, not a question.
- Bad (sentence as answer): "The exercise is a collaboration between India and France" → Too long, contains verbs.
- Bad (leaks answer): "Which scheme, launched as PM Awas Yojana 2.0, gives urban housing?"
- Good Q: "Which exercise did India and France conduct in Rajasthan?"
- Good A: "Shakti"

EXAMPLE OUTPUT (unrelated to the note; use for format only)
{"ssc_question":"Which exercise did India and France conduct in Rajasthan?","ssc_answer":"Shakti","key_fact":"13-day exercise held at Mahajan Field Firing Range","static_gk":"Mahajan Field Firing Range is in Bikaner, Rajasthan"}

<note>
{note}
</note>

Output only the JSON object. No markdown, no comments, no text outside the JSON."""

SCHEMA = {
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


def schema(lang="en"):
    return SCHEMA


def format_note(note):
    lines = []
    title = note.get("title") or note.get("original_title") or ""
    if title:
        lines.append(f"Title: {title}")
    if note.get("gs_paper"):
        lines.append(f"Paper: {note.get('gs_paper')} · {note.get('subject') or 'General'}")
    if note.get("why_in_news"):
        lines.append(f"Why in news: {note.get('why_in_news')}")
    if note.get("fact_box"):
        lines.append(f"Key facts: {note.get('fact_box')}")

    pointers = note.get("prelims_pointers") or []
    if pointers:
        lines.append("Prelims pointers:")
        for p in pointers:
            if isinstance(p, dict):
                t = p.get("type", "fact")
                txt = p.get("text", "")
                lines.append(f"- {t}: {txt}")
            elif isinstance(p, str):
                lines.append(f"- {p}")

    keywords = note.get("keywords") or []
    if keywords:
        lines.append(f"Keywords: {keywords}")

    return "\n".join(lines)


def build_messages(note, lang="en", feedback=None):
    note_text = format_note(note)
    prompt = PROMPT_TEMPLATE.replace("{note}", note_text)
    if feedback:
        prompt += f"\n\nYour previous answer was rejected: {feedback}. Please rewrite and fix that."
    return [{"role": "user", "content": prompt}]


class SscInvalid(ValueError):
    pass


# Interrogative starters that mark a genuine question (case-insensitive)
# Supports introductory phrases like "In Rajasthan, what...", "According to ..., how...", "By how much..."
_Q_STARTERS = re.compile(
    r"^(?:(?:in|under|according to|as per|by)\b[^,?:;]{1,60},\s*)?"
    r"(who|what|where|when|how|which|name|whom|whose|in which|under which|for which|from which|to which|with which|by how)"
    r"\b", re.IGNORECASE)


# Sentence-like answer: contains a verb phrase or is unreasonably long
_SENTENCE_ANS = re.compile(
    r"\b(is a|was a|is the|was the|are the|were the|has been|have been"
    r"|will be|launched|signed|released|conducted|established|formed"
    r"|approved|inaugurated|announced|proposed|collaboration between)"
    r"\b", re.IGNORECASE)


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
    sgk = card["static_gk"]

    # 1. Must end in ?
    if not q.endswith("?"):
        raise SscInvalid("Question must end with '?'")

    # 2. Question must start with an interrogative word (not a headline)
    if not _Q_STARTERS.search(q):
        raise SscInvalid(f"Question looks like a headline, not a question: '{q[:60]}'")

    # 3. Leakage check: answer should not appear inside question
    if len(ans) >= 4 and ans.lower() in q.lower():
        raise SscInvalid(f"Answer '{ans}' leaked inside question '{q}'")

    # 4. Answer must be short and entity-like, not a sentence fragment
    ans_words = ans.split()
    if len(ans_words) > 10:
        raise SscInvalid(f"Answer too long ({len(ans_words)} words), must be ≤10 words: '{ans[:50]}'")
    if _SENTENCE_ANS.search(ans):
        raise SscInvalid(f"Answer looks like a sentence, not an entity: '{ans[:50]}'")

    # 5. No field repetition: key_fact and static_gk should not just repeat the question/answer
    def _norm(s):
        return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()
    q_norm = _norm(q.rstrip("?"))
    ans_norm = _norm(ans)
    kf_norm = _norm(kf)
    sgk_norm = _norm(sgk)
    # key_fact should not be a near-copy of the question
    if kf_norm and q_norm and (kf_norm in q_norm or q_norm in kf_norm):
        raise SscInvalid("key_fact is just repeating the question")
    # static_gk should not be a near-copy of key_fact
    if sgk_norm and kf_norm and (sgk_norm == kf_norm):
        raise SscInvalid("static_gk is identical to key_fact")
    # static_gk should not be a near-copy of the question
    if sgk_norm and q_norm and (sgk_norm in q_norm or q_norm in sgk_norm):
        raise SscInvalid("static_gk is just repeating the question")

    # 6. Digit grounding: any 2+ digit numbers in answer and key_fact must appear in source note
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
