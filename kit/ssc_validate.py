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
        r"\b(?:Act|Treaty|Amendment|Code|Convention)\b[^.;]{0,40}?\b(1[89]\d{2}|20\d{2})\b"),
    "constitutional article": re.compile(r"\bArticles?\s+\d+[A-Z]?\b"),
    "headquarters": re.compile(r"\b(?:HQ|headquarter(?:s|ed)?)\b", re.I),
    "ministry / nodal body": re.compile(
        r"\b(?:Ministry of|nodal (?:ministry|body|agency)|parent ministry)\b", re.I),
    "department / directorate": re.compile(
        r"\b(?:Department of|Directorate of|nodal department)\b", re.I),
    "static geography": re.compile(
        r"\b(?:capital(?: of|:)?|currency|river|national park|IUCN|state formation|border)\b", re.I),
    "physical geography": re.compile(
        r"\b(?:strait|gulf|sea|ocean|bay|ghats|hills|plateau|mountains?|peninsula|island|lake|"
        r"desert|world heritage|UNESCO)\b[^.;]*\b(?:is|are|connects|lies|located|situated|flows|"
        r"borders|separates|spans)\b|\b(?:is|are|connects|lies|located|situated|borders|separates)\b"
        r"[^.;]*\b(?:strait|gulf|sea|ocean|bay|ghats|hills|plateau|mountains?|peninsula|island|lake|"
        r"desert|world heritage|UNESCO)\b", re.I),
    "major award": re.compile(
        r"\b(?:Nobel Prize|Bharat Ratna)\b[^.;]{0,40}?\b(19\d{2}|20\d{2})\b"),
    "founding fact": re.compile(
        r"\b(?:established|founded|launched|signed|enacted|formed|constituted|adopted|ratified|"
        r"came into force|entered into force)\b[^.;]{0,25}?\b(1[89]\d{2}|20\d{2})\b"),
}
_RECENT_VERBS = re.compile(
    r"\b(granted|approved|launched|enacted|signed|announced|inaugurated|cleared|"
    r"allocated|unveiled|addressed|clarified|stated|directed|released|sanctioned)\b", re.I)

CURATED_STATIC_GK = {
    "sebi": "Securities and Exchange Board of India (SEBI) was established under the SEBI Act, 1992; HQ: Mumbai",
    "rbi": "Reserve Bank of India was established on 1 April 1935 under the RBI Act, 1934; HQ: Mumbai",
    "eci": "Election Commission of India is established under Article 324 of the Constitution",
    "election commission": "Election Commission of India is established under Article 324 of the Constitution",
    "supreme court": "Supreme Court of India was established under Article 124 of the Constitution",
    "isro": "ISRO HQ: Bengaluru, Karnataka; under Department of Space",
    "drdo": "DRDO HQ: New Delhi; under Ministry of Defence",
    "cisf": "CISF was established under the CISF Act, 1968; HQ: New Delhi",
    "crpf": "CRPF was established under the CRPF Act, 1949; HQ: New Delhi",
    "bsf": "BSF was established under the BSF Act, 1968; HQ: New Delhi",
    "nhpc": "NHPC is a public-sector undertaking under the Ministry of Power",
    "nabard": "NABARD was established in 1982 under the NABARD Act, 1981; HQ: Mumbai",
    "sidbi": "SIDBI was established in 1990 under the SIDBI Act, 1989; HQ: Lucknow",
    "lic": "LIC was established in 1956 under the Life Insurance Corporation Act, 1956; HQ: Mumbai",
    "upsc": "UPSC is established under Article 315 of the Constitution",
    "cag": "Comptroller and Auditor General of India is appointed under Article 148 of the Constitution",
    "finance commission": "Finance Commission is constituted under Article 280 of the Constitution",
    "madras high court": "Madras High Court was established in 1862; principal bench at Chennai",
    "kerala high court": "Kerala High Court was established in 1956; principal bench at Kochi",
    "bombay high court": "Bombay High Court was established in 1862; principal bench at Mumbai",
    "calcutta high court": "Calcutta High Court was established in 1862; principal bench at Kolkata",
    "delhi high court": "Delhi High Court was established in 1966; principal bench at New Delhi",
    "minamata": "Minamata Convention on Mercury was adopted in 2013 under UNEP",
    "strait of hormuz": "Strait of Hormuz is a vital strait connecting the Persian Gulf and the Gulf of Oman",
    "persian gulf": "Persian Gulf is a mediterranean sea in Western Asia connecting to the Gulf of Oman",
    "western ghats": "Western Ghats is a UNESCO World Heritage site and global biodiversity hotspot in India",
    "amul": "Amul (GCMMF) was established in 1946; HQ: Anand, Gujarat",
    "kmscl": "Kerala Medical Services Corporation (KMSCL) is under Department of Health, Government of Kerala",
    "seedap": "SEEDAP is under the Department of Skill Development, Government of Andhra Pradesh",
    "jncasr": "JNCASR is an autonomous institution under the Department of Science and Technology",
}


def fallback_static_gk(text: str) -> str | None:
    t = (text or "").lower()
    for k, v in CURATED_STATIC_GK.items():
        if k in t:
            return v
    return None


def _anchor_kinds(sgk: str, year: int) -> list[str]:
    found = []
    for kind, rx in _ANCHORS.items():
        m = rx.search(sgk)
        if not m:
            continue
        if m.lastindex and m.group(1) and m.group(1).isdigit():
            if int(m.group(1)) > year - 2:  # recent year: not permanent
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
