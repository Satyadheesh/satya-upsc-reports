"""Multi-Platform Public Discussion Discovery Engine.

Discovers relevant public conversations across:
1. Reddit (r/UPSC, r/Indian_Academia, r/delhi, r/india, r/IndianCivics, r/AskIndia, r/geopolitics, r/bihar, r/uttarpradesh)
2. ForumIAS Community (active discussion threads & Q&A)
3. Quora (high-intent evergreen UPSC preparation questions)
4. YouTube (daily UPSC editorial & current affairs video discussions)
5. Medium (in-depth UPSC strategy & preparation articles)

Runs strictly at ₹0 cost without requiring API keys, private tokens, or scraping services.
"""
import hashlib
import html
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict

DEFAULT_SUBREDDITS = [
    "UPSC",
    "Indian_Academia",
    "delhi",
    "india",
    "IndianCivics",
    "AskIndia",
    "geopolitics",
    "bihar",
    "uttarpradesh",
]

DEFAULT_INTENT_SEARCHES = [
    ("UPSC", "current affairs"),
    ("UPSC", "editorial OR the hindu"),
    ("UPSC", "answer writing OR notes"),
    ("Indian_Academia", "upsc OR ias"),
    ("delhi", "upsc OR coaching OR library"),
    ("AskIndia", "upsc preparation OR civil services"),
]

PAUSE_REDDIT_UNTIL = "2026-11-06T00:00:00+05:30"


def is_reddit_paused() -> bool:
    """Checks if Reddit discovery and posting is currently paused."""
    try:
        from datetime import datetime, timezone
        import os
        pause_str = os.environ.get("PAUSE_REDDIT_UNTIL", PAUSE_REDDIT_UNTIL)
        if not pause_str:
            return False
        pause_dt = datetime.fromisoformat(pause_str)
        now_dt = datetime.now(pause_dt.tzinfo or timezone.utc)
        return now_dt < pause_dt
    except Exception:
        return True

YOUTUBE_CHANNELS = {
    "VisionIAS": "UCDa407FysJQ2Vtbf-ProNxQ",
    "StudyIQ": "UCrC8mOqJQpoB7NuIMKIS6rQ",
    "ForumIAS": "UCDK7ncRqZjWNi9oVt--23uA",
    "RausIAS": "UCm6ZUU09dU9_8yOaeCkqDNw",
    "InsightsIAS": "UCAQsSHHz0dorMP4MMj7YNjA",
    "PWOnlyIAS": "UCvuI_-ECldjoEyGd8RNbTww",
    "SleepyClasses": "UClGOsY-RB7oCtpddfsJR2jA",
    "DrishtiIASEnglish": "UCkrtAaoos4rxt2cw2CIBjuA",
}

