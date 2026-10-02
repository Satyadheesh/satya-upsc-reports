"""Prompt and JSON schemas for the study kit (one call per note)."""
from common.syllabus import SYLLABUS

from .validate import FACT_LABELS

SUBJECTS = {k: v[1] for k, v in SYLLABUS.items()}

PROMPT_VERSION = "kit-v3"  # v3: every MCQ is solved blind against the note before saving (kit/verify.py)

SYSTEM = """You turn one UPSC current-affairs note into a compact study kit for Civil Services aspirants.
Use ONLY what the note says. Never add numbers, names, dates or claims that are not in the note.

Return JSON with:
- short_title: a crisp news headline, max 80 characters, plain text, no full stop. Lead with who did what,
  e.g. "Supreme Court allows only green crackers, rules out nationwide ban".
- takeaway: why this matters for the exam, one sentence, max 150 characters. Name the exam angle,
  e.g. "DBT vs digital exclusion: a ready GS3 and Ethics case study."
- brief: the story as one line for a list. lead = 1 to 5 words that name the topic (e.g. "UPI charge"),
  text = the key fact in max 110 characters (e.g. "0.4% MDR on merchant payments above ₹2,000 from 15 October.").
- facts: 2 to 5 facts worth memorising for Prelims, each {label, text}. Labels: """ + ", ".join(FACT_LABELS) + """.
  Write each as "Name — what it is or what it says", max 160 characters. Merge repeated facts into one.
  Skip trivia such as "X is the Prime Minister of India" or the date of a meeting.
- mcq: one Prelims-style question on the most exam-worthy fact (a body, law, scheme, place, figure or concept),
  never on trivia like meeting dates. Format is given at the end of the note.

Plain English, Indian conventions (lakh, crore, ₹). No markdown."""

MCQ_SINGLE = """MCQ format: single answer. mcq = {question, correct, distractors, explanation}.
Test a supporting fact a student must remember (which body, which law or scheme, which place, which figure),
NOT the headline itself: if the answer is the main actor in the headline the question is too easy.
question ends with "?" or ":". correct = the right answer, short (a name, number, place or phrase).
distractors = exactly 3 wrong answers of the same kind (other bodies, other states, other numbers) that do NOT
appear in the note, so there is no doubt they are wrong. The question must not contain the answer.
explanation = one sentence on why the answer is right, from the note."""

MCQ_STATEMENTS = """MCQ format: statements. mcq = {stem, statements}.
stem like "With reference to <topic>, consider the following statements:".
statements = 3 items (2 only if the note is thin) {text, true, why}. Each text is one sentence on a different fact.
Make exactly {n_true} of them true. A false statement changes one detail of a fact in the note (a wrong number, body,
place, year or relationship) so that the note clearly contradicts it. why = for a false statement, what the note
actually says (one short sentence); for a true one, leave it empty."""

_FACTS = {"type": "array", "minItems": 2, "maxItems": 5, "items": {
    "type": "object", "properties": {"label": {"type": "string", "enum": FACT_LABELS}, "text": {"type": "string"}},
    "required": ["label", "text"]}}
_BASE = {"short_title": {"type": "string"}, "takeaway": {"type": "string"},
         "brief": {"type": "object", "properties": {"lead": {"type": "string"}, "text": {"type": "string"}},
                   "required": ["lead", "text"]},
         "facts": _FACTS}

SCHEMA_SINGLE = {"type": "object", "properties": {**_BASE, "mcq": {
    "type": "object", "properties": {"question": {"type": "string"}, "correct": {"type": "string"},
                                     "distractors": {"type": "array", "minItems": 3, "maxItems": 3, "items": {"type": "string"}},
                                     "explanation": {"type": "string"}},
    "required": ["question", "correct", "distractors", "explanation"]}},
    "required": ["short_title", "takeaway", "brief", "facts", "mcq"]}

SCHEMA_STATEMENTS = {"type": "object", "properties": {**_BASE, "mcq": {
    "type": "object", "properties": {"stem": {"type": "string"},
                                     "statements": {"type": "array", "minItems": 2, "maxItems": 3, "items": {
                                         "type": "object", "properties": {"text": {"type": "string"}, "true": {"type": "boolean"},
                                                                          "why": {"type": "string"}},
                                         "required": ["text", "true", "why"]}}},
    "required": ["stem", "statements"]}},
    "required": ["short_title", "takeaway", "brief", "facts", "mcq"]}


def mcq_type(article_id):
    """Alternate formats so a report gets a mix of both."""
    return "statements" if int(article_id) % 2 == 0 else "single"


def n_true(article_id):
    """How many of 3 statements should be true, varied so the answer is not always the same shape."""
    return (1, 2, 2, 3)[(int(article_id) // 2) % 4]


def user_prompt(note, kind, feedback=None):
    ptrs = "\n".join(f"- {p.get('type', '')}: {p.get('text', '')}" for p in note.get("prelims_pointers") or []
                     if isinstance(p, dict))
    parts = [
        f"Title: {note.get('title') or note.get('original_title') or ''}",
        f"Paper: {note.get('gs_paper')} · {SUBJECTS.get(note.get('subject'), note.get('subject'))}",
        f"Why in news: {note.get('why_in_news') or ''}",
        f"Key facts: {note.get('fact_box') or ''}",
        f"Prelims pointers:\n{ptrs}" if ptrs else "",
        f"Mains question: {note.get('mains_question')}" if note.get("mains_question") else "",
        f"Keywords: {', '.join(note.get('keywords') or [])}" if note.get("keywords") else "",
        "",
        MCQ_STATEMENTS.replace("{n_true}", str(n_true(note["article_id"]))) if kind == "statements" else MCQ_SINGLE,
    ]
    if feedback:
        parts.append(f"\nYour previous answer was rejected: {feedback}. Write it again and fix that.")
    return "\n".join(p for p in parts if p is not None)


def schema(kind):
    return SCHEMA_STATEMENTS if kind == "statements" else SCHEMA_SINGLE
