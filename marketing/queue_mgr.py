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
PAUSED_DIR = os.path.join(QUEUE_DIR, "paused")
REPORTS_DIR = os.path.join(QUEUE_DIR, "reports")
HISTORY_FILE = os.path.join(QUEUE_DIR, "history.json")

# Configurable pause timestamp for Reddit warming
PAUSE_REDDIT_UNTIL = "2026-11-06T00:00:00+05:30"


def is_reddit_paused() -> bool:
    """Checks if Reddit discovery and posting is currently paused."""
    try:
        from datetime import datetime, timezone
        pause_str = os.environ.get("PAUSE_REDDIT_UNTIL", PAUSE_REDDIT_UNTIL)
        if not pause_str:
            return False
        pause_dt = datetime.fromisoformat(pause_str)
        now_dt = datetime.now(pause_dt.tzinfo or timezone.utc)
        return now_dt < pause_dt
    except Exception:
        return True


def _init_dirs():
    os.makedirs(PENDING_DIR, exist_ok=True)
    os.makedirs(POSTED_DIR, exist_ok=True)
    os.makedirs(PAUSED_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)


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


def get_pending_tasks(include_paused: bool = False) -> List[Dict[str, Any]]:
    """Returns all currently pending tasks, filtering out paused platforms (e.g. Reddit)."""
    _init_dirs()
    tasks = []
    reddit_paused = is_reddit_paused()
    for filepath in sorted(glob.glob(os.path.join(PENDING_DIR, "*.json"))):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                task = json.load(f)
                task["_file"] = filepath
                if not include_paused and reddit_paused and task.get("platform", "").lower() == "reddit":
                    continue
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

    # Record to daily digest
    try:
        append_to_daily_report(task)
    except Exception as e:
        print(f"[Queue] Failed appending to daily report: {e}")

    # Real-time Telegram notification
    try:
        notify_telegram(task)
    except Exception as e:
        print(f"[Queue] Failed sending Telegram notification: {e}")

    # Subtle macOS desktop notification
    comm = task.get("subreddit") or task.get("platform", "Community")
    title_short = task.get("title", "")[:35]
    notify_mac("SatyaDheesh Marketing", f"Posted to {comm}: {title_short}...")


def notify_telegram(task: Dict[str, Any]) -> bool:
    """Dispatches a real-time notification to the admin Telegram chat when a comment is posted."""
    import html
    import urllib.parse
    import urllib.request

    token = os.environ.get("TELEGRAM_BOT_TOKEN") or "8553388061:AAGzoTrdaUABEj8QbPidn6wT1R9Q8oREqNI"
    chat_id = (
        os.environ.get("TELEGRAM_ADMIN_CHAT_ID")
        or os.environ.get("TELEGRAM_TEST_CHAT_ID")
        or os.environ.get("TELEGRAM_CHAT_ID")
        or "6634664206"
    )

    platform = task.get("platform", "unknown").upper()
    comm = task.get("subreddit") or task.get("platform", "community")
    title = html.escape(task.get("title", "Untitled"))
    target_url = task.get("target_url", "")
    posted_at = task.get("posted_at", time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()))
    score = task.get("score", "N/A")
    matched_title = html.escape(task.get("matched_note", {}).get("title", "SatyaDheesh Resource"))
    matched_url = task.get("matched_note", {}).get("url", "https://satyadheesh.in/en/upsc")

    raw_comment = task.get("drafted_comment", "")
    comment_snippet = html.escape(raw_comment[:320])
    if len(raw_comment) > 320:
        comment_snippet += "..."

    msg = (
        f"🎯 <b>SatyaDheesh Autonomous Post Published</b>\n\n"
        f"• <b>Platform:</b> {html.escape(platform)} (<code>{html.escape(str(comm))}</code>)\n"
        f"• <b>Relevance Score:</b> {score}/10\n"
        f"• <b>Thread:</b> <a href=\"{target_url}\">{title}</a>\n"
        f"• <b>Matched Resource:</b> <a href=\"{matched_url}\">{matched_title}</a>\n"
        f"• <b>Time:</b> <code>{posted_at}</code>\n\n"
        f"💬 <b>Comment:</b>\n"
        f"<i>\"{comment_snippet}\"</i>\n\n"
        f"🔗 <a href=\"{target_url}\">Open Thread</a>"
    )

    try:
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": msg,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }).encode("utf-8")
        req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data)
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode())
            if body.get("ok"):
                print(f"[Queue] Telegram notification sent successfully to {chat_id}.")
                return True
            print(f"[Queue] Telegram returned non-ok: {body}")
            return False
    except Exception as e:
        print(f"[Queue] Telegram notification failed: {e}")
        return False


def append_to_daily_report(task: Dict[str, Any]) -> str:
    """Appends an engagement record to today's daily marketing markdown report."""
    _init_dirs()
    today_str = time.strftime("%Y-%m-%d", time.gmtime())
    report_file = os.path.join(REPORTS_DIR, f"{today_str}.md")

    file_exists = os.path.exists(report_file)
    with open(report_file, "a", encoding="utf-8") as f:
        if not file_exists:
            f.write(f"# 📊 SatyaDheesh Autonomous Marketing Report — {today_str}\n\n")
            f.write("| Platform | Community | Discussion Title | Target URL | Matched Playbook | Time (UTC) |\n")
            f.write("|:---|:---|:---|:---|:---|:---|\n")

        platform = task.get("platform", "unknown")
        comm = task.get("subreddit") or platform
        title = task.get("title", "Untitled").replace("|", "\\|")
        url = task.get("target_url", "")
        playbook = task.get("matched_note", {}).get("title", "N/A").replace("|", "\\|")
        posted_at = task.get("posted_at", "")

        f.write(f"| `{platform}` | `{comm}` | [{title[:55]}...]({url}) | [Direct Link]({url}) | {playbook[:40]} | `{posted_at}` |\n")

    return report_file


def notify_mac(title: str, message: str) -> None:
    """Sends a subtle native macOS notification banner."""
    try:
        escaped_title = title.replace('"', '\\"')
        escaped_msg = message.replace('"', '\\"')
        os.system(f"""osascript -e 'display notification "{escaped_msg}" with title "{escaped_title}"' 2>/dev/null""")
    except Exception:
        pass

