"""Back up the report PDFs (upsc_reports + upsc_report_chunks in the UPSC DB) to GitHub releases of the private
repo Satyadheesh/satyadheesh-archive: one release `reports-YYYY-MM` per month, one asset per PDF
(daily_2026-10-09_en_brief.pdf ...). Re-running replaces assets whose PDF changed (same name, new size), so a month
can be archived again after late rebuilds. Reads the DB only.

  python tools/archive_reports.py              (last month and this month so far: the monthly run on the 30th)
  python tools/archive_reports.py 2026-09      (one month)
  python tools/archive_reports.py all          (every month in the DB)

Needs ARCHIVE_TOKEN (contents read/write on the archive repo; CORE_TOKEN works if it includes that repo).
"""
import datetime as dt
import os
import sys
import time

import requests

from common.db import close_all, upsc_db

REPO = os.environ.get("ARCHIVE_REPO", "Satyadheesh/satyadheesh-archive")
API = f"https://api.github.com/repos/{REPO}"


def gh(method, url, **kw):
    tok = os.environ.get("ARCHIVE_TOKEN") or os.environ.get("CORE_TOKEN")
    if not tok:
        raise SystemExit("ARCHIVE_TOKEN not set")
    h = {"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json", **kw.pop("headers", {})}
    for attempt in range(4):
        r = requests.request(method, url, headers=h, timeout=120, **kw)
        if r.status_code < 500:
            return r
        time.sleep(5 * (attempt + 1))
    return r


def month_of(kind, period):
    """The month a stored report belongs to: daily 2026-10-09 -> 2026-10; weekly 2026-W41 -> its Monday's month."""
    if kind == "weekly":
        y, w = period.split("-W")
        return dt.date.fromisocalendar(int(y), int(w), 1).strftime("%Y-%m")
    return period[:7]


def release(month):
    tag = f"reports-{month}"
    r = gh("GET", f"{API}/releases/tags/{tag}")
    if r.status_code == 200:
        return r.json()
    r = gh("POST", f"{API}/releases", json={"tag_name": tag, "name": f"Reports {month}", "target_commitish": "main",
                                             "body": f"Report PDFs of {month} (UPSC Brief, Detailed, SSC; EN and HI)."})
    if r.status_code >= 300:
        raise SystemExit(f"could not create release {tag}: {r.status_code} {r.text[:200]}")
    return r.json()


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    up = upsc_db()
    rows = up.execute("SELECT key, kind, period, bytes FROM upsc_reports ORDER BY key").rows
    by_month = {}
    for key, kind, period, size in rows:
        by_month.setdefault(month_of(kind, period), []).append((key, size))
    if arg == "all":
        months = sorted(by_month)
    elif arg:
        months = [arg]
    else:  # last month (its last days, built after the previous run) and this month so far; unchanged PDFs are skipped
        today = (dt.datetime.utcnow() + dt.timedelta(hours=5, minutes=30)).date()
        first = today.replace(day=1)
        months = [(first - dt.timedelta(days=1)).strftime("%Y-%m"), today.strftime("%Y-%m")]
    total = 0
    for month in months:
        items = by_month.get(month, [])
        if not items:
            print(f"{month}: no reports")
            continue
        rel = release(month)
        have = {a["name"]: a for a in gh("GET", f"{API}/releases/{rel['id']}/assets?per_page=100").json()}
        page = 2
        while len(have) and len(have) % 100 == 0:
            more = gh("GET", f"{API}/releases/{rel['id']}/assets?per_page=100&page={page}").json()
            if not more:
                break
            have.update({a["name"]: a for a in more})
            page += 1
        up_n = skip = 0
        for key, size in items:
            name = key.replace(":", "_") + ".pdf"
            if name in have and have[name]["size"] == size:
                skip += 1
                continue
            pdf = b"".join(bytes(r[0]) for r in up.execute(
                "SELECT data FROM upsc_report_chunks WHERE key = ? ORDER BY n", [key]).rows)
            if not pdf:
                continue
            if name in have:  # changed since the last backup
                gh("DELETE", f"{API}/releases/assets/{have[name]['id']}")
            r = gh("POST", f"https://uploads.github.com/repos/{REPO}/releases/{rel['id']}/assets?name={name}",
                   headers={"Content-Type": "application/pdf"}, data=pdf)
            if r.status_code >= 300:
                print(f"::warning::{name}: upload failed {r.status_code} {r.text[:150]}")
                continue
            up_n += 1
            total += len(pdf)
        print(f"{month}: {up_n} uploaded, {skip} unchanged ({len(items)} reports)")
    print(f"done: {total / 1048576:.1f} MB uploaded")


if __name__ == "__main__":
    try:
        main()
    finally:
        close_all()
