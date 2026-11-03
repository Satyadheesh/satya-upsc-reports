"""Mac Posting Agent ("The Hands").

Runs locally on your Mac using your residential IP and persistent browser session.
Reads pending drafts from the queue, types them with human-like delays, and posts
across supported portals (Reddit, ForumIAS, Quora, YouTube, Medium).
"""
import argparse
import os
import random
import sys
import time
from typing import Dict, Any

from marketing.queue_mgr import get_pending_tasks, mark_as_posted

PROFILE_DIR = os.path.expanduser("~/.satya-marketing/chrome_profile")


def human_type(locator, text: str):
    """Types text with randomized human-like delays between keystrokes."""
    for char in text:
        locator.type(char, delay=random.randint(25, 75))
        if char in {".", "\n", "!"}:
            time.sleep(random.uniform(0.2, 0.5))


def run_setup():
    """Opens a visible browser with the persistent profile so you can log into community accounts once."""
    from playwright.sync_api import sync_playwright

    os.makedirs(PROFILE_DIR, exist_ok=True)
    print("=== [SatyaDheesh Poster] Multi-Portal Account Setup Mode ===")
    print(f"Profile directory: {PROFILE_DIR}")
    print("\nOpening browser tabs for supported communities:")
    print(" 1. Reddit:    https://www.reddit.com/login")
    print(" 2. ForumIAS:  https://one.forumias.com/login.php")
    print(" 3. Quora:     https://www.quora.com")
    print(" 4. YouTube:   https://www.youtube.com")
    print(" 5. Medium:    https://medium.com/m/signin")
    print("\nPlease log into your dedicated accounts for whichever platforms you want to post on.")
    print("Once logged in, simply close the browser window or press Enter here to save your session.")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=False,
            viewport={"width": 1280, "height": 800},
            args=["--disable-blink-features=AutomationControlled"]
        )
        page1 = context.new_page()
        page1.goto("https://www.reddit.com/login")

        page2 = context.new_page()
        page2.goto("https://one.forumias.com/login.php")

        try:
            input("\n--> Press Enter here AFTER you have logged in to your account(s) in the browser... ")
        except (KeyboardInterrupt, EOFError):
            pass

        context.close()

    print("[Setup] Profile saved! You are now ready to run autonomous posting across portals.")


# ==========================================
# 1. REDDIT POSTER
# ==========================================

def sanitize_comment_for_reddit(comment: str) -> str:
    """Removes raw URLs and replaces them with clean 'check on satyadheesh portal' cues

    to avoid triggering Reddit's automated spam filters on new accounts.
    """
    import re
    # Remove markdown link formatting [text](url) -> text
    comment = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', comment)

    cta_patterns = [
        (r'\(search [^\)]*on Google[^\)]*\)', '(check on satyadheesh portal for more details)'),
        (r'search [\"\']?satyadheesh upsc[\"\']? on Google(?: for more details)?', 'check on satyadheesh portal'),
        (r'\(check out SatyaDheesh:?\s*https?://[^\)]+\)', '(check on satyadheesh portal)'),
        (r'check out SatyaDheesh:?\s*(?:https?://\S+|satyadheesh\.in\S*)', 'check on satyadheesh portal'),
        (r'\(For clean[^)]*satyadheesh\.in[^)]*\)', '(For clean, syllabus-mapped daily briefs and committee facts, check on satyadheesh portal)'),
        (r'\(If you want free[^)]*satyadheesh\.in[^)]*\)', '(For free, clean daily notes mapped to the GS syllabus and MCQs, check on satyadheesh portal)'),
        (r'\(SatyaDheesh published[^)]*satyadheesh\.in[^)]*\)', '(check on satyadheesh portal for the full breakdown and facts)'),
        (r'\(SatyaDheesh has an open daily tracker:?\s*satyadheesh\.in[^\)]*\)', '(check on satyadheesh portal for the daily tracker and notes)'),
    ]
    for pat, rep in cta_patterns:
        comment = re.sub(pat, rep, comment, flags=re.IGNORECASE)

    # Strip any leftover raw URLs
    comment = re.sub(r'https?://\S+', 'check on satyadheesh portal', comment)
    comment = re.sub(r'satyadheesh\.in\S*', 'check on satyadheesh portal', comment)
    return comment.strip()


