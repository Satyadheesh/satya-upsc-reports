"""Broadsheet-style HTML for one paper's last 24 hours, printed to PDF by paper/build.py with Chromium.

A personal reading copy (Yash, 24 Oct 2026: the channels are private, for him only; paper/post.py refuses to post to a
public channel). English editions use the original reports and photos; Hindi editions use our Hindi write-ups (there
is no original Hindi text)."""
import datetime as dt
import html
import re

from .data import SECTIONS, image_variant

MONTHS_HI = ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"]
DAYS_HI = ["सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार"]
BOLD = re.compile(r"\*\*(.+?)\*\*")
KICK = {"politics": ("Politics", "राजनीति"), "regional": ("States", "राज्य"), "crime": ("Law & Order", "क़ानून-व्यवस्था"),
        "economy": ("Business", "कारोबार"), "international": ("World", "दुनिया"), "education": ("Education", "शिक्षा"),
        "health": ("Health", "स्वास्थ्य"), "environment": ("Environment", "पर्यावरण"), "sports": ("Sport", "खेल")}
N_BRIEFS = 12
PHOTOS_PER_SECTION = 4


def e(s):
    return html.escape(str(s or ""), quote=True)


def inline(s):
    return BOLD.sub(r"<b>\1</b>", e(s)).replace("__", "").replace("`", "")


def kick(it, hi):
    en, h = KICK.get(it["category"], ("News", "ख़बर"))
    return h if hi else en


def section_of(it):
    for key, en, hi, cats in SECTIONS:
        if cats is None or it["category"] in cats:
            return key
    return "more"


def date_line(d, hi):
    return f"{DAYS_HI[d.weekday()]}, {d.day} {MONTHS_HI[d.month - 1]} {d.year}" if hi else d.strftime("%A, %B %-d, %Y")


def title_of(it, hi):
    return it["title_hi"] if hi else (it.get("orig_title") or it["title"])


def paras_of(it, hi):
    if hi:
        return [p.strip() for p in re.split(r"\n+", it["body_hi"]) if p.strip()]
    return it.get("orig") or [p.strip() for p in re.split(r"\n+", it["body"]) if p.strip()]


def take(paras, limit):
    """Paragraphs up to about `limit` characters: (taken, rest)."""
    out, n = [], 0
    for i, p in enumerate(paras):
        if out and n + len(p) > limit:
            return out, paras[i:]
        out.append(p); n += len(p)
    return out, []


def ps(paras, first=False):
    return "".join(f'<p{" class=first" if first and i == 0 else ""}>{inline(p)}</p>' for i, p in enumerate(paras))


def has_photo(it):
    return bool(it.get("image_data"))


def fig(it, wide=False, cls=""):
    data = it.get("image_data")
    return f'<figure class="{cls}"><img src="{data}"></figure>' if data else ""


def story(it, hi, photo=False, tag=""):
    t = f'<div class="tag">{e(tag)}</div>' if tag else ""
    return (f'<article class="st">{t}<h3>{e(title_of(it, hi))}</h3>{fig(it) if photo else ""}'
            f'{ps(paras_of(it, hi), True)}</article>')


