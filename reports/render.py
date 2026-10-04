"""HTML for the Brief and Detailed editions (printed to PDF by Chromium in reports/build.py).
Design: the dummies approved on 2 Oct 2026 (masthead, top stories, cards, In brief, quiz)."""
import datetime as dt
import html
import re

try:
    import qrcode
    import qrcode.image.svg
except ImportError:
    qrcode = None

from common.syllabus import SYLLABUS

SITE = "https://satyadheesh.in"
TELEGRAM = "https://t.me/satyadheesh"
GAVEL = ('<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg"><rect x="1" y="1" width="62" height="62" rx="13" fill="#f8f6f2" stroke="#120f0b" stroke-width="2"/>'
         '<g transform="rotate(-38 32 30)"><rect x="17" y="18" width="16" height="24" rx="4" fill="#bf4a07"/><rect x="17" y="24" width="16" height="3" fill="#8f3a08"/>'
         '<rect x="33" y="27.5" width="16" height="6" rx="3" fill="#bf4a07"/></g><rect x="15" y="49" width="34" height="4" rx="2" fill="#a39c92"/></svg>')
PAPER_HINT = {"GS1": ("History · Society · Geography", "इतिहास · समाज · भूगोल"),
              "GS2": ("Polity · Governance · Social Justice · IR", "राजव्यवस्था · शासन · सामाजिक न्याय · अंतर्राष्ट्रीय संबंध"),
              "GS3": ("Economy · S&T · Environment · Security", "अर्थव्यवस्था · विज्ञान-तकनीक · पर्यावरण · सुरक्षा"),
              "GS4": ("Ethics", "नीतिशास्त्र")}
SUBJECT_HI = {"history_culture": "इतिहास एवं संस्कृति", "society": "भारतीय समाज", "geography": "भूगोल",
              "polity": "राजव्यवस्था एवं संविधान", "governance": "शासन", "social_justice": "सामाजिक न्याय",
              "ir": "अंतर्राष्ट्रीय संबंध", "economy": "अर्थव्यवस्था", "agriculture": "कृषि",
              "science_tech": "विज्ञान एवं प्रौद्योगिकी", "environment": "पर्यावरण एवं पारिस्थितिकी",
              "disaster": "आपदा प्रबंधन", "security": "आंतरिक सुरक्षा", "ethics": "नीतिशास्त्र एवं सत्यनिष्ठा"}
POINTER = {"constitution": ("Constitution", "संविधान"), "act_bill": ("Act / Bill", "अधिनियम"), "scheme": ("Scheme", "योजना"),
           "institution": ("Body", "संस्था"), "report_index": ("Report", "रिपोर्ट"), "place": ("Place", "स्थान"),
           "species_environment": ("Environment", "पर्यावरण"), "sci_tech": ("S&T", "विज्ञान"),
           "international_org": ("Intl. org", "अंत. संगठन"), "person_post": ("Post", "पद"), "data_fact": ("Fact", "तथ्य")}
FACT_LABEL_HI = {"Body": "संस्था", "Case": "मामला", "Act": "अधिनियम", "Scheme": "योजना", "Place": "स्थान", "Person": "व्यक्ति",
                 "Figure": "आँकड़ा", "Date": "तिथि", "Report": "रिपोर्ट", "Concept": "अवधारणा", "Event": "घटना",
                 "Index": "सूचकांक", "Mission": "मिशन"}
MONTHS_HI = ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"]
DAYS_HI = ["सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार"]
SUBJ_ORDER = list(SYLLABUS)

