"""Newspaper-style HTML for one paper's last 24 hours (printed to PDF by paper/build.py with Chromium).

Our own masthead (SATYADHEESH), never the paper's: the stories are our rewritten summaries of that paper's reports,
credited and linked to the original. No publisher photos are reproduced."""
import datetime as dt
import html
import re

from .data import SECTIONS

MONTHS_HI = ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"]
DAYS_HI = ["सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार"]
FRONT = 7          # stories on the front page (1 lead + 6)
BOLD = re.compile(r"\*\*(.+?)\*\*")


def e(s):
    return html.escape(str(s or ""), quote=True)


def md(s):
    """Our summaries use **bold** for names: keep that, drop other markdown, split into paragraphs."""
    s = e(s)
    s = BOLD.sub(r"<b>\1</b>", s).replace("__", "").replace("`", "")
    paras = [p.strip() for p in re.split(r"\n\s*\n|\n", s) if p.strip()]
    return "".join(f"<p>{p}</p>" for p in paras)


def date_line(d, hi):
    if hi:
        return f"{DAYS_HI[d.weekday()]}, {d.day} {MONTHS_HI[d.month - 1]} {d.year}"
    return d.strftime("%A, %-d %B %Y").upper()


def story(it, hi, cls="", paper_name=""):
    t = it["title_hi"] if hi else it["title"]
    b = it["body_hi"] if hi else it["body"]
    src = (f'<a class="src" href="{e(it["url"])}">{"मूल रिपोर्ट" if hi else "Original report"}: {e(paper_name)} ↗</a>'
           if it.get("url") else "")
    return f'<article class="st {cls}"><h3>{e(t)}</h3>{md(b)}{src}</article>'


KICK = {"politics": ("Politics", "राजनीति"), "regional": ("States", "राज्य"), "crime": ("Law & Order", "क़ानून-व्यवस्था"),
        "economy": ("Business", "कारोबार"), "international": ("World", "दुनिया"), "education": ("Education", "शिक्षा"),
        "health": ("Health", "स्वास्थ्य"), "environment": ("Environment", "पर्यावरण"), "sports": ("Sport", "खेल")}


def kick(it, hi):
    en, h = KICK.get(it["category"], ("News", "ख़बर"))
    return h if hi else en


def section_of(it):
    for key, en, hi, cats in SECTIONS:
        if cats is None or it["category"] in cats:
            return key
    return "more"


def render(paper, paper_hi, items, lang, day, total_all=None):
    """paper: 'The Hindu'; items: best first (paper.data.edition); day: dt.date of the edition."""
    hi = lang == "hi"
    name = paper_hi if hi else paper
    front, rest = items[:FRONT], items[FRONT:]
    groups = {k: [] for k, *_ in SECTIONS}
    for it in rest:
        groups[section_of(it)].append(it)
    sec_names = {k: (h if hi else en) for k, en, h, _ in SECTIONS}

    inside = " · ".join(f"{sec_names[k]} {len(v)}" for k, v in groups.items() if v)
    lead = front[0] if front else None
    seconds = front[1:]

    mast = "सत्याधीश" if hi else "SATYADHEESH"
    ear_l = (f"<b>{e(name)}</b> संस्करण<br>पिछले 24 घंटे की ख़बरें, संक्षेप में" if hi else
             f"<b>{e(name)}</b> edition<br>The last 24 hours, in brief")
    ear_r = ("मुफ़्त · रोज़ सुबह<br><b>t.me/satyadheesh</b>" if hi else "Free · every morning<br><b>t.me/satyadheesh</b>")
    note = (f"ये ख़बरें {e(name)} में पिछले 24 घंटे में छपी रिपोर्टों का सत्याधीश द्वारा लिखा संक्षिप्त सार हैं। "
            f"सत्याधीश का {e(name)} से कोई संबंध नहीं है; पूरी रिपोर्ट के लिए हर ख़बर के नीचे दिया लिंक देखें।"
            if hi else
            f"Summaries written by SatyaDheesh from reports published by {e(name)} in the last 24 hours. "
            f"SatyaDheesh is not affiliated with {e(name)}; each story links to the full original report.")

    parts = [f'''<header class="mast">
  <div class="topline"><span>{"अंक" if hi else "VOL. I · NO."} {day.timetuple().tm_yday}</span>
    <span>{date_line(day, hi)}</span><span>{len(items)} {"ख़बरें" if hi else "STORIES"}</span></div>
  <div class="row"><div class="ear">{ear_l}</div><h1 class="{'hi' if hi else ''}">{mast}</h1><div class="ear r">{ear_r}</div></div>
  <div class="inside"><b>{"अंदर" if hi else "INSIDE"}</b> {e(inside)}</div>
</header>''']
    if lead:
        lt = lead["title_hi"] if hi else lead["title"]
        lb = lead["body_hi"] if hi else lead["body"]
        src = (f'<a class="src" href="{e(lead["url"])}">{"मूल रिपोर्ट" if hi else "Original report"}: {e(name)} ↗</a>'
               if lead.get("url") else "")
        parts.append(f'<section class="lead"><div class="kick">{e(kick(lead, hi))}</div>'
                     f'<h2>{e(lt)}</h2><div class="lead-body">{md(lb)}{src}</div></section>')
    if seconds:
        parts.append('<section class="seconds">' + "".join(
            f'<div class="sec2"><div class="kick">{e(kick(it, hi))}</div>{story(it, hi, "", name)}</div>'
            for it in seconds) + '</section>')
    parts.append(f'<p class="note">{note}</p>')
    for k, *_ in SECTIONS:
        if not groups[k]:
            continue
        parts.append(f'<section class="sect"><h4 class="bar"><span>{e(sec_names[k])}</span></h4>'
                     f'<div class="cols">{"".join(story(it, hi, "", name) for it in groups[k])}</div></section>')

    title = f"{name} — {date_line(day, hi)}"
    return f'''<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><title>{e(title)}</title>
<style>{FONTS}{CSS}</style></head>
<body class="{'hi' if hi else 'en'}">{"".join(parts)}</body></html>'''


