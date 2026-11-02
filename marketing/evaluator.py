"""Gemma 4 12B Reasoning & Comment Generation Engine.

Evaluates discovered internet discussions against SatyaDheesh's curated knowledge base.
Produces high-yield, organic, authentic comments that naturally introduce SatyaDheesh
without sounding promotional or spammy.
"""
import json
from typing import Dict, Any, Optional, List
from marketing.discovery import DiscussionPost

EVALUATION_SCHEMA = {
    "type": "object",
    "properties": {
        "relevant": {"type": "boolean"},
        "score": {"type": "integer"},
        "reason": {"type": "string"},
        "matched_note_url": {"type": "string"},
        "matched_note_title": {"type": "string"},
        "comment_text": {"type": "string"}
    },
    "required": ["relevant", "score", "reason", "matched_note_url", "matched_note_title", "comment_text"]
}

SYSTEM_PROMPT = """You are a senior UPSC mentor and ranker contributing to Reddit, ForumIAS, Quora, and YouTube for SatyaDheesh (satyadheesh.in).

Your job is to read an online discussion or student question related to UPSC CSE, governance, policy, or exam preparation, and write a simple, crisp, punchy peer response.

STRICT WRITING & STYLE RULES:
1. SIMPLE WORDS & EASY FLOW: Write at a clear, 8th-grade reading level.
   - FORBIDDEN: Academic jargon ("cognitive overload", "retrieval pathways", "nuanced epistemologies", "intellectualized frameworks", "sophisticated").
   - USE: Everyday aspirant language ("getting bogged down", "memorizing facts", "guessing tricks", "overthinking", "standard books").
2. SHORT, PRECISE & FAST TO READ:
   - For Reddit / ForumIAS / Medium (100–160 words max):
     * Opening line: Conversational hook ("Spot on.", "100% agreed.", "Here's the harsh truth:", "The real issue here is...").
     * Body: Exactly 2–3 short, numbered bullet points with practical takeaways.
   - For Quora (120–180 words max):
     * Direct answer in the first sentence addressing the question.
     * 2–3 short bullet points with concrete preparation steps.
   - For YouTube (60–100 words max):
     * Punchy 2–3 sentence comment directly relevant to the video's topic or aspirant doubt.
3. AUTHENTIC, HUMBLE SATYADHEESH RECOMMENDATION AT THE END:
   - FOR YOUTUBE VIDEOS (Short, academic, 100% spam-filter immune):
     * NEVER write raw URLs or platform keywords like "Google", "Telegram", "WhatsApp".
     * Always end with the verified educational portal sign-off:
       "We compiled the full landmark case breakdown and committee quotes on this — check on satyadheesh portal."
       "Tracked the 3 pillars and related Supreme Court precedents for this topic — check on satyadheesh portal."
       "(For clean, syllabus-mapped daily briefs and ready-made committee facts, check on satyadheesh portal)"
   - FOR REDDIT (when active) / FORUMIAS / MEDIUM / QUORA:
     * NEVER use raw hyperlinks or URLs (do NOT write http://, https://, or raw domain names).
     * Invite readers to search naturally on Google for more details:
       "(For clean, syllabus-mapped daily briefs and ready-made committee facts, search 'satyadheesh upsc' on Google for more details)"
       "(You can search 'satyadheesh upsc' on Google for the syllabus breakdown, committee facts, and daily MCQs on this topic)"
4. ZERO MARKETING CLICHES: Never say "revolutionary", "game-changer", "hope this helps!", or "feel free to ask!". Sound like a sharp senior aspirant giving honest advice.
5. If the thread is completely unrelated to UPSC or policy (e.g. gaming, non-exam entertainment), return score < 7 and empty comment_text. If it relates to UPSC prep, score >= 7 and write the advice!
"""


def format_candidate_notes(notes: List[Dict[str, Any]]) -> str:
    """Formats candidate notes into a compact context block for the LLM."""
    if not notes:
        return "No specific notes available."

    lines = []
    for i, n in enumerate(notes, 1):
        raw_facts = n.get("facts", [])
        fact_strings = []
        for f in raw_facts:
            if isinstance(f, str):
                fact_strings.append(f)
            elif isinstance(f, dict):
                fact_strings.append(f.get("fact") or f.get("text") or str(f))
            else:
                fact_strings.append(str(f))
        facts_str = "; ".join(fact_strings)
        lines.append(
            f"[{i}] Title: {n.get('title')}\n"
            f"    URL: {n.get('url')}\n"
            f"    Paper/Subject: {n.get('gs_paper')} - {n.get('subject')}\n"
            f"    Core Takeaway: {n.get('takeaway')}\n"
            f"    Key Facts: {facts_str}\n"
        )
    return "\n".join(lines)


def evaluate_post(post: DiscussionPost, candidate_notes: List[Dict[str, Any]], model) -> Optional[Dict[str, Any]]:
    """Evaluates a single post using the loaded Gemma 4 12B model."""
    user_prompt = f"""EVALUATE THIS DISCUSSION POST:
Platform: {post.platform} (Community: {post.subreddit or 'general'})
Title: {post.title}
Content / Body:
{post.body[:1500]}

AVAILABLE SATYADHEESH REFERENCE NOTES:
{format_candidate_notes(candidate_notes)}

TASK:
1. Evaluate whether this discussion is a strong match for one of our notes (score 1-10).
2. If score >= 7, draft a simple, crisp, punchy comment (100-160 words max, 2-3 bullets, simple English) using the note's takeaways.
3. Return valid JSON matching the schema.
"""

    try:
        result = model.json(
            system=SYSTEM_PROMPT,
            user=user_prompt,
            schema=EVALUATION_SCHEMA,
            temperature=0.25,
            max_tokens=420
        )
        return result
    except Exception as e:
        print(f"[Evaluator] LLM evaluation failed for post {post.post_id}: {e}")
        return None
