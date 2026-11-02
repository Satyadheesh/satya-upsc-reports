"""Marketing Scout Agent Entrypoint.

Discovers relevant discussions, evaluates them using Gemma 4 12B,
and enqueues high-yield, contextual drafts for local publishing.
Guarantees real-time observability, continuous unbuffered streaming,
and persistent audit logging.
"""
import argparse
import datetime
import json
import os
import sys
import time
from typing import Dict, Any, List, Optional

from marketing.discovery import discover_all, DiscussionPost
from marketing.evaluator import evaluate_post
from marketing.knowledge import load_knowledge_base, export_from_db, save_knowledge_base, find_candidate_notes_with_overlap
from marketing.queue_mgr import is_seen, load_history, enqueue_draft, record_seen_batch, record_seen, QUEUE_DIR


class AuditLogger:
    """Manages real-time unbuffered logging to console, immediate disk persistence

    to queue/audit_log.jsonl, and GitHub Actions Step Summary generation.
    """

    def __init__(self, log_path: Optional[str] = None):
        os.makedirs(QUEUE_DIR, exist_ok=True)
        self.log_path = log_path or os.path.join(QUEUE_DIR, "audit_log.jsonl")
        self.events: List[Dict[str, Any]] = []
        self.evaluations: List[Dict[str, Any]] = []
        self.start_time = time.time()

    def _now(self) -> str:
        return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    def log(self, level: str, message: str) -> None:
        """Prints immediately to console with timestamp and flushes stdout."""
        ts = self._now()
        prefix = f"[{ts}] [{level}]"
        print(f"{prefix} {message}", flush=True)
        sys.stdout.flush()

    def info(self, message: str) -> None:
        self.log("INFO", message)

    def warn(self, message: str) -> None:
        self.log("WARN", message)

    def error(self, message: str) -> None:
        self.log("ERROR", message)

    def record_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Appends a structured event to audit_log.jsonl and flushes immediately to disk."""
        payload = {
            "timestamp": self._now(),
            "event_type": event_type,
            **data
        }
        self.events.append(payload)
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())
        except Exception as e:
            self.error(f"Failed writing audit log to disk: {e}")

    def record_eval(self, post: DiscussionPost, candidates: List[Any], result: Optional[Dict[str, Any]], duration_sec: float, drafted: bool):
        eval_record = {
            "platform": post.platform,
            "community": post.subreddit or "general",
            "post_id": post.post_id,
            "title": post.title,
            "url": post.url,
            "duration_sec": round(duration_sec, 2),
            "matched_note_title": candidates[0][2].get("title") if candidates else None,
            "matched_note_url": candidates[0][2].get("url") if candidates else None,
            "overlap_tokens": candidates[0][1] if candidates else [],
            "overlap_count": candidates[0][0] if candidates else 0,
            "score": result.get("score", 0) if result else 0,
            "relevant": result.get("relevant", False) if result else False,
            "reason": result.get("reason", "No evaluation result") if result else "Evaluation failed",
            "drafted": drafted,
        }
        self.evaluations.append(eval_record)
        self.record_event("candidate_evaluation", eval_record)

    def generate_step_summary(self, total_scanned: int, prescreen_passed: int, drafts_created: int) -> None:
        """Writes GitHub Markdown Step Summary table if GITHUB_STEP_SUMMARY is set."""
        summary_file = os.getenv("GITHUB_STEP_SUMMARY")
        if not summary_file:
            return

        elapsed = round(time.time() - self.start_time, 1)
        lines = [
            "# 🛰️ SatyaDheesh Marketing Scout Report",
            f"**Completed at**: `{self._now()}` | **Total Run Time**: `{elapsed}s` | **Drafts Created**: `{drafts_created}`\n",
            "### 📈 Pipeline Stats",
            f"- **Posts Scanned Across Communities**: `{total_scanned}`",
            f"- **Passed Knowledge Pre-Screening**: `{prescreen_passed}`",
            f"- **Evaluated by Gemma 4 12B**: `{len(self.evaluations)}`",
            f"- **Drafts Enqueued**: `{drafts_created}`\n",
            "### 🔍 Detailed Evaluations",
            "| Community | Discussion Title | Top Matched SatyaDheesh Note | Overlap | Score | Decision |",
            "|:---|:---|:---|:---:|:---:|:---|",
        ]

        if not self.evaluations:
            lines.append("| - | *No candidate discussions met pre-screening criteria today* | - | - | - | ℹ️ None |")
        else:
            for ev in self.evaluations:
                comm = f"`r/{ev['community']}`" if ev['platform'] == 'reddit' else ev['platform']
                title_link = f"[{ev['title'][:55]}...]({ev['url']})" if len(ev['title']) > 55 else f"[{ev['title']}]({ev['url']})"
                note_link = f"[{ev['matched_note_title'][:40]}...]({ev['matched_note_url']})" if ev['matched_note_title'] else "None"
                tokens_str = ", ".join(ev['overlap_tokens'][:3])
                status = "✅ **Drafted**" if ev['drafted'] else f"❌ Rejected ({ev['reason'][:40]}...)"
                lines.append(f"| {comm} | {title_link} | {note_link} | `{tokens_str}` ({ev['overlap_count']}) | **{ev['score']}/10** | {status} |")

        try:
            with open(summary_file, "a", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n\n")
            self.info(f"Wrote Step Summary table to {summary_file}")
        except Exception as e:
            self.warn(f"Could not write to GITHUB_STEP_SUMMARY: {e}")


def run_scout(limit_per_source: int = 15, max_drafts: int = 5, dry_run: bool = False):
    audit = AuditLogger()
    audit.info("=== [SatyaDheesh Marketing Scout] Starting Autonomous Pipeline ===")

    # 1. Load or build knowledge base
    kb = load_knowledge_base()
    if not kb:
        audit.warn("Local knowledge base snapshot missing, attempting export from DB...")
        kb = export_from_db(limit=40)
        if kb:
            save_knowledge_base(kb)

    if not kb:
        audit.error("No knowledge base available. Please provide knowledge_base.json or valid DB credentials.")
        audit.record_event("run_aborted", {"reason": "missing_knowledge_base"})
        return

    audit.info(f"Loaded {len(kb)} curated notes from local SatyaDheesh snapshot.")
    audit.record_event("kb_loaded", {"notes_count": len(kb)})

    # 2. Discover discussions
    history = load_history()
    audit.info(f"Deduplication index loaded with {len(history)} previously handled posts.")

    posts = discover_all(max_per_source=limit_per_source)
    new_posts = [p for p in posts if not is_seen(p.post_id, history)]
    audit.info(f"Discovered {len(posts)} total posts ({len(new_posts)} unhandled after deduplication).")
    audit.record_event("discovery_completed", {
        "total_discovered": len(posts),
        "new_unhandled": len(new_posts),
    })

    if not new_posts:
        audit.info("No unhandled discussions found in this cycle. Scout run complete.")
        audit.generate_step_summary(len(posts), 0, 0)
        return

    # 3. Pre-screen & Rank Discussions by Knowledge Base Overlap
    audit.info(f"Pre-screening {len(new_posts)} discussions for topic overlap against our {len(kb)} notes...")
    screened_candidates = []
    
    for post in new_posts:
        matches = find_candidate_notes_with_overlap(f"{post.title} {post.body}", kb, top_k=3, min_overlap=2)
        if matches:
            screened_candidates.append((post, matches))

    audit.info(f"{len(screened_candidates)} discussions passed pre-screening with >= 2 keyword matches.")
    audit.record_event("prescreening_completed", {"passed_count": len(screened_candidates)})

    if not screened_candidates:
        audit.info("No discussions met topical relevance criteria today. Scout run complete.")
        # Mark scanned posts as seen so we don't repeat them
        record_seen_batch([p.post_id for p in new_posts])
        audit.generate_step_summary(len(posts), 0, 0)
        return

    # Sort screened candidates descending by top overlap count
    screened_candidates.sort(key=lambda item: item[1][0][0], reverse=True)

    # Cap evaluation queue at 3 candidates per run to keep CPU execution fast (< 5 minutes total)
    eval_queue = screened_candidates[:3]
    audit.info(f"Selected top {len(eval_queue)} candidate discussions for Gemma 4 12B reasoning:")
    for idx, (p, m) in enumerate(eval_queue, 1):
        top_m = m[0]
        audit.info(f"  [{idx}/{len(eval_queue)}] [r/{p.subreddit or p.platform}] \"{p.title[:65]}\" -> Overlap: {top_m[1]} ({top_m[0]} kw)")

    # 4. Load Gemma 4 12B Model
    audit.info("Initializing Gemma 4 12B Q4_K_M GGUF model via llama.cpp...")
    t_model_start = time.time()
    try:
        from kit.model import download, Model
        model_path = download()
        model = Model(model_path)
        load_sec = round(time.time() - t_model_start, 2)
        audit.info(f"Gemma 4 12B loaded into memory successfully in {load_sec}s.")
        audit.record_event("model_loaded", {"load_time_sec": load_sec})
    except Exception as e:
        audit.error(f"Failed to load Gemma 4 12B model: {e}")
        audit.record_event("run_aborted", {"reason": "model_load_failure", "error": str(e)})
        return

    # 5. Evaluate and Draft Comments
    drafts_created = 0
    for idx, (post, matches) in enumerate(eval_queue, 1):
        if drafts_created >= max_drafts:
            audit.info(f"Reached target quota of {max_drafts} drafts. Stopping scout loop.")
            break

        candidate_notes = [item for _, _, item in matches]
        top_note = candidate_notes[0]

        audit.info(f"\n--- [Evaluating Candidate {idx}/{len(eval_queue)}] ---")
        audit.info(f"Community: [{post.subreddit or post.platform}] | URL: {post.url}")
        audit.info(f"Title: \"{post.title}\"")
        audit.info(f"Target Note: \"{top_note.get('title')}\" ({top_note.get('url')})")
        audit.info(f"Shared Keywords: {matches[0][1]}")

        t_eval_start = time.time()
        result = evaluate_post(post, candidate_notes, model)
        eval_sec = time.time() - t_eval_start

        if not result:
            audit.warn(f"Gemma evaluation produced no result for post {post.post_id}.")
            audit.record_eval(post, matches, None, eval_sec, drafted=False)
            record_seen(post.post_id)
            continue

        score = result.get("score", 0)
        relevant = result.get("relevant", False)
        reason = result.get("reason", "N/A")
        comment_text = result.get("comment_text", "").strip()

        audit.info(f"Gemma 12B Verdict: Score {score}/10 | Relevant: {relevant} | Time: {round(eval_sec, 1)}s")
        audit.info(f"Reasoning: {reason}")

        drafted = False
        if relevant and score >= 7 and comment_text:
            if dry_run:
                audit.info(">>> DRY RUN: Draft comment generated (not enqueued):")
                print(f"\n{comment_text}\n", flush=True)
            else:
                task_file = enqueue_draft(post, result)
                audit.info(f"✅ Draft enqueued successfully -> {os.path.basename(task_file)}")
            drafts_created += 1
            drafted = True
        else:
            audit.info(f"⏭️ Skipping post (score {score} < 7 or no substantive comment).")

        audit.record_eval(post, matches, result, eval_sec, drafted=drafted)
        record_seen(post.post_id)

    # Mark posts with zero candidate matches as seen so we don't re-screen them
    zero_match_ids = [p.post_id for p in new_posts if p.post_id not in [item[0].post_id for item in screened_candidates]]
    if zero_match_ids:
        record_seen_batch(zero_match_ids)

    audit.info(f"\n=== [SatyaDheesh Marketing Scout] Complete. Generated {drafts_created} drafts ===")
    audit.record_event("scout_completed", {
        "total_scanned": len(posts),
        "prescreen_passed": len(screened_candidates),
        "evaluated_by_gemma": len(audit.evaluations),
        "drafts_created": drafts_created,
        "elapsed_seconds": round(time.time() - audit.start_time, 1),
    })

    audit.generate_step_summary(len(posts), len(screened_candidates), drafts_created)


def main():
    parser = argparse.ArgumentParser(description="SatyaDheesh Marketing Scout")
    parser.add_argument("--limit", type=int, default=15, help="Max posts to inspect per community")
    parser.add_argument("--max-drafts", type=int, default=5, help="Max drafts to create in this run")
    parser.add_argument("--dry-run", action="store_true", help="Evaluate and print drafts without saving to queue")
    parser.add_argument("--refresh-kb", action="store_true", help="Force rebuild knowledge base from DB")

    args = parser.parse_args()

    if args.refresh_kb:
        print("[Agent] Refreshing knowledge base from database...", flush=True)
        kb = export_from_db(limit=40)
        if kb:
            save_knowledge_base(kb)
        else:
            print("[Agent] DB export failed or no credentials found.", flush=True)
        return

    run_scout(limit_per_source=args.limit, max_drafts=args.max_drafts, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
