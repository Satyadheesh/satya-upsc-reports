"""READ-ONLY: how the Instagram posts are doing: the last 50 posts with type, first caption line, views, reach,
likes, comments, saves and shares (Instagram's own numbers), and averages per type and per topic (reels)."""
import collections
import statistics

import requests

from common.db import close_all, upsc_db

BASE = "https://graph.instagram.com/v23.0"
upsc = upsc_db()
tok = {r[0]: r[1] for r in upsc.execute("SELECT k, token FROM ig_auth").rows}.get("long_lived")
P = {"access_token": tok}
me = requests.get(f"{BASE}/me", params={**P, "fields": "user_id,username,followers_count,media_count"}, timeout=60).json()
print(f"@{me.get('username')}: {me.get('followers_count')} followers, {me.get('media_count')} posts\n")
media = requests.get(f"{BASE}/{me.get('user_id') or me.get('id')}/media", timeout=60,
                     params={**P, "fields": "id,timestamp,media_type,media_product_type,caption,like_count,comments_count,permalink",
                             "limit": 50}).json().get("data", [])
rows = []
for m in media:
    ins = {}
    for metric in ("views", "reach", "saved", "shares", "total_interactions"):
        r = requests.get(f"{BASE}/{m['id']}/insights", params={**P, "metric": metric}, timeout=60).json()
        try:
            ins[metric] = r["data"][0]["values"][0]["value"]
        except Exception:
            ins[metric] = None
    kind = "reel" if m.get("media_product_type") == "REELS" else ("carousel" if m.get("media_type") == "CAROUSEL_ALBUM" else m.get("media_type", "").lower())
    first = (m.get("caption") or "").strip().splitlines()[0][:70] if m.get("caption") else ""
    rows.append((m["timestamp"][:16].replace("T", " "), kind, ins["views"], ins["reach"], m.get("like_count"), m.get("comments_count"),
                 ins["saved"], ins["shares"], first))
print("| posted (UTC) | type | views | reach | likes | comments | saves | shares | first line |")
print("|---|---|---|---|---|---|---|---|---|")
for r in rows:
    print("| " + " | ".join("-" if v is None else str(v) for v in r) + " |")
print()
by = collections.defaultdict(list)
for r in rows:
    by[r[1]].append(r)
for k, rs in by.items():
    v = [r[2] for r in rs if r[2] is not None]
    re_ = [r[3] for r in rs if r[3] is not None]
    print(f"- {k}: {len(rs)} posts, median views {statistics.median(v) if v else '-'}, median reach {statistics.median(re_) if re_ else '-'}, "
          f"likes {sum(r[4] or 0 for r in rs)}, shares {sum(r[7] or 0 for r in rs)}, saves {sum(r[6] or 0 for r in rs)}")
close_all()
