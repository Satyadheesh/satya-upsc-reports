"""Page-designed newspaper (v3, 24 Oct 2026). Every page is a fixed Berliner page with slots (CSS grid); stories are
placed into slots, photo stories get the big slots, text-only stories become briefs, and fitAll() (run by
paper/build.py before printing) trims each story at a sentence end so nothing spills onto another page.

A personal reading copy (Yash, 24 Oct 2026): English editions use the original reports and photos, Hindi editions our
Hindi write-ups; paper/post.py posts only to private channels."""
import html
import re

from .data import image_variant  # noqa: F401  (kept for callers)

MONTHS_HI = ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"]
DAYS_HI = ["सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार"]
BOLD = re.compile(r"\*\*(.+?)\*\*")

# Sections in print order: (key, English, Hindi, categories, max pages)
SECTIONS = [
    ("nation", "Nation", "देश", {"politics"}, 3),
    ("states", "States", "राज्य", {"regional"}, 2),
    ("law", "Law & Order", "क़ानून-व्यवस्था", {"crime"}, 2),
    ("business", "Business", "कारोबार", {"economy"}, 2),
    ("world", "World", "दुनिया", {"international"}, 2),
    ("society", "Health, Education & Environment", "स्वास्थ्य, शिक्षा और पर्यावरण", {"education", "health", "environment"}, 2),
    ("sport", "Sport", "खेल", {"sports"}, 1),
    ("more", "More News", "और ख़बरें", None, 1),
]
KICK = {"politics": ("Politics", "राजनीति"), "regional": ("States", "राज्य"), "crime": ("Law & Order", "क़ानून-व्यवस्था"),
        "economy": ("Business", "कारोबार"), "international": ("World", "दुनिया"), "education": ("Education", "शिक्षा"),
        "health": ("Health", "स्वास्थ्य"), "environment": ("Environment", "पर्यावरण"), "sports": ("Sport", "खेल")}
BRIEFS_FRONT, BRIEFS_PAGE = 7, 6


def e(s):
    return html.escape(str(s or ""), quote=True)


def inline(s):
    return BOLD.sub(r"<b>\1</b>", e(s)).replace("__", "").replace("`", "")


def kick(it, hi):
    en, h = KICK.get(it["category"], ("News", "ख़बर"))
    return h if hi else en


def date_line(d, hi):
    return f"{DAYS_HI[d.weekday()]}, {d.day} {MONTHS_HI[d.month - 1]} {d.year}" if hi else d.strftime("%A, %B %-d, %Y")


def title_of(it, hi):
    return it["title_hi"] if hi else (it.get("orig_title") or it["title"])


def paras_of(it, hi):
    if hi:
        return [p.strip() for p in re.split(r"\n+", it["body_hi"]) if p.strip()]
    return it.get("orig") or [p.strip() for p in re.split(r"\n+", it["body"]) if p.strip()]


def first_sentence(p, n=170):
    m = re.match(r"(.{40,%d}?[.!?।])\s" % n, p + " ")
    return m.group(1) if m else (p[:n].rsplit(" ", 1)[0] + "…" if len(p) > n else p)


def length(it, hi):
    return sum(len(p) for p in paras_of(it, hi))


def photo(it):
    return bool(it.get("image_data"))


# ---------------------------------------------------------------- blocks

def fig(it):
    return f'<figure><img src="{it["image_data"]}"></figure>' if photo(it) else ""


def body(it, hi, cols=1):
    ps = "".join(f"<p>{inline(p)}</p>" for p in paras_of(it, hi))
    more = "पूरी ख़बर: मूल रिपोर्ट" if hi else "Full report online"
    link = f'<a class="more" href="{e(it.get("url"))}">{more} ›</a>' if it.get("url") else ""
    return f'<div class="txt c{cols}" data-fit>{ps}</div>{link}'


def story(it, hi, cls, cols=1, img=True, k=True):
    kk = f'<div class="kick">{e(kick(it, hi))}</div>' if k else ""
    return (f'<article class="slot {cls}">{kk}<h3>{e(title_of(it, hi))}</h3>'
            f'{fig(it) if img else ""}{body(it, hi, cols)}</article>')


def lead(it, hi, cls="lead"):
    """Headline across; photo left, text right (2 columns)."""
    return (f'<article class="slot {cls}"><div class="kick">{e(kick(it, hi))}</div><h2>{e(title_of(it, hi))}</h2>'
            f'<div class="lgrid">{fig(it)}<div class="lcol">{body(it, hi, 2)}</div></div></article>')