def post_to_reddit(page, task: Dict[str, Any]) -> bool:
    """Posts a drafted comment to a Reddit thread."""
    url = task["target_url"]
    comment = sanitize_comment_for_reddit(task["drafted_comment"])

    print(f"\n[Poster] Navigating to Reddit: {url}")
    page.goto(url, wait_until="load", timeout=45000)
    time.sleep(random.uniform(2.5, 4.0))

    # Activate modern Reddit composer if present
    try:
        composer_host = page.locator("comment-composer-host, shreddit-comment-composer").first
        if composer_host.is_visible(timeout=3000):
            composer_host.click()
            time.sleep(1.0)
    except Exception:
        pass

    # Reddit comment box selectors across modern / shreddit UI
    selectors = [
        "comment-composer-host div[contenteditable='true']",
        "comment-composer-host div[role='textbox']",
        "comment-composer-host faceplate-textarea-input textarea",
        "faceplate-textarea-input:visible textarea",
        "div[slot='rte']:visible",
        "div[contenteditable='true']:visible",
        "div[role='textbox']:visible",
        "textarea:visible",
    ]

    target_box = None
    for sel in selectors:
        try:
            elem = page.locator(sel).first
            if elem.is_visible(timeout=1500):
                target_box = elem
                break
        except Exception:
            continue

    if not target_box:
        # Try clicking placeholder / "Add a comment" button to activate editor
        try:
            placeholder = page.locator("button:has-text('Add a comment'), [placeholder*='Add a comment' i]").first
            if placeholder.is_visible(timeout=2000):
                placeholder.click()
                time.sleep(1.5)
                target_box = page.locator("div[role='textbox']:visible, div[contenteditable='true']:visible, textarea:visible").first
        except Exception as e:
            print(f"[Poster] Could not activate Reddit editor: {e}")

    if not target_box:
        print(f"[Poster] FAILED: Could not locate comment input box on {url}")
        return False

    print("[Poster] Editor located. Typing comment with human latency...")
    target_box.click()
    time.sleep(random.uniform(0.5, 1.2))
    human_type(target_box, comment)

    time.sleep(random.uniform(2.0, 4.0))

    submit_buttons = [
        "comment-composer-host button[type='submit']",
        "comment-composer-host button:has-text('Comment')",
        "button[type='submit']:has-text('Comment'):visible",
        "button:has-text('Comment'):visible",
        "button[slot='submit-button']:visible",
        "button:has-text('Reply'):visible",
    ]

    clicked = False
    for btn_sel in submit_buttons:
        try:
            btn = page.locator(btn_sel).first
            if btn.is_visible(timeout=2000) and btn.is_enabled():
                btn.click()
                clicked = True
                print("[Poster] Comment submitted successfully on Reddit!")
                break
        except Exception:
            continue

    if not clicked:
        print("[Poster] Warning: Could not locate enabled Comment button.")
        return False

    time.sleep(random.uniform(4.0, 6.0))
    return True


# ==========================================
# 2. FORUMIAS POSTER
# ==========================================

def post_to_forumias(page, task: Dict[str, Any]) -> bool:
    """Posts a drafted comment to a ForumIAS discussion thread."""
    url = task["target_url"]
    comment = task["drafted_comment"]

    print(f"\n[Poster] Navigating to ForumIAS: {url}")
    page.goto(url, wait_until="domcontentloaded", timeout=45000)
    time.sleep(random.uniform(3.0, 5.0))

    # Click comment placeholder to open editor if needed
    try:
        pre_box = page.locator(".write-comment-pre-placeholder, .write-comment, button:has-text('Write a comment')").first
        if pre_box.is_visible(timeout=3000):
            pre_box.click()
            time.sleep(1.5)
    except Exception:
        pass

    # Check for login modal or requirement
    login_prompt = page.locator(".login-card, a:has-text('Login Now'), [id*='login']").first
    try:
        if login_prompt.is_visible(timeout=1500):
            print("[Poster] ForumIAS session required. Please run '--setup' to log in to ForumIAS.")
            return False
    except Exception:
        pass

    # Find editor textarea / contenteditable
    editor = page.locator(".note-editable, div[contenteditable='true'], textarea.form-control, textarea[placeholder*='comment' i]").first
    try:
        if not editor.is_visible(timeout=4000):
            print(f"[Poster] FAILED: Could not locate reply editor on ForumIAS thread {url}")
            return False
    except Exception:
        return False

    print("[Poster] ForumIAS editor located. Typing reply with human latency...")
    editor.click()
    time.sleep(random.uniform(0.5, 1.2))
    human_type(editor, comment)
    time.sleep(random.uniform(2.0, 4.0))

    # Click submit
    submit_btn = page.locator("button:has-text('Post Comment'), button:has-text('Submit'), button.btn-primary:has-text('Post')").first
    try:
        if submit_btn.is_visible(timeout=3000) and submit_btn.is_enabled():
            submit_btn.click()
            print("[Poster] Reply submitted successfully on ForumIAS!")
            time.sleep(random.uniform(4.0, 6.0))
            return True
        else:
            print("[Poster] Warning: ForumIAS submit button not visible or disabled.")
            return False
    except Exception as e:
        print(f"[Poster] Error submitting on ForumIAS: {e}")
        return False


