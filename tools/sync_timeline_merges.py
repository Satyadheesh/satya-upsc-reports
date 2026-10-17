"""Hourly (orchestrator): follow up on timelines the timeline service merged (event_redirects in the main DB).

  * UPSC notes keep the timeline they belong to: upsc_articles.event_id of the moved updates -> the new timeline
    (by article id, so only those rows are touched);
  * the site refreshes its timeline caches once ('events' tag), so the old address starts redirecting and the
    merged timeline shows all its updates.
A bookmark (sync_marks in the UPSC DB) remembers the last merge handled; it moves only after both steps worked.
Safe to run any number of times.
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

from common.db import close_all, in_chunks, main_db, upsc_db

SITE = "https://satyadheesh.in"
SITE_UA = "SatyaDheesh-Orchestrator/1.0 (+https://satyadheesh.in)"


def q(c, sql, args=()):
    for i in range(3):
        try:
            return c.execute(sql, list(args)).rows
        except Exception:
            if i == 2:
                raise
            time.sleep(2)


def main():
    dry = "--dry-run" in sys.argv
    m, u = main_db(), upsc_db()
    try:
        if not q(m, "SELECT 1 FROM sqlite_master WHERE name = 'event_redirects'"):
            print("no merges yet")
            return 0
        q(u, "CREATE TABLE IF NOT EXISTS sync_marks (name TEXT PRIMARY KEY, value INTEGER NOT NULL)")
        row = q(u, "SELECT value FROM sync_marks WHERE name = 'timeline_merges'")
        mark = int(row[0][0]) if row else 0
        reds = q(m, "SELECT old_id, new_id, merged_at FROM event_redirects WHERE merged_at > ? ORDER BY merged_at", [mark])
        if not reds:
            print(f"nothing new since {mark}")
            return 0
        newest = max(int(r[2]) for r in reds)
        fixed = 0
        for old_id, new_id, _ in reds:
            arts = [int(r[0]) for r in q(m, "SELECT article_id FROM event_articles WHERE event_id = ?", [int(new_id)])]
            if not arts or dry:
                continue
            for i in range(0, len(arts), 300):
                chunk = arts[i:i + 300]
                res = u.execute(f"UPDATE upsc_articles SET event_id = ? WHERE event_id = ? AND article_id IN ({','.join('?' * len(chunk))})",
                                [int(new_id), int(old_id)] + chunk)
                fixed += res.rows_affected or 0
        print(f"{len(reds)} new merges; UPSC notes moved to their merged timeline: {fixed}")
        if dry:
            return 0
        secret = os.environ.get("REVALIDATE_SECRET", "")
        if not secret:
            print("REVALIDATE_SECRET not set: bookmark not moved")
            return 0
        url = f"{SITE}/api/revalidate?" + urllib.parse.urlencode({"tag": "events", "secret": secret})
        req = urllib.request.Request(url, method="POST", data=b"", headers={"User-Agent": SITE_UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            res = json.loads(r.read() or b"{}")
        print("site refresh:", {k: v for k, v in res.items() if k != "now"})
        if res.get("revalidated"):
            q(u, "INSERT OR REPLACE INTO sync_marks (name, value) VALUES ('timeline_merges', ?)", [newest])
        return 0
    finally:
        close_all()


if __name__ == "__main__":
    sys.exit(main())
