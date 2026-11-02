"""Mac Posting Agent ("The Hands").

Runs locally on your Mac using your residential IP and persistent browser session.
Reads pending drafts from the queue, types them with human-like delays, and posts.
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
    """Opens a visible browser with the persistent profile so you can log into Reddit/forums once."""
    from playwright.sync_api import sync_playwright

    os.makedirs(PROFILE_DIR, exist_ok=True)
    print("=== [SatyaDheesh Poster] Account Setup Mode ===")
    print(f"Profile directory: {PROFILE_DIR}")
    print("Opening browser. Please log into your dedicated Reddit / community accounts.")
    print("Once logged in, simply close the browser window or press Enter here to save.")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=False,
            viewport={"width": 1280, "height": 800},
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = context.new_page()
        page.goto("https://www.reddit.com/login")

        try:
            input("\n--> Press Enter here AFTER you have successfully logged in in the browser... ")
        except (KeyboardInterrupt, EOFError):
            pass

        context.close()

    print("[Setup] Profile saved! You are now ready to run autonomous posting.")


def post_to_reddit(page, task: Dict[str, Any]) -> bool:
    """Posts a drafted comment to a Reddit thread."""
    url = task["target_url"]
    comment = task["drafted_comment"]

    print(f"\n[Poster] Navigating to: {url}")
    page.goto(url, wait_until="domcontentloaded", timeout=45000)
    time.sleep(random.uniform(3.0, 5.0))

    # Reddit comment box selectors across modern / shreddit UI
    selectors = [
        "faceplate-textarea-input[name='body'] textarea",
        "div[data-testid='comment-submission-form-richtext']",
        "div[slot='rte']",
        "textarea[placeholder*='comment' i]",
        "div[role='textbox']",
        "p[data-placeholder*='comment' i]"
    ]

    target_box = None
    for sel in selectors:
        try:
            elem = page.locator(sel).first
            if elem.is_visible(timeout=2000):
                target_box = elem
                break
        except Exception:
            continue

    if not target_box:
        # Try clicking placeholder / "Add a comment" button to activate editor
        try:
            placeholder = page.locator("button:has-text('Add a comment'), [placeholder*='Add a comment' i]").first
            if placeholder.is_visible(timeout=3000):
                placeholder.click()
                time.sleep(1.5)
                target_box = page.locator("div[role='textbox'], faceplate-textarea-input textarea, textarea").first
        except Exception as e:
            print(f"[Poster] Could not activate editor: {e}")

    if not target_box:
        print(f"[Poster] FAILED: Could not locate comment input box on {url}")
        return False

    print("[Poster] Editor located. Typing comment with human latency...")
    target_box.click()
    time.sleep(random.uniform(0.5, 1.2))
    human_type(target_box, comment)

    time.sleep(random.uniform(2.0, 4.0))

    # Submit button
    submit_buttons = [
        "button[type='submit']:has-text('Comment')",
        "button:has-text('Comment')",
        "button[slot='submit-button']",
        "button:has-text('Reply')"
    ]

    clicked = False
    for btn_sel in submit_buttons:
        try:
            btn = page.locator(btn_sel).first
            if btn.is_visible(timeout=2000) and btn.is_enabled():
                btn.click()
                clicked = True
                print("[Poster] Comment submitted successfully!")
                break
        except Exception:
            continue

    if not clicked:
        print("[Poster] Warning: Could not locate enabled Comment button.")
        return False

    time.sleep(random.uniform(4.0, 6.0))
    return True


def run_poster(max_posts: int = 5, headless: bool = False):
    """Executes pending posting tasks using your local residential profile."""
    from playwright.sync_api import sync_playwright

    tasks = get_pending_tasks()
    if not tasks:
        print("[Poster] No pending drafts found in queue. Everything is up to date!")
        return

    print(f"=== [SatyaDheesh Poster] Starting Autonomous Run ({len(tasks)} pending) ===")
    os.makedirs(PROFILE_DIR, exist_ok=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=headless,
            viewport={"width": 1280, "height": 800},
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = context.new_page()

        posted_count = 0
        for task in tasks:
            if posted_count >= max_posts:
                print(f"[Poster] Reached max posts limit ({max_posts}). Stopping run.")
                break

            platform = task.get("platform", "reddit")
            print(f"\n[Poster] Processing task {task.get('task_id')} on {platform}...")
            print(f"Title: {task.get('title')}")

            success = False
            if platform == "reddit":
                success = post_to_reddit(page, task)
            else:
                print(f"[Poster] Platform {platform} posting not yet configured.")

            if success:
                mark_as_posted(task)
                posted_count += 1

                # Safe pacing delay between posts (35 to 55 seconds)
                if posted_count < min(len(tasks), max_posts):
                    wait_sec = random.randint(35, 55)
                    print(f"[Poster] Pacing delay: waiting {wait_sec} seconds before next post...")
                    time.sleep(wait_sec)
            else:
                print(f"[Poster] Skipping task {task.get('task_id')} due to failure.")

        context.close()

    print(f"\n=== [SatyaDheesh Poster] Finished. Posted {posted_count} comments. ===")


def main():
    parser = argparse.ArgumentParser(description="SatyaDheesh Mac Posting Agent")
    parser.add_argument("--setup", action="store_true", help="Launch browser to log in to accounts once")
    parser.add_argument("--run", action="store_true", help="Run autonomous hands-free poster")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--max", type=int, default=5, help="Maximum comments to post in this run")

    args = parser.parse_args()

    if args.setup:
        run_setup()
    elif args.run:
        run_poster(max_posts=args.max, headless=args.headless)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
