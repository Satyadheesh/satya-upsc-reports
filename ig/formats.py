"""The day's other Instagram posts, besides the UPSC 'Today's 5' carousel (ig.slides):

- 'qotd'  Number (or Question) of the day, 2 slides: a big hook (a number from today's UPSC study kit, or the day's
          top SSC question), then the answer with the story behind it.
- 'ssc'   SSC quiz carousel, 8 slides: cover ('Can you get 5/5?'), 5 questions with 4 options, all answers, CTA.

Everything comes from checked data (study-kit facts, SSC cards); nothing is written for the post.
Hindi uses the paired Hindi kit facts / Hindi SSC cards, or is skipped."""
import re

from reports.render import subject_name

from .slides import CSS, L as UPSC_L, _brand, e

T = {
    "en": dict(num_k="NUMBER OF THE DAY", q_k="QUESTION OF THE DAY", guess="What does this number stand for?",
               guess2="Guess, then swipe for the answer  →", hint="Hint", think="Think of your answer, then swipe  →",
               answer="ANSWER", in_news="In the news", why="Why it matters", daily="A new one every morning",
               ssc_k="SSC CURRENT AFFAIRS QUIZ", ssc_h="5 questions from today’s news", ssc_sub="Can you get 5/5?",
               ssc_sub2="Answers on slide 7. Comment your score!", q="Question", answers="Answers", key="Key",
               cta1="Every day’s SSC one-liner PDF", cta2="All questions by topic, free, at satyadheesh.in/ssc",
               cta3="Follow @satyadheesh", cta4="Save this for revision", site="satyadheesh.in"),
    "hi": dict(num_k="आज का आँकड़ा", q_k="आज का प्रश्न", guess="यह आँकड़ा किस बारे में है?",
               guess2="सोचिए, फिर उत्तर के लिए स्वाइप करें  →", hint="संकेत", think="अपना उत्तर सोचिए, फिर स्वाइप करें  →",
               answer="उत्तर", in_news="ख़बर", why="क्यों ज़रूरी", daily="हर सुबह एक नया",
               ssc_k="एसएससी करेंट अफेयर्स क्विज़", ssc_h="आज की ख़बरों से 5 प्रश्न", ssc_sub="क्या आप 5/5 कर पाएँगे?",
               ssc_sub2="उत्तर स्लाइड 7 पर। अपना स्कोर कमेंट करें!", q="प्रश्न", answers="उत्तर", key="मुख्य तथ्य",
               cta1="हर दिन का एसएससी वन-लाइनर पीडीएफ", cta2="सभी प्रश्न विषय के अनुसार, मुफ़्त: satyadheesh.in/ssc",
               cta3="फ़ॉलो करें @satyadheesh", cta4="दोहराव के लिए सेव करें", site="satyadheesh.in"),
}

EXTRA_CSS = """
.big { font: 900 230px/1 var(--display); color: var(--accent); letter-spacing: -.02em; margin: 170px 0 40px; }
.hint2 { margin-top: 34px; font: 600 28px var(--mono); color: var(--ink3); letter-spacing: .06em; }
.big.mid { font-size: 150px; } .big.small { font-size: 112px; }
.hook { font: 700 60px/1.25 var(--sans); }
.hookq { font: 800 66px/1.25 var(--display); margin: 90px 0 0; }
:lang(hi) .hookq { font-family: 'Deva Serif', serif; line-height: 1.4; }
.sub2 { margin-top: auto; font: 600 30px var(--mono); color: var(--accent); letter-spacing: .04em; }
.ans { font: 800 64px/1.2 var(--display); color: var(--gs1); margin: 30px 0 28px; }
.fact { font: 500 44px/1.4 var(--sans); margin-bottom: 44px; }
.hl { font: 700 38px/1.32 var(--sans); margin-bottom: 18px; }
.whyp { font-size: 34px; line-height: 1.42; color: var(--ink2); }
.qn { font: 600 26px var(--mono); color: var(--ink3); }
.alist { list-style: none; padding: 0; display: flex; flex-direction: column; gap: 22px; margin-top: 36px; }
.alist li { display: grid; grid-template-columns: 64px 1fr; gap: 10px; font: 500 33px/1.32 var(--sans); }
.alist b { color: var(--gs1); } .alist .n { font: 900 44px/1 var(--display); color: var(--accent); }
.alist .k { display: block; font-size: 26px; color: var(--ink3); margin-top: 4px; }
"""


def _foot(site, i, n):
    return f'<div class="foot"><span>{e(site)}</span><span><b>@satyadheesh</b> · {i}/{n}</span></div>'


def _page(lang, slides):
    return (f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><style>{CSS}{EXTRA_CSS}</style></head>'
            f'<body>{"".join(slides)}</body></html>')


# ------------------------------------------------------------------ Number / Question of the day

NUM = re.compile(r"\d")