def briefs(items, hi, title=None, cls="briefs"):
    t = f'<div class="bhead">{e(title)}</div>' if title else ""
    rows = "".join(f'<div class="brief" data-drop><h4>{e(title_of(it, hi))}</h4>'
                   f'<p>{inline(first_sentence(paras_of(it, hi)[0]))}</p></div>' for it in items if paras_of(it, hi))
    return f'<aside class="slot {cls}" data-fitlist>{t}<div class="blist">{rows}</div></aside>'


def bar(name, sec, day, hi, page_no):
    return (f'<header class="bar"><span class="sname">{e(sec)}</span>'
            f'<span class="sinfo">{e(name)} · {e(date_line(day, hi))}</span></header>')


# ---------------------------------------------------------------- pages

def render(paper, paper_hi, items, lang, day, total_all=None):
    hi = lang == "hi"
    name = paper_hi if hi else {"Times of India": "The Times of India", "Economic Times": "The Economic Times",
                                "Indian Express": "The Indian Express"}.get(paper, paper)
    used = set()

    def pick(pool, n, need_photo=True, min_len=0):
        out = []
        for it in pool:
            if it["id"] in used or (need_photo and not photo(it)) or length(it, hi) < min_len:
                continue
            out.append(it); used.add(it["id"])
            if len(out) == n:
                break
        return out

    pages = []
    # Front page: the strongest photo story, 3 more photo stories, In Brief
    f_lead = pick(items, 1, True, 700) or pick(items, 1, False)
    f_row = pick(items, 3, True, 300)
    f_br = pick(items, BRIEFS_FRONT, False)
    secs_present = []
    groups = {}
    # assign every remaining story to exactly one section (first match)
    assigned = set()
    for key, en, h, cats, maxp in SECTIONS:
        groups[key] = [i for i in items if i["id"] not in used and i["id"] not in assigned
                       and (cats is None or i["category"] in cats)]
        assigned |= {i["id"] for i in groups[key]}

    body_pages = []
    for key, en, h, cats, maxp in SECTIONS:
        pool = groups[key]
        n_photo = sum(1 for i in pool if photo(i))
        if n_photo < 2 and key != "more":
            groups["more"] = groups.get("more", []) + pool   # too thin for its own page: into More News
            continue
        sec = h if hi else en
        for pno in range(maxp):
            if pno == 0:
                ld = pick(pool, 1, True, 500) or pick(pool, 1, True)
                mid = pick(pool, 2, True, 250)
                if not ld:
                    break
                br = pick(pool, BRIEFS_PAGE, False)
                body_pages.append((sec, f'''<div class="grid p1">{lead(ld[0], hi)}
 {"".join(story(it, hi, f"m{i}", 1) for i, it in enumerate(mid))}
 {briefs(br, hi, "संक्षेप में" if hi else "In brief", "briefs band")}</div>'''))
            else:
                top = pick(pool, 2, True, 250)
                bot = pick(pool, 3, True, 200)
                if len(top) < 2:
                    break
                br = pick(pool, BRIEFS_PAGE, False)
                body_pages.append((sec, f'''<div class="grid p2">{"".join(story(it, hi, f"t{i}", 2) for i, it in enumerate(top))}
 {"".join(story(it, hi, f"b{i}", 1) for i, it in enumerate(bot))}
 {briefs(br, hi, "संक्षेप में" if hi else "In brief", "briefs band")}</div>'''))
        if key not in secs_present and any(s == sec for s, _ in body_pages):
            secs_present.append(sec)

    total = 1 + len(body_pages)
    index = "  |  ".join(f"{s} {next(n for n, (s2, _) in enumerate(body_pages, 2) if s2 == s)}" for s in secs_present)
    mast = f'''<header class="mast">
 <div class="strip"><span>{"निजी प्रति" if hi else "PERSONAL COPY"}</span><span>{e(date_line(day, hi)) if hi else e(date_line(day, hi)).upper()}</span>
  <span>{total} {"पृष्ठ" if hi else "PAGES"}</span></div>
 <h1 class="{'hi' if hi else ''}">{e(name)}</h1>
 <div class="strip2"><b>{"अंदर" if hi else "INSIDE"}</b> {e(index)}</div></header>'''
    front = f'''<div class="grid front">{lead(f_lead[0], hi, "lead flead") if f_lead else ""}
 {briefs(f_br, hi, "संक्षेप में" if hi else "In Brief", "briefs rail")}
 {"".join(story(it, hi, f"r{i}", 1) for i, it in enumerate(f_row))}</div>'''
    out = [f'<section class="page">{mast}{front}{foot(name, day, hi, 1, total)}</section>']
    for n, (sec, html_) in enumerate(body_pages, 2):
        out.append(f'<section class="page">{bar(name, sec, day, hi, n)}{html_}{foot(name, day, hi, n, total)}</section>')
    return f'''<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><title>{e(name)} — {e(date_line(day, hi))}</title>
<style>{FONTS}{CSS}</style></head><body class="{'hi' if hi else 'en'}">{"".join(out)}<script>{FIT_JS}</script></body></html>'''