T = {
    "en": dict(
        brief="UPSC {kind} Brief", detailed="UPSC {kind} Detailed Notes", daily="Daily", weekly="Weekly", monthly="Monthly",
        vol_brief="Vol. I · {kind} Brief", vol_detailed="Vol. I · Detailed Notes", ca="Current Affairs",
        read="Reading time", min="min", key="Key stories", inbrief="In brief", quiz="Mains", notes="Notes",
        merged="Stories merged", mix="Paper mix",
        k_top="01 — {when} in 2 minutes", today="Today", week="The week", month="The month",
        top="The {n} stories you can’t skip", matters="Why it matters:",
        number="Number of the day", number_w="Figures worth remembering", static="Connect to static",
        k_cards="02 — Key stories", cards="What to know, in 60 seconds each", cards_aside="{n} of {t} notes · picked for exam value",
        why="Why in news:", remember="Remember", angle="Mains angle", use="Use:", full="Full note →",
        k_brief="03 — In brief", inbrief_h="Everything else, one line each", brief_aside="{n} more notes · full versions online",
        k_places="Map work", places="Places in news",
        k_test="04 — Test yourself", test="{n} questions, {n} minutes", test_aside="Answers at the bottom, upside down",
        k_mains="Mains practice", mains1="Write one answer today", mains_n="Mains questions to practise",
        answers="ANSWERS", ask="Which of the statements given above is/are correct?",
        cta1="Get it every morning on <i>Telegram</i>", cta2="Daily PDF + quiz at 5 AM · weekly review every Sunday · English and Hindi · free, no sign-up.",
        qr_tg="Telegram", qr_site="Website",
        disc="Notes are generated from SatyaDheesh’s news feed and mapped to the UPSC CSE syllabus. Verify facts with the original report or PIB before using them in an answer.",
        inside_b="<span><b>p.2</b> Key stories</span><span><b>»</b> In brief + places</span><span><b>»</b> Test yourself</span><span style=\"margin-left:auto\">P = Prelims · M = Mains</span>",
        contents="Contents", contents_h="Every note, grouped by paper", how_k="How each note reads",
        how="Why in news → facts to remember → a Mains question with keywords. Duplicate stories are merged.",
        short_k="Short on time?", short="The 5-page <b>Brief</b> has the stories that matter most, plus a quiz. Same day, same notes.",
        why_d="Why in news", mq="Mains Q", reports_merged="{n} reports merged", practice="Practice", mcqs="MCQs",
        ptot="{n} notes"),
    "hi": dict(
        brief="यूपीएससी {kind} सार", detailed="यूपीएससी {kind} विस्तृत नोट्स", daily="दैनिक", weekly="साप्ताहिक", monthly="मासिक",
        vol_brief="भाग I · {kind} सार", vol_detailed="भाग I · विस्तृत नोट्स", ca="करेंट अफेयर्स",
        read="पढ़ने का समय", min="मिनट", key="मुख्य ख़बरें", inbrief="संक्षेप में", quiz="मेन्स प्रश्न", notes="नोट्स",
        merged="ख़बरें जोड़ी गईं", mix="पेपर मिश्रण",
        k_top="01 — {when} 2 मिनट में", today="आज", week="यह सप्ताह", month="यह महीना",
        top="{n} ख़बरें जो छोड़नी नहीं हैं", matters="क्यों ज़रूरी:",
        number="आज का आँकड़ा", number_w="याद रखने योग्य आँकड़े", static="स्टैटिक से जोड़ें",
        k_cards="02 — मुख्य ख़बरें", cards="हर ख़बर, 60 सेकंड में", cards_aside="{t} में से {n} नोट्स · परीक्षा के हिसाब से",
        why="चर्चा में क्यों:", remember="याद रखें", angle="मेन्स कोण", use="उत्तर में लिखें:", full="पूरा नोट →",
        k_brief="03 — संक्षेप में", inbrief_h="बाकी सब, एक पंक्ति में", brief_aside="{n} और नोट्स · पूरे नोट्स ऑनलाइन",
        k_places="मानचित्र", places="चर्चा में स्थान",
        k_test="04 — अभ्यास", test="{n} प्रश्न", test_aside="उत्तर नीचे उल्टे लिखे हैं",
        k_mains="मेन्स अभ्यास", mains1="आज एक उत्तर लिखें", mains_n="अभ्यास के लिए मेन्स प्रश्न",
        answers="उत्तर", ask="ऊपर दिए गए कथनों में से कौन-सा/से सही है/हैं?",
        cta1="हर सुबह <i>टेलीग्राम</i> पर पाएँ", cta2="रोज़ सुबह 5 बजे पीडीएफ + क्विज़ · हर रविवार साप्ताहिक · हिंदी और अंग्रेज़ी · मुफ़्त, बिना साइन-अप।",
        qr_tg="टेलीग्राम", qr_site="वेबसाइट",
        disc="नोट्स सत्याधीश के समाचार फ़ीड से स्वचालित रूप से बनाए जाते हैं और यूपीएससी सीएसई पाठ्यक्रम से जुड़े हैं। उत्तर में उपयोग से पहले तथ्यों का मूल रिपोर्ट या पीआईबी से मिलान करें।",
        inside_b="<span><b>पृ.2</b> मुख्य ख़बरें</span><span><b>»</b> संक्षेप में</span><span><b>»</b> अभ्यास</span><span style=\"margin-left:auto\">P = प्रीलिम्स · M = मेन्स</span>",
        contents="विषय सूची", contents_h="सभी नोट्स, पेपर के अनुसार", how_k="हर नोट में",
        how="चर्चा में क्यों → याद रखने योग्य तथ्य → कीवर्ड के साथ मेन्स प्रश्न। एक ही ख़बर की रिपोर्टें जोड़ दी गई हैं।",
        short_k="समय कम है?", short="5 पेज के <b>सार</b> में सबसे ज़रूरी ख़बरें और अभ्यास प्रश्न हैं।",
        why_d="चर्चा में क्यों", mq="मेन्स प्रश्न", reports_merged="{n} रिपोर्टें जोड़ी गईं", practice="अभ्यास", mcqs="MCQ",
        ptot="{n} नोट्स"),
}
SIZE = {  # per edition kind: top, cards, in-brief lines, mcqs, mains
    "daily": (5, 8, 24, 5, 1), "weekly": (6, 10, 36, 8, 2), "monthly": (6, 12, 54, 10, 3)}


def e(s):
    return html.escape(str(s or ""), quote=False)


def clip(s, n):
    s = " ".join(str(s or "").split())
    if len(s) <= n:
        return s
    cut = s.rfind(" ", 0, n - 1)
    return s[: cut if cut > n * 0.6 else n - 1].rstrip(" ,;:") + "…"


def first_sentence(s, n=240):
    """The first sentence, whole. A very long one is cut back at its last clause (', ' / '; ') — never mid-word
    and never with '…' (reviewer, 3 Oct: cut-off text reads as broken)."""
    s = " ".join(str(s or "").split())
    m = re.search(r"(?<=[.।!?])\s", s)
    first = s[: m.start()] if m else s
    if len(first) <= n:
        return first
    for sep in ("; ", ", ", " — "):
        k = first.rfind(sep, 0, n)
        if k > n // 2:
            return first[:k]
    return clip(first, n)


def fit(s, n):
    """Text for a box of about n characters: whole if it nearly fits (Hindi runs ~30% longer), else its first
    sentence cut back at a clause — never mid-word with '…'."""
    s = " ".join(str(s or "").split())
    return s if len(s) <= int(n * 1.3) else first_sentence(s, n)


def subject_name(s, hi):
    return (SUBJECT_HI.get(s) if hi else None) or (SYLLABUS.get(s, (None, s))[1])


def node_name(s, n):
    return SYLLABUS.get(s, (None, None, {}))[2].get(n, n)


def date_label(d, hi, short=False, year=True):
    if hi:
        out = f"{d.day} {MONTHS_HI[d.month - 1]}"
    else:
        out = f"{d.day} {d.strftime('%b' if short else '%B')}"
    return f"{out} {d.year}" if year else out


def period_label(p, hi):
    if p["kind"] == "daily":
        return date_label(p["first"], hi)
    if p["kind"] == "monthly":
        return f"{MONTHS_HI[p['first'].month - 1]} {p['first'].year}" if hi else p["first"].strftime("%B %Y")
    a = date_label(p["first"], hi, short=True, year=False)
    b = date_label(p["last"], hi, short=True)
    return (f"सप्ताह {p['week']} · {a} – {b}" if hi else f"Week {p['week']} · {a} – {b}")


