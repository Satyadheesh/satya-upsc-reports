"""'explain': the morning explainer (replaces 'Number of the day', which gave a number without the story behind it).

One of yesterday's most important UPSC notes, explained over 6-7 slides:
  cover (headline + the issue) -> what happened (why in news + fact box) -> the backstory (earlier notes on the same
  story, dated) -> why it matters (the note's Mains angles + Mains question) -> remember for Prelims (kit facts)
  -> quiz -> answer.
Everything comes from checked data: the note, its study kit, earlier notes on the same story and their Hindi
translations; nothing is written for the post. The Hindi post is the English one in Hindi: a part that has no Hindi
is left out of both."""
import datetime as dt
import json
import re

from common.db import in_chunks
from reports.data import clean_hi, same_headline
from reports.render import MONTHS_HI, subject_name
from tg.periods import ist_date

from .slides import CSS, _brand, e, fact_pairs, quiz_slides
from .text import tidy

DAY = 86400
BACK_DAYS = 120
STOP_KW = {"india", "indian", "government", "upsc", "gs2", "gs3", "gs1", "gs4", "policy", "supreme court", "centre", "states"}

T = {
    "en": dict(kicker="EXPLAINED", issue="The issue", inside="Inside: what happened · the backstory · why it matters · Prelims facts · quiz",
               swipe="Swipe to understand it in a minute  →", what="What happened", detail="The details", back="The backstory",
               back_sub="How this story got here", now="Now", matters="Why it matters", mains="Mains question",
               remember="Remember for Prelims", quiz="Quick quiz", quiz_hint="Answer on the next slide", answer="Answer",
               ask="Which of the statements given above is/are correct?", daily="A new explainer every morning · follow @satyadheesh",
               save="Save this for revision", site="satyadheesh.in/upsc"),
    "hi": dict(kicker="समझिए", issue="मुद्दा", inside="अंदर: क्या हुआ · पृष्ठभूमि · क्यों ज़रूरी · प्रीलिम्स तथ्य · क्विज़",
               swipe="एक मिनट में समझने के लिए स्वाइप करें  →", what="क्या हुआ", detail="विवरण", back="पृष्ठभूमि",
               back_sub="यह ख़बर यहाँ तक कैसे पहुँची", now="अब", matters="क्यों ज़रूरी", mains="मेन्स प्रश्न",
               remember="प्रीलिम्स के लिए याद रखें", quiz="क्विज़", quiz_hint="उत्तर अगली स्लाइड पर", answer="उत्तर",
               ask="ऊपर दिए गए कथनों में से कौन-सा/से सही है/हैं?", daily="हर सुबह एक नया विश्लेषण · फ़ॉलो करें @satyadheesh",
               save="दोहराव के लिए सेव करें", site="satyadheesh.in/upsc"),
}

XCSS = """
.s.t-orange { background: var(--accent); color: #fff8f2; }
.s.t-orange .stripe { background: var(--ink); }
.s.t-orange .kicker, .s.t-orange .lbl { color: #ffe3cc; }
.s.t-orange .word, .s.t-orange .word i { color: #fff; }
.s.t-orange .hiword, .s.t-orange .foot { color: #ffd9bd; }
.s.t-orange .foot b { color: #fff; }
.s.t-orange .chip { background: var(--ink) !important; }
.s.t-orange h1.lead { color: #fff; margin: 34px 0 40px; }
.issue { font: 500 38px/1.42 var(--sans); color: #fff3e8; }
.inside { margin-top: 44px; font: 600 25px/1.5 var(--mono); color: #ffe3cc; letter-spacing: .03em; }
.s.t-orange .swipe { color: #fff; }
.para { font-size: 40px; line-height: 1.45; margin-bottom: 40px; }
.para.sm { font-size: 35px; color: var(--ink2); }
.h2 { font: 900 64px/1.12 var(--display); margin: 26px 0 40px; }
:lang(hi) .h2 { font-size: 58px; line-height: 1.3; }
ol.tl { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 0; border-left: 4px solid var(--rule); }
ol.tl li { position: relative; padding: 0 0 30px 40px; font-size: 34px; line-height: 1.38; color: var(--ink2); }
ol.tl li::before { content: ''; position: absolute; left: -14px; top: 10px; width: 24px; height: 24px; border-radius: 50%;
                   background: var(--cream); border: 4px solid var(--accent); }
ol.tl li.now::before { background: var(--accent); }
ol.tl li.now { color: var(--ink); font-weight: 500; }
ol.tl .d { display: block; font: 600 24px var(--mono); color: var(--accent); letter-spacing: .06em; margin-bottom: 4px; }
ul.dims { list-style: none; padding: 0; display: flex; flex-direction: column; gap: 28px; margin-bottom: 44px; }
ul.dims li { position: relative; padding-left: 44px; font-size: 38px; line-height: 1.4; }
ul.dims li::before { content: '→'; position: absolute; left: 0; top: 0; color: var(--accent); font-weight: 700; }
.mq { border-left: 8px solid var(--accent); background: #fff; padding: 26px 30px; font: 500 34px/1.42 var(--sans); color: var(--ink2);
      border-radius: 0 14px 14px 0; }
.mq .lbl { margin-bottom: 8px; }
.cta2 { margin-top: auto; font: 600 27px var(--mono); color: var(--accent); letter-spacing: .04em; }
"""

