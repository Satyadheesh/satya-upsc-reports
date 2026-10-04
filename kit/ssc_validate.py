"""ssc-v4 guards for SSC one-liner cards."""
from __future__ import annotations

import re
from datetime import date


from .ssc_guard import SscInvalid, circular, static_gk_from_table


def fallback_static_gk(text: str) -> str | None:
    t = static_gk_from_table(text)
    return t or None


def _year(year: int | None) -> int:
    return year or date.today().year


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 3}


def validate_static_gk(sgk: str, key: str = "", year: int | None = None) -> None:
    """Structural checks for static GK: length, no recent year, doesn't copy KEY, non-circular."""
    year = _year(year)
    sgk = (sgk or "").strip()
    if not sgk:
        raise SscInvalid("static_gk is empty.")
    for y in re.findall(r"\b(20\d{2})\b", sgk):
        if int(y) >= year - 1:
            raise SscInvalid(
                f"static_gk mentions {y}, which is current affairs. Static GK must be "
                f"permanent knowledge.")
    sg, kw = _words(sgk), _words(key)
    if sg and kw and len(sg & kw) / len(sg) >= 0.6:
        raise SscInvalid("static_gk repeats the KEY line. Give a different, permanent fact.")
    if circular(sgk):
        raise SscInvalid("static_gk is circular. Give a substantive fact.")


# --------------------------------------- 2. key structural validation
def validate_key(key: str, year: int | None = None) -> None:
    """Structural check for key fact line."""
    k = (key or "").strip()
    if not k:
        raise SscInvalid("key is empty.")
    if len(k) < 5 or len(k) > 200:
        raise SscInvalid("key length must be between 5 and 200 characters.")


# ------------------------------------------------ 3. entity filter + ranking
_CONTEXT = re.compile(
    r"\b(venue|context|seminar|banquet|backdrop|setting|dais|on the sidelines)\b", re.I)
_TIERS = [
    re.compile(r"\b(high commissioner|ambassador|governor|chief justice|chairperson|chairman|"
               r"secretary|minister|president|director|head)\b", re.I),
    re.compile(r"\b(scheme|yojana|act|bill|portal|app|mission)\b", re.I),
    re.compile(r"(crore|lakh|\bMW\b|%|target|outlay|budget|capacity)", re.I),
    re.compile(r"\b(champion|award|trophy|medal|winner)\b", re.I),
    re.compile(r"\b(exercise|summit|bilateral)\b", re.I),
]


def _split_pointer(p) -> tuple[str, str]:
    if isinstance(p, dict):
        lbl = p.get("label") or ""
        desc = p.get("description") or ""
        txt = p.get("text") or ""
        if not lbl and ":" in txt:
            l, _, d = txt.partition(":")
            return l.strip(), d.strip()
        if not desc:
            desc = txt
        return str(lbl).strip(), str(desc).strip()
    label, _, desc = str(p).partition(":")
    return label.strip(), desc.strip()


def filter_pointers(pointers: list) -> list:
    """Drop pointers whose description says they are only the event venue/context."""
    return [p for p in pointers if not _CONTEXT.search(_split_pointer(p)[1])]


def rank_pointers(pointers: list, headline: str = "") -> list:
    """Headline entities first, then the SSC hierarchy as a tie-break."""
    head = _words(headline)

    def score(p):
        label, desc = _split_pointer(p)
        in_head = 0 if (_words(label) & head) else 1
        tier = next((i for i, rx in enumerate(_TIERS) if rx.search(label + " " + desc)), len(_TIERS))
        return (in_head, tier)

    return sorted(filter_pointers(pointers), key=score)


# ------------------------------------------------------------ entry point
def check_card_v4(card: dict, year: int | None = None) -> None:
    """Raise SscInvalid with a model-readable reason, or return None if the card passes."""
    key = card.get("key") or card.get("key_fact") or ""
    sgk = card.get("static_gk") or ""
    validate_key(key, year)
    validate_static_gk(sgk, key, year)