def qr_svg(url):
    if not qrcode:
        return '<svg class="qr" viewBox="0 0 100 100"></svg>'
    s = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, border=1, box_size=10).to_string(encoding="unicode")
    return re.sub(r"<\?xml[^>]*>", "", s).replace("<svg ", '<svg class="qr" ', 1)


def chip(paper, subject=None):
    return f'<span class="chip {paper.lower()}">{e(paper)}{(" · " + e(subject)) if subject else ""}</span>'


def exam_chips(exam):
    return "".join(f'<span class="chip ex">{x}</span>' for x in {"prelims": "P", "mains": "M", "both": "PM"}.get(exam, "PM"))


def split_fact(text):
    """'Name — what it is' -> (name, rest)."""
    m = re.match(r"^(.{2,60}?)\s*[—:–-]\s+(.+)$", text or "")
    return (m.group(1).strip(), m.group(2).strip()) if m else (None, text)


# ---------------------------------------------------------------- shared blocks

def masthead(p, lang, edition):
    t, hi = T[lang], lang == "hi"
    kind = t[p["kind"]]
    if edition == "ssc":
        left = "Vol. I · SSC CGL One-Liner" if not hi else "भाग I · एसएससी सीजीएल वन-लाइनर"
        product = f"SSC CGL {kind} One-Liner Revision" if not hi else f"एसएससी सीजीएल {kind} वन-लाइनर"
    else:
        left = (t["vol_brief"].format(kind=kind) if edition == "brief" else t["vol_detailed"])
        product = (t["brief"] if edition == "brief" else t["detailed"]).format(kind=kind)
    if p["kind"] == "daily":
        d = p["first"]
        right = f"{DAYS_HI[d.weekday()]}, {date_label(d, True)}" if hi else d.strftime("%A, ") + date_label(d, False)
    else:
        right = period_label(p, hi)
    return f'''<header class="mast"><div class="stripe"></div>
<div class="edition"><span>{e(left)}</span><span>{e(right)}</span></div>
<div class="logo">{GAVEL}<div><div class="word">Satya<i>Dheesh</i></div><div class="hiword">सत्याधीश</div></div></div>
<div><span class="product">{e(product)}</span></div>
<div class="dateline">{e(t["ca"])} · {e(period_label(p, hi))}</div><div class="hair"></div></header>'''


def glance(cells, mix, mix_label):
    c = "".join(f'<div><div class="n">{e(n)}</div><div class="l">{e(l)}</div></div>' for n, l in cells)
    m = "".join(chip(pp, str(n)) for pp, n in mix)
    return f'<div class="glance">{c}<div><div class="mix">{m}</div><div class="l">{e(mix_label)}</div></div></div>'


def paper_mix(items):
    out = {}
    for it in items:
        out[it["paper"]] = out.get(it["paper"], 0) + 1
    return [(pp, out[pp]) for pp in ("GS1", "GS2", "GS3", "GS4") if pp in out]


def sec_head(kicker, title, aside=""):
    return (f'<div class="sec-row"><div><div class="kicker">{e(kicker)}</div><h2 class="sec">{e(title)}</h2></div>'
            f'<div class="aside">{e(aside)}</div></div>')


def cta(lang):
    """Closing box: Telegram channel first (where the daily PDF goes), the reports page second."""
    t = T[lang]
    site = f"{SITE}/upsc/reports" + ("?lang=hi" if lang == "hi" else "")
    qrs = (f'<div class="qrs"><figure>{qr_svg(TELEGRAM)}<figcaption>{e(t["qr_tg"])}</figcaption></figure>'
           f'<figure>{qr_svg(site)}<figcaption>{e(t["qr_site"])}</figcaption></figure></div>')
    return (f'<div class="cta">{qrs}<div><div class="t1">{t["cta1"]}</div><div class="t2">{e(t["cta2"])}</div>'
            f'<div class="t3">t.me/satyadheesh · satyadheesh.in/upsc/reports</div></div></div><p class="disc">{e(t["disc"])}</p>')


def mcq_block(qs, lang):
    t = T[lang]
    out = []
    for i, m in enumerate(qs):
        st = ""
        if m.get("statements"):
            st = '<ol class="stmts">' + "".join(f"<li>{e(s)}</li>" for s in m["statements"]) + "</ol>"
            st += f'<div class="t" style="margin:1mm 0 0 7mm;font-size:8.7pt">{e(t["ask"])}</div>'
        opts = "".join(f'<div><i>{"abcd"[j]}</i>{e(o)}</div>' for j, o in enumerate(m["options"]))
        out.append(f'<div class="mcq"><div class="qn"><div class="n">{i + 1}</div><div class="t">{e(m["question"])}</div></div>'
                   f'{st}<div class="opts">{opts}</div></div>')
    keys = " &nbsp; ".join(f'{i + 1} ({"abcd"[m["answer"]]})' for i, m in enumerate(qs))
    return "".join(out), f'<div class="answers">{e(t["answers"])} &nbsp;·&nbsp; {keys}</div>' if qs else ""


def mains_block(items, lang):
    t = T[lang]
    out = []
    for it in items:
        kw = "".join(f"<span>{e(k)}</span>" for k in it["keywords"][:5]) if lang == "en" else ""
        meta = f'{it["paper"]} · {e(subject_name(it["subject"], lang == "hi"))}'
        out.append(f'<div class="mains"><div class="meta">{meta}</div><div class="t">{e(it["mains"])}</div>'
                   + (f'<div class="kw"><em>{e(t["use"])}</em>{kw}</div>' if kw else "") + "</div>")
    return "".join(out)


def kit_of(it, lang):
    """The study kit in the report's language (Hindi kit comes from the Hindi service), or None."""
    k = it.get("kit_hi") if lang == "hi" else it.get("kit")
    return k if k and k.get("short_title") else None


