"""Second check for every MCQ: the model solves the question blind (without the answer key) using only the
note. If its answer differs from the key, or another option is also right, the question is rejected."""

VERIFY_SYSTEM = """You check UPSC quiz questions against a news note. Use ONLY the note; do not use outside knowledge.
If the note does not settle something, say so. Return JSON only."""

SCHEMA_SINGLE = {"type": "object", "properties": {
    "answer": {"type": "string", "enum": ["a", "b", "c", "d", "none"]},
    "also_correct": {"type": "array", "items": {"type": "string", "enum": ["a", "b", "c", "d"]}},
    "reason": {"type": "string"}}, "required": ["answer", "also_correct", "reason"]}

SCHEMA_STATEMENTS = {"type": "object", "properties": {
    "statements": {"type": "array", "items": {"type": "object", "properties": {
        "n": {"type": "integer"}, "verdict": {"type": "string", "enum": ["true", "false", "not in note"]}},
        "required": ["n", "verdict"]}},
    "reason": {"type": "string"}}, "required": ["statements", "reason"]}


def note_text(note):
    ptrs = "\n".join(f"- {p.get('text', '')}" for p in note.get("prelims_pointers") or [] if isinstance(p, dict))
    return "\n".join(x for x in [
        f"Title: {note.get('title') or note.get('original_title') or ''}",
        f"Why in news: {note.get('why_in_news') or ''}",
        f"Key facts: {note.get('fact_box') or ''}",
        f"Pointers:\n{ptrs}" if ptrs else "",
    ] if x)


def check(model, note, mcq):
    """Returns None when the question holds up, else a short reason (fed back to the generator)."""
    L = "abcd"
    if mcq["type"] == "statements":
        q = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(mcq["statements"]))
        user = (f"NOTE\n{note_text(note)}\n\nSTATEMENTS\n{q}\n\nFor each statement, say whether the note shows it is "
                f"true, false, or not in note.")
        out = model.json(VERIFY_SYSTEM, user, SCHEMA_STATEMENTS, temperature=0.0, max_tokens=300)
        got = {int(s.get("n", 0)): s.get("verdict") for s in out.get("statements") or []}
        key_true = {i + 1 for i, ok in enumerate(_truths(mcq)) if ok}
        for n in range(1, len(mcq["statements"]) + 1):
            v = got.get(n)
            if v == "not in note":
                return f"statement {n} can't be checked against the note; use facts the note states"
            if v is None or (v == "true") != (n in key_true):
                return f"statement {n}'s true/false flag doesn't match the note"
        return None
    opts = "\n".join(f"({L[i]}) {o}" for i, o in enumerate(mcq["options"]))
    user = (f"NOTE\n{note_text(note)}\n\nQUESTION\n{mcq['question']}\n{opts}\n\nWhich option is correct according to "
            f"the note? Put any other option that the note also supports in also_correct.")
    out = model.json(VERIFY_SYSTEM, user, SCHEMA_SINGLE, temperature=0.0, max_tokens=200)
    ans = out.get("answer")
    if ans == "none" or ans not in L:
        return "the note doesn't clearly support any option"
    if L.index(ans) != mcq["answer"]:
        return f"a blind check picked ({ans}), not the marked answer; the question or options are ambiguous"
    also = [x for x in out.get("also_correct") or [] if x in L and L.index(x) != mcq["answer"]]
    if also:
        return f"option ({also[0]}) is also supported by the note; use clearly wrong distractors"
    return None


def _truths(mcq):
    """True/false per statement, recovered from the stored answer option ('1 and 3 only', 'Both 1 and 2' …)."""
    n = len(mcq["statements"])
    label = mcq["options"][mcq["answer"]].lower()
    if label.startswith("neither"):
        return [False] * n
    if label.startswith("both"):
        return [True] * n
    nums = {int(x) for x in label.replace(",", " ").split() if x.isdigit()}
    return [(i + 1) in nums for i in range(n)]
