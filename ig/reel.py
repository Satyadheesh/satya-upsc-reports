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
import sys
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
    import shutil
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(z.content)) as zf:
        zf.extractall(OUT)
    mp4s = sorted(OUT.rglob("satyadheesh-news-*.mp4")) or sorted(OUT.rglob("*.mp4"))
    if not mp4s:
        raise SystemExit("the artifact has no MP4")
    mp4 = mp4s[-1]
    txt = mp4.with_suffix(".txt")
    article = ""
    for js in OUT.rglob("*.json"):  # older runs: the article id, if the script kept it
        m = re.search(r'"article_id"\s*:\s*"?(\d+)', js.read_text(encoding="utf-8", errors="replace"))
        if m:
            article = m.group(1)
            break
    return mp4, (txt.read_text(encoding="utf-8") if txt.exists() else ""), article


def news_link(article_id):
    """The story's page on the site: Hindi when that page exists (the reels are Hindi), else English."""
    if not str(article_id or "").isdigit():
        return ""
    for url in (f"https://satyadheesh.in/news/{article_id}?lang=hi", f"https://satyadheesh.in/news/{article_id}"):
        try:
            if requests.get(url, timeout=30, headers={"User-Agent": "SatyaDheeshIG/1.0"}).status_code == 200:
                return url.replace("https://", "")
        except requests.RequestException:
            pass
    return ""


def reel_caption(text, link=""):
    """The reel's description, made for Instagram: the story's link (as text: captions show no clickable links),
    no YouTube tags, 5 hashtags."""
    lines = [l.rstrip() for l in (text or "").splitlines()]
    lines = [re.sub(r"https?://", "", l) for l in lines if not re.fullmatch(r"\s*(#\S+\s*)+", l)]
    if link:
        lines = [f"पूरी ख़बर / Full story: {link}" if re.search(r"Website:", l) else l for l in lines]
        if not any(link in l for l in lines):
            lines.append(f"पूरी ख़बर / Full story: {link}")
    body = "\n".join(lines).strip()
    body = re.sub(r"\n{3,}", "\n\n", body)
    if len(body) > 1500:  # cut at the last sentence end before 1500 characters
        cut = max(body.rfind(x, 0, 1500) for x in ("। ", ". ", "।\n", ".\n"))
        body = body[: cut + 1] if cut > 300 else body[:1500]
    tail = "रोज़ की ख़बरें: फ़ॉलो करें @satyadheesh"
    return (f"{body}\n\n{tail}\n\n{TAGS}" if body else f"SatyaDheesh\n\n{tail}\n\n{TAGS}")[:MAX]


SINCE = "2026-10-20T12:00:00Z"  # reels before this were caught up by hand on 20 Oct


def pending_runs(upsc, token, hours=72):
    """Successful reels runs (made from a real story) of the last `hours` that aren't on Instagram yet, oldest first.
    The hourly orchestrator asks for these, so a reel whose own 'post to Instagram' signal got lost is posted anyway."""
    import datetime as dt
    h = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    runs = requests.get(f"{API}/repos/{REPO}/actions/workflows/daily-reel.yml/runs", headers=h, timeout=60,
                        params={"status": "success", "event": "repository_dispatch", "per_page": 30}).json().get("workflow_runs", [])
    floor = max(dt.datetime.fromisoformat(SINCE.replace("Z", "+00:00")).timestamp(), time.time() - hours * 3600)
    out = []
    for r in runs:
        t = dt.datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")).timestamp()
        if t >= floor and not upsc.execute("SELECT 1 FROM ig_posts WHERE key = ?", [f"ig:reel:{r['id']}"]).rows:
            out.append((t, str(r["id"])))
    return [i for _, i in sorted(out)]


def host(mp4, run_id):
    """Put the MP4 where Instagram can fetch it: a one-commit branch `ig-reels` of this public repo (force-pushed,
    so old videos don't pile up in its history), served by jsDelivr with the right content type. -> URL"""
    import subprocess
    repo, tok = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_TOKEN")
    if not repo or not tok:
        raise SystemExit("GITHUB_REPOSITORY / GITHUB_TOKEN missing (run inside the workflow)")
    wt = pathlib.Path("/tmp/ig_reels_wt")
    subprocess.run(["rm", "-rf", str(wt)], check=True)
    (wt / "reels").mkdir(parents=True)
    name = f"{run_id}.mp4"
    (wt / "reels" / name).write_bytes(mp4.read_bytes())
    git = lambda *a: subprocess.run(["git", *a], cwd=wt, check=True, capture_output=True, text=True)
    git("init", "-q")
    git("config", "user.name", "github-actions[bot]")
    git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    git("checkout", "-q", "--orphan", "ig-reels")
    git("add", "-A")
    git("commit", "-qm", f"reel {run_id}")
    git("push", "-q", "-f", f"https://x-access-token:{tok}@github.com/{repo}.git", "HEAD:ig-reels")
    sha = git("rev-parse", "HEAD").stdout.strip()
    urls = [f"https://cdn.jsdelivr.net/gh/{repo}@{sha}/reels/{name}", f"https://raw.githubusercontent.com/{repo}/{sha}/reels/{name}"]
    t0 = time.time()
    while time.time() - t0 < 240:
        for u in urls:
            try:
                r = requests.head(u, timeout=30, allow_redirects=True)
                if r.ok and int(r.headers.get("content-length") or 0) == mp4.stat().st_size:
                    print(f"video at {u} ({r.headers.get('content-type')})", flush=True)
                    return u
            except requests.RequestException:
                pass
        time.sleep(10)
    raise SystemExit("the video never became reachable")


