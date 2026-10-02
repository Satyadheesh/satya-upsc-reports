"""HTML for the Brief and Detailed editions (printed to PDF by Chromium in reports/build.py).
Design: the dummies approved on 2 Oct 2026 (masthead, top stories, cards, In brief, quiz)."""
import datetime as dt
import html
import re

import qrcode
import qrcode.image.svg

from common.syllabus import SYLLABUS

SITE = "https://satyadheesh.in"
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
        cta1="Read it in <i>Hindi</i>, or get tomorrow’s brief", cta2="Free · no sign-up · new edition every morning, weekly review every Sunday.",
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
        cta1="<i>English</i> में पढ़ें, या कल का सार पाएँ", cta2="मुफ़्त · बिना साइन-अप · हर सुबह नया अंक, हर रविवार साप्ताहिक।",
        disc="नोट्स सत्याधीश के समाचार फ़ीड से स्वचालित रूप से बनाए जाते हैं और यूपीएससी सीएसई पाठ्यक्रम से जुड़े हैं। उत्तर में उपयोग से पहले तथ्यों का मूल रिपोर्ट या पीआईबी से मिलान करें।",
        inside_b="<span><b>पृ.2</b> मुख्य ख़बरें</span><span><b>»</b> संक्षेप में</span><span><b>»</b> अभ्यास</span><span style=\"margin-left:auto\">P = प्रीलिम्स · M = मेन्स</span>",
        contents="विषय सूची", contents_h="सभी नोट्स, पेपर के अनुसार", how_k="हर नोट में",
        how="चर्चा में क्यों → याद रखने योग्य तथ्य → कीवर्ड के साथ मेन्स प्रश्न। एक ही ख़बर की रिपोर्टें जोड़ दी गई हैं।",
        short_k="समय कम है?", short="5 पेज के <b>सार</b> में सबसे ज़रूरी ख़बरें और अभ्यास प्रश्न हैं।",
        why_d="चर्चा में क्यों", mq="मेन्स प्रश्न", reports_merged="{n} रिपोर्टें जोड़ी गईं", practice="अभ्यास", mcqs="MCQ",
        ptot="{n} नोट्स"),
}
SIZE = {  # per edition kind: top, cards, in-brief lines, mcqs, mains
    "daily": (5, 8, 30, 5, 1), "weekly": (6, 10, 40, 8, 2), "monthly": (6, 12, 60, 10, 3)}


def e(s):
    return html.escape(str(s or ""), quote=False)


def clip(s, n):
    s = " ".join(str(s or "").split())
    if len(s) <= n:
        return s
    cut = s.rfind(" ", 0, n - 1)
    return s[: cut if cut > n * 0.6 else n - 1].rstrip(" ,;:") + "…"


def first_sentence(s, n=150):
    s = " ".join(str(s or "").split())
    m = re.search(r"(?<=[.।!?])\s", s)
    return clip(s[: m.start()] if m and m.start() <= n else s, n)


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
    left = (t["vol_brief"].format(kind=kind) if edition == "brief" else t["vol_detailed"])
    if p["kind"] == "daily":
        d = p["first"]
        right = f"{DAYS_HI[d.weekday()]}, {date_label(d, True)}" if hi else d.strftime("%A, ") + date_label(d, False)
    else:
        right = period_label(p, hi)
    product = (t["brief"] if edition == "brief" else t["detailed"]).format(kind=kind)
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
    t = T[lang]
    url = f"{SITE}/upsc/reports" + ("" if lang == "hi" else "?lang=hi")
    return (f'<div class="cta">{qr_svg(url)}<div><div class="t1">{t["cta1"]}</div><div class="t2">{e(t["cta2"])}</div>'
            f'<div class="t3">satyadheesh.in/upsc/reports</div></div></div><p class="disc">{e(t["disc"])}</p>')


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


def kit_facts(it, lang, n=3):
    """Facts to remember: study-kit facts (English) or the note's own pointers."""
    if lang == "en" and it.get("kit") and it["kit"].get("facts"):
        return [f["text"] for f in it["kit"]["facts"][:n]]
    return [p["text"] for p in it["pointers"][:n]]


def doc(lang, title, body):
    return (f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><title>{e(title)}</title>'
            f'<link rel="stylesheet" href="base.css"></head><body>{body}</body></html>')


# ---------------------------------------------------------------- Brief