def number_fact(story):
    """(number, what it is) from a story's 'Figure' fact ('13.37 crore — names deleted ...'), or None."""
    for lab, txt in story.get("facts") or []:
        m = re.match(r"^(.{1,22}?)\s*[—:–-]\s+(.{12,})$", txt or "")
        if m and NUM.search(m.group(1)) and len(m.group(1).split()) <= 4 and (lab or "").lower() in ("figure", "आँकड़ा", ""):
            return m.group(1).strip(), m.group(2).strip()
    return None


def qotd_number(stories_en, stories_hi=None):
    """The first of today's top stories with a number fact in English (and, paired, in Hindi). -> (en, hi|None)."""
    for k, s in enumerate(stories_en):
        nf = number_fact(s)
        if not nf:
            continue
        en = {"kind": "number", "number": nf[0], "what": nf[1], "title": s["title"], "why": s["why"],
              "paper": s["paper"], "subject": s["subject"]}
        hi = None
        if stories_hi and k < len(stories_hi):
            h = stories_hi[k]
            nh = number_fact(h)
            if nh and re.sub(r"\D", "", nh[0])[:3] == re.sub(r"\D", "", nf[0])[:3]:  # same number in both
                hi = {**en, "number": nh[0], "what": nh[1], "title": h["title"], "why": h["why"]}
        return en, hi
    return None, None


def qotd_question(card_en, card_hi=None):
    """From the day's top SSC card (question, answer, key fact)."""
    en = {"kind": "question", "question": card_en["question"], "answer": card_en["answer"], "key": card_en.get("key") or "",
          "title": card_en.get("title") or ""}
    hi = ({**en, "question": card_hi["question"], "answer": card_hi["answer"], "key": card_hi.get("key") or "",
           "title": ""} if card_hi else None)
    return en, hi


def qotd_html(item, lang):
    t, hi = T[lang], lang == "hi"
    s = []
    if item["kind"] == "number":
        size = "" if len(item["number"]) <= 6 else "mid" if len(item["number"]) <= 10 else "small"
        s.append(f'<section class="s"><div class="stripe"></div><div class="c">{_brand()}<div class="kicker" style="margin-top:60px">{e(t["num_k"])}</div>'
                 f'<div class="big {size}">{e(item["number"])}</div><div class="hook">{e(t["guess"])}</div>'
                 f'<div class="hint2">{e(t["hint"])}: {e(item["paper"])} · {e(subject_name(item["subject"], hi))}</div>'
                 f'<div class="sub2">{e(t["guess2"])}</div></div>{_foot(t["site"], 1, 2)}</section>')
        chip = f'<span class="chip {item["paper"].lower()}">{e(item["paper"])} · {e(subject_name(item["subject"], hi))}</span>'
        s.append(f'<section class="s"><div class="stripe"></div><div class="c"><div class="top-row">{chip}<span class="count">{e(t["answer"])}</span></div>'
                 f'<div class="big small" style="margin:56px 0 20px">{e(item["number"])}</div><div class="fact">{e(item["what"])}</div>'
                 f'<div class="lbl">{e(t["in_news"])}</div><div class="hl">{e(item["title"])}</div>'
                 f'<div class="whyp">{e(item["why"])}</div><div class="sub2">{e(t["daily"])} · @satyadheesh</div></div>{_foot(t["site"], 2, 2)}</section>')
    else:
        s.append(f'<section class="s"><div class="stripe"></div><div class="c">{_brand()}<div class="kicker" style="margin-top:60px">{e(t["q_k"])}</div>'
                 f'<div class="hookq">{e(item["question"])}</div><div class="sub2">{e(t["think"])}</div></div>{_foot(t["site"], 1, 2)}</section>')
        s.append(f'<section class="s"><div class="stripe"></div><div class="c"><div class="kicker">{e(t["answer"])}</div>'
                 f'<div class="hl" style="margin-top:40px">{e(item["question"])}</div><div class="ans">{e(item["answer"])}</div>'
                 + (f'<div class="lbl">{e(t["key"])}</div><div class="whyp">{e(item["key"])}</div>' if item.get("key") else "")
                 + f'<div class="sub2">{e(t["daily"])} · @satyadheesh</div></div>{_foot(t["site"], 2, 2)}</section>')
    return _page(lang, s), 2


# ------------------------------------------------------------------ SSC quiz carousel