def render(paper, paper_hi, items, lang, day, total_all=None):
    hi = lang == "hi"
    name = paper_hi if hi else {"Times of India": "The Times of India", "Economic Times": "The Economic Times",
                                 "Indian Express": "The Indian Express"}.get(paper, paper)
    sec_names = {k: (h if hi else en) for k, en, h, _ in SECTIONS}
    with_img = [i for i in items if has_photo(i)]
    lead = (with_img or items)[0]
    seconds = [i for i in with_img if i is not lead][:2]
    briefs = [i for i in items if i is not lead and i not in seconds][:N_BRIEFS]
    groups = {k: [] for k, *_ in SECTIONS}
    for it in items:
        groups[section_of(it)].append(it)
    front_ids = {lead["id"]} | {i["id"] for i in seconds}
    inside = " · ".join(f"{sec_names[k]}" for k, v in groups.items() if v)
    cont = "पूरी ख़बर अंदर" if hi else "Full story inside"

    lead_paras = paras_of(lead, hi)
    l1, rest = take(lead_paras, 700)
    l2, rest2 = take(rest, 1500)

    p = []
    p.append(f'''<header class="mast">
 <div class="strip"><span>{"निजी प्रति · वितरण के लिए नहीं" if hi else "PERSONAL COPY · NOT FOR DISTRIBUTION"}</span>
  <span>{e(date_line(day, hi)).upper() if not hi else e(date_line(day, hi))}</span><span>{len(items)} {"ख़बरें" if hi else "STORIES"}</span></div>
 <h1 class="{'hi' if hi else ''}">{e(name)}</h1>
 <div class="strip2"><span>{"पिछले 24 घंटे" if hi else "The last 24 hours"}</span><span><b>{"अंदर" if hi else "INSIDE"}</b> {e(inside)}</span>
  <span>{"सत्याधीश द्वारा संकलित" if hi else "Compiled by SatyaDheesh"}</span></div>
</header>''')
    p.append(f'''<section class="flead"><div class="kick">{e(kick(lead, hi))}</div><h2>{e(title_of(lead, hi))}</h2>
 <div class="fgrid">{fig(lead, True, "big")}<div class="ftext">{ps(l1, True)}</div></div>
 <div class="cols c5">{ps(l2)}{f'<p class="jump">{cont}: {e(sec_names[section_of(lead)])} →</p>' if rest2 else ""}</div></section>''')
    sec_html = "".join(
        f'<article class="fsec"><div class="kick">{e(kick(it, hi))}</div><h3>{e(title_of(it, hi))}</h3>{fig(it)}'
        f'<div class="cols c2">{ps(take(paras_of(it, hi), 900)[0], True)}'
        f'<p class="jump">{cont}: {e(sec_names[section_of(it)])} →</p></div></article>' for it in seconds)
    brief_html = "".join(
        f'<div class="brief"><h4>{e(title_of(it, hi))}</h4><p>{inline(take(paras_of(it, hi), 160)[0][0])}</p></div>'
        for it in briefs if paras_of(it, hi))
    p.append(f'<div class="frow"><div class="fmain">{sec_html}</div><aside class="rail"><div class="railh">'
             f'{"संक्षेप में" if hi else "IN BRIEF"}</div>{brief_html}</aside></div>')

    for k, *_ in SECTIONS:
        its = groups[k]
        if not its:
            continue
        big = len(its) >= 8
        slead = next((i for i in its if has_photo(i) and i["id"] not in front_ids), its[0])
        others = [i for i in its if i is not slead]
        s1, srest = take(paras_of(slead, hi), 650)
        tag = ("पहले पन्ने से" if hi else "From Page 1") if slead["id"] in front_ids else ""
        cols = []
        if srest:
            cols.append(f'<article class="st cont"><div class="tag">{e(title_of(slead, hi))[:60]}… '
                        f'{"(जारी)" if hi else "(continued)"}</div>{ps(srest)}</article>')
        n_ph = 0
        for it in others:
            ph = has_photo(it) and n_ph < PHOTOS_PER_SECTION and len(paras_of(it, hi)) > 1
            n_ph += ph
            cols.append(story(it, hi, ph, ("पहले पन्ने से" if hi else "From Page 1") if it["id"] in front_ids else ""))
        p.append(f'''<section class="sec{' newpage' if big else ''}">
 <div class="sbar"><span>{e(sec_names[k])}</span><span class="sdate">{e(name)} · {e(date_line(day, hi))}</span></div>
 <div class="slead">{f'<div class="tag">{e(tag)}</div>' if tag else ""}<h2>{e(title_of(slead, hi))}</h2>
  <div class="sgrid">{fig(slead, True, "big")}<div class="ftext">{ps(s1, True)}</div></div></div>
 <div class="cols c5">{"".join(cols)}</div></section>''')

    return f'''<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><title>{e(name)} — {e(date_line(day, hi))}</title>
<style>{FONTS}{CSS}</style></head><body class="{'hi' if hi else 'en'}">{"".join(p)}</body></html>'''


