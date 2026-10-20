"""'Today in 60 seconds': the one daily post (Yash, 20 Oct 2026: one post instead of six; people don't read much).

Up to 6 slides, little text per slide, built from the same checked data as the old formats:
  1  cover: the day's lead story, big                                       (UPSC notes, as 'Today's 5')
  2  number of the day: a big number and what it is                         (ig.formats.qotd_number)  [if any]
  3  the lead story: why it matters + 2 facts to remember
  4  also today: the other 4 stories, one line each
  5  quick quiz: 3 one-line SSC questions                                   (today's SSC cards)       [if 2+]
  6  answers + where to get the PDFs
English at 19:00, Hindi at 21:00 (IST). Nothing is written for the post."""
from reports.render import subject_name

from .formats import EXTRA_CSS, number_score  # noqa: F401  (number_score re-exported for tests)
from .slides import CSS, _brand, _date, e

T = {
    "en": dict(kicker="TODAY IN 60 SECONDS", inside="Inside: {bits}", bits_num="number of the day", bits_more="{n} more stories",
               bits_quiz="{n}-question quiz", swipe="Swipe  →", num_k="NUMBER OF THE DAY", why="Why it matters",
               remember="Remember", also="ALSO TODAY", quiz="QUICK QUIZ", quiz_sub="Answer in your head, then swipe  →",
               answers="ANSWERS", score="Comment your score!", cta1="Full notes free, every day",
               cta2="satyadheesh.in  ·  PDFs on Telegram @satyadheesh", save="Save · Share · Follow @satyadheesh",
               site="satyadheesh.in"),
    "hi": dict(kicker="आज 60 सेकंड में", inside="इसमें: {bits}", bits_num="आज का आँकड़ा", bits_more="{n} और ख़बरें",
               bits_quiz="{n} प्रश्नों का क्विज़", swipe="स्वाइप करें  →", num_k="आज का आँकड़ा", why="क्यों ज़रूरी",
               remember="याद रखें", also="आज और", quiz="क्विज़", quiz_sub="मन में उत्तर सोचिए, फिर स्वाइप करें  →",
               answers="उत्तर", score="अपना स्कोर कमेंट करें!", cta1="पूरे नोट्स मुफ़्त, हर दिन",
               cta2="satyadheesh.in  ·  पीडीएफ टेलीग्राम पर @satyadheesh", save="सेव करें · शेयर करें · फ़ॉलो करें @satyadheesh",
               site="satyadheesh.in"),
}

DIGEST_CSS = """
.d-lead { font: 900 88px/1.08 var(--display); margin: 40px 0 36px; letter-spacing: -.01em; }
:lang(hi) .d-lead { font-size: 76px; line-height: 1.3; }
.d-inside { font: 600 30px/1.4 var(--mono); color: var(--ink2); letter-spacing: .02em; }
.d-what { font: 600 52px/1.3 var(--sans); }
.d-from { margin-top: 40px; font: 500 32px/1.4 var(--sans); color: #ffe3cc; }
.d-why { font-size: 44px; line-height: 1.42; margin-bottom: 44px; }
ol.d-also { list-style: none; padding: 0; margin: 40px 0 0; display: flex; flex-direction: column; gap: 34px; }
ol.d-also li { display: grid; grid-template-columns: 70px 1fr; gap: 14px; font: 600 40px/1.3 var(--sans); }
ol.d-also .n { font: 900 54px/1 var(--display); color: var(--accent); }
ol.d-also .p { display: block; font: 600 22px var(--mono); color: var(--ink3); letter-spacing: .08em; margin-top: 8px; }
ol.d-q { padding: 0; list-style: none; margin: 46px 0 0; display: flex; flex-direction: column; gap: 46px; }
ol.d-q li { display: grid; grid-template-columns: 70px 1fr; gap: 14px; font: 600 44px/1.32 var(--sans); }
ol.d-q .n { font: 900 54px/1 var(--display); color: #f0a46e; }
ol.d-q .a { display: block; margin-top: 10px; font: 700 40px/1.3 var(--sans); color: #7fd3a8; }
ol.d-q .k { display: block; margin-top: 6px; font: 400 28px/1.35 var(--sans); color: #a39c92; }
"""


