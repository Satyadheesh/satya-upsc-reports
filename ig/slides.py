"""Instagram carousel slides (1080x1350, 4:5) in the SatyaDheesh report style.

cover -> 5 stories -> quiz -> answer -> 'get the PDF' (9 slides, Instagram allows 10).
Text comes from the study kit (short title, why it matters, facts, MCQ) in the post's language."""
import html

from reports.render import GAVEL, MONTHS_HI, POINTER, FACT_LABEL_HI, qr_svg, subject_name

W, H = 1080, 1350
TELEGRAM = "https://t.me/satyadheesh"

L = {
    "en": dict(kicker="UPSC CURRENT AFFAIRS", today="Today’s 5 for UPSC", swipe="Swipe for the notes  →",
               why="Why it matters", remember="Remember", quiz="Quick quiz", quiz_hint="Answer on the next slide",
               answer="Answer", ask="Which of the statements given above is/are correct?",
               cta1="Get the full PDF every morning", cta2="Brief + Detailed notes in English and Hindi, with a quiz, at 5 AM.",
               cta3="Telegram  @satyadheesh", cta4="Save this post for revision", site="satyadheesh.in/upsc"),
    "hi": dict(kicker="यूपीएससी करेंट अफेयर्स", today="आज की 5 ज़रूरी ख़बरें", swipe="नोट्स के लिए स्वाइप करें  →",
               why="क्यों ज़रूरी", remember="याद रखें", quiz="क्विज़", quiz_hint="उत्तर अगली स्लाइड पर",
               answer="उत्तर", ask="ऊपर दिए गए कथनों में से कौन-सा/से सही है/हैं?",
               cta1="पूरी पीडीएफ हर सुबह पाएँ", cta2="सार + विस्तृत नोट्स, हिंदी और अंग्रेज़ी में, क्विज़ के साथ, सुबह 5 बजे।",
               cta3="टेलीग्राम  @satyadheesh", cta4="दोहराव के लिए यह पोस्ट सेव करें", site="satyadheesh.in/upsc"),
}

