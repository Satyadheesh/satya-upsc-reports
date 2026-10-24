"""Last-24-hours stories per source for the newspaper-style PDFs (paper/)."""
import re
import time
import zlib

from common.db import in_chunks

# Newspapers we make an edition for (name in `sources`, short file slug, Hindi name). An edition is only made when
# the window has at least MIN_STORIES of its stories.
PAPERS = [
    ("The Hindu", "thehindu", "द हिंदू"),
    ("Times of India", "toi", "द टाइम्स ऑफ़ इंडिया"),
    ("Economic Times", "et", "द इकनॉमिक टाइम्स"),
    ("Indian Express", "indianexpress", "इंडियन एक्सप्रेस"),
    ("Livemint", "mint", "मिंट"),
    ("Deccan Herald", "deccanherald", "डेक्कन हेराल्ड"),
    ("The Tribune", "tribune", "द ट्रिब्यून"),
    ("The Telegraph", "telegraph", "द टेलीग्राफ"),
]
MIN_STORIES = 8

SECTIONS = [  # (key, English, Hindi, categories)
    ("nation", "Nation", "देश", {"politics", "regional"}),
    ("law", "Law & Order", "क़ानून-व्यवस्था", {"crime"}),
    ("business", "Business", "कारोबार", {"economy"}),
    ("world", "World", "दुनिया", {"international"}),
    ("society", "Education · Health · Environment", "शिक्षा · स्वास्थ्य · पर्यावरण", {"education", "health", "environment"}),
    ("sport", "Sport", "खेल", {"sports"}),
    ("more", "More News", "और ख़बरें", None),
]
WEIGHT = {"politics": 2, "economy": 2, "international": 1, "regional": 1, "crime": 0.5, "education": 1, "health": 1,
          "environment": 1}


def text(v):
    if v is None:
        return ""
    if isinstance(v, (bytes, bytearray, memoryview)):
        b = bytes(v)
        try:
            return zlib.decompress(b).decode("utf-8")
        except Exception:
            return b.decode("utf-8", "replace")
    return str(v)


# ---- the original article text (personal-use edition): strip site furniture and make paragraphs
_CUT = [r"\(You can now subscribe", r"Subscribe to ET Prime", r"Also, ETMarkets\.com is now on Telegram", r"Top Trending Stocks:",
        r"\(Disclaimer", r"Download The Economic Times", r"Catch all the", r"Read More News on", r"Follow the live updates below:",
        r"Watch: ", r"Also Read:", r"FOLLOW US ON SOCIAL MEDIA"]
_DROP = [r"Listen to this article in summarized format\s*", r"Published\s*-\s*\w+ \d{1,2}, \d{4} \d{1,2}:\d{2} [ap]m IST\s*",
         r"\|\s*Photo Credit:\s*(?:(?!(?:The|A|An|In|On|It|He|She|They|This|Its|According|Meanwhile|Shares|Earlier)\b)[A-Z][\w.\-’']*\s?){1,4}", r"Also read \|[^|]{0,160}?(?= (?:The|A|An|In|On|It|He|She|They|This|Its|According|Meanwhile|Shares|Earlier)\b)", r"\(This story has not been edited[^)]*\)"]
_ABBR = {"mr", "ms", "mrs", "dr", "st", "rs", "no", "vs", "jr", "sr", "lt", "gen", "col", "prof", "capt", "maj", "hon",
         "govt", "dept", "inc", "ltd", "co", "u.s", "u.k", "a.m", "p.m", "approx", "fig", "nos", "sh", "smt", "shri", "e.g", "i.e"}
_END = re.compile(r"[.!?][\"”’]?\s+(?=[\"“‘(]?[A-Z0-9])")


def sentences(c):
    out, start = [], 0
    for m in _END.finditer(c):
        word = re.findall(r"([\w.]+)$", c[start:m.start()])
        w = (word[0] if word else "").lower()
        if w in _ABBR or (len(w) == 1 and w.isalpha()):
            continue   # "Mr." / "T." initials: not a sentence end
        out.append(c[start:m.end()].strip()); start = m.end()
    if c[start:].strip():
        out.append(c[start:].strip())
    return out


