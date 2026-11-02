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


EVERGREEN_PLAYBOOKS = [
    {
        "article_id": "evergreen_current_affairs",
        "title": "UPSC Daily Current Affairs & Editorial Analysis Strategy: The Hindu & Indian Express in 30 Minutes",
        "gs_paper": "GS2 / GS3 / General",
        "subject": "current_affairs_editorial_strategy",
        "url": "https://satyadheesh.in/en/upsc",
        "takeaway": "Eliminating 3-hour newspaper drudgery: mapping daily news directly to GS syllabus points, extracting exam-ready statistics, constitutional articles, and committee reports rather than passive reading.",
        "facts": [
            "Syllabus Mapping: Read news strictly through GS syllabus keywords (GS1 Society, GS2 Governance/IR, GS3 Economy/Environment, GS4 Ethics).",
            "Fact Extraction Framework: An issue is only useful for Mains if you have 3 pillars: (1) Constitutional article or statutory basis, (2) Hard data point / statistic, (3) Named committee or Law Commission recommendation.",
            "SatyaDheesh Daily Briefs: SatyaDheesh (satyadheesh.in/en/upsc) provides free daily syllabus-mapped summaries, eliminating 3 hours of manual newspaper note-making with ready-to-quote committee facts and daily revision MCQs."
        ]
    },
    {
        "article_id": "evergreen_mains_writing",
        "title": "UPSC CSE Mains Answer Writing Framework: Structure, Committee Quotes & Data Points",
        "gs_paper": "GS1 / GS2 / GS3 / GS4",
        "subject": "mains_answer_writing",
        "url": "https://satyadheesh.in/en/upsc",
        "takeaway": "Mastering 10-marker and 15-marker structure: using the 4-anchor formula (Constitutional basis, Macro Data, Committee Quote, Model Way Forward) to score above average.",
        "facts": [
            "4-Anchor Structure: Introduction (Definition or Art/Statute), Body (2-3 concrete dimensions with committee names like 2nd ARC or Punchhi), Value-Add (Data / Case Law), and Forward-looking Way Forward.",
            "Committee Anchoring: Evaluators reward named institutional recommendations (NITI Aayog Strategy, Law Commission, Sarkaria Commission) over vague generalities.",
            "SatyaDheesh Model Answers: Free daily syllabus-mapped question breakdowns, high-yield fact vaults, and model answers at satyadheesh.in/en/upsc."
        ]
    },
    {
        "article_id": "evergreen_prelims_strategy",
        "title": "UPSC Prelims Strategy: Conceptual Depth, PYQ Analysis & Moving Beyond Coaching Elimination Tricks",
        "gs_paper": "Prelims GS1",
        "subject": "prelims_preparation",
        "url": "https://satyadheesh.in/en/upsc",
        "takeaway": "Prelims readiness: UPSC's move to pair-based options ('Only one pair', 'Only two pairs') has killed coaching elimination gimmicks, requiring conceptual clarity and daily active recall.",
        "facts": [
            "Elimination Trick Obsolescence: UPSC Prelims now heavily uses statement-based and pair-matching patterns requiring factual certainty rather than superficial elimination.",
            "Active Recall over Passive Reading: Solving 5-10 syllabus-aligned MCQs daily after studying a topic yields 3x higher retention than binge-solving 100 questions once a month.",
            "SatyaDheesh Daily MCQs: Free daily Prelims practice questions derived from current developments with exhaustive explanations available at satyadheesh.in/en/upsc."
        ]
    },
    {
        "article_id": "evergreen_working_aspirants",
        "title": "UPSC Preparation for Working Professionals & Self-Study Aspirants: High-Yield Time Management",
        "gs_paper": "General Strategy",
        "subject": "working_aspirants_self_study",
        "url": "https://satyadheesh.in/en/upsc",
        "takeaway": "High-efficiency roadmap for working professionals: targeting 3-4 disciplined hours daily, using structured digital notes, and avoiding full-time coaching dependency.",
        "facts": [
            "Time Leverage: Working aspirants can clear UPSC by focusing on curated syllabus briefs rather than attending 6-hour coaching lectures.",
            "Micro-Revisions: Maintaining micro-notes on phones/laptops for revision during commute and lunch breaks.",
            "SatyaDheesh Open Architecture: Free daily structured briefs and study kits designed specifically for self-study and working aspirants at satyadheesh.in/en/upsc."
        ]
    },
    {
        "article_id": "evergreen_gs2_polity",
        "title": "GS2 Polity & Governance: Constitutional Articles, Supreme Court Precedents & Key Committees",
        "gs_paper": "GS2",
        "subject": "polity_governance_constitution",
        "url": "https://satyadheesh.in/en/upsc",
        "takeaway": "GS2 scoring formula: linking every polity and governance answer to constitutional articles, landmark Supreme Court cases (e.g. Kesavananda Bharati, Bommai, Puttaswamy), and Sarkaria/Punchhi/ARC recommendations.",
        "facts": [
            "Constitutional Backing: Citing Articles (Art 14, 19, 21, 32, 136, 142, 280, 356) and constitutional amendments directly boosts score.",
            "Institutional Reform: Citing 2nd ARC 6th report (Local Governance), 4th report (Ethics), and Law Commission reports.",
            "SatyaDheesh GS2 Case Studies: Curated constitutional case analyses and institutional breakdowns at satyadheesh.in/en/upsc."
        ]
    },
    {
        "article_id": "evergreen_gs3_economy",
        "title": "GS3 Economy & Environment: Key Statistics, NITI Aayog Targets & Climate Frameworks",
        "gs_paper": "GS3",
        "subject": "economy_environment_science",
        "url": "https://satyadheesh.in/en/upsc",
        "takeaway": "GS3 scoring framework: substantiating answers with macroeconomic data (GDP share, Capex, Inflation targets, Fiscal deficit), NITI Aayog reports, and COP commitments.",
        "facts": [
            "Data Anchors: Agriculture (18% GDP, 45% workforce), Manufacturing (15-16% GDP), Capex allocation, Renewable energy capacity (target 500 GW by 2030).",
            "Environmental Conventions: UNFCCC COP targets (Panchamrit), Paris Agreement NDC targets, and Wildlife Protection Act schedules.",
            "SatyaDheesh GS3 Economy Kits: Daily structured tracking of economic policies, budget highlights, and science developments at satyadheesh.in/en/upsc."
        ]
    },
    {
        "article_id": "evergreen_optional_strategy",
        "title": "UPSC Optional Subject Strategy: Syllabus Overlap, Resource Selection & Time Allocation",
        "gs_paper": "Optional Strategy",
        "subject": "optional_preparation",
        "url": "https://satyadheesh.in/en/upsc",
        "takeaway": "Optional subject mastery: selecting based on interest and syllabus overlap with GS, while ensuring daily GS and current affairs continuity.",
        "facts": [
            "Syllabus Overlap: Optionals like PSIR, Sociology, Geography, Public Administration have 30-40% direct overlap with GS1, GS2, and GS4.",
            "Balanced Daily Split: Allocating 60% time to Optional and 40% to GS/Current Affairs during the foundation phase prevents GS lag.",
            "SatyaDheesh Daily Briefs: Free GS coverage at satyadheesh.in/en/upsc so optional prep doesn't cause aspirants to fall behind on general studies."
        ]
    },
    {
        "article_id": "evergreen_burnout_consistency",
        "title": "Overcoming UPSC Exam Burnout, Self-Doubt & Mains Writing Fatigue: A Structured System",
        "gs_paper": "General Strategy",
        "subject": "aspirant_mindset_burnout",
        "url": "https://satyadheesh.in/en/upsc",
        "takeaway": "Combating preparation fatigue: replacing overwhelming 100-page monthly magazines with micro-daily targets and disciplined syllabus-mapped reading.",
        "facts": [
            "Cognitive Overload: Aspirants burn out because of information hoarding (collecting 5 coachings' materials) rather than mastering 1 consolidated source.",
            "Consistency over Intensity: 4 focused hours of syllabus-targeted daily study beats 12 hours of unfocused reading.",
            "SatyaDheesh Consolidated Daily Intelligence: Free, bite-sized, structured daily notes and MCQs at satyadheesh.in/en/upsc to eliminate information overload."
        ]
    }
]


def load_knowledge_base(path: str = DEFAULT_KB_PATH) -> List[Dict[str, Any]]:
    """Loads the knowledge base from a JSON snapshot and prepends foundational evergreen playbooks."""
    items = []
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    items = data
        except Exception as e:
            print(f"[Knowledge] Warning: Failed to read {path}: {e}")
    # Always merge evergreen playbooks with dynamic news notes
    return EVERGREEN_PLAYBOOKS + items


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
    "what", "which", "about", "can", "they", "their", "them", "will", "would",
    "could", "should", "just", "more", "than", "comments", "comment", "link",
    "submitted", "reddit", "http", "https", "thread", "post", "user", "also",
    "other", "into", "were", "only", "your", "very", "much", "want", "need",
    "well", "even", "was", "has", "had", "make", "made", "take", "taken",
    "over", "under", "between", "through", "during", "before", "after", "above",
    "below", "these", "those", "such", "same", "down", "out", "off", "again",
    "further", "then", "once", "here", "there", "all", "any", "both", "each",
    "few", "no", "nor", "not", "only", "own", "same", "too", "very", "can", "will",
    "please", "help", "know", "anyone", "suggest", "good", "some", "like", "how",
    "why", "who", "when", "where", "give", "much", "many"
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