def kit_facts(it, lang, n=3):
    """Facts to remember: study-kit facts or the note's own pointers."""
    k = kit_of(it, lang)
    if k and k.get("facts"):
        return [f["text"] for f in k["facts"][:n]]
    return [p["text"] for p in it["pointers"][:n]]


def doc(lang, title, body):
    return (f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><title>{e(title)}</title>'
            f'<link rel="stylesheet" href="base.css"></head><body>{body}</body></html>')


# ---------------------------------------------------------------- Brief

_PROPER = re.compile(r"\b(?:[A-Z]{3,}|[A-Z][a-z]{4,})\b")
_COMMON = {"India", "Indian", "Supreme", "Court", "Union", "Government", "Minister", "State", "States", "National",
           "Centre", "Central", "President", "Prime", "Chief", "Ministry", "Department", "Report", "Bill", "Delhi",
           "Commission", "Council", "Board", "Authority", "Policy", "Scheme", "World", "Global", "International"}


def _salient(it):
    t = it.get("title_en") or it["title"]
    return {w for w in _PROPER.findall(t) if w not in _COMMON}


def pick_cards(items, n, kind):
    """Key stories: best first, but never two cards on the same story (e.g. two BRICS-summit reports), and
    in weekly/monthly digests no subject takes more than about a third of the cards."""
    cap = n if kind == "daily" else max(2, round(n * 0.34))
    out, per_subject = [], {}
    for it in items:
        if len(out) == n:
            break
        if per_subject.get(it["subject"], 0) >= cap:
            continue
        s = _salient(it)
        if any(c["paper"] == it["paper"] and (s & _salient(c)) for c in out):
            continue  # same story told twice
        out.append(it)
        per_subject[it["subject"]] = per_subject.get(it["subject"], 0) + 1
    for it in items:  # top up if the rules left gaps
        if len(out) == n:
            break
        if it not in out:
            out.append(it)
    return out


