"""READ-ONLY: screenshots of the live site for a visual check. The desktop layout is live for everyone at >= 1024px
(24 Oct 2026); this checks it with NO flag across pages and widths, the story pane, the opt-out (?beta=off),
phones, console errors and horizontal overflow. PNGs go to /tmp/diag_out (diag.yml publishes them to previews:diag/)."""
import os
import time

from playwright.sync_api import sync_playwright

OUT = "/tmp/diag_out"
os.makedirs(OUT, exist_ok=True)
SITE = os.environ.get("SITE") or "https://satyadheesh.in"
NO_SPLASH = "try{sessionStorage.setItem('satya_splash_seen','true')}catch(e){}"
bust = str(int(time.time()))
PAGES = [("home", "/"), ("timelines", "/timelines"), ("upsc", "/upsc"), ("ssc", "/ssc"), ("promises", "/promises"),
         ("netas", "/netas"), ("reports", "/upsc/reports"), ("hindi_home", "/?lang=hi")]


def shot(page, name):
    page.screenshot(path=f"{OUT}/{name}.png")
    print(f"- {name}.png")


def visit(ctx, path, name, errors):
    p = ctx.new_page()
    p.on("pageerror", lambda e: errors.append(f"{name}: {str(e)[:160]}"))
    sep = "&" if "?" in path else "?"
    r = p.goto(f"{SITE}{path}{sep}v={bust}", wait_until="networkidle", timeout=90000)
    p.wait_for_timeout(2500)
    info = p.evaluate("""() => ({cls: document.documentElement.className,
        nav: !!document.querySelector('.desk-nav') && getComputedStyle(document.querySelector('.desk-nav')).display !== 'none',
        overflowX: document.documentElement.scrollWidth > window.innerWidth + 2,
        width: window.innerWidth})""")
    print(f"{name}: HTTP {r.status if r else '?'} | desk-beta={'desk-beta' in info['cls']} | navbar={info['nav']} "
          f"| horizontal overflow={info['overflowX']} | width={info['width']}")
    shot(p, name)
    return p


with sync_playwright() as pw:
    b = pw.chromium.launch()
    errors = []
    d = b.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
    d.add_init_script(NO_SPLASH)
    for name, path in PAGES:
        p = visit(d, path, f"desk_{name}", errors)
        if name == "home":
            cards = p.locator(".feed-list [role=button]")
            if cards.count() > 1:
                cards.nth(1).click()
                p.wait_for_timeout(2500)
                print("  story pane open =", p.evaluate("document.documentElement.classList.contains('desk-pane-open')"),
                      "| story link =", p.locator(".desk-story-link").first.get_attribute("href") if p.locator(".desk-story-link").count() else None)
                shot(p, "desk_story")
        p.close()
    d.close()
    for w in (1024, 1280):
        c = b.new_context(viewport={"width": w, "height": 800})
        c.add_init_script(NO_SPLASH)
        visit(c, "/", f"desk_home_{w}", errors).close()
        c.close()
    # opt-out
    o = b.new_context(viewport={"width": 1440, "height": 900})
    o.add_init_script(NO_SPLASH)
    visit(o, "/?beta=off", "desk_optout", errors).close()
    visit(o, "/timelines", "desk_optout_next_page", errors).close()
    o.close()
    # phones: unchanged
    m = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
    m.add_init_script(NO_SPLASH)
    for name, path in (("home", "/"), ("timelines", "/timelines")):
        visit(m, path, f"mobile_{name}", errors).close()
    m.close()
    b.close()
    print("\nJS errors:", len(errors))
    for x in errors[:20]:
        print("  ", x)