def ssc_quiz_html(quiz, keys, lang, day_label):
    """quiz: [(question, options[4], correct index)] x 5 (reports.render.ssc_quiz); keys: key fact per question."""
    t = T[lang]
    n = 1 + len(quiz) + 2
    s = [f'<section class="s"><div class="stripe"></div><div class="c">{_brand()}<div class="kicker" style="margin-top:60px">{e(t["ssc_k"])} · {e(day_label)}</div>'
         f'<div class="hookq" style="margin-top:70px">{e(t["ssc_h"])}</div><div class="big mid" style="margin:50px 0 0">{e(t["ssc_sub"])}</div>'
         f'<div class="sub2">{e(t["ssc_sub2"])}</div></div>{_foot(t["site"], 1, n)}</section>']
    for k, (q, opts, _) in enumerate(quiz, 1):
        o = "".join(f'<div class="opt"><i>({"abcd"[j]})</i><span>{e(x)}</span></div>' for j, x in enumerate(opts))
        s.append(f'<section class="s{" long" if len(q) > 150 else ""}"><div class="stripe"></div><div class="c"><div class="top-row"><span class="kicker">{e(t["q"])} {k}</span>'
                 f'<span class="qn">{k}/{len(quiz)}</span></div><div class="q">{e(q)}</div><div class="opts">{o}</div></div>{_foot(t["site"], k + 1, n)}</section>')
    li = "".join(f'<li><span class="n">{k}</span><span><b>({"abcd"[c]}) {e(opts[c])}</b>'
                 + (f'<span class="k">{e(keys[k - 1])}</span>' if keys[k - 1] else "") + '</span></li>'
                 for k, (_, opts, c) in enumerate(quiz, 1))
    s.append(f'<section class="s"><div class="stripe"></div><div class="c"><div class="kicker">{e(t["answers"])}</div><ol class="alist">{li}</ol></div>'
             f'{_foot(t["site"], n - 1, n)}</section>')
    s.append(f'<section class="s dark"><div class="stripe"></div><div class="c">{_brand()}<div class="date" style="margin-top:70px;font-size:72px">{e(t["cta1"])}</div>'
             f'<div class="sub">{e(t["cta2"])}</div><div class="tg" style="margin-top:80px">{e(t["cta3"])}</div>'
             f'<div class="save">{e(t["cta4"])}</div></div>{_foot(t["site"], n, n)}</section>')
    return _page(lang, s), n


# ------------------------------------------------------------------ captions

TAGS = {  # 4-5 tags that match the audience; keywords in the first lines matter more for search
    "qotd": {"en": "#UPSC #CurrentAffairs #UPSCPrelims #SSCCGL #SatyaDheesh",
             "hi": "#UPSCHindi #करेंटअफेयर्स #SSCCGL #UPSC #SatyaDheesh"},
    "ssc": {"en": "#SSCCGL #SSC #CurrentAffairs #GKQuiz #SatyaDheesh",
            "hi": "#SSCCGL #SSC #करेंटअफेयर्स #जीके #SatyaDheesh"},
    "upsc": {"en": "#UPSC #UPSCCurrentAffairs #UPSCPrelims #CurrentAffairs #SatyaDheesh",
             "hi": "#UPSCHindi #यूपीएससी #करेंटअफेयर्स #UPSC #SatyaDheesh"},
}


def qotd_caption(item, lang):
    hi = lang == "hi"
    if item["kind"] == "number":
        head = (f"आज का आँकड़ा: {item['number']} — क्या आप जानते हैं यह किस बारे में है?" if hi
                else f"Number of the day: {item['number']}. Do you know what it stands for?")
        body = [head, "", ("सोचिए, फिर स्वाइप करें। उत्तर स्लाइड 2 पर।" if hi else "Guess first, then swipe: the answer is on slide 2."),
                "", f"{item['title']}"]
    else:
        head = f"{'आज का प्रश्न' if hi else 'Question of the day'}: {item['question']}"
        body = [head, "", ("अपना उत्तर कमेंट करें, फिर स्वाइप करें।" if hi else "Comment your answer, then swipe to check.")]
    body += ["", ("रोज़ करेंट अफेयर्स: फ़ॉलो करें @satyadheesh · पीडीएफ: satyadheesh.in" if hi
                  else "Daily current affairs: follow @satyadheesh · free PDFs at satyadheesh.in"),
             "", TAGS["qotd"][lang]]
    return "\n".join(body)


def ssc_caption(quiz, lang, day_label):
    hi = lang == "hi"
    lines = [("एसएससी करेंट अफेयर्स क्विज़ — आज की ख़बरों से 5 प्रश्न। क्या आप 5/5 कर पाएँगे?" if hi
              else "SSC current affairs quiz: 5 questions from today’s news. Can you get 5/5?"), day_label, ""]
    lines += [f"{k}. {q}" for k, (q, _, _) in enumerate(quiz, 1)]
    lines += ["", ("उत्तर स्लाइड 7 पर। अपना स्कोर कमेंट करें!" if hi else "Answers on slide 7. Comment your score!"),
              ("सभी प्रश्नों वाली दैनिक पीडीएफ मुफ़्त: satyadheesh.in/ssc" if hi else "Free daily PDF with every question: satyadheesh.in/ssc"),
              ("दोहराव के लिए सेव करें · फ़ॉलो करें @satyadheesh" if hi else "Save for revision · follow @satyadheesh"),
              "", TAGS["ssc"][lang]]
    return "\n".join(lines)[:2200]