def brief(p, items, total, lang):
    """items: the chosen notes, best first. Returns (html, n_items)."""
    t, hi = T[lang], lang == "hi"
    n_top, n_cards, n_lines, n_mcq, n_mains = SIZE[p["kind"]]
    kit = (lambda it: kit_of(it, lang))
    cards = pick_cards(items, n_cards, p["kind"])
    top = cards[:n_top]
    chosen_ids = {it["id"] for it in cards}
    rest = [it for it in items if it["id"] not in chosen_ids][:n_lines]
    mcqs = [kit_of(it, lang)["mcq"] for it in items if kit_of(it, lang) and kit_of(it, lang).get("mcq")][:n_mcq]
    mains = [it for it in items if it.get("mains")][:n_mains]
    mins = round(len(cards) * 1 + len(rest) * 0.15 + len(mcqs) * 1 + 2)

    cells = [(f"{mins} {t['min']}", t["read"]), (str(len(cards)), t["key"]), (str(len(rest)), t["inbrief"])]
    if mcqs:
        cells.append((f"{len(mcqs)} + {len(mains)}", "MCQs + Mains"))
    elif mains:
        cells.append((str(len(mains)), "मेन्स प्रश्न" if hi else ("Mains question" if len(mains) == 1 else "Mains questions")))
    when = {"daily": t["today"], "weekly": t["week"], "monthly": t["month"]}[p["kind"]]

    def short_title(it):
        k = kit(it)
        return (k or {}).get("short_title") or it["title"]

    def facts_both(it):
        """(English fact, fact in this report's language) pairs, so number-of-the-day, static and places are chosen
        on the English facts and both editions pick the same ones."""
        fe = (it.get("kit") or {}).get("facts") or []
        fd = (kit(it) or {}).get("facts") or []
        return list(zip(fe, fd)) if len(fe) == len(fd) else []

    tops = "".join(
        f'<li><div class="num">{i + 1}</div><div><div class="hl">{e(short_title(it))}</div>'
        f'<div class="why"><b>{e(t["matters"])}</b> {e((kit(it) or {}).get("takeaway") or first_sentence(it["why"]))}</div>'
        f'<div class="chips">{chip(it["paper"], subject_name(it["subject"], hi))}{exam_chips(it["exam"])}</div></div></li>'
        for i, it in enumerate(top))
    p1 = (masthead(p, lang, "brief") + glance(cells, paper_mix(items), t["mix"])
          + f'<div class="kicker">{e(t["k_top"].format(when=when))}</div><h2 class="sec" style="margin-bottom:1mm">'
          f'{e(t["top"].format(n=len(top)))}</h2><ol class="top5">{tops}</ol>')

    # Number of the day / week in numbers + connect to static (study-kit facts, English only)
    figures, static = [], None
    for it in cards:
        for fe, f in facts_both(it):
            name_e = split_fact(fe["text"])[0]
            name, rest_t = split_fact(f["text"])
            name = name or name_e
            if fe["label"] == "Figure" and name_e and len(name_e) <= 18 and re.search(r"\d", name_e):
                figures.append((name, rest_t, it))
            if static is None and fe["label"] in ("Case", "Act") and name_e:
                static = (name, rest_t, it)
    boxes = ""
    if p["kind"] == "daily" and (figures or static):
        num = (f'<div class="box cream"><div class="kicker">{e(t["number"])}</div><div class="bignum">{e(figures[0][0])}</div>'
               f'<p>{e(fit(figures[0][1], 150))}</p></div>') if figures else ""
        st = (f'<div class="box line"><div class="kicker">{e(t["static"])}</div><h4>{e(static[0])}</h4>'
              f'<p>{e(fit(static[1], 120))} <i>{"ख़बर में" if hi else "In the news"}: {e(short_title(static[2]))}.</i></p></div>') if static else ""
        boxes = f'<div class="duo" style="grid-template-columns:{"1fr 1.25fr" if num and st else "1fr"}">{num}{st}</div>'
    elif p["kind"] != "daily" and len(figures) >= 3:
        tiles = "".join(f'<div class="tile"><div class="v">{e(v)}</div><div class="c">{e(fit(c, 90))}</div></div>' for v, c, _ in figures[:4])
        boxes = (f'<div class="kicker">{e(t["number_w"])}</div><div class="tiles" style="grid-template-columns:repeat({min(4, len(figures))},1fr)">{tiles}</div>')
    p1 += boxes + f'<div class="inside">{t["inside_b"]}</div>'

    def card(it):
        k = kit(it) or {}
        rem = "".join(f"<li>{e(fit(x, 170))}</li>" for x in kit_facts(it, lang))
        kw = "".join(f"<span>{e(x)}</span>" for x in it["keywords"][:4]) if not hi else ""
        angle = (f'<div class="angle"><div class="q"><b>{e(t["angle"])}</b>{e(fit(it["mains"], 220))}</div>'
                 + (f'<div class="kw"><em>{e(t["use"])}</em>{kw}</div>' if kw else "")
                 + f'<div class="more">{e(t["full"])} satyadheesh.in/news/{it["id"]}</div></div>') if it.get("mains") else \
            f'<div class="angle"><div class="more">{e(t["full"])} satyadheesh.in/news/{it["id"]}</div></div>'
        return (f'<article class="card"><div class="in"><div class="chips">{chip(it["paper"], subject_name(it["subject"], hi))}'
                f'{exam_chips(it["exam"])}</div><h3>{e(k.get("short_title") or it["title"])}</h3>'
                f'<p class="why"><b>{e(t["why"])}</b> {e(fit(it["why"], 260))}</p>'
                + (f'<div class="lbl">{e(t["remember"])}</div><ul class="rem">{rem}</ul>' if rem else "")
                + f'</div>{angle}</article>')

    p2 = (f'<section class="page">{sec_head(t["k_cards"], t["cards"], t["cards_aside"].format(n=len(cards), t=total))}'
          f'<div class="cards">{"".join(card(it) for it in cards)}</div></section>')

    p3 = ""
    if rest:
        groups = []
        for paper in ("GS1", "GS2", "GS3", "GS4"):
            lines = [it for it in rest if it["paper"] == paper]
            if not lines:
                continue
            li = []
            for it in lines:
                k = kit(it)
                if k and k.get("brief_lead"):
                    li.append(f'<li><b>{e(k["brief_lead"])}</b> {e(k["brief_text"])}</li>')
                else:
                    li.append(f'<li>{e(fit(it["title"], 150))}</li>')
            groups.append(f'<div class="grp">{chip(paper, (PAPER_HINT[paper][1] if hi else PAPER_HINT[paper][0]))}<ul>{"".join(li)}</ul></div>')
        places, seen = [], set()
        for it in items:
            for fe, f in facts_both(it):
                name_e = split_fact(fe["text"])[0]
                name, desc = split_fact(f["text"])
                if fe["label"] == "Place" and name_e and name_e.lower() not in seen and len(places) < 5:
                    seen.add(name_e.lower())
                    places.append(f'<tr><td>{e(name or name_e)}</td><td>{e(fit(desc, 140))}</td></tr>')
        pl = (f'<div class="places"><div class="kicker">{e(t["k_places"])}</div><h2 class="sec" style="font-size:13pt;margin:.4mm 0 1.6mm">'
              f'{e(t["places"])}</h2><table>{"".join(places)}</table></div>') if len(places) >= 3 else ""
        p3 = (f'<section class="page">{sec_head(t["k_brief"], t["inbrief_h"], t["brief_aside"].format(n=len(rest)))}'
              f'<div class="brief">{"".join(groups)}</div>{pl}</section>')

    qs, keys = mcq_block(mcqs, lang)
    p4 = f'<section class="page">'
    if mcqs:
        p4 += sec_head(t["k_test"], t["test"].format(n=len(mcqs)), t["test_aside"]) + qs
    if mains:
        p4 += (f'<div class="kicker" style="margin-top:4mm">{e(t["k_mains"])}</div><h2 class="sec" style="font-size:13pt;margin:.4mm 0 2mm">'
               f'{e(t["mains1"] if len(mains) == 1 else t["mains_n"])}</h2>{mains_block(mains, lang)}')
    p4 += keys + cta(lang) + "</section>"
    title = f'{(t["brief"]).format(kind=t[p["kind"]])} — {period_label(p, hi)}'
    return doc(lang, title, p1 + p2 + p3 + p4)


# ---------------------------------------------------------------- Detailed

