"""Load news articles (title + decoded body) from the main DB for the SSC runner."""
import zlib

from common.db import in_chunks, main_db


def decode(blob):
    if blob is None:
        return ""
    if isinstance(blob, (bytes, bytearray, memoryview)):
        try:
            return zlib.decompress(bytes(blob)).decode("utf-8")
        except zlib.error:
            return bytes(blob).decode("utf-8", "ignore")
    return str(blob)


def load(ids):
    m = main_db()
    arts = {}
    for aid, title, orig, reph, content, cat, pub, cluster in in_chunks(
            m, "SELECT id, rephrased_title, title, rephrased_article, content, category, scraped_at, cluster_id "
               "FROM articles WHERE id IN ({ph})", ids):
        body = decode(reph)
        if len(body) < 400:
            body = (body + "\n" + decode(content)).strip()
        arts[int(aid)] = {"id": int(aid), "title": (title or orig or "").strip(), "original_title": (orig or "").strip(),
                          "body": body, "category": cat, "published_at": int(pub or 0), "cluster_id": cluster}
    return arts