# ==========================================
# 3. QUORA POSTER
# ==========================================

def post_to_quora(page, task: Dict[str, Any]) -> bool:
    """Posts a drafted answer/comment to a Quora question thread."""
    url = task["target_url"]
    comment = task["drafted_comment"]

    print(f"\n[Poster] Navigating to Quora: {url}")
    page.goto(url, wait_until="domcontentloaded", timeout=45000)
    time.sleep(random.uniform(3.0, 5.0))

    # Guard: Detect Cloudflare bot challenge
    page_title = page.title().lower()
    if "just a moment" in page_title or "cloudflare" in page_title:
        print(f"[Poster] BLOCKED: Cloudflare bot challenge encountered on Quora ({url}). Session login required.")
        return False

    # Look for "Answer" button
    answer_btn = page.locator("button:has-text('Answer'), div[role='button']:has-text('Answer')").first
    try:
        if answer_btn.is_visible(timeout=4000):
            answer_btn.click()
            time.sleep(2.0)
    except Exception:
        pass

    editor = page.locator("div[role='textbox'], div[contenteditable='true']").first
    try:
        if not editor.is_visible(timeout=4000):
            print(f"[Poster] Quora editor not active on {url}. Session login may be required.")
            return False
    except Exception:
        return False

    print("[Poster] Quora editor located. Typing answer with human latency...")
    editor.click()
    time.sleep(random.uniform(0.5, 1.2))
    human_type(editor, comment)
    time.sleep(random.uniform(2.0, 4.0))

    post_btn = page.locator("button:has-text('Post'), button:has-text('Submit')").first
    try:
        if post_btn.is_visible(timeout=3000) and post_btn.is_enabled():
            post_btn.click()
            print("[Poster] Answer posted successfully on Quora!")
            time.sleep(random.uniform(4.0, 6.0))
            return True
    except Exception as e:
        print(f"[Poster] Error posting to Quora: {e}")

    return False


# ==========================================
# 4. YOUTUBE POSTER
# ==========================================

def sanitize_comment_for_youtube(comment: str) -> str:
    """Sanitizes comments for YouTube by stripping URLs, third-party platform keywords

    (like Google/Telegram/WhatsApp), and ensuring clean 'check on satyadheesh portal' sign-offs.
    """
    import re
    # Remove markdown link formatting [text](url) -> text
    comment = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', comment)

    patterns = [
        (r'\(search [^\)]*on Google[^\)]*\)', '(check on satyadheesh portal for more details)'),
        (r'search [\"\']?satyadheesh upsc[\"\']? on Google(?: for more details)?', 'check on satyadheesh portal'),
        (r'\(check out SatyaDheesh:?\s*https?://[^\)]+\)', '(check on satyadheesh portal)'),
        (r'check out SatyaDheesh:?\s*(?:https?://\S+|satyadheesh\.in\S*)', 'check on satyadheesh portal'),
        (r'\(For clean[^)]*satyadheesh\.in[^)]*\)', '(check on satyadheesh portal for more details)'),
        (r'\(If you want free[^)]*satyadheesh\.in[^)]*\)', '(check on satyadheesh portal for more details)'),
        (r'\(SatyaDheesh published[^)]*satyadheesh\.in[^)]*\)', '(check on satyadheesh portal for the full breakdown)'),
        (r'\(SatyaDheesh has an open daily tracker:?\s*satyadheesh\.in[^\)]*\)', '(check on satyadheesh portal for the daily tracker)'),
    ]
    for pat, rep in patterns:
        comment = re.sub(pat, rep, comment, flags=re.IGNORECASE)

    comment = re.sub(r'https?://\S+', 'check on satyadheesh portal', comment)
    comment = re.sub(r'satyadheesh\.in\S*', 'check on satyadheesh portal', comment)
    return comment.strip()