def detailed(p, items, total, lang):
    t, hi = T[lang], lang == "hi"
    merged = sum(it["related"] for it in items)
    mcqs = [kit_of(it, lang)["mcq"] for it in items if kit_of(it, lang) and kit_of(it, lang).get("mcq")][:10]
    groups = {}
    for it in items:
        groups.setdefault(it["paper"], {}).setdefault(it["subject"], []).append(it)
    cells = [(str(len(items)), t["notes"]), (str(merged), t["merged"])]
    if mcqs:
        cells.append((str(len(mcqs)), t["mcqs"]))

    rows = []
    for paper in ("GS1", "GS2", "GS3", "GS4"):
        if paper not in groups:
            continue
        n = sum(len(v) for v in groups[paper].values())
        rows.append(f'<tr class="paper"><td>{chip(paper)} &nbsp;{e(PAPER_HINT[paper][1 if hi else 0])}</td><td class="n">{e(t["ptot"].format(n=n))}</td></tr>')
        for s in sorted(groups[paper], key=lambda x: SUBJ_ORDER.index(x) if x in SUBJ_ORDER else 99):
            rows.append(f'<tr><td>{e(subject_name(s, hi))}</td><td class="n">{len(groups[paper][s])}</td></tr>')
    if mcqs:
        rows.append(f'<tr class="paper"><td>{e(t["practice"])} — {len(mcqs)} {e(t["mcqs"])}</td><td class="n"></td></tr>')
    cover = (masthead(p, lang, "detailed") + glance(cells, paper_mix(items), t["mix"])
             + f'<div class="kicker">{e(t["contents"])}</div><h2 class="sec" style="margin-bottom:1mm">{e(t["contents_h"])}</h2>'
             + f'<table class="toc">{"".join(rows)}</table>'
             + f'<div class="legend"><div class="box cream"><div class="kicker">{e(t["how_k"])}</div><p style="margin-top:0">{e(t["how"])}</p></div>'
             + f'<div class="box line"><div class="kicker">{e(t["short_k"])}</div><p style="margin-top:0">{t["short"]}</p></div></div>')

    def note(it):
        k = kit_of(it, lang)
        if k and k.get("facts"):
            facts = [((FACT_LABEL_HI.get(f["label"], f["label"]) if hi else f["label"]), f["text"]) for f in k["facts"]]
        else:
            facts = [(POINTER.get(x.get("type"), ("Fact", "तथ्य"))[1 if hi else 0], x["text"]) for x in it["pointers"][:5]]
            if it["fact_box"] and len(facts) < 2:
                facts.insert(0, ("तथ्य" if hi else "Facts", it["fact_box"]))
        dl = "".join(f"<dt>{e(a)}</dt><dd>{e(b)}</dd>" for a, b in facts)
        kw = "".join(f"<span>{e(k)}</span>" for k in it["keywords"][:5]) if not hi else ""
        mq = (f'<div class="mq"><div class="q"><b>{e(t["mq"])}</b>{e(it["mains"])}</div>'
              + (f'<div class="kw"><em>{e(t["use"])}</em>{kw}</div>' if kw else "") + "</div>") if it.get("mains") else ""
        when = dt.datetime.fromtimestamp(it["published_at"] + 19800, dt.timezone.utc).date()
        src = f'{date_label(when, hi, short=True, year=False)}' + (f' · {e(it["source"])}' if it.get("source") else "")
        mergedc = f'<span class="merged">{e(t["reports_merged"].format(n=it["related"] + 1))}</span>' if it["related"] else ""
        return (f'<article class="dnote"><div class="top"><div class="chips"><span class="chip ex" style="border-color:transparent;background:var(--cream2)">'
                f'{e(node_name(it["subject"], it["node"]))}</span>{exam_chips(it["exam"])}{mergedc}</div>'
                f'<div class="src">{src} · satyadheesh.in/news/{it["id"]}</div></div>'
                f'<h4>{e((kit_of(it, lang) or {}).get("short_title") or it["title"])}</h4><p class="why"><b>{e(t["why_d"])}</b>{e(it["why"])}</p><dl class="facts">{dl}</dl>{mq}</article>')

    body = ""
    for paper in ("GS1", "GS2", "GS3", "GS4"):
        if paper not in groups:
            continue
        n = sum(len(v) for v in groups[paper].values())
        sec = (f'<div class="band {paper.lower()}"><div class="pp">{paper}</div><div class="tt"><b>{e(PAPER_HINT[paper][1 if hi else 0])}</b>'
               f'<span>{e(t["ptot"].format(n=n))}</span></div></div>')
        for s in sorted(groups[paper], key=lambda x: SUBJ_ORDER.index(x) if x in SUBJ_ORDER else 99):
            its = groups[paper][s]
            if p["kind"] != "daily":
                its = sorted(its, key=lambda x: x["published_at"])
            sec += f'<h3 class="subj2">{e(subject_name(s, hi))}<span>{len(its)}</span></h3>' + "".join(note(x) for x in its)
        body += f'<section class="page">{sec}</section>'
    qs, keys = mcq_block(mcqs, lang)
    tail = (f'<section class="page">{sec_head(t["practice"], t["test"].format(n=len(mcqs)), t["test_aside"])}{qs}{keys}{cta(lang)}</section>'
            if mcqs else f'<section>{cta(lang)}</section>')
    title = f'{t["detailed"].format(kind=t[p["kind"]])} — {period_label(p, hi)}'
    return doc(lang, title, cover + body + tail)


# ---------------------------------------------------------------- SSC One-Liner

def _map_ssc_topic(it):
    s = (it.get("subject") or "").lower()
    n = (it.get("node") or it.get("syllabus_node") or "").lower()
    t = ((it.get("title") or "") + " " + (it.get("why") or "")).lower()

    # 05. Sports
    if any(w in t for w in ("trophy", "cup", "medal", "champion", "olympic", "cricket", "fifa", "badminton", "chess", "tennis", "grand slam", "athletics", "hockey")):
        return ("05", "Sports")
    # 07. Awards & Honours
    if any(w in t for w in ("award", "prize", "honour", "honor", "padma", "bharat ratna", "khel ratna", "nobel", "oscar", "booker", "saraswati samman")):
        return ("07", "Awards & Honours")
    # 06. Important Days
    if any(w in t for w in ("day", "divas", "anniversary", "pakhwada", "week")) and any(w in t for w in ("observed", "celebrated", "theme", "commemorated")):
        return ("06", "Important Days")
    # 04. Appointments
    if n in ("appointments", "person_post") or any(w in t for w in ("high commissioner", "ambassador", "appointed as", "assumes office", "took charge", "takes charge", "director general", "chief justice", "election commissioner", "governor")):
        return ("04", "Appointments")
    # 09. Books & Authors
    if any(w in t for w in ("book", "authored by", "released a book", "memoir", "biography", "written by")):
        return ("09", "Books & Authors")
    # 08. Government Bills
    if n in ("legislation", "act_bill") or any(w in t for w in ("information technology act", "section 69", "bill, 20", "amendment act", "ordinance", "passed by parliament")):
        return ("08", "Government Bills")
    # 03. Government Schemes
    if n in ("schemes", "scheme") or any(w in t for w in ("scheme", "yojana", "mission", "vettri payanam", "subhadra", "pradhan mantri")):
        return ("03", "Government Schemes")
    # 11. Defence
    if s == "security" or any(w in t for w in ("defence", "defense", "iaf", "squadron", "nuclear warhead", "nuclear triad", "missile", "exercise", "yudh abhyas", "hal", "drdo", "navy", "army")):
        return ("11", "Defence")
    # 13. International News
    if s == "ir" or any(w in t for w in ("russia", "ukraine", "ceasefire", "summit", "munich", "seychelles", "unsc", "united nations", "bilateral")):
        return ("13", "International News")
    # 01. Science & Technology
    if s in ("science_tech", "environment") or any(w in t for w in ("pathogen", "fungal", "candida", "isea", "antarctica", "bess", "battery storage", "ai security", "openai", "gpt", "protein", "lactoferrin", "isro", "nasa", "satellite")):
        return ("01", "Science & Technology")
    # 02. Reports & Rankings
    if any(w in t for w in ("index", "rank", "ranking", "bulletin of the atomic scientists", "report")):
        return ("02", "Reports & Rankings")
    # 10. Union Budget & Economy
    if s == "economy" or any(w in t for w in ("repo rate", "rbi", "gdp", "growth", "fpi", "fii", "inflation", "natural gas", "ppac", "hydropower", "sawalkot", "budget", "fiscal", "taxation")):
        return ("10", "Union Budget & Economy")
    # 12. National & State News
    return ("12", "National & State News")


