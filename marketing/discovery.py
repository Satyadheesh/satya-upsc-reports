"""Public Discussion Discovery Engine.

Discovers relevant public conversations on Reddit, Quora, and forums
without requiring API keys, credentials, or private logins.
"""
import html
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from typing import List, Optional

DEFAULT_SUBREDDITS = [
    "UPSC",
    "india",
    "geopolitics",
    "IndianCivics",
    "AskIndia",
]

DEFAULT_INTENT_SEARCHES = [
    ("UPSC", "current affairs"),
    ("UPSC", "editorial OR the hindu"),
    ("UPSC", "answer writing OR notes"),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "application/atom+xml,application/xml,text/xml",
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
    """Removes HTML tags and unescapes text, stripping Reddit RSS boilerplate."""
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


def fetch_reddit_subreddit(subreddit: str, max_posts: int = 20) -> List[DiscussionPost]:
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

                # Skip ultra-short or promotional / stickied meta posts
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


def fetch_reddit_search(subreddit: str, query: str, max_posts: int = 10) -> List[DiscussionPost]:
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


def discover_all(subreddits: Optional[List[str]] = None, max_per_source: int = 15, delay_between: float = 3.5, include_search: bool = True) -> List[DiscussionPost]:
    """Scans all configured communities and high-intent searches with polite rate-limiting intervals."""
    targets = subreddits or DEFAULT_SUBREDDITS
    all_posts = []
    seen_ids = set()

    print(f"[Discovery] Starting community scans across {len(targets)} subreddits...")
    for idx, sub in enumerate(targets):
        print(f"[Discovery] Scanning r/{sub} /new...")
        posts = fetch_reddit_subreddit(sub, max_posts=max_per_source)
        for p in posts:
            if p.post_id not in seen_ids:
                seen_ids.add(p.post_id)
                all_posts.append(p)
        print(f"[Discovery] Found {len(posts)} candidate posts in r/{sub}")

        if delay_between > 0:
            time.sleep(delay_between)

    if include_search:
        print(f"[Discovery] Running {len(DEFAULT_INTENT_SEARCHES)} high-intent searches...")
        for sub, query in DEFAULT_INTENT_SEARCHES:
            print(f"[Discovery] Searching r/{sub} for '{query}'...")
            search_posts = fetch_reddit_search(sub, query, max_posts=8)
            added = 0
            for p in search_posts:
                if p.post_id not in seen_ids:
                    seen_ids.add(p.post_id)
                    all_posts.append(p)
                    added += 1
            print(f"[Discovery] Found {len(search_posts)} search results ({added} new unique)")
            if delay_between > 0:
                time.sleep(delay_between)

    print(f"[Discovery] Total unique candidate discussions collected: {len(all_posts)}")
    return all_posts
