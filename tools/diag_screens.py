"""READ-ONLY: screenshots of the live site for a visual check (desktop beta + mobile without the flag).
PNGs go to /tmp/diag_out (diag.yml publishes them to previews:diag/)."""
import os
import time

from playwright.sync_api import sync_playwright

OUT = "/tmp/diag_out"
os.makedirs(OUT, exist_ok=True)
SITE = os.environ.get("SITE") or "https://satyadheesh.in"
NO_SPLASH = "try{sessionStorage.setItem('satya_splash_seen','true')}catch(e){}"
bust = str(int(time.time()))


def shot(page, name):
    page.screenshot(path=f"{OUT}/{name}.png")
    print(f"- {name}.png")


with sync_playwright() as pw:
    b = pw.chromium.launch()
    d = b.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
    d.add_init_script(NO_SPLASH)
    p = d.new_page()
    p.goto(f"{SITE}/?beta=desktop&v={bust}", wait_until="networkidle", timeout=90000)
    p.wait_for_timeout(2500)
    print("desktop home: html class =", p.evaluate("document.documentElement.className"),
          "| navbar visible =", p.is_visible(".desk-nav"), "| rail items =", p.locator(".desk-rail-item").count(),
          "| feed cards =", p.locator(".feed-list > div").count())
    shot(p, "desk_home")
    cards = p.locator(".feed-list [role=button]")
    if cards.count() > 1:
        cards.nth(1).click()
        p.wait_for_timeout(2500)
        print("story pane open =", p.evaluate("document.documentElement.classList.contains('desk-pane-open')"),
              "| story link =", p.locator(".desk-story-link").first.get_attribute("href"))
        shot(p, "desk_story")
    p.goto(f"{SITE}/timelines?beta=desktop&v={bust}", wait_until="networkidle", timeout=90000)
    p.wait_for_timeout(3500)
    print("timelines: pane =", p.is_visible(".tl-pane"), "| title =", (p.locator(".tl-pane-title").first.text_content() or "")[:80] if p.locator(".tl-pane-title").count() else None)
    shot(p, "desk_timelines")
    d.close()

    m = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
    m.add_init_script(NO_SPLASH)
    mp = m.new_page()
    mp.goto(f"{SITE}/?v={bust}", wait_until="networkidle", timeout=90000)
    mp.wait_for_timeout(2000)
    print("mobile (no flag): html class =", mp.evaluate("document.documentElement.className"),
          "| navbar visible =", mp.is_visible(".desk-nav"), "| bottom nav visible =", mp.is_visible("nav"))
    shot(mp, "mobile_home")
    m.close()

    # a desktop visitor WITHOUT the flag also sees today's layout
    n = b.new_context(viewport={"width": 1440, "height": 900})
    n.add_init_script(NO_SPLASH)
    np_ = n.new_page()
    np_.goto(f"{SITE}/?v={bust}", wait_until="networkidle", timeout=90000)
    np_.wait_for_timeout(1500)
    print("desktop without flag: html class =", np_.evaluate("document.documentElement.className"), "| navbar visible =", np_.is_visible(".desk-nav"))
    shot(np_, "desk_noflag")
    b.close()