CSS = """
@font-face { font-family: 'DM Sans'; font-weight: 400; src: url(fonts/dm-sans-latin-400-normal.woff2); }
@font-face { font-family: 'DM Sans'; font-weight: 500; src: url(fonts/dm-sans-latin-500-normal.woff2); }
@font-face { font-family: 'DM Sans'; font-weight: 700; src: url(fonts/dm-sans-latin-700-normal.woff2); }
@font-face { font-family: 'Playfair Display'; font-weight: 900; src: url(fonts/playfair-display-latin-900-normal.woff2); }
@font-face { font-family: 'Plex Mono'; font-weight: 500; src: url(fonts/ibm-plex-mono-latin-500-normal.woff2); }
@font-face { font-family: 'Plex Mono'; font-weight: 600; src: url(fonts/ibm-plex-mono-latin-600-normal.woff2); }
@font-face { font-family: 'Deva'; font-weight: 400; src: url(fonts/noto-sans-devanagari-devanagari-400-normal.woff2); }
@font-face { font-family: 'Deva'; font-weight: 500; src: url(fonts/noto-sans-devanagari-devanagari-500-normal.woff2); }
@font-face { font-family: 'Deva'; font-weight: 700; src: url(fonts/noto-sans-devanagari-devanagari-700-normal.woff2); }
@font-face { font-family: 'Deva Serif'; font-weight: 800; src: url(fonts/noto-serif-devanagari-devanagari-800-normal.woff2); }
:root { --ink:#120f0b; --ink2:#4a453f; --ink3:#857d75; --rule:#e4ded5; --cream:#f8f6f2; --cream2:#f1ede6;
  --accent:#bf4a07; --gs1:#1b7050; --gs2:#34558a; --gs3:#bf4a07; --gs4:#7a3e6e;
  --sans:'DM Sans','Deva',sans-serif; --display:'Playfair Display','Deva Serif',Georgia,serif; --mono:'Plex Mono','Deva',monospace; }
:lang(hi) { --sans:'Deva','DM Sans',sans-serif; --display:'Deva Serif','Playfair Display',serif; }
* { box-sizing: border-box; margin: 0; }
body { background: #ccc; }
.s { width: 1080px; height: 1350px; background: var(--cream); color: var(--ink); font: 400 34px/1.42 var(--sans);
     position: relative; overflow: hidden; padding: 84px 84px 120px; display: flex; flex-direction: column; }
.stripe { position: absolute; top: 0; left: 0; right: 0; height: 18px; background: var(--accent); }
.brand { display: flex; align-items: center; gap: 18px; }
.brand svg { width: 72px; height: 72px; }
.word { font: 900 46px/1 var(--display); letter-spacing: -.01em; }
.word i { font-style: normal; color: var(--accent); }
.hiword { font: 500 22px/1.2 'Deva', sans-serif; color: var(--ink3); margin-top: 4px; }
.kicker { font: 600 24px/1.2 var(--mono); letter-spacing: .14em; color: var(--accent); text-transform: uppercase; }
:lang(hi) .kicker { letter-spacing: .02em; font-size: 26px; }
.foot { position: absolute; left: 84px; right: 84px; bottom: 54px; display: flex; justify-content: space-between;
        font: 500 22px var(--mono); color: var(--ink3); letter-spacing: .06em; }
.foot b { color: var(--accent); font-weight: 600; }
.date { font: 900 92px/1.02 var(--display); margin: 26px 0 8px; letter-spacing: -.01em; }
:lang(hi) .date { font-size: 84px; line-height: 1.2; }
.sub { font: 500 34px var(--sans); color: var(--ink2); }
ol.top { list-style: none; padding: 0; margin: 44px 0 0; display: flex; flex-direction: column; gap: 22px; }
ol.top li { display: grid; grid-template-columns: 64px 1fr; gap: 12px; align-items: start; font: 500 33px/1.32 var(--sans); }
ol.top .n { font: 900 48px/1 var(--display); color: var(--accent); }
ol.top .p { font: 600 20px var(--mono); color: var(--ink3); letter-spacing: .08em; margin-top: 6px; display: block; }
.swipe { margin-top: auto; font: 600 28px var(--mono); color: var(--accent); letter-spacing: .06em; }
.chip { display: inline-block; font: 600 23px var(--mono); letter-spacing: .08em; padding: 8px 16px; border-radius: 8px;
        color: #fff; text-transform: uppercase; }
:lang(hi) .chip { text-transform: none; letter-spacing: .02em; }
.gs1 { background: var(--gs1); } .gs2 { background: var(--gs2); } .gs3 { background: var(--gs3); } .gs4 { background: var(--gs4); }
.top-row { display: flex; justify-content: space-between; align-items: center; }
.count { font: 600 26px var(--mono); color: var(--ink3); }
h1 { font: 900 66px/1.1 var(--display); margin: 34px 0 30px; letter-spacing: -.01em; }
:lang(hi) h1 { font-size: 60px; line-height: 1.3; }
.lbl { font: 600 22px var(--mono); letter-spacing: .14em; color: var(--accent); text-transform: uppercase; margin-bottom: 10px; }
:lang(hi) .lbl { letter-spacing: .02em; font-size: 25px; }
.why { font-size: 35px; line-height: 1.42; padding-bottom: 30px; border-bottom: 3px solid var(--rule); margin-bottom: 30px; }
ul.rem { list-style: none; padding: 0; display: flex; flex-direction: column; gap: 18px; }
ul.rem li { position: relative; padding-left: 34px; font-size: 31px; line-height: 1.38; color: var(--ink2); }
ul.rem li::before { content: ''; position: absolute; left: 0; top: 16px; width: 14px; height: 14px; background: var(--accent); }
ul.rem b { color: var(--ink); }
.q { font: 700 40px/1.35 var(--sans); margin: 36px 0 26px; }
ol.st { padding-left: 44px; margin: 0 0 22px; font-size: 31px; line-height: 1.38; display: flex; flex-direction: column; gap: 10px; }
.ask { font: 500 30px var(--sans); color: var(--ink2); margin-bottom: 20px; }
.opts { display: flex; flex-direction: column; gap: 16px; }
.opt { display: grid; grid-template-columns: 60px 1fr; align-items: center; gap: 16px; font-size: 32px; line-height: 1.3;
       background: #fff; border: 3px solid var(--rule); border-radius: 14px; padding: 16px 22px; }
.opt i { font: 600 30px var(--mono); font-style: normal; color: var(--accent); }
.opt.ok { border-color: var(--gs1); background: #e6f2ec; }
.opt.ok i { color: var(--gs1); }
.hint { margin-top: auto; font: 600 26px var(--mono); color: var(--ink3); letter-spacing: .06em; }
.expl { margin-top: 28px; font-size: 31px; line-height: 1.42; color: var(--ink2); }
.dark { background: var(--ink); color: var(--cream); }
.dark .word, .dark .date { color: var(--cream); }
.dark .sub { color: #d9d2c8; }
.qr { width: 340px; height: 340px; background: #fff; padding: 18px; border-radius: 18px; margin: 46px 0 30px; }
.tg { font: 700 46px var(--sans); color: #f0a46e; }
.save { margin-top: auto; font: 600 28px var(--mono); color: #f0a46e; letter-spacing: .06em; }
"""


