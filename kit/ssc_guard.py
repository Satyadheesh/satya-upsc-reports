"""ssc_guard: Strict Q&A validation and safe static GK selection for SSC one-liner cards."""
from __future__ import annotations

import re


class SscInvalid(ValueError):
    pass


# ---------- Q&A checks ----------
_Q_START = re.compile(
    r"^\s*(?:(?:by|on|in|to|at|from|for|with|under|of|against|since|until)\s+)?"
    r"(?:who|whom|whose|what|which|when|where|why|how)\b",
    re.I,
)
_BAD_Q = re.compile(r"key development|key update|what is the news|\.{3}|…|:\s*\?", re.I)
_VAGUE = re.compile(
    r"^\s*(not specified|unknown|n/?a|none|unspecified|not mentioned|not stated|not available)\b",
    re.I,
)
_QUAL = re.compile(r"\b(up to|over|nearly|about|at least|approximately|around|more than)\s+$", re.I)


def validate_qa(question: str, answer: str, note_text: str = "") -> None:
    q, a = (question or "").strip(), (answer or "").strip()
    if not q.endswith("?") or not _Q_START.match(q):
        raise SscInvalid("question must be a real question ending with '?'.")
    if _BAD_Q.search(q):
        raise SscInvalid("question is a headline template or truncated. Ask about one specific entity or number.")
    if not a or _VAGUE.match(a):
        raise SscInvalid("answer is vague. Pick a different entity or number that the note states explicitly.")
    if len(a) > 60 or len(a.split()) > 10 or a.endswith(("…", "...")):
        raise SscInvalid("answer must be a short entity or number (max ~10 words), not a sentence fragment.")
    if note_text:
        for m in re.finditer(re.escape(a), note_text):
            hit = _QUAL.search(note_text[max(0, m.start() - 12):m.start()])
            if hit:
                if hit.group(1).lower() not in a.lower():
                    raise SscInvalid(f"answer drops the qualifier '{hit.group(1)}'. Write '{hit.group(1)} {a}'.")
                break


# ---------- verified static GK table ----------
# Add ONLY lines you have checked against an official source.
STATIC_GK = {
    "rbi": (["rbi", "reserve bank of india"], "RBI was established on 1 April 1935 under the RBI Act, 1934; HQ: Mumbai"),
    "eci": (["election commission of india", "eci"], "ECI is a constitutional body under Article 324"),
    "nhpc": (["nhpc"], "NHPC is a PSU under the Ministry of Power; HQ: Faridabad"),
    "sebi": (["sebi"], "SEBI was established under the SEBI Act, 1992; HQ: Mumbai"),
    "meity": (["meity"], "MeitY is the nodal ministry for India's IT sector"),
    "ncpor": (["ncpor"], "NCPOR is headquartered in Goa"),
    "jncasr": (["jncasr"], "JNCASR is an autonomous institution under the Department of Science and Technology"),
    "madras_hc": (["madras high court"], "Madras High Court was established in 1862; principal bench at Chennai"),
}


def static_gk_from_table(*texts: str) -> str:
    blob = " ".join(texts).lower()
    for aliases, line in STATIC_GK.values():
        if any(re.search(rf"\b{re.escape(a)}\b", blob) for a in aliases):
            return line
    return ""


# ---------- static GK relevance + circularity ----------
_MIN = re.compile(r"\b([A-Z]{2,})\b[^.;]*?\bMinistry of ([A-Z][\w&, ]+)")


def circular(sgk: str) -> bool:
    """'MNRE is under the Ministry of New and Renewable Energy' says nothing."""
    for m in _MIN.finditer(sgk):
        initials = "".join(
            w[0] for w in re.findall(r"[A-Za-z]+", m.group(2))
            if w.lower() not in {"of", "and", "for"}
        )
        if m.group(1).upper().endswith(initials.upper()) or initials.upper().startswith(m.group(1).upper()):
            return True
    return False


def relevant(sgk: str, question: str, answer: str, key: str) -> bool:
    toks = lambda s: {w for w in re.findall(r"[A-Za-z0-9]+", s.lower()) if len(w) > 3}
    return bool(toks(sgk) & toks(question + " " + answer + " " + key))


def choose_static_gk(card: dict, gemma_ok) -> tuple[str, str]:
    """Returns (line, source). The table always wins for known entities, because Gemma can be
    confidently wrong. Otherwise Gemma's line is kept only if it validates, is relevant and not
    circular, and is tagged 'gemma-unverified' for the review queue. Else blank."""
    q = card.get("ssc_question") or card.get("question") or ""
    a = card.get("ssc_answer") or card.get("answer") or ""
    k = card.get("key_fact") or card.get("key") or ""
    t = static_gk_from_table(q, a, k)
    if t:
        return t, "table"
    s = (card.get("static_gk") or "").strip()
    if s:
        try:
            gemma_ok(s)  # e.g. lambda s: validate_static_gk(s, k, today.year)
            if not circular(s) and relevant(s, q, a, k):
                return s, "gemma-unverified"
        except Exception:
            pass
    return "", "none"