def foot(name, day, hi, n, total):
    return (f'<footer class="pfoot"><span>{e(name)} · {e(date_line(day, hi))}</span>'
            f'<span>{"निजी प्रति · सत्याधीश द्वारा संकलित" if hi else "Personal copy · compiled by SatyaDheesh"}</span>'
            f'<span>{"पृष्ठ" if hi else "PAGE"} {n} / {total}</span></footer>')


# Trim every [data-fit] text block at a sentence end until it fits its slot; drop briefs that don't fit.
FIT_JS = r"""
function over(el){ return el.scrollHeight > el.clientHeight + 1 || el.scrollWidth > el.clientWidth + 1; }
function trimOne(el){
  const ps = el.querySelectorAll('p'); if (!ps.length) return false;
  const p = ps[ps.length - 1];
  const parts = p.textContent.match(/[^.!?।]+(?:[.!?।]+[”"’)]?|$)\s*/g) || [p.textContent];
  if (parts.length > 1) { p.textContent = parts.slice(0, -1).join('').trim(); return true; }
  if (ps.length > 1) { p.remove(); return true; }
  const w = p.textContent.split(' '); if (w.length < 8) return false;
  p.textContent = w.slice(0, -5).join(' ') + '…'; return true;
}
window.fitAll = function(){
  document.querySelectorAll('[data-fit]').forEach(el => { let g = 0; while (over(el) && g++ < 600 && trimOne(el)); });
  document.querySelectorAll('[data-fitlist]').forEach(el => { const l = el.querySelector('.blist'); let g = 0;
    while (over(l) && g++ < 40) { const b = l.querySelectorAll('[data-drop]'); if (!b.length) break; b[b.length-1].remove(); } });
  return true;
};
"""

