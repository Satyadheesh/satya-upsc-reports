"""Semantic LLM Judge for SSC CGL flashcards.

Audits cards against source notes using a second model call at temperature 0
enforcing rules R1-R6.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "pass": {"type": "boolean"},
        "failed": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": ["R1", "R2", "R3", "R4", "R5", "R6"],
            },
        },
        "fix_hint": {"type": "string"},
    },
    "required": ["pass", "failed", "fix_hint"],
    "additionalProperties": False,
}

JUDGE_SYSTEM = """You are auditing one SSC quiz card against its source note.
Return JSON only: {"pass": bool, "failed": [rule_ids], "fix_hint": str}
Rules:
R1 The question asks about ONE specific entity/number the note actually states.
R2 The answer is that entity/number, not a sentence or a venue/event name.
R3 The answer's qualifier (up to/over/nearly) matches the note.
R4 KEY keeps actor + verb + date together; past dates are not presented as deadlines.
R5 STATIC_GK is permanent knowledge; it contains no event from the last two years.
R6 STATIC_GK is about the card's subject, not generic or circular."""

JUDGE_USER_TEMPLATE = """Card:
Question: {question}
Answer: {answer}
KEY: {key}
STATIC_GK: {static_gk}

Note:
{note}"""


def _rule_evaluator_offline(card: dict, note_text: str) -> dict:
    """Offline heuristic judge matching rules R1-R6 for environments without an LLM."""
    q = (card.get("ssc_question") or card.get("question") or "").strip()
    a = (card.get("ssc_answer") or card.get("answer") or "").strip()
    k = (card.get("key_fact") or card.get("key") or "").strip()
    sgk = (card.get("static_gk") or "").strip()

    failed = []
    hints = []

    # R1: The question asks about ONE specific entity/number the note actually states.
    if not q.endswith("?") or re.search(r"key development|key update|what is the news", q, re.I):
        failed.append("R1")
        hints.append("Ask about one specific entity or number, not a headline.")

    # R2: The answer is that entity/number, not a sentence or a venue/event name.
    if re.search(r"\b(not specified|unknown|n/?a|none)\b", a, re.I) or len(a.split()) > 10 or len(a) > 60:
        failed.append("R2")
        hints.append("Answer must be a short entity or number, not a sentence or vague placeholder.")

    # R3: The answer's qualifier (up to/over/nearly) matches the note.
    for m in re.finditer(re.escape(a), note_text, re.I):
        hit = re.search(r"\b(up to|over|nearly|about|at least|approximately|around|more than)\s+$",
                        note_text[max(0, m.start() - 12):m.start()], re.I)
        if hit and hit.group(1).lower() not in a.lower():
            failed.append("R3")
            hints.append(f"Answer drops the qualifier '{hit.group(1)}'. Include '{hit.group(1)} {a}'.")
            break

    # R4: KEY keeps actor + verb + date together; past dates are not presented as deadlines.
    has_deadline = bool(re.search(r"\b(?:by\s+(?:[A-Za-z]+\s+\d{1,2},?\s+)?\d{4}|deadline|target)\b", k, re.I))
    if has_deadline:
        has_actor = bool(re.search(r"\b[A-Z]{2,}\b|\b[A-Z][a-z]+", k))
        has_routine_purpose = bool(re.search(r"\b(mitigate|reduce|meet|address|ease|curb)\b", k, re.I))
        has_completion = bool(re.search(r"\b(complete|commission|operational|ready)\b", k, re.I))
        if not has_actor or (has_routine_purpose and not has_completion):
            failed.append("R4")
            hints.append("KEY must keep actor + verb + date together; do not present routine purpose as a deadline.")

    # R5: STATIC_GK is permanent knowledge; contains no event from last 2 years.
    if sgk and re.search(r"\b(2025|2026)\b", sgk):
        failed.append("R5")
        hints.append("STATIC_GK mentions a recent year; must be permanent knowledge.")

    # R6: STATIC_GK is about the card's subject, not generic or circular.
    if sgk:
        from .ssc_guard import circular, relevant
        if circular(sgk):
            failed.append("R6")
            hints.append("STATIC_GK is circular (e.g. self-parent acronym loop).")
        elif not relevant(sgk, q, a, k):
            failed.append("R6")
            hints.append("STATIC_GK is off-topic from card subject.")

    passed = len(failed) == 0
    return {
        "pass": passed,
        "failed": failed,
        "fix_hint": "; ".join(hints) if hints else "Passes audit",
    }


def judge_card(card: dict, note_text: str, model: Any = None) -> dict:
    """Run semantic LLM judge audit on one card against its source note."""
    q = (card.get("ssc_question") or card.get("question") or "").strip()
    a = (card.get("ssc_answer") or card.get("answer") or "").strip()
    k = (card.get("key_fact") or card.get("key") or "").strip()
    sgk = (card.get("static_gk") or "").strip()

    if model is not None and hasattr(model, "chat"):
        user_prompt = JUDGE_USER_TEMPLATE.format(
            question=q,
            answer=a,
            key=k,
            static_gk=sgk,
            note=note_text[:2000],
        )
        msgs = [
            {"role": "system", "content": JUDGE_SYSTEM},
            {"role": "user", "content": user_prompt},
        ]
        try:
            res = model.chat(msgs, JUDGE_SCHEMA, temperature=0.0, max_tokens=150)
            if isinstance(res, dict) and "pass" in res:
                return res
        except Exception:
            pass

    return _rule_evaluator_offline(card, note_text)
