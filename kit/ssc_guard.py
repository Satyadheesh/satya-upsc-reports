"""ssc_guard: Strict Q&A validation and safe static GK selection for SSC one-liner cards."""
from __future__ import annotations

import re


class SscInvalid(ValueError):
    pass


# ---------- Q&A checks ----------
_Q_START = re.compile(
    r"^\s*(?:(?:by|on|in|to|at|from|for|with|under|of|against|since|until|according to|as per)\b[^,?:;]{1,80},\s*)?"
    r"(?:who|whom|whose|what|which|when|where|why|how|in which|under which|for which|from which|to which|with which|by how|by what|by which|on which|to what)\b",
    re.I,
)
_BAD_Q = re.compile(r"key development|key update|what is the news|\.{3}|…|:\s*\?", re.I)
_VAGUE = re.compile(
    r"^\s*(not specified|unknown|n/?a|none|unspecified|not mentioned|not stated|not available)\b",
    re.I,
)
_QUAL = re.compile(r"\b(up to|over|nearly|about|at least|approximately|around|more than)\s+$", re.I)


def grounded(answer: str, note_text: str) -> bool:
    norm = lambda s: re.sub(r"[^a-z0-9.%]+", " ", (s or "").lower()).strip()
    a, n = norm(answer), norm(note_text)
    if not a or not n:
        return False
    if a in n:
        return True
    toks = [t for t in a.split() if len(t) > 2]
    return bool(toks) and sum(t in n for t in toks) / len(toks) >= 0.8


