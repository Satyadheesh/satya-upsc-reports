"""Marketing Scout Agent Entrypoint.

Discovers relevant discussions, evaluates them using Gemma 4 12B,
and enqueues high-yield, contextual drafts for local publishing.
"""
import argparse
import os
import sys

from marketing.discovery import discover_all
from marketing.evaluator import evaluate_post
from marketing.knowledge import load_knowledge_base, export_from_db, save_knowledge_base, find_candidate_notes
from marketing.queue_mgr import is_seen, load_history, enqueue_draft


def run_scout(limit_per_source: int = 15, max_drafts: int = 5, dry_run: bool = False):
    print("=== [SatyaDheesh Marketing Scout] Starting Run ===")

    # 1. Load or build knowledge base
    kb = load_knowledge_base()
    if not kb:
        print("[Agent] Knowledge base snapshot empty, checking for DB export...")
        kb = export_from_db(limit=40)
        if kb:
            save_knowledge_base(kb)

    if not kb:
        print("[Agent] ERROR: No knowledge base available. Please provide knowledge_base.json or DB credentials.")
        return

    print(f"[Agent] Loaded {len(kb)} notes in Knowledge Base.")

    # 2. Discover discussions
    history = load_history()
    print(f"[Agent] Total posts in history: {len(history)}")

    posts = discover_all(max_per_source=limit_per_source)
    new_posts = [p for p in posts if not is_seen(p.post_id, history)]
    print(f"[Agent] {len(new_posts)} unhandled discussions after history deduplication.")

    if not new_posts:
        print("[Agent] No new discussions found today. Scout run complete.")
        return

    # 3. Load Gemma Model
    print("[Agent] Initializing Gemma 4 12B reasoning model...")
    try:
        from kit.model import download, Model
        model_path = download()
        model = Model(model_path)
        print("[Agent] Gemma model loaded successfully.")
    except Exception as e:
        print(f"[Agent] Could not load local llama model: {e}")
        print("[Agent] Exiting scout run.")
        return

    # 4. Evaluate and Draft
    drafts_created = 0
    for post in new_posts:
        if drafts_created >= max_drafts:
            print(f"[Agent] Reached maximum draft limit of {max_drafts} for this run.")
            break

        print(f"\n[Agent] Evaluating: [{post.subreddit or post.platform}] {post.title[:80]}...")
        candidates = find_candidate_notes(f"{post.title} {post.body}", kb, top_k=3)
        result = evaluate_post(post, candidates, model)

        if not result:
            continue

        score = result.get("score", 0)
        relevant = result.get("relevant", False)
        print(f"[Agent] Score: {score}/10 | Relevant: {relevant} | Reason: {result.get('reason')}")

        if relevant and score >= 7 and result.get("comment_text"):
            if dry_run:
                print("\n--- [DRY RUN DRAFT] ---")
                print("Target:", post.url)
                print("Matched:", result.get("matched_note_url"))
                print("Comment:\n", result.get("comment_text"))
                print("-----------------------\n")
            else:
                enqueue_draft(post, result)
            drafts_created += 1

    print(f"\n=== [SatyaDheesh Marketing Scout] Complete. Generated {drafts_created} drafts ===")


def main():
    parser = argparse.ArgumentParser(description="SatyaDheesh Marketing Scout")
    parser.add_argument("--limit", type=int, default=15, help="Max posts to inspect per community")
    parser.add_argument("--max-drafts", type=int, default=5, help="Max drafts to create in this run")
    parser.add_argument("--dry-run", action="store_true", help="Evaluate and print drafts without saving to queue")
    parser.add_argument("--refresh-kb", action="store_true", help="Force rebuild knowledge base from DB")

    args = parser.parse_args()

    if args.refresh_kb:
        print("[Agent] Refreshing knowledge base from database...")
        kb = export_from_db(limit=40)
        if kb:
            save_knowledge_base(kb)
        else:
            print("[Agent] DB export failed or no credentials found.")
        return

    run_scout(limit_per_source=args.limit, max_drafts=args.max_drafts, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