def _foot(t, i, n):
    return f'<div class="foot"><span>{e(t["site"])}</span><span><b>@satyadheesh</b> · {i}/{n}</span></div>'


def _chip(s, hi):
    return f'<span class="chip {s["paper"].lower()}">{e(s["paper"])} · {e(subject_name(s["subject"], hi))}</span>'


def quick_quiz(cards, n=3):
    """Up to n one-line SSC questions (question, answer, key fact) from SSC cards: the most important first, short
    ones only (a slide holds three), one per topic. cards: SSC items whose ssc_kit has question_en/answer_en (the
    Hindi cards are passed with the Hindi text in those fields)."""
    out, topics = [], set()
    for c in sorted(cards, key=lambda c: -(c.get("importance") or 0)):
        k = c.get("ssc_kit") or {}
        q, a = " ".join(str(k.get("question_en") or "").split()), " ".join(str(k.get("answer_en") or "").split())
        topic = (c.get("ssc_topic") or [None])[0]
        if not q or not a or len(q) > 120 or len(a) > 48 or topic in topics:
            continue
        topics.add(topic)
        key = " ".join(str(k.get("key_fact_en") or "").split())
        out.append({"q": q, "a": a, "key": key if 0 < len(key) <= 110 else ""})
        if len(out) == n:
            break
    return out