QUORA_SEARCH_QUERIES = [
    "site:quora.com upsc preparation strategy",
    "site:quora.com current affairs for upsc the hindu",
    "site:quora.com upsc mains answer writing",
    "site:quora.com upsc self study coaching",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml,application/atom+xml;q=0.9,*/*;q=0.8",
}


@dataclass
class DiscussionPost:
    platform: str
    post_id: str
    title: str
    url: str
    body: str
    subreddit: Optional[str] = None
    author: Optional[str] = None
    published_at: Optional[str] = None

    def to_dict(self):
        return asdict(self)


def clean_html(raw_html: str) -> str:
    """Removes HTML tags and unescapes text, stripping boilerplate."""
    if not raw_html:
        return ""
    text = html.unescape(raw_html)
    # Strip submitted by boilerplate before tags are removed
    text = re.sub(r"submitted by\s+.*?/u/.*", "", text, flags=re.DOTALL | re.IGNORECASE)
    # Strip HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Strip leftover boilerplate links
    text = re.sub(r"\[link\]|\[comments\]", "", text, flags=re.IGNORECASE)
    return " ".join(text.split())


# ==========================================
# 1. REDDIT DISCOVERY
# ==========================================

def fetch_reddit_subreddit(subreddit: str, max_posts: int = 15) -> List[DiscussionPost]:
    """Fetches recent posts from a subreddit using its public Atom RSS feed."""
    url = f"https://www.reddit.com/r/{subreddit}/new.rss"
    req = urllib.request.Request(url, headers=HEADERS)

    posts = []
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
            root = ET.fromstring(data)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            entries = root.findall("atom:entry", ns)

            for entry in entries[:max_posts]:
                title_elem = entry.find("atom:title", ns)
                link_elem = entry.find("atom:link", ns)
                content_elem = entry.find("atom:content", ns)
                id_elem = entry.find("atom:id", ns)
                author_elem = entry.find("atom:author/atom:name", ns)
                updated_elem = entry.find("atom:updated", ns)

                title = title_elem.text if title_elem is not None else ""
                link = link_elem.attrib.get("href") if link_elem is not None else ""
                raw_id = id_elem.text if id_elem is not None else link
                post_id = raw_id.split("/")[-1] if "/" in raw_id else raw_id
                if post_id.startswith("t3_"):
                    post_id = post_id[3:]

                content = content_elem.text if content_elem is not None else ""
                clean_body = clean_html(content)
                author = author_elem.text if author_elem is not None else ""
                updated = updated_elem.text if updated_elem is not None else ""

                if len(title.strip()) < 15 and len(clean_body) < 30:
                    continue

                posts.append(DiscussionPost(
                    platform="reddit",
                    post_id=post_id,
                    title=title.strip(),
                    url=link.strip(),
                    body=clean_body,
                    subreddit=subreddit,
                    author=author,
                    published_at=updated,
                ))
    except urllib.error.HTTPError as e:
        print(f"[Discovery] Reddit r/{subreddit} HTTP {e.code}: {e.reason}")
    except Exception as e:
        print(f"[Discovery] Reddit r/{subreddit} error: {e}")

    return posts


def fetch_reddit_search(subreddit: str, query: str, max_posts: int = 8) -> List[DiscussionPost]:
    """Fetches high-intent posts matching a query using Reddit's public search RSS feed."""
    encoded_query = urllib.parse.quote_plus(query)
    url = f"https://www.reddit.com/r/{subreddit}/search.rss?q={encoded_query}&sort=new&restrict_sr=1"
    req = urllib.request.Request(url, headers=HEADERS)

    posts = []
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
            root = ET.fromstring(data)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            entries = root.findall("atom:entry", ns)

            for entry in entries[:max_posts]:
                title_elem = entry.find("atom:title", ns)
                link_elem = entry.find("atom:link", ns)
                content_elem = entry.find("atom:content", ns)
                id_elem = entry.find("atom:id", ns)
                author_elem = entry.find("atom:author/atom:name", ns)
                updated_elem = entry.find("atom:updated", ns)

                title = title_elem.text if title_elem is not None else ""
                link = link_elem.attrib.get("href") if link_elem is not None else ""
                raw_id = id_elem.text if id_elem is not None else link
                post_id = raw_id.split("/")[-1] if "/" in raw_id else raw_id
                if post_id.startswith("t3_"):
                    post_id = post_id[3:]

                content = content_elem.text if content_elem is not None else ""
                clean_body = clean_html(content)
                author = author_elem.text if author_elem is not None else ""
                updated = updated_elem.text if updated_elem is not None else ""

                if len(title.strip()) < 15 and len(clean_body) < 30:
                    continue

                posts.append(DiscussionPost(
                    platform="reddit",
                    post_id=post_id,
                    title=title.strip(),
                    url=link.strip(),
                    body=clean_body,
                    subreddit=subreddit,
                    author=author,
                    published_at=updated,
                ))
    except urllib.error.HTTPError as e:
        print(f"[Discovery] Search r/{subreddit} query '{query}' HTTP {e.code}: {e.reason}")
    except Exception as e:
        print(f"[Discovery] Search r/{subreddit} query '{query}' error: {e}")

    return posts


# ==========================================
# 2. FORUMIAS COMMUNITY DISCOVERY
# ==========================================

def fetch_forumias_community(max_pages: int = 2) -> List[DiscussionPost]:
    """Fetches active aspirant discussions from ForumIAS community feeds."""
    posts = []
    seen = set()

    for page in range(max_pages):
        url = f"https://forumias.com/community/get_post?flag=1&page={page}&acttype=3"
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = resp.read().decode("utf-8", errors="ignore")
                matches = re.findall(
                    r'<a[^>]+href=\"(https://forumias\.com/community/post/detail/([^\"]+))\"[^>]*>(.*?)</a>',
                    data
                )
                for link, slug, raw_title in matches:
                    clean_title = clean_html(raw_title)
                    if clean_title and not clean_title.isdigit() and slug not in seen and len(clean_title) >= 10:
                        seen.add(slug)
                        posts.append(DiscussionPost(
                            platform="forumias",
                            post_id=f"fias_{slug[:40]}",
                            title=clean_title,
                            url=link.strip(),
                            body=clean_title,
                            subreddit="ForumIAS:Community",
                        ))
        except Exception as e:
            print(f"[Discovery] ForumIAS page {page} error: {e}")

    return posts


# ==========================================
# 3. QUORA UPSC Q&A DISCOVERY
# ==========================================

def fetch_quora_questions(queries: Optional[List[str]] = None, max_per_query: int = 4) -> List[DiscussionPost]:
    """Discovers high-intent UPSC preparation questions ranking on Quora."""
    targets = queries or QUORA_SEARCH_QUERIES
    posts = []
    seen_slugs = set()

    for q in targets:
        encoded = urllib.parse.quote_plus(q)
        url = f"https://news.google.com/rss/search?q={encoded}&hl=en-IN&gl=IN&ceid=IN:en"
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                root = ET.fromstring(resp.read())
                for item in root.findall(".//item")[:max_per_query]:
                    raw_title = item.find("title").text or ""
                    clean_title = re.sub(r"\s*-\s*Quora.*$", "", raw_title, flags=re.IGNORECASE).strip()
                    if len(clean_title) < 15:
                        continue

                    # Direct Quora question slug
                    slug = re.sub(r"[^a-zA-Z0-9\s-]", "", clean_title).strip()
                    slug = re.sub(r"[\s]+", "-", slug)
                    if not slug or slug in seen_slugs:
                        continue
                    seen_slugs.add(slug)

                    direct_url = f"https://www.quora.com/{slug}"
                    post_id = f"quora_{hashlib.md5(slug.encode()).hexdigest()[:12]}"

                    posts.append(DiscussionPost(
                        platform="quora",
                        post_id=post_id,
                        title=clean_title,
                        url=direct_url,
                        body=clean_title,
                        subreddit="Quora:UPSC",
                    ))
        except Exception as e:
            print(f"[Discovery] Quora query '{q}' error: {e}")

    return posts


# ==========================================
# 4. YOUTUBE UPSC EDITORIAL DISCUSSIONS
# ==========================================

def fetch_youtube_editorial_discussions(channels: Optional[Dict[str, str]] = None, max_per_channel: int = 3) -> List[DiscussionPost]:
    """Discovers fresh daily editorial & current affairs video discussions on YouTube."""
    targets = channels or YOUTUBE_CHANNELS
    posts = []
    ns = {"atom": "http://www.w3.org/2005/Atom"}

    for ch_name, cid in targets.items():
        url = f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                root = ET.fromstring(resp.read())
                for entry in root.findall("atom:entry", ns)[:max_per_channel]:
                    title = entry.find("atom:title", ns).text or ""
                    link = entry.find("atom:link", ns).attrib.get("href", "")
                    vid_match = re.search(r"v=([a-zA-Z0-9_-]+)", link)
                    vid_id = vid_match.group(1) if vid_match else link.split("/")[-1]
                    updated = entry.find("atom:updated", ns)
                    pub_date = updated.text if updated is not None else ""

                    if len(title.strip()) < 15:
                        continue

                    posts.append(DiscussionPost(
                        platform="youtube",
                        post_id=f"yt_{vid_id}",
                        title=title.strip(),
                        url=link.strip(),
                        body=title.strip(),
                        subreddit=f"YouTube:{ch_name}",
                        published_at=pub_date,
                    ))
        except Exception as e:
            print(f"[Discovery] YouTube channel '{ch_name}' error: {e}")

    return posts


# ==========================================
# 5. MEDIUM UPSC STRATEGY ARTICLES
# ==========================================

def fetch_medium_upsc(tag: str = "upsc", max_posts: int = 5) -> List[DiscussionPost]:
    """Discovers in-depth preparation and strategy articles on Medium with open responses."""
    url = f"https://medium.com/feed/tag/{tag}"
    req = urllib.request.Request(url, headers=HEADERS)
    posts = []

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            root = ET.fromstring(resp.read())
            for item in root.findall(".//item")[:max_posts]:
                title = item.find("title").text or ""
                link = item.find("link").text or ""
                clean_link = link.split("?")[0]
                post_id = f"med_{hashlib.md5(clean_link.encode()).hexdigest()[:12]}"

                if len(title.strip()) < 15:
                    continue

                posts.append(DiscussionPost(
                    platform="medium",
                    post_id=post_id,
                    title=title.strip(),
                    url=clean_link,
                    body=title.strip(),
                    subreddit=f"Medium:{tag}",
                ))
    except Exception as e:
        print(f"[Discovery] Medium tag '{tag}' error: {e}")

    return posts


# ==========================================
# MASTER MULTI-PORTAL DISCOVERY
# ==========================================

def discover_all(
    subreddits: Optional[List[str]] = None,
    max_per_source: int = 15,
    delay_between: float = 3.2,
    include_search: bool = True,
    include_forumias: bool = True,
    include_quora: bool = True,
    include_youtube: bool = True,
    include_medium: bool = True,
) -> List[DiscussionPost]:
    """Scans all configured communities and portals with polite rate-limiting intervals."""
    targets = subreddits or DEFAULT_SUBREDDITS
    all_posts = []
    seen_ids = set()

    # 1. Reddit Subreddits
    if is_reddit_paused():
        print(f"[Discovery] Reddit is currently PAUSED until {PAUSE_REDDIT_UNTIL}. Skipping Reddit subreddits.")
    else:
        print(f"[Discovery] Scanning {len(targets)} Reddit subreddits...")
        for idx, sub in enumerate(targets):
            posts = fetch_reddit_subreddit(sub, max_posts=max_per_source)
            added = 0
            for p in posts:
                if p.post_id not in seen_ids:
                    seen_ids.add(p.post_id)
                    all_posts.append(p)
                    added += 1
            print(f"[Discovery] r/{sub}: {len(posts)} found ({added} new)")
            if delay_between > 0:
                time.sleep(delay_between)

    # 2. Reddit Intent Searches
    if include_search and not is_reddit_paused():
        print(f"[Discovery] Running {len(DEFAULT_INTENT_SEARCHES)} high-intent Reddit searches...")
        for sub, query in DEFAULT_INTENT_SEARCHES:
            search_posts = fetch_reddit_search(sub, query, max_posts=6)
            added = 0
            for p in search_posts:
                if p.post_id not in seen_ids:
                    seen_ids.add(p.post_id)
                    all_posts.append(p)
                    added += 1
            print(f"[Discovery] Search r/{sub} '{query}': {len(search_posts)} found ({added} new)")
            if delay_between > 0:
                time.sleep(delay_between)

    # 3. ForumIAS Community
    if include_forumias:
        print("[Discovery] Scanning ForumIAS Community discussion threads...")
        fias_posts = fetch_forumias_community(max_pages=2)
        added = 0
        for p in fias_posts:
            if p.post_id not in seen_ids:
                seen_ids.add(p.post_id)
                all_posts.append(p)
                added += 1
        print(f"[Discovery] ForumIAS: {len(fias_posts)} found ({added} new)")
        if delay_between > 0:
            time.sleep(delay_between)

    # 4. Quora UPSC Questions
    if include_quora:
        print(f"[Discovery] Scanning Quora UPSC questions across {len(QUORA_SEARCH_QUERIES)} intent topics...")
        quora_posts = fetch_quora_questions(max_per_query=4)
        added = 0
        for p in quora_posts:
            if p.post_id not in seen_ids:
                seen_ids.add(p.post_id)
                all_posts.append(p)
                added += 1
        print(f"[Discovery] Quora: {len(quora_posts)} found ({added} new)")
        if delay_between > 0:
            time.sleep(delay_between)

    # 5. YouTube Daily UPSC Editorials
    if include_youtube:
        print(f"[Discovery] Scanning YouTube UPSC daily editorial channels ({len(YOUTUBE_CHANNELS)} channels)...")
        yt_posts = fetch_youtube_editorial_discussions(max_per_channel=3)
        added = 0
        for p in yt_posts:
            if p.post_id not in seen_ids:
                seen_ids.add(p.post_id)
                all_posts.append(p)
                added += 1
        print(f"[Discovery] YouTube: {len(yt_posts)} found ({added} new)")
        if delay_between > 0:
            time.sleep(delay_between)

    # 6. Medium UPSC Articles
    if include_medium:
        print("[Discovery] Scanning Medium UPSC publications...")
        med_posts = fetch_medium_upsc(max_posts=5)
        added = 0
        for p in med_posts:
            if p.post_id not in seen_ids:
                seen_ids.add(p.post_id)
                all_posts.append(p)
                added += 1
        print(f"[Discovery] Medium: {len(med_posts)} found ({added} new)")

    print(f"[Discovery] Complete! Total unique candidate discussions collected across all portals: {len(all_posts)}")
    return all_posts