def dispatched_article(upsc, run_id, token):
    """For a reel whose payload is gone: the article the reel scorer dispatched (reel_posts.dispatched_at) within
    10 minutes before the run started."""
    try:
        r = requests.get(f"{API}/repos/{REPO}/actions/runs/{run_id}", timeout=60,
                         headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}).json()
        import datetime as dt
        start = dt.datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")).timestamp()
        rows = upsc.execute("SELECT article_id FROM reel_posts WHERE dispatched_at BETWEEN ? AND ? "
                            "ORDER BY dispatched_at DESC LIMIT 1", [int(start) - 600, int(start) + 60]).rows
        return str(rows[0][0]) if rows else ""
    except Exception as ex:
        print(f"(no article id for run {run_id}: {type(ex).__name__})")
        return ""


def post_one(upsc, ig, run_id, token, article_id, dry, seen):
    key = f"ig:reel:{run_id}"
    if upsc.execute("SELECT 1 FROM ig_posts WHERE key = ?", [key]).rows:
        print(f"reel of run {run_id} already posted")
        return False
    mp4, text, art = fetch(run_id, token)
    title = (text.strip().splitlines() or [""])[0].strip()
    if title and title in seen:  # the same story rendered twice (re-runs): post it once
        print(f"run {run_id}: same story as an earlier reel ({title[:60]}), skipped")
        return False
    seen.add(title)
    cap = reel_caption(text, news_link(article_id or art or dispatched_article(upsc, run_id, token)))
    print(f"reel {run_id} {mp4.name}: {mp4.stat().st_size / 1e6:.1f} MB\n--- caption ---\n{cap}\n---", flush=True)
    if dry:
        print(f"::notice title=Instagram reel dry-run {run_id}::{mp4.name} {mp4.stat().st_size / 1e6:.1f} MB%0A"
              + cap.replace("%", "%25").replace("\n", "%0A")[:2500])
        return False
    media_id = ig.reel(host(mp4, run_id), cap)
    upsc.execute("INSERT OR REPLACE INTO ig_posts (key, media_id, posted_at) VALUES (?, ?, ?)", [key, media_id, int(time.time())])
    try:
        link = ig.get(media_id, fields="permalink").get("permalink")
    except Exception as ex:
        link = f"media {media_id} (permalink lookup failed: {type(ex).__name__})"
    print(f"::notice title=Instagram reel {run_id}::{link}", flush=True)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True, help="a reels run id, several (comma-separated, oldest first), or 'pending' "
                                                    "(every recent reel not on Instagram yet)")
    ap.add_argument("--article-id", default="", help="the story's article id (from the reel's payload), for the link")
    ap.add_argument("--gap", type=float, default=0, help="minutes between reels when several are posted")
    ap.add_argument("--dry-run", action="store_true", help="download and show the caption; post nothing")
    a = ap.parse_args()
    token = os.environ.get("REELS_TOKEN") or ""
    if not token:
        raise SystemExit("REELS_TOKEN missing")
    upsc = upsc_db()
    if a.run_id == "pending":
        runs = pending_runs(upsc, token)
        print(f"reels not on Instagram yet: {runs or 'none'}")
        if not runs:
            return
        a.gap = a.gap or 20
    else:
        runs = [r for r in a.run_id.split(",") if r.strip().isdigit()]
    ig = None if a.dry_run else IG(current_token(upsc))
    seen, failed, last = set(), 0, 0.0
    for k, run in enumerate(runs):
        if last and a.gap and not a.dry_run:
            wait = last + a.gap * 60 - time.time()
            if wait > 0:
                print(f"waiting {wait / 60:.0f} min before the next reel", flush=True)
                time.sleep(wait)
        try:
            if post_one(upsc, ig, run, token, a.article_id if len(runs) == 1 else "", a.dry_run, seen):
                last = time.time()
        except (Exception, SystemExit) as ex:  # one bad reel must not stop the others
            failed += 1
            print(f"::warning::reel {run} failed: {type(ex).__name__}: {str(ex)[:300]}", flush=True)
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    finally:
        close_all()