SSC_CSS = """
:root{--rust:#bf4a07;--ink:#120f0b;--cream:#f8f6f2;--line:#e0dfdb;--mute:#6b6a67}
*{box-sizing:border-box}
body{margin:0;background:#fff;color:var(--ink);font:15px/1.5 "DM Sans",system-ui,Arial,sans-serif}
.page{max-width:820px;margin:0 auto;padding:0 20px 40px;border-top:3px solid var(--rust)}
.mono{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--mute)}
.meta{display:flex;justify-content:space-between;padding:10px 0}
.brand{text-align:center;padding:14px 0 6px}
.logo{display:inline-flex;align-items:center;gap:14px;text-align:left}
.word{font-family:"Playfair Display",Georgia,serif;font-weight:900;font-size:40px;letter-spacing:.14em;line-height:1}
.word b{color:var(--rust);font-weight:900}
.dev{font-family:"Noto Serif Devanagari",serif;font-weight:700;color:var(--rust);font-size:18px;line-height:1.2;margin-top:2px}
.pill{display:inline-block;background:var(--ink);color:#fff;font-family:"IBM Plex Mono",monospace;font-size:10.5px;letter-spacing:.16em;padding:6px 16px;border-radius:3px;margin:16px 0 12px}
h1{font:700 22px "Playfair Display",Georgia,serif;margin:0 0 16px}
.stats{display:flex;background:var(--cream);border:1px solid var(--line);border-radius:4px;margin-bottom:8px}
.stats div{flex:1;padding:10px 16px}.stats div+div{border-left:1px solid var(--line)}
.stats b{font:700 20px "Playfair Display",serif;display:block;line-height:1.2}
.stats .stats-mix{flex:2.2;display:flex;flex-direction:column;justify-content:space-between}
.mix-chips{display:flex;flex-wrap:wrap;gap:4px 6px;align-items:center;margin-bottom:4px}
.chip-mod{display:inline-flex;align-items:baseline;gap:3px;font-family:"IBM Plex Mono",monospace;font-size:10.5px;font-weight:600;color:var(--ink);background:#edebe6;border:1px solid #ddd9d0;padding:2px 6px;border-radius:3px;white-space:nowrap;line-height:1.3}
.chip-mod .chip-code{color:var(--rust);font-weight:700}
.chip-mod b{display:inline;font-family:"IBM Plex Mono",monospace;font-size:10.5px;font-weight:700;color:var(--rust)}
h2{display:flex;justify-content:space-between;align-items:baseline;font:700 26px "Playfair Display",Georgia,serif;margin:34px 0 4px;padding-bottom:0}
h2 small{font:500 10.5px "IBM Plex Mono",monospace;color:var(--mute);letter-spacing:.08em;text-transform:uppercase}
.mod{display:block;margin-top:30px;color:var(--rust)}
.mod+h2{margin-top:2px}
.list{border:1px solid var(--line);border-radius:4px;overflow:hidden;margin-top:10px}
.row{position:relative;padding:16px 18px 14px 58px;border-top:1px solid var(--line);break-inside:avoid}
.row:first-child{border-top:0}
.row h3{padding-right:30px;font:700 15.5px/1.4 "Playfair Display",Georgia,serif;margin:0 0 10px;color:#3a3732}
.row h3 i{position:absolute;left:14px;width:32px;text-align:right;font-style:normal;font-variant-numeric:tabular-nums;color:var(--rust)}
.ans{background:var(--cream);border-left:4px solid var(--rust);padding:10px 16px;font:900 24px/1.25 "Playfair Display",Georgia,serif;color:var(--ink);border-radius:0 4px 4px 0}
.more{margin-top:10px;display:grid;grid-template-columns:76px 1fr;row-gap:4px;align-items:baseline}
.more p{display:contents;margin:0}
.more p span{font:600 9px/1.6 "IBM Plex Mono",monospace;letter-spacing:.1em;text-transform:uppercase;color:#a9a7a2;white-space:nowrap}
.more p{font-size:12px;line-height:1.5;color:#8a8883}
sup{color:var(--rust);font-weight:700}
.note{margin-top:22px;font-size:12px;color:var(--mute);border-top:1px solid var(--line);padding-top:10px}
.cta{margin-top:26px;background:var(--cream);border:1px solid var(--line);border-left:3px solid var(--rust);border-radius:4px;padding:14px 18px;break-inside:avoid}
.cta b{font:700 17px "Playfair Display",serif;display:block}
.cta span{font-size:13px;color:#3a3732}
.foot{display:flex;justify-content:space-between;margin-top:22px;padding-top:10px;border-top:1px solid var(--line)}
.foot a{color:var(--rust);text-decoration:none}
@media(max-width:620px){.ans{font-size:20px}.word{font-size:26px}.meta,.foot{flex-direction:column;gap:2px}}
@page{size:A4;margin:11mm}
@media print{body{font-size:12.5px;-webkit-print-color-adjust:exact;print-color-adjust:exact}.page{max-width:none;padding:0 2px;border-top:3px solid var(--rust)}h2{break-after:avoid}.mod{break-after:avoid}.row{padding:10px 14px 9px 52px}.ans{font-size:19px;padding:7px 14px}}
.src{position:absolute;top:14px;right:14px;display:block;padding:2px 4px;font-size:15px;line-height:1;color:#b5b3ae;text-decoration:none}.src:hover{color:var(--rust);text-decoration:underline}.src[hidden]{display:none}
"""

