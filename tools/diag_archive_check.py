"""READ-ONLY: can the workflow token reach the archive repo, and what would the backup cover (months in upsc_reports)."""
import os

import requests

from common.db import close_all, upsc_db
from tools.archive_reports import month_of

REPO = "Satyadheesh/satyadheesh-archive"
for name in ("ARCHIVE_TOKEN", "CORE_TOKEN"):
    tok = os.environ.get(name)
    if not tok:
        print(f"{name}: not set")
        continue
    r = requests.get(f"https://api.github.com/repos/{REPO}", headers={"Authorization": f"Bearer {tok}"}, timeout=30)
    perms = r.json().get("permissions") if r.status_code == 200 else None
    print(f"{name}: repo GET {r.status_code} permissions={perms}")
up = upsc_db()
try:
    by = {}
    for kind, period, size in up.execute("SELECT kind, period, bytes FROM upsc_reports").rows:
        m = by.setdefault(month_of(kind, period), [0, 0])
        m[0] += 1
        m[1] += size or 0
    for m in sorted(by):
        print(f"{m}: {by[m][0]} PDFs, {by[m][1] / 1048576:.1f} MB")
finally:
    close_all()
