"""READ-ONLY: checks the live site after a deploy: title, nav, Netas card, slow pages and their live news."""
import json, re, time, urllib.request

def get(path, n=2):
    out = None
    for _ in range(n):
        req = urllib.request.Request("https://satyadheesh.in" + path, headers={"User-Agent": "SatyaDiag/1"})
        t = time.time()
        with urllib.request.urlopen(req, timeout=60) as r:
            b = r.read(); out = (r.status, b, r.headers.get("x-vercel-cache"), r.headers.get("age"), r.headers.get("cache-control"), round(time.time() - t, 2))
    return out

def title(b):
    m = re.search(rb"<title>([^<]*)</title>", b); return m.group(1).decode() if m else "-"

s, b, c, a, cc, t = get("/")
desc = re.search(rb'<meta name="description" content="([^"]*)"', b)
print("## Home")
print("- title:", title(b))
print("- description:", desc.group(1).decode() if desc else "-")
print("- og:image alt:", (re.search(rb'property="og:image:alt" content="([^"]*)"', b) or [b"", b"-"])[1].decode())
print("- bottom bar labels:", [x.decode() for x in re.findall(rb">(FEED|TIMELINES|NETAS|VAADE|DATA)<", b)])
print("- bytes:", f"{len(b):,}", "cache:", c)

s, b, c, a, cc, t = get("/netas")
print("\n## /netas")
print("- vaade card:", b"Promise tracker" in b, "| promises line:", (re.search(rb"(\d+) promises, with sources", b) or [b"", b"-"])[1].decode())
print("- bytes:", f"{len(b):,}", "cache:", c, "| cache-control:", cc)

print("\n## Slow pages (2nd fetch)")
print("| path | status | bytes | cache | cache-control |")
print("|---|---|---|---|---|")
for p in ["/vaade", "/party/bjp", "/party/inc", "/state/delhi", "/topic/economy", "/vaade/p001"]:
    try:
        s, b, c, a, cc, t = get(p)
        print(f"| {p} | {s} | {len(b):,} | {c} | {cc} |")
    except Exception as e:
        print(f"| {p} | {type(e).__name__} {e} | | | |")

print("\n## Live news API")
for q in ["type=entityNews&kind=party&param=bjp&lang=en", "type=entityNews&kind=state&param=delhi&lang=en", "type=entityNews&kind=topic&param=economy&lang=en"]:
    s, b, c, a, cc, t = get("/api/data?" + q, 1)
    d = json.loads(b)
    arts = d.get("articles", [])
    print(f"- {q}: {s}, {len(arts)} stories, newest: {(arts[0].get('scraped_at') if arts else '-')}, cache-control: {cc}")