def numbers_in(text: str) -> set[str]:
    return {re.sub(r",", "", m) for m in re.findall(r"\b\d+(?:,\d+)*(?:\.\d+)?\b", text or "")}


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
        if not grounded(a, note_text):
            raise SscInvalid(f"answer '{a}' is not grounded in the source note.")

        note_nums = numbers_in(note_text)
        ans_nums = numbers_in(a)
        for num in ans_nums:
            if num not in note_nums:
                raise SscInvalid(f"number '{num}' in answer does not appear in the source note.")

        for m in re.finditer(re.escape(a), note_text, re.I):
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
    "kmscl": (["kmscl"], "KMSCL is under Department of Health, Government of Kerala"),
    "isro": (["isro"], "ISRO HQ: Bengaluru, Karnataka; under Department of Space"),
    "drdo": (["drdo"], "DRDO HQ: New Delhi; under Ministry of Defence"),
    "cisf": (["cisf"], "CISF was established under the CISF Act, 1968; HQ: New Delhi"),
    "crpf": (["crpf"], "CRPF was established under the CRPF Act, 1949; HQ: New Delhi"),
    "bsf": (["bsf"], "BSF was established under the BSF Act, 1968; HQ: New Delhi"),
    "nabard": (["nabard"], "NABARD was established in 1982 under the NABARD Act, 1981; HQ: Mumbai"),
    "sidbi": (["sidbi"], "SIDBI was established in 1990 under the SIDBI Act, 1989; HQ: Lucknow"),
    "lic": (["lic"], "LIC was established in 1956 under the Life Insurance Corporation Act, 1956; HQ: Mumbai"),
    "upsc": (["upsc"], "UPSC is established under Article 315 of the Constitution"),
    "cag": (["cag", "comptroller and auditor general"], "CAG of India is appointed under Article 148 of the Constitution"),
    "finance_commission": (["finance commission"], "Finance Commission is constituted under Article 280 of the Constitution"),
    "supreme_court": (["supreme court"], "Supreme Court of India was established under Article 124 of the Constitution"),
    "minamata": (["minamata convention", "minamata"], "Minamata Convention on Mercury was adopted in 2013 under UNEP"),
    "strait_of_hormuz": (["strait of hormuz"], "Strait of Hormuz connects the Persian Gulf and the Gulf of Oman"),
    "persian_gulf": (["persian gulf"], "Persian Gulf is a mediterranean sea in Western Asia connecting to the Gulf of Oman"),
    "western_ghats": (["western ghats"], "Western Ghats is a UNESCO World Heritage site and global biodiversity hotspot in India"),
    "unicef": (["unicef"], "UNICEF is headquartered in New York City"),
    "mea": (["ministry of external affairs", "mea"], "Ministry of External Affairs HQ: South Block, New Delhi"),
    "germany": (["germany"], "Germany's capital is Berlin; currency: Euro"),
    "seychelles": (["seychelles"], "Seychelles is an archipelago nation in the Indian Ocean; capital: Victoria"),
    "ppac": (["ppac", "petroleum planning"], "PPAC operates under the Ministry of Petroleum and Natural Gas"),
    "indus_water": (["indus water treaty"], "Indus Water Treaty was signed in 1960 between India and Pakistan; mediated by World Bank"),
    "desert_np": (["desert national park"], "Desert National Park is located in Rajasthan; known for Great Indian Bustard"),
    "gib": (["great indian bustard"], "Great Indian Bustard is listed as Critically Endangered on the IUCN Red List"),
    "lactoferrin": (["lactoferrin"], "Lactoferrin is an iron-binding glycoprotein found in milk and mucosal secretions"),
    "openai": (["openai"], "OpenAI was founded in 2015; HQ: San Francisco, California"),
    "survey_of_india": (["survey of india"], "Survey of India was established in 1767 under the Department of Science and Technology; HQ: Dehradun"),
    "aisi": (["aisi", "ai safety institute"], "UK AI Safety Institute (AISI) was established in 2023 under the UK Government"),
    "dfsi": (["dfsi", "diabetic foot society"], "Diabetic Foot Society of India (DFSI) was established in 2001; HQ: Chennai"),
    # --- added 5 Oct 2026 (standard reference facts; SSC staples) ---
    "nasa": (["nasa"], "NASA was established in 1958; HQ: Washington, D.C."),
    "esa": (["european space agency", "esa"], "European Space Agency was established in 1975; HQ: Paris"),
    "un": (["united nations"], "United Nations was founded in 1945; HQ: New York"),
    "unesco": (["unesco"], "UNESCO was founded in 1945; HQ: Paris"),
    "who": (["world health organization"], "WHO was established in 1948; HQ: Geneva"),
    "imf": (["imf", "international monetary fund"], "IMF was set up at Bretton Woods in 1944; HQ: Washington, D.C."),
    "world_bank": (["world bank"], "World Bank was set up at Bretton Woods in 1944; HQ: Washington, D.C."),
    "wto": (["wto", "world trade organization"], "WTO was established in 1995; HQ: Geneva"),
    "adb": (["asian development bank", "adb"], "Asian Development Bank was established in 1966; HQ: Manila"),
    "aiib": (["aiib", "asian infrastructure investment bank"], "AIIB began operations in 2016; HQ: Beijing"),
    "ndb": (["new development bank"], "New Development Bank (BRICS bank) was set up in 2015; HQ: Shanghai"),
    "asean": (["asean"], "ASEAN was founded in 1967; secretariat: Jakarta"),
    "saarc": (["saarc"], "SAARC was founded in 1985; secretariat: Kathmandu"),
    "bimstec": (["bimstec"], "BIMSTEC was founded in 1997; secretariat: Dhaka"),
    "sco": (["shanghai cooperation organisation", "sco"], "SCO was founded in 2001; secretariat: Beijing"),
    "nato": (["nato"], "NATO was founded in 1949; HQ: Brussels"),
    "unep": (["unep", "un environment programme"], "UNEP was founded in 1972; HQ: Nairobi"),
    "fao": (["fao", "food and agriculture organization"], "FAO was founded in 1945; HQ: Rome"),
    "ilo": (["ilo", "international labour organization"], "ILO was founded in 1919; HQ: Geneva"),
    "iucn": (["iucn"], "IUCN was founded in 1948; HQ: Gland, Switzerland"),
    "ramsar": (["ramsar"], "Ramsar Convention on Wetlands was signed in 1971 at Ramsar, Iran"),
    "icc": (["international cricket council"], "International Cricket Council HQ: Dubai"),
    "fifa": (["fifa"], "FIFA was founded in 1904; HQ: Zurich"),
    "ioc": (["international olympic committee"], "International Olympic Committee was founded in 1894; HQ: Lausanne"),
    "bcci": (["bcci"], "BCCI was founded in 1928; HQ: Mumbai"),
    "niti": (["niti aayog"], "NITI Aayog replaced the Planning Commission on 1 January 2015; chaired by the Prime Minister"),
    "npci": (["npci"], "NPCI was set up in 2008 by RBI and IBA; HQ: Mumbai; runs UPI"),
    "sbi": (["state bank of india", "sbi"], "State Bank of India was constituted in 1955; HQ: Mumbai"),
    "irdai": (["irdai"], "IRDAI was set up under the IRDA Act, 1999; HQ: Hyderabad"),
    "nhrc": (["nhrc", "national human rights commission"], "NHRC was set up under the Protection of Human Rights Act, 1993"),
    "ngt": (["national green tribunal", "ngt"], "National Green Tribunal was set up under the NGT Act, 2010"),
    "lokpal": (["lokpal"], "Lokpal was set up under the Lokpal and Lokayuktas Act, 2013"),
    "nobel": (["nobel prize", "nobel"], "Nobel Prizes were first awarded in 1901"),
    "booker": (["booker prize"], "The Booker Prize was first awarded in 1969"),
    "bharat_ratna": (["bharat ratna"], "Bharat Ratna, India's highest civilian award, was instituted in 1954"),
    "padma": (["padma shri", "padma bhushan", "padma vibhushan", "padma awards"], "Padma awards were instituted in 1954"),
    "project_tiger": (["project tiger"], "Project Tiger was launched in 1973"),
    "gst_council": (["gst council"], "GST Council is a constitutional body under Article 279A, chaired by the Union Finance Minister"),
    "nhai": (["nhai"], "NHAI was constituted under the NHAI Act, 1988; under the Ministry of Road Transport and Highways"),
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
    toks = lambda s: {w for w in re.findall(r"[A-Za-z0-9]+", s.lower()) if len(w) >= 3}
    return bool(toks(sgk) & toks(question + " " + answer + " " + key))


def choose_static_gk(card: dict, gemma_ok=None) -> tuple[str, str]:
    """Returns (published_line, source).
    Table first. If the entity isn't in the table, leave the line blank.
    Gemma's own line goes to a review queue and is never published automatically.
    """
    q = card.get("ssc_question") or card.get("question") or ""
    a = card.get("ssc_answer") or card.get("answer") or ""
    k = card.get("key_fact") or card.get("key") or ""

    # Subject entities in Q and A get top priority
    t = static_gk_from_table(q, a)
    if t:
        return t, "table"

    # Only check key if the static GK line is relevant to the card subject
    candidate = static_gk_from_table(k)
    if candidate and relevant(candidate, q, a, k):
        return candidate, "table"

    return "", "none"