BOILER = re.compile(r"\bcase study\b|\bGS ?[1-4]\b|\bkey topic\b|केस स्टडी|विषय।?$", re.I)


def topic_of(takeaway):
    """'Judicial review of reservation limits: a GS2 Polity case study.' -> 'Judicial review of reservation limits'.
    The kit's takeaway is almost always 'Topic: a GSn case study'; only the topic part says anything."""
    t = " ".join(str(takeaway or "").split())
    if ":" in t:
        head = t.split(":", 1)[0].strip()
        if 12 <= len(head) <= 160 and not BOILER.search(head):
            return head
    return None


def _date(ts, hi):
    d = ist_date(ts)
    return f"{d.day} {MONTHS_HI[d.month - 1]} {d.year}" if hi else f"{d.day} {d.strftime('%b')} {d.year}"


def first_sentence(s, n=230):
    s = " ".join(str(s or "").split())
    m = re.search(r"(?<=[.।!?])\s", s)
    first = s[: m.start()] if m else s
    if len(first) <= n:
        return first
    k = max(first.rfind(", ", 0, n), first.rfind("; ", 0, n))
    return first[:k] if k > n // 2 else None


def _kw(v):
    try:
        x = json.loads(v) if v else []
    except (TypeError, ValueError):
        return set()
    return {k.strip().lower() for k in x if isinstance(k, str) and k.strip()} - STOP_KW if isinstance(x, list) else set()


def _arr(v):
    try:
        x = json.loads(v) if v else []
    except (TypeError, ValueError):
        return []
    return [" ".join(str(s).split()) for s in x if isinstance(s, str) and s.strip()] if isinstance(x, list) else []


def extras(upsc, main, trans, items):
    """For each candidate note: Mains angles (en, hi) and the backstory = earlier notes (BACK_DAYS) on the same story
    (same timeline, or 2+ shared keywords in the same GS paper), oldest first, with their Hindi.
    -> {article_id: {"dims": [..], "dims_hi": [..], "back": [(ts, why_en, why_hi|None)]}}"""
    ids = [it["id"] for it in items]
    if not ids:
        return {}
    out = {i: {"dims": [], "dims_hi": [], "back": []} for i in ids}
    meta = {r[0]: r for r in in_chunks(upsc, "SELECT article_id, mains_dimensions, keywords, gs_paper, published_at "
                                              "FROM upsc_articles WHERE article_id IN ({ph})", ids)}
    for i in ids:
        if i in meta:
            out[i]["dims"] = [d for d in _arr(meta[i][1]) if 25 <= len(d) <= 200][:4]
    if trans is not None:
        for r in in_chunks(trans, "SELECT article_id, mains_dimensions_hi FROM upsc_translations WHERE article_id IN ({ph})", ids):
            out[r[0]]["dims_hi"] = [clean_hi(d) for d in _arr(r[1])][:4]
    # same timeline: the events these notes belong to, and every article on them
    ev_of = {r[0]: r[1] for r in in_chunks(main, "SELECT article_id, event_id FROM event_articles WHERE article_id IN ({ph})", ids)}
    ev_arts = {}
    evs = sorted(set(ev_of.values()))
    if evs:
        for a, ev in in_chunks(main, "SELECT article_id, event_id FROM event_articles WHERE event_id IN ({ph})", evs):
            ev_arts.setdefault(ev, set()).add(a)
    first = min(meta[i][4] for i in ids if i in meta) if meta else 0
    older = upsc.execute("SELECT article_id, published_at, gs_paper, why_in_news, keywords FROM upsc_articles INDEXED BY idx_upsc_pub "
                         "WHERE published_at >= ? AND published_at < ?", [first - BACK_DAYS * DAY, first + 2 * DAY]).rows
    for i in ids:
        if i not in meta:
            continue
        _, _, kws, paper, pub = meta[i]
        kw = _kw(kws)
        same_ev = ev_arts.get(ev_of.get(i), set())
        cands = []
        for a, ts, p, why, okw in older:
            if a == i or ts >= pub - 12 * 3600 or not why:
                continue
            if a in same_ev or (p == paper and len(kw & _kw(okw)) >= 2):
                s = first_sentence(why, 200)
                if s:
                    cands.append((ts, a, s))
        cands.sort()
        picked = []
        for ts, a, s in cands:  # one per day, no repeats of the same headline
            if any(ist_date(ts) == ist_date(t) or same_headline(s, x) for t, _, x in picked):
                continue
            picked.append((ts, a, s))
        out[i]["back"] = picked[-4:]  # the latest four steps before this one
    back_ids = sorted({a for v in out.values() for _, a, _ in v["back"]})
    hi_why = {}
    if trans is not None and back_ids:
        hi_why = {r[0]: clean_hi(r[1]) for r in in_chunks(trans, "SELECT article_id, why_in_news_hi FROM upsc_translations "
                                                              "WHERE article_id IN ({ph})", back_ids) if r[1]}
    for v in out.values():
        v["back"] = [(ts, s, first_sentence(hi_why.get(a), 260) if hi_why.get(a) else None) for ts, a, s in v["back"]]
    return out


