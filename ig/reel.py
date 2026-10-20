"""Post a reel of the Satyadheesh/reels pipeline to Instagram as a Reel (Yash, 20 Oct 2026: every reel that goes to
YouTube goes to Instagram too).

The reels workflow sends repository_dispatch 'ig_reel' {run_id} after its YouTube upload; instagram-reel.yml then runs

  python -m ig.reel --run-id <reels run id> [--dry-run]

It downloads that run's artifact (the MP4 + its description text), uploads the video straight to Instagram and records
it in ig_posts (key ig:reel:<run id>), so a reel is never posted twice."""
import argparse
import io
import os
import pathlib
import re
import time
import zipfile

import requests

from common.db import close_all, upsc_db

from .graph import IG, current_token

REPO = "Satyadheesh/reels"
API = "https://api.github.com"
OUT = pathlib.Path("/tmp/ig_reel")
TAGS = "#SatyaDheesh #HindiNews #NewsInHindi #CurrentAffairs #Reels"
MAX = 2200


def fetch(run_id, token, wait=600):
    """The run's MP4 and description text (artifact 'reel-<run id>'). Waits up to `wait` s for the artifact."""
    h = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    t0 = time.time()
    while True:
        r = requests.get(f"{API}/repos/{REPO}/actions/runs/{run_id}/artifacts", headers=h, timeout=60)
        if r.status_code in (401, 403, 404):
            raise SystemExit(f"cannot read the reels run's artifacts (HTTP {r.status_code}): the token needs Actions read on {REPO}")
        arts = [a for a in r.json().get("artifacts", []) if not a.get("expired")]
        if arts:
            break
        if time.time() - t0 > wait:
            raise SystemExit(f"no artifact on reels run {run_id} after {wait}s")
        time.sleep(20)
    z = requests.get(arts[0]["archive_download_url"], headers=h, timeout=300)  # redirects to storage; requests drops the auth header
    z.raise_for_status()
    OUT.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(z.content)) as zf:
        zf.extractall(OUT)
    mp4s = sorted(OUT.rglob("satyadheesh-news-*.mp4")) or sorted(OUT.rglob("*.mp4"))
    if not mp4s:
        raise SystemExit("the artifact has no MP4")
    mp4 = mp4s[-1]
    txt = mp4.with_suffix(".txt")
    return mp4, (txt.read_text(encoding="utf-8") if txt.exists() else "")


def reel_caption(text):
    """The reel's description, made for Instagram: no links (they aren't clickable), no YouTube tags, 5 hashtags."""
    lines = [l.rstrip() for l in (text or "").splitlines()]
    lines = [re.sub(r"https?://", "", l) for l in lines if not re.fullmatch(r"\s*(#\S+\s*)+", l)]
    body = "\n".join(lines).strip()
    body = re.sub(r"\n{3,}", "\n\n", body)
    if len(body) > 1500:  # cut at the last sentence end before 1500 characters
        cut = max(body.rfind(x, 0, 1500) for x in ("। ", ". ", "।\n", ".\n"))
        body = body[: cut + 1] if cut > 300 else body[:1500]
    tail = "रोज़ की ख़बरें: फ़ॉलो करें @satyadheesh"
    return (f"{body}\n\n{tail}\n\n{TAGS}" if body else f"SatyaDheesh\n\n{tail}\n\n{TAGS}")[:MAX]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--dry-run", action="store_true", help="download and show the caption; post nothing")
    a = ap.parse_args()
    token = os.environ.get("REELS_TOKEN") or ""
    if not token:
        raise SystemExit("REELS_TOKEN missing")
    upsc = upsc_db()
    key = f"ig:reel:{a.run_id}"
    if upsc.execute("SELECT 1 FROM ig_posts WHERE key = ?", [key]).rows:
        print(f"reel of run {a.run_id} already posted")
        return
    mp4, text = fetch(a.run_id, token)
    cap = reel_caption(text)
    print(f"reel {mp4.name}: {mp4.stat().st_size / 1e6:.1f} MB\n--- caption ---\n{cap}\n---")
    if a.dry_run:
        print(f"::notice title=Instagram reel dry-run::{mp4.name} {mp4.stat().st_size / 1e6:.1f} MB%0A"
              + cap.replace("%", "%25").replace("\n", "%0A")[:2500])
        return
    ig = IG(current_token(upsc))
    media_id = ig.reel(str(mp4), cap)
    upsc.execute("INSERT OR REPLACE INTO ig_posts (key, media_id, posted_at) VALUES (?, ?, ?)", [key, media_id, int(time.time())])
    try:
        link = ig.get(media_id, fields="permalink").get("permalink")
    except Exception as ex:
        link = f"media {media_id} (permalink lookup failed: {type(ex).__name__})"
    print(f"::notice title=Instagram reel::{link}")


if __name__ == "__main__":
    try:
        main()
    finally:
        close_all()