def post_to_youtube(page, task: Dict[str, Any]) -> bool:
    """Posts a comment under a YouTube editorial video."""
    url = task["target_url"]
    comment = sanitize_comment_for_youtube(task["drafted_comment"])

    print(f"\n[Poster] Navigating to YouTube video: {url}")
    page.goto(url, wait_until="domcontentloaded", timeout=45000)
    time.sleep(random.uniform(3.0, 5.0))

    # Scroll down to reveal lazy-loaded comment section
    page.evaluate("window.scrollBy(0, 650)")
    time.sleep(2.5)

    # YouTube comment box selectors
    placeholder = page.locator("#placeholder-area, #simplebox-placeholder, ytd-comment-simplebox-renderer").first
    try:
        if placeholder.is_visible(timeout=5000):
            placeholder.click()
            time.sleep(1.5)
    except Exception:
        pass

    editor = page.locator("#contenteditable-root, div#contenteditable-textarea").first
    try:
        if not editor.is_visible(timeout=4000):
            print(f"[Poster] YouTube comment box not available on {url}. Google login may be required.")
            return False
    except Exception:
        return False

    print("[Poster] YouTube comment box located. Typing with human latency...")
    editor.click()
    time.sleep(random.uniform(0.5, 1.2))
    human_type(editor, comment)
    time.sleep(random.uniform(2.0, 4.0))

    submit_btn = page.locator("#submit-button button, ytd-button-renderer#submit-button button, button:has-text('Comment')").first
    try:
        if submit_btn.is_visible(timeout=3000) and submit_btn.is_enabled():
            submit_btn.click()
            print("[Poster] Comment submitted on YouTube, verifying placement...")
            time.sleep(random.uniform(4.0, 6.0))
            # Verify comment appeared in comments section or editor cleared
            comments = page.locator("#content-text").all_text_contents()
            if any(keyword in c.lower() for c in comments for keyword in ["satyadheesh", "portal"]):
                print("[Poster] VERIFIED: Comment is live and visible in YouTube comments section!")
                return True
            editor_text = editor.text_content() or ""
            if not editor_text.strip():
                print("[Poster] VERIFIED: Comment submitted and editor cleared.")
                return True
            print("[Poster] Comment button clicked successfully.")
            return True
    except Exception as e:
        print(f"[Poster] Error submitting on YouTube: {e}")

    return False


# ==========================================
# 5. MEDIUM POSTER
# ==========================================

def post_to_medium(page, task: Dict[str, Any]) -> bool:
    """Posts a response to a Medium UPSC article."""
    url = task["target_url"]
    comment = task["drafted_comment"]

    print(f"\n[Poster] Navigating to Medium: {url}")
    page.goto(url, wait_until="domcontentloaded", timeout=45000)
    time.sleep(random.uniform(3.0, 5.0))

    # Guard: Detect Cloudflare bot challenge
    page_title = page.title().lower()
    if "just a moment" in page_title or "cloudflare" in page_title:
        print(f"[Poster] BLOCKED: Cloudflare bot challenge encountered on Medium ({url}). Session login required.")
        return False

    # Open responses sidebar if present
    resp_icon = page.locator("button[aria-label*='responses' i], button:has-text('Respond')").first
    try:
        if resp_icon.is_visible(timeout=3000):
            resp_icon.click()
            time.sleep(1.5)
    except Exception:
        pass

    editor = page.locator("div[role='textbox'], textarea[placeholder*='response' i]").first
    try:
        if not editor.is_visible(timeout=4000):
            print(f"[Poster] Medium response editor not open on {url}. Medium login may be required.")
            return False
    except Exception:
        return False

    print("[Poster] Medium editor located. Typing response with human latency...")
    editor.click()
    time.sleep(random.uniform(0.5, 1.2))
    human_type(editor, comment)
    time.sleep(random.uniform(2.0, 4.0))

    respond_btn = page.locator("button:has-text('Respond')").first
    try:
        if respond_btn.is_visible(timeout=3000) and respond_btn.is_enabled():
            respond_btn.click()
            print("[Poster] Response submitted successfully on Medium!")
            time.sleep(random.uniform(4.0, 6.0))
            return True
    except Exception as e:
        print(f"[Poster] Error submitting on Medium: {e}")

    return False


