"""ssc-v4 guards for SSC one-liner cards."""
from __future__ import annotations

import re
from datetime import date


class SscInvalid(ValueError):
    pass


def _year(year: int | None) -> int:
    return year or date.today().year


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 3}


# ------------------------------------------------- 1. static GK purity
_ANCHORS = {
    "act/treaty with year": re.compile(
        r"\b(?:Act|Treaty|Amendment|Code|Convention)\b[^.;]{0,20}?\b(1[89]\d{2}|20\d{2})\b"),
    "constitutional article": re.compile(r"\bArticles?\s+\d+[A-Z]?\b"),
    "headquarters": re.compile(r"\b(?:HQ|headquarter(?:s|ed)?)\b", re.I),
    "ministry / nodal body": re.compile(
        r"\b(?:Ministry of|nodal (?:ministry|body|agency)|parent ministry)\b", re.I),
    "static geography": re.compile(
        r"\b(?:capital(?: of|:)?|currency|river|national park|IUCN|state formation|border)\b", re.I),
    "founding fact": re.compile(
        r"\b(?:established|founded|launched|signed|enacted|formed|constituted)\b[^.;]{0,25}?\b(1[89]\d{2}|20\d{2})\b"),
}
_RECENT_VERBS = re.compile(
    r"\b(granted|approved|launched|enacted|signed|announced|inaugurated|cleared|"
    r"allocated|unveiled|addressed|clarified|stated|directed|released|sanctioned)\b", re.I)


def _anchor_kinds(sgk: str, year: int) -> list[str]:
    found = []
    for kind, rx in _ANCHORS.items():
        m = rx.search(sgk)
        if not m:
            continue
        if m.lastindex and int(m.group(1)) > year - 2:  # recent year: not permanent
            continue
        found.append(kind)
    return found


def validate_static_gk(sgk: str, key: str = "", year: int | None = None) -> None:
    year = _year(year)
    sgk = (sgk or "").strip()
    if not sgk:
        raise SscInvalid("static_gk is empty.")
    for y in re.findall(r"\b(20\d{2})\b", sgk):
        if int(y) >= year - 1:
            raise SscInvalid(
                f"static_gk mentions {y}, which is current affairs. Static GK must be "
                f"permanent knowledge (Act and year, Article, HQ, parent ministry, capital, currency).")
    sg, kw = _words(sgk), _words(key)
    if sg and kw and len(sg & kw) / len(sg) >= 0.6:
        raise SscInvalid("static_gk repeats the KEY line. Give a different, permanent fact.")
    if not _anchor_kinds(sgk, year):
        hint = (" It reads like breaking news (" + _RECENT_VERBS.search(sgk).group(1) + ").") \
            if _RECENT_VERBS.search(sgk) else ""
        raise SscInvalid(
            f"static_gk has no permanent anchor.{hint} Use one of: Act/Treaty and year, "
            f"Article number, headquarters, parent ministry, capital/currency/river.")


# --------------------------------------- 2. timelines vs. operational purpose
_PURPOSE = re.compile(
    r"\b(mitigate|reduce|meet|address|ease|curb|improve|boost|enable|ensure|provide|manage)\b", re.I)
_COMPLETION = re.compile(
    r"\b(complet\w+|commission\w*|operational|deadline|target\w*|ready|handover|go-live)\b", re.I)
_ACTOR_STOP = {"The", "This", "It", "Project", "Scheme", "Plan", "Government", "State"}


def validate_key(key: str, year: int | None = None) -> None:
    year = _year(year)
    for sent in re.split(r"(?<=[.;])\s+", key or ""):
        years = [int(y) for y in re.findall(r"\b(20\d{2})\b", sent)]
        if not any(y >= year for y in years) or not _PURPOSE.search(sent):
            continue
        actor = re.search(r"\b[A-Z]{2,}\b", sent) or any(
            w[0].isupper() and w not in _ACTOR_STOP for w in re.findall(r"[A-Za-z]+", sent)[1:])
        if not (_COMPLETION.search(sent) and actor):
            raise SscInvalid(
                "key mixes a routine purpose with a deadline. Say who targets what by when "
                "(e.g. 'KSEB aims to complete the project by <date>') and keep the purpose separate.")


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
