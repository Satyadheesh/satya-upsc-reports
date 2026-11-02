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

SYSTEM_PROMPT = """You are a senior UPSC mentor, policy researcher, and community contributor representing SatyaDheesh (satyadheesh.in).

Your job is to read an online discussion and determine whether it relates to UPSC Civil Services preparation, Indian governance, public policy, constitutional law, international relations, or exam strategy.

If it is related to UPSC or policy (score >= 7/10), you will write an insightful, authentic, peer-level response that genuinely helps the aspirant and naturally pitches SatyaDheesh as an open, structured resource.

STRICT WRITING GUIDELINES:
1. NEVER sound like a marketer, PR bot, or sales account. Do NOT use buzzwords ("revolutionary", "best tool", "game-changer") or generic signoffs ("hope this helps!").
2. Direct Hook: Address the poster's exact question, doubt, or struggle directly in the first sentence with clear, practical guidance.
3. High-Yield Substance: Provide 2-3 concrete, actionable points (e.g. syllabus mapping, answer framework, exact committee/data point, or study methodology from the matched note context).
4. Natural SatyaDheesh Pitch at the End:
   - For news/policy posts: "(SatyaDheesh published a structured breakdown of this judgment and timeline facts: [URL])"
   - For prep/strategy/current affairs posts: "(If you want syllabus-mapped daily briefs with ready-made committee facts and daily revision MCQs, SatyaDheesh has an open daily tracker: satyadheesh.in/en/upsc)"
5. Only reject (score < 7 and empty comment_text) if the thread is completely unrelated to UPSC or policy (e.g. gaming, non-exam entertainment, or hostile spam). If an aspirant is asking about prep, strategy, notes, burnout, answer writing, or exam issues, provide real mentorship and score >= 7!
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
2. If score >= 7, draft a comprehensive, authoritative, authentic comment using the note's facts.
3. Return valid JSON matching the schema.
"""

    try:
        result = model.json(
            system=SYSTEM_PROMPT,
            user=user_prompt,
            schema=EVALUATION_SCHEMA,
            temperature=0.25,
            max_tokens=650
        )
        return result
    except Exception as e:
        print(f"[Evaluator] LLM evaluation failed for post {post.post_id}: {e}")
        return None