# ==========================================
# MASTER POSTER RUNNER
# ==========================================

PLATFORM_DISPATCH = {
    "reddit": post_to_reddit,
    "forumias": post_to_forumias,
    "quora": post_to_quora,
    "youtube": post_to_youtube,
    "medium": post_to_medium,
}


def run_poster(max_youtube: int = 2, max_other: int = 3, headless: bool = False):
    """Executes pending posting tasks using your local residential profile.
    Policy:
      1. Always posts at least 2 comments on YouTube (from the 24 channels).
      2. Then posts 2-3 comments on other authenticated platforms (e.g. Reddit after warm-up).
    """
    from playwright.sync_api import sync_playwright

    tasks = get_pending_tasks()
    if not tasks:
        print("[Poster] No pending drafts found in queue. Everything is up to date!")
        return

    # Prioritize: YouTube tasks first (target 2), then other platforms (target 2-3)
    yt_tasks = [t for t in tasks if t.get("platform", "").lower() == "youtube"]
    other_tasks = [t for t in tasks if t.get("platform", "").lower() != "youtube"]

    plan = yt_tasks[:max_youtube] + other_tasks[:max_other]

    print(f"=== [SatyaDheesh Poster] Starting Autonomous Run ({len(tasks)} pending: {len(yt_tasks)} YT, {len(other_tasks)} Other) ===")
    print(f"[Poster] Policy target: up to {max_youtube} YouTube comments + up to {max_other} other community comments")
    os.makedirs(PROFILE_DIR, exist_ok=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=headless,
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = context.new_page()

        posted_yt = 0
        posted_other = 0

        for task in plan:
            platform = task.get("platform", "reddit").lower()
            is_yt = (platform == "youtube")

            if is_yt and posted_yt >= max_youtube:
                continue
            if not is_yt and posted_other >= max_other:
                continue

            print(f"\n[Poster] Processing task {task.get('task_id')} on {platform}...")
            print(f"Title: {task.get('title')}")

            handler = PLATFORM_DISPATCH.get(platform)
            success = False
            if handler:
                try:
                    success = handler(page, task)
                except Exception as e:
                    print(f"[Poster] Unexpected error executing handler for {platform}: {e}")
            else:
                print(f"[Poster] Warning: No handler registered for platform '{platform}'.")

            if success:
                mark_as_posted(task)
                if is_yt:
                    posted_yt += 1
                else:
                    posted_other += 1

                # Safe pacing delay between posts (35 to 55 seconds)
                total_posted = posted_yt + posted_other
                if total_posted < (max_youtube + max_other):
                    wait_sec = random.randint(35, 55)
                    print(f"[Poster] Pacing delay: waiting {wait_sec} seconds before next post...")
                    time.sleep(wait_sec)
            else:
                print(f"[Poster] Skipping task {task.get('task_id')} (not posted).")

        context.close()

    print(f"\n=== [SatyaDheesh Poster] Finished. Posted {posted_yt} YouTube comments and {posted_other} other comments. ===")


def main():
    parser = argparse.ArgumentParser(description="SatyaDheesh Multi-Portal Mac Posting Agent")
    parser.add_argument("--setup", action="store_true", help="Launch browser to log in to community accounts once")
    parser.add_argument("--run", action="store_true", help="Run autonomous hands-free poster")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--max-youtube", type=int, default=2, help="Maximum YouTube comments to post in this run (default 2)")
    parser.add_argument("--max-other", type=int, default=3, help="Maximum other community comments to post in this run (default 3)")
    parser.add_argument("--max", type=int, default=5, help="Legacy: total maximum comments")

    args = parser.parse_args()

    if args.setup:
        run_setup()
    elif args.run:
        run_poster(max_youtube=args.max_youtube, max_other=args.max_other, headless=args.headless)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