def brief(p, items, total, lang):
    """items: the chosen notes, best first. Returns (html, n_items)."""
    t, hi = T[lang], lang == "hi"
    n_top, n_cards, n_lines, n_mcq, n_mains = SIZE[p["kind"]]
    kit = (lambda it: it.get("kit") if not hi else None)
    top, cards = items[:n_top], items[:n_cards]
    rest = items[n_cards:n_cards + n_lines]
    mcqs = [it["kit"]["mcq"] for it in items if not hi and it.get("kit") and it["kit"].get("mcq")][:n_mcq]
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
        for f in ((kit(it) or {}).get("facts") or []):
            name, rest_t = split_fact(f["text"])
            if f["label"] == "Figure" and name and len(name) <= 18 and re.search(r"\d", name):
                figures.append((name, rest_t, it))
            if static is None and f["label"] in ("Case", "Act") and name:
                static = (name, rest_t, it)
    boxes = ""
    if p["kind"] == "daily" and (figures or static):
        num = (f'<div class="box cream"><div class="kicker">{e(t["number"])}</div><div class="bignum">{e(figures[0][0])}</div>'
               f'<p>{e(clip(figures[0][1], 150))}</p></div>') if figures else ""
        st = (f'<div class="box line"><div class="kicker">{e(t["static"])}</div><h4>{e(static[0])}</h4>'
              f'<p>{e(clip(static[1], 120))} <i>In the news: {e(short_title(static[2]))}.</i></p></div>') if static else ""
        boxes = f'<div class="duo" style="grid-template-columns:{"1fr 1.25fr" if num and st else "1fr"}">{num}{st}</div>'
    elif p["kind"] != "daily" and len(figures) >= 3:
        tiles = "".join(f'<div class="tile"><div class="v">{e(v)}</div><div class="c">{e(clip(c, 90))}</div></div>' for v, c, _ in figures[:4])
        boxes = (f'<div class="kicker">{e(t["number_w"])}</div><div class="tiles" style="grid-template-columns:repeat({min(4, len(figures))},1fr)">{tiles}</div>')
    p1 += boxes + f'<div class="inside">{t["inside_b"]}</div>'

    def card(it):
        k = kit(it) or {}
        rem = "".join(f"<li>{e(clip(x, 170))}</li>" for x in kit_facts(it, lang))
        kw = "".join(f"<span>{e(x)}</span>" for x in it["keywords"][:4]) if not hi else ""
        angle = (f'<div class="angle"><div class="q"><b>{e(t["angle"])}</b>{e(clip(it["mains"], 220))}</div>'
                 + (f'<div class="kw"><em>{e(t["use"])}</em>{kw}</div>' if kw else "")
                 + f'<div class="more">{e(t["full"])} satyadheesh.in/news/{it["id"]}</div></div>') if it.get("mains") else \
            f'<div class="angle"><div class="more">{e(t["full"])} satyadheesh.in/news/{it["id"]}</div></div>'
        return (f'<article class="card"><div class="in"><div class="chips">{chip(it["paper"], subject_name(it["subject"], hi))}'
                f'{exam_chips(it["exam"])}</div><h3>{e(k.get("short_title") or it["title"])}</h3>'
                f'<p class="why"><b>{e(t["why"])}</b> {e(clip(it["why"], 260))}</p>'
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
                    li.append(f'<li>{e(clip(it["title"], 150))}</li>')
            groups.append(f'<div class="grp">{chip(paper, (PAPER_HINT[paper][1] if hi else PAPER_HINT[paper][0]))}<ul>{"".join(li)}</ul></div>')
        places, seen = [], set()
        for it in items:
            for f in ((kit(it) or {}).get("facts") or []):
                name, desc = split_fact(f["text"])
                if f["label"] == "Place" and name and name.lower() not in seen and len(places) < 6:
                    seen.add(name.lower())
                    places.append(f'<tr><td>{e(name)}</td><td>{e(clip(desc, 140))}</td></tr>')
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
    mcqs = [it["kit"]["mcq"] for it in items if not hi and it.get("kit") and it["kit"].get("mcq")][:10]
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
        if not hi and it.get("kit") and it["kit"].get("facts"):
            facts = [(f["label"], f["text"]) for f in it["kit"]["facts"]]
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
                f'<h4>{e(it["title"])}</h4><p class="why"><b>{e(t["why_d"])}</b>{e(it["why"])}</p><dl class="facts">{dl}</dl>{mq}</article>')

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
