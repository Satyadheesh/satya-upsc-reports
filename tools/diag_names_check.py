"""READ-ONLY: how often the UPSC service's new named-body check (v2.8) would drop a fact-box sentence or pointer of
recent notes, with examples, so the rule can be tuned before it goes live. DAYS env (default 2)."""
import json
import os
import re
import time

from common.db import close_all, in_chunks, main_db, upsc_db
from sscca.articles import decode

STOP = set("""about above after again against also among and another any are around because been before being below
between both but by can could did does doing down during each either even ever every few for from further had has have
having here him his how however into its itself just least less made make many may might more most much must near
neither never nor not now off often once only other others our out over own per rather same several shall should since
some such than that the their them then there these they this those though through thus till under until upon very was
were what when where whether which while who whom whose why will with within without would yet india indian new said
says year years including""".split())
WORD_RE = re.compile(r"[a-z][a-z'\-]+|\d+(?:[.,]\d+)*")


def _words(text):
    return {w[:6] for w in WORD_RE.findall((text or "").lower()) if w not in STOP and (len(w) >= 4 or w[0].isdigit())}


NAME_RE = re.compile(r"\b[A-Z][\w'’-]*(?:\s+(?:(?:of|for|and|on|the|de|in)\s+)*[A-Z][\w'’-]*){1,8}")
NAME_SPLIT = re.compile(r",\s*|\s+(?:and|in|on|at)\s+(?=[A-Z])")
INSTITUTION = re.compile(r"\b(?:Court|Tribunal|Commission|Committee|Council|Authority|Board|Bank|Organi[sz]ation|Agency|"
                         r"Institute|Fund|Assembly|Corporation|Bureau|Directorate|Secretariat|Parliament|Forum|Alliance|"
                         r"Treaty|Convention|Agreement|Act|Mission|Yojana|Scheme|Programme|Observatory)\b")
NAME_GENERIC = {"the", "of", "for", "and", "on", "de", "in"}
NAME_OK = {"supreme court", "high court", "union cabinet", "united nations", "lok sabha", "rajya sabha"}


def body_names(text):
    """Names of bodies (courts, commissions, banks, treaties, schemes ...) in `text`."""
    out = []
    for m in NAME_RE.finditer(text or ""):
        for part in NAME_SPLIT.split(m.group()):
            part = part.strip()
            if INSTITUTION.search(part) and len([w for w in part.split() if w.lower() not in NAME_GENERIC]) >= 2:
                out.append(part)
    return out


def body_missing(name, text, words):
    """True if the article (`text`, its `words` as _words gives them) does not name this body."""
    low = re.sub(r"\s+", " ", text.lower())
    n = name.lower()
    if n in NAME_OK or n in low or n.replace("-", " ") in low.replace("-", " "):
        return False
    initials = "".join(w[0] for w in name.split() if w.lower() not in NAME_GENERIC).upper()
    if len(initials) >= 2 and re.search(r"\b" + re.escape(initials) + r"\b", text):
        return False
    # its words close together in any order ("Housing and Urban Affairs Ministry"), not spread over a sentence
    # ("International Criminal Court ... justice" is not the International Court of Justice)
    content = [w for w in _words(name) if not w[0].isdigit()]
    if not content:
        return True
    toks = [w[:6] for w in WORD_RE.findall(low)]
    pos = {}
    for i, w in enumerate(toks):
        pos.setdefault(w, []).append(i)
    if not all(w in pos for w in content):
        return True
    first = content[0]
    span = len(content) + 2
    return not any(all(any(abs(j - i) < span for j in pos[w]) for w in content[1:]) for i in pos[first])


def missing(names, text):
    ws = _words(text)
    return [n for n in names if body_missing(n, text, ws)]


DAYS = int(os.environ.get("DAYS") or 3)
try:
    up, m = upsc_db(), main_db()
    rows = up.execute("SELECT article_id, fact_box, prelims_pointers, why_in_news FROM upsc_articles WHERE published_at >= ? "
                      "ORDER BY published_at DESC", [int(time.time()) - DAYS * 86400]).rows
    arts = {r[0]: (r[1] or r[2] or "", decode(r[3]), decode(r[4])) for r in in_chunks(
        m, "SELECT id, rephrased_title, title, rephrased_article, content FROM articles WHERE id IN ({ph})", [r[0] for r in rows])}
    n_s = n_p = d_s = d_p = d_w = 0
    ex = []
    for aid, fb, ptrs, why in rows:
        a = arts.get(aid)
        if not a:
            continue
        title, reph, content = a
        body = reph if len(reph) >= 400 else (reph + "\n" + content)
        text = f"{title}\n{body[:2500]}"
        for sent in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])", fb or ""):
            if not sent.strip():
                continue
            n_s += 1
            miss = missing(body_names(sent), text)
            if miss:
                d_s += 1
                ex.append(f"- fact ({aid}): {sent[:160]} -> **{', '.join(miss)}**")
        try:
            pl = json.loads(ptrs) if ptrs else []
        except ValueError:
            pl = []
        for p in pl:
            t = (p or {}).get("text") or ""
            n_p += 1
            miss = missing(body_names(t), text)
            if miss:
                d_p += 1
                ex.append(f"- pointer ({aid}): {t[:160]} -> **{', '.join(miss)}**")
        if missing(body_names(why or ""), text):
            d_w += 1
    print(f"## Named-body check on {len(rows)} notes of the last {DAYS} days\n")
    print(f"- fact-box sentences: {d_s} of {n_s} would be dropped")
    print(f"- pointers: {d_p} of {n_p} would be dropped")
    print(f"- why-in-news lines that would be retried: {d_w}\n")
    print("\n".join(ex[:150]))
    print("\nPillay note 133529 fact box:", [n for n in body_names("She is currently a judge at the International Court of Justice and previously worked at the International Criminal Tribunal for Rwanda.")])
finally:
    close_all()