def e(s):
    return html.escape(str(s or ""), quote=False)


def _date(d, hi):
    return f"{d.day} {MONTHS_HI[d.month - 1]} {d.year}" if hi else f"{d.day} {d.strftime('%B')} {d.year}"


def _foot(t, i, n):
    return f'<div class="foot"><span>{e(t["site"])}</span><span><b>@satyadheesh</b> · {i}/{n}</span></div>'


def _brand():
    return (f'<div class="brand">{GAVEL}<div><div class="word">Satya<i>Dheesh</i></div>'
            f'<div class="hiword">सत्याधीश</div></div></div>')


def _chip(story, hi):
    return f'<span class="chip {story["paper"].lower()}">{e(story["paper"])} · {e(subject_name(story["subject"], hi))}</span>'


def slides_html(day, stories, quiz, lang):
    """day: date; stories: up to 5 dicts {title, why, facts:[(label, text)], paper, subject};
    quiz: {question, statements|None, options, answer, explanation} or None."""
    t, hi = L[lang], lang == "hi"
    n = 1 + len(stories) + (2 if quiz else 0) + 1
    out, i = [], 1
    top = "".join(f'<li><span class="n">{k}</span><span>{e(s["title"])}<span class="p">{e(s["paper"])} · '
                  f'{e(subject_name(s["subject"], hi))}</span></span></li>' for k, s in enumerate(stories, 1))
    out.append(f'<section class="s"><div class="stripe"></div>{_brand()}<div style="margin-top:56px" class="kicker">{e(t["kicker"])}</div>'
               f'<div class="date">{e(_date(day, hi))}</div><div class="sub">{e(t["today"])}</div><ol class="top">{top}</ol>'
               f'<div class="swipe">{e(t["swipe"])}</div>{_foot(t, i, n)}</section>')
    for k, s in enumerate(stories, 1):
        i += 1
        facts = "".join(f'<li>{"<b>" + e(lab) + ":</b> " if lab else ""}{e(txt)}</li>' for lab, txt in s["facts"][:3])
        out.append(f'<section class="s"><div class="stripe"></div><div class="top-row">{_chip(s, hi)}<span class="count">{k}/{len(stories)}</span></div>'
                   f'<h1>{e(s["title"])}</h1><div class="lbl">{e(t["why"])}</div><div class="why">{e(s["why"])}</div>'
                   + (f'<div class="lbl">{e(t["remember"])}</div><ul class="rem">{facts}</ul>' if facts else "")
                   + f'{_foot(t, i, n)}</section>')
    if quiz:
        st = ("<ol class='st'>" + "".join(f"<li>{e(x)}</li>" for x in quiz["statements"]) + "</ol>"
              f'<div class="ask">{e(t["ask"])}</div>') if quiz.get("statements") else ""
        for reveal in (False, True):
            i += 1
            opts = "".join(f'<div class="opt{" ok" if reveal and j == quiz["answer"] else ""}"><i>({"abcd"[j]})</i><span>{e(o)}</span></div>'
                           for j, o in enumerate(quiz["options"]))
            tail = (f'<div class="expl"><b>{e(t["answer"])}: ({"abcd"[quiz["answer"]]})</b> {e(quiz["explanation"])}</div>' if reveal
                    else f'<div class="hint">{e(t["quiz_hint"])}  →</div>')
            out.append(f'<section class="s"><div class="stripe"></div><div class="kicker">{e(t["quiz"] if not reveal else t["answer"])}</div>'
                       f'<div class="q">{e(quiz["question"])}</div>{st}<div class="opts">{opts}</div>{tail}{_foot(t, i, n)}</section>')
    i += 1
    out.append(f'<section class="s dark"><div class="stripe"></div>{_brand()}<div class="date" style="margin-top:70px;font-size:76px">{e(t["cta1"])}</div>'
               f'<div class="sub">{e(t["cta2"])}</div>{qr_svg(TELEGRAM)}<div class="tg">{e(t["cta3"])}</div>'
               f'<div class="save">{e(t["cta4"])}</div>{_foot(t, i, n)}</section>')
    return (f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><style>{CSS}</style></head>'
            f'<body>{"".join(out)}</body></html>'), n


def fact_pairs(facts, pointers, hi):
    """[(label, text)] from study-kit facts (label + text) or the note's prelims pointers."""
    if facts:
        return [((FACT_LABEL_HI.get(f.get("label"), f.get("label")) if hi else f.get("label")), f.get("text"))
                for f in facts if f.get("text")]
    return [((POINTER.get(p.get("type"), (None, None))[1 if hi else 0]), p.get("text")) for p in pointers if p.get("text")]