CSS = r"""
@page { size: 315mm 470mm; margin: 0; }
html, body { margin: 0; background: #f6f2e9; }
body { color: #111; font: 9.6pt/1.36 'Source Serif 4', 'Deva', Georgia, serif; }
body.hi { font: 10.4pt/1.6 'Deva', 'Source Serif 4', sans-serif; }
b { font-weight: 600; }
.page { width: 315mm; height: 470mm; box-sizing: border-box; padding: 11mm 11mm 9mm; display: flex; flex-direction: column;
  overflow: hidden; break-after: page; position: relative; background: #f6f2e9; }
.grid { flex: 1; display: grid; gap: 5mm 6mm; min-height: 0; grid-template-columns: repeat(6, 1fr); }
/* front: lead (4 cols) + rail (2 cols), then 3 photo stories */
.front { grid-template-rows: 58% 1fr; grid-template-areas: "lead lead lead lead rail rail" "r0 r0 r1 r1 r2 r2"; }
.front .flead { grid-area: lead; } .front .rail { grid-area: rail; } .r0 { grid-area: r0; } .r1 { grid-area: r1; } .r2 { grid-area: r2; }
/* section page 1: lead across, two photo stories, briefs band */
.p1 { grid-template-rows: 52% 1fr 23%; grid-template-areas: "lead lead lead lead lead lead" "m0 m0 m0 m1 m1 m1" "br br br br br br"; }
.p1 .lead { grid-area: lead; } .m0 { grid-area: m0; } .m1 { grid-area: m1; } .p1 .band, .p2 .band { grid-area: br; }
/* section page 2+: two big photo stories, three smaller, briefs band */
.p2 { grid-template-rows: 44% 1fr 20%; grid-template-areas: "t0 t0 t0 t1 t1 t1" "b0 b0 b1 b1 b2 b2" "br br br br br br"; }
.t0 { grid-area: t0; } .t1 { grid-area: t1; } .b0 { grid-area: b0; } .b1 { grid-area: b1; } .b2 { grid-area: b2; }
.slot { display: flex; flex-direction: column; min-height: 0; overflow: hidden; border-top: 2px solid #111; padding-top: 2mm; }
.slot figure { margin: 0 0 2.2mm; flex: 1 1 46%; min-height: 32mm; max-height: 55%; overflow: hidden; }
.slot figure img { width: 100%; height: 100%; object-fit: cover; display: block; }
.slot .txt { flex: 0 1 auto; min-height: 12mm; overflow: hidden; }
.txt.c2 { columns: 2; column-gap: 5mm; column-rule: .5pt solid #b9b0a1; }
.txt p { margin: 0 0 1.3mm; text-align: justify; hyphens: auto; }
.txt p + p { text-indent: 3.5mm; }
.hi .txt p { text-align: left; }
.more { font: 600 7pt 'DM Sans', 'Deva', sans-serif; color: #9b1c1c; text-decoration: none; margin-top: 1mm; flex: none; }
.kick { font: 700 7.4pt 'DM Sans', 'Deva', sans-serif; letter-spacing: .18em; text-transform: uppercase; color: #9b1c1c; margin-bottom: 1mm; flex: none; }
h2, h3, h4 { margin: 0; flex: none; }
.lead h2 { font: 900 30pt/1.06 'Playfair Display', 'Deva Serif', serif; margin-bottom: 3mm; letter-spacing: -.005em; }
.flead h2 { font-size: 36pt; }
.hi .lead h2 { font: 800 25pt/1.32 'Deva Serif', serif; }
.lgrid { flex: 1; min-height: 0; display: grid; grid-template-columns: 3fr 2fr; gap: 5mm; }
.lgrid figure { margin: 0; height: 100%; max-height: none; }
.lcol { display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
.lcol .txt { flex: 1 1 auto; font-size: 10.4pt; line-height: 1.42; }
.lcol .txt.c2 { columns: 1; }
.lead .txt p:first-child::first-letter { float: left; font: 900 36pt/.82 'Playfair Display', serif; padding: 1.2mm 1.6mm 0 0; }
.hi .lead .txt p:first-child::first-letter { float: none; font: inherit; padding: 0; }
.slot h3 { font: 700 17pt/1.12 'Playfair Display', 'Deva Serif', serif; margin-bottom: 2mm; }
.t0 h3, .t1 h3 { font-size: 20pt; }
.b0 h3, .b1 h3, .b2 h3 { font-size: 14pt; }
.hi .slot h3 { font: 700 14pt/1.4 'Deva Serif', serif; }
.mast { text-align: center; margin-bottom: 4mm; flex: none; }
.strip { display: flex; justify-content: space-between; font: 600 7.4pt 'Plex Mono', 'Deva', monospace; letter-spacing: .1em;
  border-bottom: 1px solid #111; padding-bottom: 1.2mm; }
.mast h1 { margin: 2mm 0 1.5mm; font: 900 74pt/1 'Playfair Display', serif; letter-spacing: -.01em; }
.mast h1.hi { font: 800 64pt/1.2 'Deva Serif', serif; }
.strip2 { border-top: 3px double #111; border-bottom: 1.5px solid #111; padding: 1.3mm 0; font: 8pt 'DM Sans', 'Deva', sans-serif; }
.strip2 b { letter-spacing: .16em; margin-right: 2mm; }
.bar { flex: none; display: flex; justify-content: space-between; align-items: baseline; border-bottom: 3px double #111;
  padding-bottom: 1.5mm; margin-bottom: 4mm; }
.sname { font: 900 30pt/1 'Playfair Display', 'Deva Serif', serif; text-transform: uppercase; letter-spacing: .02em; }
.hi .sname { font: 800 26pt/1.2 'Deva Serif', serif; }
.sinfo { font: 600 7.6pt 'Plex Mono', 'Deva', monospace; letter-spacing: .08em; color: #555; }
.briefs { background: #ece5d6; padding: 3mm 3.5mm; border-top: 3px solid #111; }
.bhead { font: 900 12pt 'Playfair Display', 'Deva Serif', serif; letter-spacing: .08em; text-transform: uppercase;
  border-bottom: 1.5px solid #111; margin-bottom: 2mm; padding-bottom: 1mm; flex: none; }
.blist { flex: 1; min-height: 0; overflow: hidden; }
.band .blist { columns: 3; column-gap: 6mm; column-rule: .5pt solid #b9b0a1; }
.brief { break-inside: avoid; border-bottom: .5pt solid #b9b0a1; padding-bottom: 1.6mm; margin-bottom: 2mm; }
.brief h4 { font: 700 10pt/1.22 'Source Serif 4', 'Deva Serif', serif; margin-bottom: .7mm; }
.brief p { margin: 0; font-size: 8.6pt; line-height: 1.32; }
.pfoot { flex: none; display: flex; justify-content: space-between; border-top: 1px solid #111; margin-top: 3mm; padding-top: 1.2mm;
  font: 600 6.8pt 'Plex Mono', 'Deva', monospace; letter-spacing: .08em; color: #555; }
"""


def _fonts():
    import pathlib
    css = (pathlib.Path(__file__).parent.parent / "reports" / "base.css").read_text(encoding="utf-8")
    return "\n".join(l for l in css.split(":root")[0].splitlines() if l.strip())


FONTS = _fonts()
