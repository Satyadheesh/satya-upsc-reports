"""Checks for everything the model writes into a study kit. Nothing is saved unless it passes.

Grounding rule: a kit may only state what the note states. Numbers in titles, facts and the
correct answer must appear in the note (1% rounding allowed), and answers/true statements must
share most of their content words with the note. The answer key is never written by the model:
for single-answer MCQs we shuffle the options ourselves, for statement MCQs we build the
"1 and 2 only" style options from the model's true/false flags.
"""
import hashlib
import itertools
import random
import re

FACT_LABELS = ["Body", "Case", "Act", "Scheme", "Place", "Person", "Figure", "Date",
               "Report", "Concept", "Event", "Index", "Mission"]
_LABEL = {l.lower(): l for l in FACT_LABELS}

NUM_RE = re.compile(r"\d+(?:[.,]\d+)*")
WORD_RE = re.compile(r"[a-z][a-z'\-]+|\d+(?:[.,]\d+)*")
STOP = set("""about above after again against also among and another any are around because been before being
below between both but by can could did does doing down during each either even ever every few for from further had
has have having here hers herself him himself his how however into its itself just least less made make many may might
more most much must near neither never nor not now off often once only other others our ours out over own per rather
same several shall should since some such than that the their theirs them themselves then there these they this those
though through thus till under until upon very was were what when where whether which while who whom whose why will
with within without would yet your yours india indian india's new said says year years also including""".split())
JUNK_FACT = re.compile(r"\b(?:is|serves as|was)\s+(?:the\s+)?(?:current\s+)?(?:prime minister|president|chief minister|"
                       r"finance minister|external affairs minister|union minister|minister)\s+of\s+india\b", re.I)
BANNED_OPTION = re.compile(r"\b(all|none) of the above\b", re.I)
MD = re.compile(r"(\*\*|__|`|^#+\s*)")


class Invalid(ValueError):
    pass


def clean(s):
    s = MD.sub("", " ".join(str(s or "").split()))
    return s.strip().strip('"“”').strip()


def need(s, name, lo, hi):
    s = clean(s)
    if len(s) < lo:
        raise Invalid(f"{name} too short")
    if len(s) > hi:
        raise Invalid(f"{name} too long ({len(s)} > {hi} characters)")
    return s


def _num(x):
    return x.replace(",", "")


def numbers(text):
    return {_num(n) for n in NUM_RE.findall(text or "")}


def grounded_number(n, source_nums):
    if n in source_nums:
        return True
    try:
        v = float(n)
    except ValueError:
        return False
    for m in source_nums:
        try:
            w = float(m)
        except ValueError:
            continue
        if w and abs(v - w) / abs(w) <= 0.01:  # "₹49,194 crore" vs "₹49,194.05 crore"
            return True
    return False


def ungrounded(text, source_nums):
    bad = []
    for m in NUM_RE.finditer(text or ""):
        n = _num(m.group())
        small = n.isdigit() and int(n) <= 5 and not (text[m.end():m.end() + 2].lstrip().startswith("%"))
        if not small and not grounded_number(n, source_nums) and n not in bad:
            bad.append(n)  # small whole numbers are counts ("two bodies", statement 1); anything else must be in the note
    return bad


def _stem(w):
    return w[:6]


def words(text):
    return {_stem(w) for w in WORD_RE.findall((text or "").lower()) if w not in STOP and (len(w) >= 4 or w[0].isdigit())}


def overlap(text, source_words):
    ws = words(text)
    if not ws:
        return 1.0
    return len(ws & source_words) / len(ws)


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


class Source:
    """The note as plain text, with its numbers and content words, for grounding checks."""

    def __init__(self, note):
        parts = [note.get("title"), note.get("original_title"), note.get("why_in_news"), note.get("fact_box"),
                 note.get("mains_question"), " ".join(note.get("keywords") or [])]
        parts += [p.get("text") for p in note.get("prelims_pointers") or [] if isinstance(p, dict)]
        self.text = "\n".join(str(p) for p in parts if p)
        self.nums = numbers(self.text)
        self.words = words(self.text)


def check_numbers(text, src, name):
    bad = ungrounded(text, src.nums)
    if bad:
        raise Invalid(f"{name} has numbers not in the note: {', '.join(bad[:3])}")


def _facts(raw, src):
    out, seen = [], []
    for f in raw or []:
        if not isinstance(f, dict):
            continue
        label = _LABEL.get(clean(f.get("label")).lower(), "Concept")
        text = clean(f.get("text"))
        if not 8 <= len(text) <= 170 or JUNK_FACT.search(text):
            continue
        if ungrounded(text, src.nums) or overlap(text, src.words) < 0.5:
            continue  # drop facts the note does not support
        ws = words(text)
        if any(ws and len(ws & s) / len(ws) > 0.8 for s in seen):
            continue  # same fact twice
        seen.append(ws)
        out.append({"label": label, "text": text})
    if len(out) < 2:
        raise Invalid("fewer than 2 usable facts (facts must come from the note, no trivia)")
    return out[:5]