CSS = r"""
@page { size: A4; margin: 11mm 10mm 13mm; }
html, body { background: #fbf9f4; }
body { margin: 0; color: #141210; font: 9.1pt/1.38 'Source Serif 4', 'Deva', Georgia, serif; }
body.hi { font: 9.4pt/1.6 'Deva', 'Source Serif 4', sans-serif; }
b { font-weight: 600; }
.mast { border-bottom: 3px double #141210; margin-bottom: 4mm; }
.topline { display: flex; justify-content: space-between; font: 600 7pt 'Plex Mono', 'Deva', monospace; letter-spacing: .12em;
  border-bottom: 1px solid #141210; padding-bottom: 1.2mm; }
.row { display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; padding: 2.5mm 0 1.5mm; }
.mast h1 { margin: 0 4mm; font: 900 40pt/1 'Playfair Display', serif; letter-spacing: .01em; text-align: center; }
.mast h1.hi { font: 800 44pt/1.15 'Deva Serif', serif; letter-spacing: 0; }
.ear { font: 7.4pt/1.35 'DM Sans', 'Deva', sans-serif; color: #3d3833; border: 1px solid #141210; padding: 1.6mm 2.2mm;
  justify-self: start; max-width: 38mm; }
.ear.r { justify-self: end; text-align: right; }
.ear b { color: #bf4a07; }
.inside { border-top: 1px solid #141210; padding: 1.2mm 0 1.4mm; font: 7.2pt 'DM Sans', 'Deva', sans-serif;
  text-align: center; color: #3d3833; }
.inside b { letter-spacing: .14em; margin-right: 2mm; color: #141210; }
.kick { font: 700 6.8pt 'DM Sans', 'Deva', sans-serif; letter-spacing: .16em; text-transform: uppercase; color: #bf4a07;
  margin-bottom: .8mm; }
.lead { border-bottom: 1px solid #141210; padding-bottom: 3mm; margin-bottom: 3mm; }
.lead h2 { font: 900 25pt/1.08 'Playfair Display', 'Deva Serif', serif; margin: 0 0 2.4mm; }
.hi .lead h2 { font: 800 21pt/1.3 'Deva Serif', serif; }
.lead-body { columns: 3; column-gap: 6mm; column-rule: .5pt solid #cfc7ba; font-size: 10pt; }
.lead-body p:first-child::first-letter { float: left; font: 900 30pt/0.85 'Playfair Display', serif; padding: 1mm 1.5mm 0 0; }
.hi .lead-body p:first-child::first-letter { float: none; font: inherit; padding: 0; }
.seconds { columns: 3; column-gap: 6mm; column-rule: .5pt solid #cfc7ba; border-bottom: 1px solid #141210;
  padding-bottom: 1mm; }
.sec2 { break-inside: avoid; border-bottom: .5pt solid #e1dacd; margin-bottom: 2.5mm; }
.seconds h3 { font: 700 12.5pt/1.15 'Playfair Display', 'Deva Serif', serif; }
.hi .seconds h3 { font: 700 11.5pt/1.4 'Deva Serif', serif; }
.st { break-inside: avoid; margin: 0 0 3mm; }
.st h3 { margin: 0 0 1.1mm; font: 700 10.6pt/1.18 'Playfair Display', 'Deva Serif', serif; }
.hi .st h3 { font: 700 10.2pt/1.45 'Deva Serif', serif; }
.st p, .lead p { margin: 0 0 1.2mm; text-align: left; }
.hi .st p, .hi .lead p { text-align: left; }
.src { display: block; font: 6.4pt 'Plex Mono', 'Deva', monospace; color: #857d75; text-decoration: none; letter-spacing: .03em; }
.note { font: italic 7pt/1.4 'Source Serif 4', 'Deva', serif; color: #6b645c; margin: 1.5mm 0 3mm; text-align: center; }
.sect { margin-top: 2mm; }
.bar { margin: 0 0 2.5mm; border-top: 2.5px solid #141210; border-bottom: .5pt solid #141210; padding: 1mm 0;
  font: 900 13pt 'Playfair Display', 'Deva Serif', serif; letter-spacing: .04em; text-transform: uppercase;
  break-after: avoid; }
.hi .bar { font: 800 12.5pt 'Deva Serif', serif; letter-spacing: 0; }
.cols { columns: 3; column-gap: 6mm; column-rule: .5pt solid #cfc7ba; }
.cols .st { border-bottom: .5pt solid #e1dacd; padding-bottom: 2mm; }
"""


def _fonts():
    import pathlib
    css = (pathlib.Path(__file__).parent.parent / "reports" / "base.css").read_text(encoding="utf-8")
    return "\n".join(l for l in css.split(":root")[0].splitlines() if l.strip())


FONTS = _fonts()