def digest_html(day, stories, number, quiz, lang):
    """stories: the day's 5 (ig.post.story dicts, lead first); number: ig.formats.qotd_number item or None;
    quiz: quick_quiz() list (shown when 2+)."""
    t, hi = T[lang], lang == "hi"
    lead, rest = stories[0], stories[1:5]
    quiz = quiz if len(quiz) >= 2 else []
    n = 1 + (1 if number else 0) + 1 + (1 if rest else 0) + (1 if quiz else 0) + 1
    bits = ([t["bits_num"]] if number else []) + ([t["bits_more"].format(n=len(rest))] if rest else []) \
        + ([t["bits_quiz"].format(n=len(quiz))] if quiz else [])
    out, i = [], 1
    out.append(f'<section class="s"><div class="stripe"></div><div class="c">{_brand()}<div class="kicker" style="margin-top:56px">'
               f'{e(t["kicker"])} · {e(_date(day, hi))}</div><div class="d-lead">{e(lead["title"])}</div>'
               f'<div class="d-inside">{e(t["inside"].format(bits=" · ".join(bits)))}</div>'
               f'<div class="swipe">{e(t["swipe"])}</div></div>{_foot(t, i, n)}</section>')
    if number:
        i += 1
        size = "" if len(number["number"]) <= 6 else "mid" if len(number["number"]) <= 10 else "small"
        out.append(f'<section class="s t-orange"><div class="stripe"></div><div class="c"><div class="kicker">{e(t["num_k"])}</div>'
                   f'<div class="big {size}" style="margin:150px 0 50px">{e(number["number"])}</div>'
                   f'<div class="d-what">{e(number["what"])}</div><div class="d-from">{e(number["title"])}</div></div>{_foot(t, i, n)}</section>')
    i += 1
    facts = "".join(f'<li>{"<b>" + e(lab) + ":</b> " if lab else ""}{e(txt)}</li>' for lab, txt in lead["facts"][:2])
    out.append(f'<section class="s"><div class="stripe"></div><div class="c"><div class="top-row">{_chip(lead, hi)}<span class="count">1/{len(stories)}</span></div>'
               f'<h1>{e(lead["title"])}</h1><div class="lbl">{e(t["why"])}</div><div class="d-why">{e(lead["why"])}</div>'
               + (f'<div class="lbl">{e(t["remember"])}</div><ul class="rem">{facts}</ul>' if facts else "")
               + f'</div>{_foot(t, i, n)}</section>')
    if rest:
        i += 1
        li = "".join(f'<li><span class="n">{k}</span><span>{e(s["title"])}<span class="p">{e(s["paper"])} · '
                     f'{e(subject_name(s["subject"], hi))}</span></span></li>' for k, s in enumerate(rest, 2))
        out.append(f'<section class="s"><div class="stripe"></div><div class="c"><div class="kicker">{e(t["also"])}</div>'
                   f'<ol class="d-also">{li}</ol></div>{_foot(t, i, n)}</section>')
    if quiz:
        i += 1
        li = "".join(f'<li><span class="n">{k}</span><span>{e(x["q"])}</span></li>' for k, x in enumerate(quiz, 1))
        out.append(f'<section class="s t-dark"><div class="stripe"></div><div class="c"><div class="kicker">{e(t["quiz"])}</div>'
                   f'<ol class="d-q">{li}</ol><div class="sub2">{e(t["quiz_sub"])}</div></div>{_foot(t, i, n)}</section>')
    i += 1
    ans = ""
    if quiz:
        ans = (f'<div class="kicker">{e(t["answers"])}</div><ol class="d-q" style="margin-top:30px;gap:30px">'
               + "".join(f'<li><span class="n">{k}</span><span>{e(x["q"])}<span class="a">{e(x["a"])}</span>'
                         + (f'<span class="k">{e(x["key"])}</span>' if x["key"] else "") + '</span></li>' for k, x in enumerate(quiz, 1))
               + f'</ol><div class="tg" style="margin-top:40px;font-size:36px">{e(t["score"])}</div>')
    out.append(f'<section class="s t-dark"><div class="stripe"></div><div class="c">{ans if quiz else _brand()}'
               f'<div style="margin-top:auto"><div class="hl" style="color:var(--cream);font-size:44px">{e(t["cta1"])}</div>'
               f'<div class="whyp" style="color:#d9d2c8">{e(t["cta2"])}</div><div class="save" style="margin-top:22px">{e(t["save"])}</div></div>'
               f'</div>{_foot(t, i, n)}</section>')
    return (f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><style>{CSS}{EXTRA_CSS}{DIGEST_CSS}</style></head>'
            f'<body>{"".join(out)}</body></html>'), n


TAGS = {"en": "#UPSC #SSCCGL #CurrentAffairs #UPSCPrelims #SatyaDheesh",
        "hi": "#UPSCHindi #SSCCGL #करेंटअफेयर्स #UPSC #SatyaDheesh"}


def digest_caption(day, stories, number, quiz, lang):
    hi = lang == "hi"
    lines = [stories[0]["title"], "",
             (f"आज 60 सेकंड में — {_date(day, True)}" if hi else f"Today in 60 seconds — {_date(day, False)}")]
    if number:
        lines.append(f"{'आज का आँकड़ा' if hi else 'Number of the day'}: {number['number']} — {number['what']}")
    lines.append("")
    lines += [f"{k}. {s['title']}" for k, s in enumerate(stories[:5], 1)]
    if len(quiz) >= 2:
        lines += ["", ("क्विज़ स्लाइड पर — अपना स्कोर कमेंट करें!" if hi else "Quick quiz on the slides — comment your score!")]
    lines += ["", ("पूरे नोट्स मुफ़्त: satyadheesh.in · रोज़ की पीडीएफ टेलीग्राम पर @satyadheesh" if hi
                   else "Full notes free at satyadheesh.in · daily PDFs on Telegram @satyadheesh"),
              ("सेव करें · शेयर करें · फ़ॉलो करें @satyadheesh" if hi else "Save · share · follow @satyadheesh"),
              "", TAGS[lang]]
    return "\n".join(lines)[:2200]