CSS = r"""
@page { size: 315mm 470mm; margin: 12mm 11mm 14mm; }
html, body { background: #f7f3ea; }
body { margin: 0; color: #111; font: 9.4pt/1.34 'Source Serif 4', 'Deva', Georgia, serif; }
body.hi { font: 10pt/1.6 'Deva', 'Source Serif 4', sans-serif; }
b { font-weight: 600; }
p { margin: 0 0 1.4mm; text-align: justify; text-indent: 3.5mm; }
p.first, .ftext p:first-child { text-indent: 0; }
.hi p { text-align: left; }
.mast { text-align: center; margin-bottom: 3mm; }
.strip, .strip2 { display: flex; justify-content: space-between; font: 600 7.4pt 'Plex Mono', 'Deva', monospace;
  letter-spacing: .1em; padding: 1.2mm 0; }
.strip { border-bottom: 1px solid #111; }
.mast h1 { margin: 2mm 0 1.5mm; font: 900 76pt/1 'Playfair Display', serif; letter-spacing: -.01em; }
.mast h1.hi { font: 800 66pt/1.2 'Deva Serif', serif; }
.strip2 { border-top: 3px double #111; border-bottom: 1.5px solid #111; font: 7.6pt 'DM Sans', 'Deva', sans-serif; letter-spacing: .04em; }
.strip2 b { letter-spacing: .14em; margin-right: 1.5mm; }
.kick { font: 700 7.4pt 'DM Sans', 'Deva', sans-serif; letter-spacing: .18em; text-transform: uppercase; color: #9b1c1c; margin-bottom: 1mm; }
.tag { font: 700 6.8pt 'DM Sans', 'Deva', sans-serif; letter-spacing: .12em; text-transform: uppercase; color: #6b645c; margin-bottom: .8mm; }
.flead h2 { font: 900 40pt/1.04 'Playfair Display', 'Deva Serif', serif; margin: 0 0 3mm; letter-spacing: -.01em; }
.hi .flead h2 { font: 800 32pt/1.3 'Deva Serif', serif; }
.fgrid, .sgrid { display: grid; grid-template-columns: 3fr 2fr; gap: 6mm; margin-bottom: 3mm; }
figure { margin: 0 0 2mm; }
figure img { width: 100%; display: block; }
figure.big img { max-height: 120mm; object-fit: cover; }
.ftext { font-size: 11pt; line-height: 1.42; }
.ftext p.first::first-letter, .flead .ftext p:first-child::first-letter { float: left; font: 900 38pt/.82 'Playfair Display', serif; padding: 1.2mm 1.6mm 0 0; }
.hi .ftext p:first-child::first-letter { float: none; font: inherit; padding: 0; }
.cols { column-gap: 5.5mm; column-rule: .5pt solid #b9b0a1; }
.c5 { columns: 5; } .c2 { columns: 2; }
.flead { border-bottom: 2px solid #111; padding-bottom: 2mm; margin-bottom: 3mm; }
.jump { font: italic 600 8pt 'Source Serif 4', 'Deva', serif; text-indent: 0; color: #9b1c1c; }
.frow { display: grid; grid-template-columns: 4fr 1.15fr; gap: 6mm; break-after: page; }
.fmain { display: grid; grid-template-columns: 1fr 1fr; gap: 6mm; }
.fsec h3 { font: 700 19pt/1.12 'Playfair Display', 'Deva Serif', serif; margin: 0 0 2mm; }
.hi .fsec h3 { font: 700 15pt/1.4 'Deva Serif', serif; }
.rail { border-left: 1px solid #111; padding-left: 4mm; }
.railh { font: 900 13pt 'Playfair Display', 'Deva Serif', serif; border-bottom: 2px solid #111; margin-bottom: 2mm; letter-spacing: .06em; }
.brief { border-bottom: .5pt solid #b9b0a1; padding-bottom: 1.6mm; margin-bottom: 1.8mm; }
.brief h4 { font: 700 9.6pt/1.2 'Source Serif 4', 'Deva Serif', serif; margin: 0 0 .6mm; }
.brief p { font-size: 8.4pt; text-indent: 0; margin: 0; }
.sec { margin-bottom: 4mm; }
.sec.newpage { break-before: page; }
.sbar { display: flex; justify-content: space-between; align-items: baseline; border-top: 4px solid #111;
  border-bottom: 1px solid #111; padding: 1mm 0; margin-bottom: 3mm; }
.sbar span:first-child { font: 900 22pt 'Playfair Display', 'Deva Serif', serif; text-transform: uppercase; letter-spacing: .03em; }
.hi .sbar span:first-child { font: 800 20pt 'Deva Serif', serif; }
.sdate { font: 600 7.4pt 'Plex Mono', 'Deva', monospace; letter-spacing: .08em; color: #555; }
.slead { border-bottom: 1px solid #111; margin-bottom: 3mm; }
.slead h2 { font: 800 28pt/1.08 'Playfair Display', 'Deva Serif', serif; margin: 0 0 2.5mm; }
.hi .slead h2 { font: 800 22pt/1.35 'Deva Serif', serif; }
.st { margin: 0 0 3mm; padding-bottom: 2mm; border-bottom: .5pt solid #b9b0a1; }
.st h3 { font: 700 13pt/1.13 'Source Serif 4', 'Deva Serif', serif; margin: 0 0 1.4mm; break-after: avoid; }
.hi .st h3 { font: 700 11.5pt/1.45 'Deva Serif', serif; }
.st figure { break-inside: avoid; }

"""


def _fonts():
    import pathlib
    css = (pathlib.Path(__file__).parent.parent / "reports" / "base.css").read_text(encoding="utf-8")
    return "\n".join(l for l in css.split(":root")[0].splitlines() if l.strip())


FONTS = _fonts()
