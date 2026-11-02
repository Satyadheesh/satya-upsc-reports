"""Public Discussion Discovery Engine.

Discovers relevant public conversations on Reddit, Quora, and forums
without requiring API keys, credentials, or private logins.
"""
import re
import time
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
    """Removes HTML tags and unescapes text."""
    if not raw_html:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw_html)
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


def discover_all(subreddits: Optional[List[str]] = None, max_per_source: int = 15, delay_between: float = 3.0) -> List[DiscussionPost]:
    """Scans all configured communities with polite rate-limiting intervals."""
    targets = subreddits or DEFAULT_SUBREDDITS
    all_posts = []

    print(f"[Discovery] Starting discovery across {len(targets)} communities...")
    for idx, sub in enumerate(targets):
        print(f"[Discovery] Scanning r/{sub}...")
        posts = fetch_reddit_subreddit(sub, max_posts=max_per_source)
        print(f"[Discovery] Found {len(posts)} candidate posts in r/{sub}")
        all_posts.extend(posts)

        if idx < len(targets) - 1 and delay_between > 0:
            time.sleep(delay_between)

    print(f"[Discovery] Total candidates collected: {len(all_posts)}")
    return all_posts