def _rng(article_id):
    return random.Random(int(hashlib.sha1(str(article_id).encode()).hexdigest()[:8], 16))


def _mcq_single(m, src, article_id):
    q = need(m.get("question"), "question", 15, 220)
    if not q.endswith(("?", ":")):
        q += "?"
    correct = need(m.get("correct"), "correct answer", 1, 110)
    ds = [clean(d) for d in (m.get("distractors") or [])]
    ds = [d for d in ds if d]
    if len(ds) != 3:
        raise Invalid("need exactly 3 distractors")
    opts = [correct] + ds
    if any(len(o) > 110 for o in opts):
        raise Invalid("an option is too long")
    if len({_norm(o) for o in opts}) < 4:
        raise Invalid("options are not distinct")
    if any(BANNED_OPTION.search(o) for o in opts):
        raise Invalid("no 'all/none of the above' options")
    if _norm(correct) and _norm(correct) in _norm(q):
        raise Invalid("question gives away the answer")
    check_numbers(correct, src, "correct answer")
    if overlap(correct, src.words) < 0.5:
        raise Invalid("correct answer is not supported by the note")
    rng = _rng(article_id)
    order = list(range(4))
    rng.shuffle(order)
    options = [opts[i] for i in order]
    return {"type": "single", "question": q, "statements": None, "options": options,
            "answer": order.index(0), "explanation": need(m.get("explanation"), "explanation", 20, 260)}


def _label(subset):
    s = [str(i + 1) for i in subset]
    if len(s) == 1:
        return f"{s[0]} only"
    if len(s) == 2:
        return f"{s[0]} and {s[1]} only"
    return f"{', '.join(s[:-1])} and {s[-1]}"


def _mcq_statements(m, src, article_id):
    stem = need(m.get("stem"), "stem", 15, 200)
    if not stem.endswith(":"):
        stem = stem.rstrip(".") + ":"
    sts = [s for s in (m.get("statements") or []) if isinstance(s, dict) and clean(s.get("text"))]
    if len(sts) not in (2, 3):
        raise Invalid("need 2 or 3 statements")
    texts = [need(s.get("text"), "statement", 15, 200) for s in sts]
    truth = [s.get("true") is True for s in sts]
    if not any(truth):
        raise Invalid("at least one statement must be true")
    if all(truth) and len(sts) == 2:
        pass  # "Both 1 and 2" is a valid answer
    if len({_norm(t) for t in texts}) < len(texts):
        raise Invalid("statements repeat")
    for t, ok in zip(texts, truth):
        if ok:
            check_numbers(t, src, "a true statement")
            if overlap(t, src.words) < 0.5:
                raise Invalid("a true statement is not supported by the note")
        elif overlap(t, src.words) < 0.25:
            raise Invalid("a false statement is off-topic")
    correct = tuple(i for i, ok in enumerate(truth) if ok)
    if len(texts) == 2:
        options = ["1 only", "2 only", "Both 1 and 2", "Neither 1 nor 2"]
        answer = {(0,): 0, (1,): 1, (0, 1): 2}[correct]
    else:
        subsets = [c for r in (1, 2, 3) for c in itertools.combinations(range(3), r)]
        others = [s for s in subsets if s != correct]
        pick = _rng(article_id).sample(others, 3) + [correct]
        pick.sort(key=lambda s: (len(s), s))  # UPSC order: singles, pairs, all three
        options = [_label(s) for s in pick]
        answer = pick.index(correct)
    return {"type": "statements", "question": stem, "statements": texts,
            "ask": "Which of the statements given above is/are correct?", "options": options, "answer": answer,
            "explanation": need(m.get("explanation"), "explanation", 20, 260)}


def validate(raw, note, article_id, mcq_type):
    if not isinstance(raw, dict):
        raise Invalid("output is not an object")
    src = Source(note)
    title = need(raw.get("short_title"), "short_title", 12, 90).rstrip(".")
    check_numbers(title, src, "short_title")
    takeaway = need(raw.get("takeaway"), "takeaway", 20, 170)
    check_numbers(takeaway, src, "takeaway")
    brief = raw.get("brief") or {}
    lead = need(brief.get("lead"), "brief.lead", 2, 45).rstrip(":") + ":"
    btext = need(brief.get("text"), "brief.text", 10, 130)
    check_numbers(f"{lead} {btext}", src, "brief")
    facts = _facts(raw.get("facts"), src)
    m = raw.get("mcq") or {}
    mcq = _mcq_statements(m, src, article_id) if mcq_type == "statements" else _mcq_single(m, src, article_id)
    return {"short_title": title, "takeaway": takeaway, "brief_lead": lead, "brief_text": btext,
            "facts": facts, "mcq": mcq}
