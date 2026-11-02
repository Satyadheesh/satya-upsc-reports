"""Knowledge Base Manager for SatyaDheesh content.

Maintains a static snapshot of recent high-scoring UPSC articles and kits so
the marketing scout can reference authentic facts and URLs with ZERO database reads.
"""
import json
import os
import re
from typing import List, Dict, Any, Optional

DEFAULT_KB_PATH = os.path.join(os.path.dirname(__file__), "knowledge_base.json")
BASE_URL = os.environ.get("SATYA_BASE_URL", "https://satyadheesh.in")


def load_knowledge_base(path: str = DEFAULT_KB_PATH) -> List[Dict[str, Any]]:
    """Loads the knowledge base from a JSON snapshot."""
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception as e:
            print(f"[Knowledge] Warning: Failed to read {path}: {e}")
    return []


def save_knowledge_base(items: List[Dict[str, Any]], path: str = DEFAULT_KB_PATH) -> None:
    """Saves items to the knowledge base snapshot."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)
    print(f"[Knowledge] Saved {len(items)} notes to {path}")


def export_from_db(db_url: Optional[str] = None, db_token: Optional[str] = None, limit: int = 40) -> List[Dict[str, Any]]:
    """Exports recent high-yield notes from the UPSC DB into the knowledge base format.
    Uses indexed ORDER BY to ensure minimal row scans.
    """
    db_url = db_url or os.environ.get("SATYA_UPSC_DB_URL") or os.environ.get("NEW_UPSC_DB_URL")
    db_token = db_token or os.environ.get("SATYA_UPSC_DB_TOKEN") or os.environ.get("NEW_UPSC_DB_TOKEN")

    if not db_url:
        print("[Knowledge] No DB URL found, cannot export from live DB.")
        return []

    try:
        import urllib.request
        clean_url = db_url.replace("libsql://", "https://").replace("wss://", "https://")
        req = urllib.request.Request(f"{clean_url}/v2/pipeline")
        req.add_header("Authorization", f"Bearer {db_token}")
        req.add_header("Content-Type", "application/json")

        sql = (
            "SELECT a.article_id, a.published_at, a.gs_paper, a.subject, a.syllabus_node, "
            "k.short_title, k.takeaway, k.brief_lead, k.facts "
            "FROM upsc_articles a "
            "JOIN upsc_kit k ON a.article_id = k.article_id "
            "WHERE k.status = 'done' "
            "ORDER BY a.published_at DESC LIMIT ?"
        )
        body = json.dumps({"requests": [{"type": "execute", "stmt": {"sql": sql, "args": [{"type": "integer", "value": str(limit)}]}}]}).encode("utf-8")

        with urllib.request.urlopen(req, data=body, timeout=15) as resp:
            data = json.load(resp)
            rows = data["results"][0]["response"]["result"]["rows"]

        items = []
        for r in rows:
            article_id = str(r[0]["value"])
            published_at = r[1]["value"]
            gs_paper = r[2]["value"] or "GS"
            subject = r[3]["value"] or "General Studies"
            short_title = r[5]["value"] or ""
            takeaway = r[6]["value"] or ""
            lead = r[7]["value"] or ""
            raw_facts = r[8]["value"] if len(r) > 8 and r[8] else ""

            facts = []
            if raw_facts:
                try:
                    parsed = json.loads(raw_facts)
                    if isinstance(parsed, list):
                        facts = parsed
                    elif isinstance(parsed, dict) and "facts" in parsed:
                        facts = parsed["facts"]
                except Exception:
                    facts = [f.strip() for f in raw_facts.split("\n") if f.strip()]

            note_url = f"{BASE_URL}/en/upsc/note/{article_id}"
            items.append({
                "article_id": article_id,
                "title": short_title,
                "gs_paper": gs_paper,
                "subject": subject,
                "published_at": published_at,
                "url": note_url,
                "takeaway": takeaway,
                "lead": lead,
                "facts": facts[:6] if facts else []
            })
        return items
    except Exception as e:
        print(f"[Knowledge] Query error: {e}")
        return []


STOPWORDS = {
    "the", "and", "for", "with", "this", "that", "from", "are", "have", "been",
    "what", "which", "about", "can", "upsc", "mains", "prelims", "india", "indian",
    "delhi", "exam", "paper", "cse", "aspirants", "studies", "general", "today",
    "news", "daily", "notes", "please", "help", "know", "anyone", "suggest", "good",
    "teacher", "planning", "give", "some", "like", "how", "why", "who", "when", "where",
    "they", "their", "them", "will", "would", "could", "should", "just", "more", "than",
    "comments", "comment", "link", "submitted", "reddit", "http", "https", "thread",
    "post", "user", "also", "other", "into", "were", "only", "your", "very", "much",
    "want", "need", "well", "even", "most", "many", "time", "year", "years", "was",
    "has", "had", "topic", "series", "test", "tests", "make", "made", "take", "taken",
    "over", "under", "between", "through", "during", "before", "after", "above", "below",
    "these", "those", "such", "same", "down", "out", "off", "again", "further", "then",
    "once", "here", "there", "all", "any", "both", "each", "few", "more", "most", "other",
    "some", "such", "no", "nor", "not", "only", "own", "same", "too", "very", "can", "will"
}


def tokenize(text: str) -> set:
    """Simple tokenization for fast keyword matching with stopword suppression."""
    text = (text or "").lower()
    words = re.findall(r"\b[a-z0-9]{3,}\b", text)
    return {w for w in words if w not in STOPWORDS}


def _stringify_facts(facts: Any) -> str:
    """Safely extracts text from facts which could be strings or dicts."""
    if not facts:
        return ""
    parts = []
    for f in facts:
        if isinstance(f, str):
            parts.append(f)
        elif isinstance(f, dict):
            parts.append(f.get("fact") or f.get("text") or str(f))
        else:
            parts.append(str(f))
    return " ".join(parts)


def find_candidate_notes_with_overlap(query_text: str, kb: List[Dict[str, Any]], top_k: int = 4, min_overlap: int = 2) -> List[tuple]:
    """Scores knowledge base notes against a query text (thread title + body).
    Returns list of (overlap_count, sorted_overlap_tokens, note) sorted descending by overlap.
    Requires at least `min_overlap` distinct keywords to prevent false positives.
    """
    if not kb:
        return []

    q_tokens = tokenize(query_text)
    if not q_tokens:
        return []

    scored = []
    for item in kb:
        facts_text = _stringify_facts(item.get("facts", []))
        doc_tokens = tokenize(
            f"{item.get('title', '')} {item.get('subject', '')} {item.get('takeaway', '')} {facts_text}"
        )
        overlap = q_tokens.intersection(doc_tokens)
        if len(overlap) >= min_overlap:
            scored.append((len(overlap), sorted(list(overlap)), item))

    # Sort descending by token overlap count
    scored.sort(key=lambda x: x[0], reverse=True)
    if scored:
        return scored[:top_k]
    return []


def find_candidate_notes(query_text: str, kb: List[Dict[str, Any]], top_k: int = 4, min_overlap: int = 2) -> List[Dict[str, Any]]:
    """Convenience wrapper returning just the list of matched note dicts."""
    candidates = find_candidate_notes_with_overlap(query_text, kb, top_k=top_k, min_overlap=min_overlap)
    return [item for _, _, item in candidates]