SHORT_MODULE_NAMES = {
    "01": "Sci & Tech",
    "02": "Reports & Rankings",
    "03": "Govt Schemes",
    "04": "Appointments",
    "05": "Sports",
    "06": "Imp Days",
    "07": "Awards & Honours",
    "08": "Govt Bills",
    "09": "Books & Authors",
    "10": "Budget & Economy",
    "11": "Defence",
    "12": "National & State",
    "13": "International",
}


def ssc(p, items, total, lang="en"):
    # English-only SSC edition
    groups = {}
    for it in items:
        topic = _map_ssc_topic(it)
        groups.setdefault(topic, []).append(it)

    d = p["first"]
    date_str = f"{d.strftime('%A')}, {d.day} {d.strftime('%B %Y')}"
    h1_date = f"{d.day} {d.strftime('%B %Y')}"

    mix_chips = []
    for topic in sorted(groups.keys(), key=lambda x: x[0]):
        code, name = topic
        short = SHORT_MODULE_NAMES.get(code, name)
        count = len(groups[topic])
        mix_chips.append(f'<span class="chip-mod"><span class="chip-code">{code}</span> {e(short)} · <b>{count}</b></span>')
    mix_chips_html = "".join(mix_chips)

    topics_html = []
    q_counter = 1
    for topic in sorted(groups.keys(), key=lambda x: x[0]):
        code, topic_title = topic
        rows = []
        for it in groups[topic]:
            ssc_data = it.get("ssc_kit") or {}
            q_text = ssc_data.get("question_en")
            ans_text = ssc_data.get("answer_en")
            key_text = ssc_data.get("key_fact_en") or ""
            static_gk = ssc_data.get("static_gk_en") or ""

            if not (q_text and ans_text):
                k = kit_of(it, "en") or {}
                lead = (k.get("brief_lead") or it.get("title") or "").strip()
                why = (it.get("why") or it.get("why_in_news") or "").strip()
                if lead and why:
                    q_text = f"{lead}: {first_sentence(why, 120)}"
                elif lead:
                    q_text = f"Regarding {lead}, what is the key development?"
                else:
                    q_text = first_sentence(why, 120) or "What is the key development in this report?"
                ans_text = k.get("brief_text") or (it.get("fact_box") or "")[:50]
                key_text = it.get("fact_box") or ""
                static_gk = (it.get("pointers") or [{}])[0].get("text", "") if it.get("pointers") else ""

            src_url = f"https://satyadheesh.in/upsc/note/{it.get('id') or it.get('article_id')}"
            row_html = (
                f'<div class="row">'
                f'<h3><i>{q_counter}</i>{e(q_text)}</h3>'
                f'<div class="ans">{e(ans_text)}</div>'
                f'<div class="more">'
                f'<p><span>Key</span>{e(fit(key_text, 160))}</p>'
                f'<p><span>Static GK</span>{e(fit(static_gk, 160))}</p>'
                f'<a class="src" href="{src_url}" target="_blank" rel="noopener" title="Read note" aria-label="Read note">↗</a>'
                f'</div></div>'
            )
            rows.append(row_html)
            q_counter += 1

        sec = (
            f'<span class="mod mono">Module {code}</span>\n'
            f'<h2>{e(topic_title)} <small>{len(rows)} items</small></h2>\n'
            f'<div class="list">\n{"".join(rows)}\n</div>\n'
        )
        topics_html.append(sec)

    body = f"""
<div class="page">
<div class="meta mono"><span>Vol. I · SSC CGL One-Liner</span><span>{date_str}</span></div>

<div class="brand">
<div class="logo">
<svg width="46" height="46" viewBox="0 0 46 46" aria-hidden="true"><rect x="2" y="2" width="42" height="42" rx="10" fill="#f8f6f2" stroke="#120f0b" stroke-width="2.5"/><g transform="rotate(-35 23 21)"><rect x="12" y="17" width="14" height="10" rx="2" fill="#bf4a07"/><rect x="26" y="20" width="9" height="4" rx="2" fill="#bf4a07"/></g><rect x="11" y="34" width="24" height="3" rx="1.5" fill="#8e8d8b"/></svg>
<div><div class="word">SATYA<b>DHEESH</b></div><div class="dev">सत्याधीश</div></div>
</div>
<div><span class="pill">SSC CGL DAILY ONE-LINER REVISION</span></div>
<h1>Current Affairs · {h1_date}</h1>
</div>

<div class="stats">
<div><b>{len(items)}</b><span class="mono">Questions</span></div>
<div><b>{len(groups)}</b><span class="mono">Modules</span></div>
<div class="stats-mix">
<div class="mix-chips">{mix_chips_html}</div>
<span class="mono">Module Mix</span>
</div>
</div>

{"".join(topics_html)}

<div class="cta"><b>Get it every morning on Telegram</b><span>Daily PDF + quiz at 5 AM · weekly review every Sunday · English · free, no sign-up.</span></div>

<div class="foot mono"><span>Satyadheesh · SSC CGL Daily One-Liner · {h1_date}</span><span>satyadheesh.in/upsc · <a href="https://t.me/satyadheesh">t.me/satyadheesh</a></span></div>
</div>
"""
    title = f"Satyadheesh · SSC CGL Daily One-Liner · {h1_date}"
    return (
        f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{e(title)}</title>'
        f'<link rel="stylesheet" href="base.css">'
        f'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=IBM+Plex+Mono:wght@500;600&family=Noto+Serif+Devanagari:wght@700&family=Playfair+Display:wght@700;900&display=swap">'
        f'<style>{SSC_CSS}</style>'
        f'</head><body>{body}</body></html>'
    )