def candidate(en, hi, ex, rank):
    """(score, parts_en, parts_hi|None) for one note; score None if it can't carry an explainer."""
    def parts(it, lang):
        h = lang == "hi"
        kit = (it.get("kit_hi") if h else it.get("kit")) or {}
        return {"id": it["id"], "title": kit.get("short_title") or it["title"], "paper": it["paper"], "subject": it["subject"],
                "issue": topic_of(kit.get("takeaway")), "why": it["why"], "fact_box": it["fact_box"], "mains": it.get("mains"),
                "facts": [(lab, txt) for lab, txt in fact_pairs(kit.get("facts"), it["pointers"], h) if txt][:4],
                "mcq": kit.get("mcq"), "published_at": it["published_at"]}
    pe = parts(en, "en")
    ph = parts(hi, "hi") if hi else None
    dims, dims_hi = ex.get("dims") or [], ex.get("dims_hi") or []
    back = ex.get("back") or []
    if ph is not None:  # keep only what both languages have
        if len(dims_hi) != len(dims):
            dims = dims_hi = []
        back = [b for b in back if b[2]]
        if not (pe["issue"] and ph["issue"]):
            pe["issue"] = ph["issue"] = None
        if not (pe["mains"] and ph["mains"]):
            pe["mains"] = ph["mains"] = None
    pe["dims"], pe["back"] = dims, [(ts, s) for ts, s, _ in back]
    if ph is not None:
        ph["dims"], ph["back"] = dims_hi, [(ts, h) for ts, _, h in back]
    if len(pe["why"]) < 60 or len(pe["fact_box"]) < 100:
        return None, pe, ph
    score = 4 - 0.35 * rank
    score += 3 if len(dims) >= 2 else 0
    score += (2 + 0.5 * len(back)) if len(back) >= 2 else 0
    score += 1 if len(pe["facts"]) >= 3 else 0
    score += 1 if pe["mcq"] else 0
    if len(dims) < 2 and len(back) < 2:  # nothing beyond the news itself: not an explainer
        return None, pe, ph
    return score, pe, ph


def pick(en_ed, hi_ed, ex, top=12):
    best = None
    for k, en in enumerate(en_ed[:top]):
        hi = hi_ed[k] if hi_ed else None
        score, pe, ph = candidate(en, hi, ex.get(en["id"], {}), k)
        if score is not None and (best is None or score > best[0]):
            best = (score, pe, ph)
    return (best[1], best[2]) if best else (None, None)


def _foot(t, i, n):
    return f'<div class="foot"><span>{e(t["site"])}</span><span><b>@satyadheesh</b> · {i}/{n}</span></div>'


def _chip(p, hi):
    return f'<span class="chip {p["paper"].lower()}">{e(p["paper"])} · {e(subject_name(p["subject"], hi))}</span>'


