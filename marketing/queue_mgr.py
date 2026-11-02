"""Queue Manager for Marketing Agent.

Stores and manages drafted comments between the GitHub Actions Scout
and the Mac Posting Agent with zero database reads.
"""
import glob
import json
import os
import time
from typing import Dict, Any, List, Optional
from marketing.discovery import DiscussionPost

QUEUE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "queue"))
PENDING_DIR = os.path.join(QUEUE_DIR, "pending")
POSTED_DIR = os.path.join(QUEUE_DIR, "posted")
HISTORY_FILE = os.path.join(QUEUE_DIR, "history.json")


def _init_dirs():
    os.makedirs(PENDING_DIR, exist_ok=True)
    os.makedirs(POSTED_DIR, exist_ok=True)


def load_history() -> set:
    """Loads set of previously seen or processed post IDs."""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return set(data)
        except Exception as e:
            print(f"[Queue] Warning reading history: {e}")
    return set()


def save_history(history: set) -> None:
    """Saves updated set of seen post IDs."""
    _init_dirs()
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(list(history)), f, indent=2)


def is_seen(post_id: str, history: Optional[set] = None) -> bool:
    """Checks if a post ID has already been evaluated or posted."""
    hist = history if history is not None else load_history()
    return post_id in hist


def record_seen(post_id: str) -> None:
    """Records a single post ID as seen/evaluated."""
    _init_dirs()
    hist = load_history()
    if post_id not in hist:
        hist.add(post_id)
        save_history(hist)


def record_seen_batch(post_ids: List[str]) -> None:
    """Records a batch of post IDs as seen/evaluated in a single write."""
    if not post_ids:
        return
    _init_dirs()
    hist = load_history()
    hist.update(post_ids)
    save_history(hist)


def enqueue_draft(post: DiscussionPost, eval_result: Dict[str, Any]) -> str:
    """Writes a drafted comment to the pending queue."""
    _init_dirs()
    task_id = f"{post.platform}_{post.post_id}"
    task_file = os.path.join(PENDING_DIR, f"{task_id}.json")

    payload = {
        "task_id": task_id,
        "platform": post.platform,
        "post_id": post.post_id,
        "target_url": post.url,
        "title": post.title,
        "subreddit": post.subreddit,
        "author": post.author,
        "score": eval_result.get("score"),
        "reason": eval_result.get("reason"),
        "matched_note": {
            "title": eval_result.get("matched_note_title"),
            "url": eval_result.get("matched_note_url"),
        },
        "drafted_comment": eval_result.get("comment_text"),
        "status": "pending",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
    }

    with open(task_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    # Record in history
    hist = load_history()
    hist.add(post.post_id)
    save_history(hist)

    print(f"[Queue] Enqueued draft: {task_id} -> {task_file}")
    return task_file


def get_pending_tasks() -> List[Dict[str, Any]]:
    """Returns all currently pending tasks."""
    _init_dirs()
    tasks = []
    for filepath in sorted(glob.glob(os.path.join(PENDING_DIR, "*.json"))):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                task = json.load(f)
                task["_file"] = filepath
                tasks.append(task)
        except Exception as e:
            print(f"[Queue] Failed reading {filepath}: {e}")
    return tasks


def mark_as_posted(task: Dict[str, Any], posted_url: Optional[str] = None) -> None:
    """Moves a pending task to the posted directory."""
    _init_dirs()
    file_path = task.get("_file")
    task_id = task.get("task_id", "unknown")
    dest_path = os.path.join(POSTED_DIR, f"{task_id}.json")

    task["status"] = "posted"
    task["posted_at"] = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    if posted_url:
        task["comment_url"] = posted_url
    task.pop("_file", None)

    with open(dest_path, "w", encoding="utf-8") as f:
        json.dump(task, f, indent=2, ensure_ascii=False)

    if file_path and os.path.exists(file_path):
        os.remove(file_path)

    print(f"[Queue] Moved {task_id} to posted.")
