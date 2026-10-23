"""READ-ONLY: the live robots.txt (as Cloudflare serves it), and how UPSC notes carry ethics angles (for GS4)."""
import json
import urllib.request

from common.db import close_all, upsc_db

for ua in ("Mozilla/5.0 (compatible; SatyaDheeshAudit/1.0)", "Mozilla/5.0 (compatible; ChatGPT-User/1.0; +https://openai.com/bot)"):
    req = urllib.request.Request("https://satyadheesh.in/robots.txt", headers={"User-Agent": ua})
    try:
        r = urllib.request.urlopen(req, timeout=30)
        print(f"## robots.txt for {ua[:50]} -> {r.status}\n```\n{r.read().decode()[:4000]}\n```")
    except Exception as e:
        print(f"## robots.txt for {ua[:50]}: {e}")
u = upsc_db()
print("\nsamples of secondary / mains_dimensions:")
for r in u.execute("SELECT secondary, mains_dimensions FROM upsc_articles WHERE gs_paper IN ('GS2','GS3') ORDER BY published_at DESC LIMIT 4").rows:
    print("-", str(r[0])[:200], "|", str(r[1])[:200])
n = u.execute("SELECT COUNT(*), SUM(published_at >= strftime('%s','now') - 30*86400) FROM upsc_articles WHERE secondary LIKE '%GS4%' OR secondary LIKE '%ethic%'").rows[0]
m = u.execute("SELECT COUNT(*), SUM(published_at >= strftime('%s','now') - 30*86400) FROM upsc_articles WHERE mains_dimensions LIKE '%thic%'").rows[0]
k = u.execute("SELECT COUNT(*), SUM(published_at >= strftime('%s','now') - 30*86400) FROM upsc_articles WHERE gs_paper != 'GS4' AND "
              "(syllabus_node IN ('probity_corruption','public_admin_ethics') OR keywords LIKE '%corruption%' OR keywords LIKE '%integrity%' "
              "OR keywords LIKE '%accountab%' OR keywords LIKE '%whistle%' OR keywords LIKE '%conflict of interest%')").rows[0]
print(f"\nGS4 in secondary: {n[0]} (30 days: {n[1]}); 'ethic' in mains_dimensions: {m[0]} (30 days: {m[1]}); "
      f"probity/corruption/accountability keywords in other papers: {k[0]} (30 days: {k[1]})")
close_all()
