"""Last-24-hours stories per source for the newspaper-style PDFs (paper/)."""
import time
import zlib

from common.db import in_chunks

# Newspapers we make an edition for (name in `sources`, short file slug, Hindi name). An edition is only made when
# the window has at least MIN_STORIES of its stories.
PAPERS = [
    ("The Hindu", "thehindu", "द हिंदू"),
    ("Times of India", "toi", "टाइम्स ऑफ़ इंडिया"),
    ("Economic Times", "et", "इकनॉमिक टाइम्स"),
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


def window(main, trans, hours=24, now=None):
    """All stories of the last `hours` (every source), with Hindi where translated, and a 'weight' (cluster size:
    a story many outlets carry is a big story)."""
    now = now or int(time.time())
    rows = main.execute(
        "SELECT a.id, s.name, a.rephrased_title, a.title, a.rephrased_article, a.category, a.cluster_id, a.scraped_at, "
        "a.url FROM articles a LEFT JOIN sources s ON a.source_id = s.id WHERE a.scraped_at >= ? "
        "AND a.rephrased_article IS NOT NULL", [now - hours * 3600]).rows
    items = []
    for r in rows:
        body = text(r[4]).strip()
        title = (text(r[2]) or text(r[3])).strip()
        if not body or not title:
            continue
        items.append({"id": r[0], "source": r[1], "title": title, "body": body, "category": (r[5] or "other").lower(),
                      "cluster": r[6], "ts": r[7], "url": r[8]})
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


def edition(items, source, lang):
    """The stories of one paper in one language, best first."""
    out = [i for i in items if i["source"] == source and (lang == "en" or i.get("body_hi"))]
    return sorted(out, key=lambda i: (-i["score"], -i["ts"]))
