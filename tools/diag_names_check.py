"""READ-ONLY: how often the UPSC service's new named-body check (v2.8) would drop a fact-box sentence or pointer of
recent notes, with examples, so the rule can be tuned before it goes live. DAYS env (default 2)."""
import json
import os
import re
import time

from common.db import close_all, in_chunks, main_db, upsc_db
from sscca.articles import decode

NAME_RE = re.compile(r"\b[A-Z][a-z]+(?:[- ](?:(?:of|for|and|on|the|de|in)[- ])*[A-Z][a-z]+){1,6}\b")
NAME_OK = {"prime minister", "chief minister", "union minister", "supreme court", "high court", "lok sabha", "rajya sabha",
           "union cabinet", "government of india", "union government", "central government", "finance minister",
           "home minister", "external affairs minister", "deputy chief minister", "chief justice", "united nations",
           "united states", "united kingdom", "european union", "south africa", "new delhi", "sri lanka", "saudi arabia",
           "south korea", "north korea", "new zealand", "united arab emirates", "middle east", "south asia",
           "indian ocean", "bay of bengal", "arabian sea"}
NAME_GENERIC = {"the", "of", "for", "and", "on", "de", "in"}
NAME_START = {"the", "this", "these", "its", "his", "her", "under", "with", "after", "both", "on", "in", "at", "from",
              "as", "by", "while", "a", "an", "it", "she", "he", "they"}


def body_names(text):
    """Multi-word proper names in `text` (2+ capitalised words), without a sentence-opening word."""
    out = []
    for m in NAME_RE.finditer(text or ""):
        words = m.group().split()
        while words and words[0].lower() in NAME_START:
            words = words[1:]
        if len([w for w in words if w.lower() not in NAME_GENERIC]) >= 2:
            out.append(" ".join(words))
    return out




def missing(names, text):
    low = re.sub(r"\s+", " ", text.lower())
    out = []
    for name in names:
        n = name.lower()
        initials = "".join(w[0] for w in name.split() if w.lower() not in NAME_GENERIC).upper()
        if n in NAME_OK or n in low or n.replace("-", " ") in low.replace("-", " ") or re.search(r"\b" + initials + r"\b", text):
            continue
        out.append(name)
    return out


DAYS = int(os.environ.get("DAYS") or 2)
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
finally:
    close_all()