def explain_html(p, quiz, lang):
    """p: parts (candidate); quiz: ig.post.quiz_of(...) or None."""
    t, hi = T[lang], lang == "hi"
    body = []  # (theme, inner html)
    issue = f'<div class="lbl">{e(t["issue"])}</div><div class="issue">{e(p["issue"])}</div>' if p.get("issue") else ""
    body.append(("t-orange", f'{_brand()}<div class="top-row" style="margin-top:56px"><span class="kicker">{e(t["kicker"])} · '
                             f'{e(_date(p["published_at"], hi))}</span></div><div style="margin-top:26px">{_chip(p, hi)}</div>'
                             f'<h1 class="lead">{e(p["title"])}</h1>{issue}<div class="inside">{e(t["inside"])}</div>'
                             f'<div class="swipe">{e(t["swipe"])}</div>'))
    body.append(("", f'<div class="top-row">{_chip(p, hi)}</div><div class="h2">{e(t["what"])}</div>'
                     f'<div class="para">{e(tidy(p["why"], 320))}</div>'
                     f'<div class="lbl">{e(t["detail"])}</div><div class="para sm">{e(tidy(p["fact_box"], 520))}</div>'))
    if len(p["back"]) >= 2:
        li = "".join(f'<li><span class="d">{e(_date(ts, hi))}</span>{e(s)}</li>' for ts, s in p["back"])
        li += f'<li class="now"><span class="d">{e(t["now"])} · {e(_date(p["published_at"], hi))}</span>{e(first_sentence(p["why"], 200) or tidy(p["why"], 200))}</li>'
        body.append(("", f'<div class="kicker">{e(t["back_sub"])}</div><div class="h2">{e(t["back"])}</div><ol class="tl">{li}</ol>'))
    if p["dims"] or p.get("mains"):
        dims = "".join(f"<li>{e(d)}</li>" for d in p["dims"])
        mq = f'<div class="mq"><div class="lbl">{e(t["mains"])}</div>{e(p["mains"])}</div>' if p.get("mains") else ""
        body.append(("", f'<div class="h2">{e(t["matters"])}</div>' + (f'<ul class="dims">{dims}</ul>' if dims else "") + mq))
    if p["facts"]:
        facts = "".join(f'<li>{"<b>" + e(lab) + ":</b> " if lab else ""}{e(tidy(txt, 200))}</li>' for lab, txt in p["facts"])
        body.append(("", f'<div class="h2">{e(t["remember"])}</div><ul class="rem">{facts}</ul>'))
    n = len(body) + (2 if quiz else 0)
    slides = [f'<section class="s {th}"><div class="stripe"></div><div class="c">{inner}</div>{_foot(t, k, n)}</section>'
              for k, (th, inner) in enumerate(body, 1)]
    if quiz:
        slides += quiz_slides(quiz, t, len(body), n, _foot, tail=f'<div class="cta2">{e(t["daily"])}</div>')
    else:
        slides[-1] = slides[-1].replace('</div><div class="foot">', f'<div class="cta2">{e(t["daily"])}</div></div><div class="foot">', 1)
    return (f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><style>{CSS}{XCSS}</style></head>'
            f'<body>{"".join(slides)}</body></html>'), n


TAGS = {"en": "#UPSC #UPSCCurrentAffairs #UPSCPrelims #UPSCMains #SatyaDheesh",
        "hi": "#UPSCHindi #यूपीएससी #करेंटअफेयर्स #UPSC #SatyaDheesh"}


def explain_caption(p, has_quiz, lang):
    """A caption that is worth reading on its own: the headline, what happened, the Mains question. No quiz answer."""
    hi = lang == "hi"
    lines = [(f"समझिए: {p['title']}" if hi else f"Explained: {p['title']}"), ""]
    s = first_sentence(p["why"], 260)
    if s:
        lines += [s, ""]
    parts = [("क्या हुआ" if hi else "what happened")]
    if len(p["back"]) >= 2:
        parts.append("पृष्ठभूमि" if hi else "the backstory")
    if p["dims"] or p.get("mains"):
        parts.append(f"क्यों ज़रूरी ({p['paper']})" if hi else f"why it matters for {p['paper']}")
    if p["facts"]:
        parts.append("प्रीलिम्स तथ्य" if hi else "Prelims facts")
    if has_quiz:
        parts.append("क्विज़" if hi else "a quick quiz")
    lines.append(("स्लाइड्स में: " if hi else "On the slides: ") + " · ".join(parts))
    if p.get("mains"):
        lines += ["", ("मेन्स अभ्यास: " if hi else "Mains practice: ") + p["mains"]]
    if has_quiz:
        lines += ["", "क्विज़ का उत्तर स्वाइप करने से पहले कमेंट करें।" if hi else "Comment your quiz answer before you swipe to it."]
    lines += ["", ("हर सुबह एक नया विश्लेषण: फ़ॉलो करें @satyadheesh · मुफ़्त नोट्स: satyadheesh.in/upsc" if hi
                  else "A new explainer every morning: follow @satyadheesh · free notes at satyadheesh.in/upsc"),
              ("दोहराव के लिए सेव करें।" if hi else "Save for revision."), "", TAGS[lang]]
    return "\n".join(lines)[:2200]