MAX_ORIG = 7000


def clean_original(c, title, source):
    c = " ".join((c or "").split())
    if not c:
        return []
    if title and c.lower().startswith(title.lower()[:60]):
        c = c[len(title):].lstrip(" :-–")
    for pat in _CUT:
        m = re.search(pat, c)
        if m and m.start() > 300:
            c = c[:m.start()]
    for pat in _DROP:
        c = re.sub(pat, " ", c)
    c = " ".join(c.split())
    sents = sentences(c)
    out, n = [], 0
    for x in sents:
        if n + len(x) > MAX_ORIG and n > 1500:
            break
        out.append(x); n += len(x)
    paras, cur = [], []
    for x in out:
        cur.append(x)
        if len(cur) == 3 or sum(len(y) for y in cur) > 420:
            paras.append(" ".join(cur)); cur = []
    if cur:
        paras.append(" ".join(cur))
    return paras


def image_variant(url, wide=False):
    """A print-sized version of the publisher image (smaller PDF)."""
    if not url:
        return ""
    if "thgim.com" in url:
        return re.sub(r"/alternates/[A-Z_0-9]+/", "/alternates/" + ("LANDSCAPE_1200" if wide else "LANDSCAPE_615") + "/", url)
    if "etimg.com" in url or "toiimg.com" in url:
        return re.sub(r"width-\d+,height-\d+", "width-1000,height-563" if wide else "width-600,height-338", url)
    return url


def window(main, trans, hours=24, now=None):
    """All stories of the last `hours` (every source), with Hindi where translated, and a 'weight' (cluster size:
    a story many outlets carry is a big story)."""
    now = now or int(time.time())
    rows = main.execute(
        "SELECT a.id, s.name, a.rephrased_title, a.title, a.rephrased_article, a.category, a.cluster_id, a.scraped_at, "
        "a.url, a.content, a.image_url FROM articles a LEFT JOIN sources s ON a.source_id = s.id WHERE a.scraped_at >= ? "
        "AND a.rephrased_article IS NOT NULL", [now - hours * 3600]).rows
    items = []
    for r in rows:
        body = text(r[4]).strip()
        title = (text(r[2]) or text(r[3])).strip()
        if not body or not title:
            continue
        orig_title = text(r[3]).strip() or title
        items.append({"id": r[0], "source": r[1], "title": title, "body": body, "category": (r[5] or "other").lower(),
                      "cluster": r[6], "ts": r[7], "url": r[8], "orig_title": orig_title,
                      "orig": clean_original(text(r[9]), orig_title, r[1]), "image": r[10] or ""})
    sizes = {}
    for it in items:
        if it["cluster"]:
            sizes[it["cluster"]] = sizes.get(it["cluster"], 0) + 1
    for it in items:
        it["score"] = 3 * sizes.get(it["cluster"], 1) + WEIGHT.get(it["category"], 0) + min(len(it["body"]), 900) / 300
    if trans is not None and items:
        hi = {r[0]: (text(r[1]).strip(), text(r[2]).strip()) for r in
              in_chunks(trans, "SELECT article_id, rephrased_title_hi, rephrased_article_hi FROM translations "
                               "WHERE article_id IN ({ph})", [i["id"] for i in items])}
        for it in items:
            t, b = hi.get(it["id"], ("", ""))
            if t and b:
                it["title_hi"], it["body_hi"] = t, b
    return items


def _key(title):
    return " ".join(re.findall(r"\w+", title.lower())[:7])


def edition(items, source, lang):
    """The stories of one paper in one language, best first; one story per event (cluster) and no repeated
    headlines (the same report is often scraped twice)."""
    out = [i for i in items if i["source"] == source and (lang == "en" or i.get("body_hi"))]
    out.sort(key=lambda i: (-i["score"], -i["ts"]))
    seen_c, seen_t, keep = set(), set(), []
    for i in out:
        k = _key(i["title"])
        if (i["cluster"] and i["cluster"] in seen_c) or k in seen_t:
            continue
        seen_c.add(i["cluster"]); seen_t.add(k)
        keep.append(i)
    return keep
