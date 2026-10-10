"""READ-ONLY: material for a content review. Runs diag_sscca.py, then writes a set of stored report PDFs
(SSC + UPSC, daily/weekly/monthly, EN/HI) to /tmp/diag_out so the diag workflow publishes them."""
import os, pathlib, runpy

from common.db import close_all, upsc_db

runpy.run_path(str(pathlib.Path(__file__).with_name("diag_sscca.py")), run_name="__main__")

KEYS = os.environ.get("REVIEW_KEYS") or (
    "daily:2026-10-09:en:ssc daily:2026-10-08:en:ssc weekly:2026-W41:en:ssc "
    "daily:2026-10-09:en:brief daily:2026-10-09:en:detailed daily:2026-10-09:hi:brief "
    "weekly:2026-W40:en:brief monthly:2026-09:en:brief")
out = pathlib.Path("/tmp/diag_out"); out.mkdir(exist_ok=True)
up = upsc_db()
try:
    print("\n## Stored reports for the review")
    print("\nlatest weekly/monthly keys:", [r[0] for r in up.execute(
        "SELECT key FROM upsc_reports WHERE kind IN ('weekly','monthly') ORDER BY updated_at DESC LIMIT 12").rows])
    for key in KEYS.split():
        meta = up.execute("SELECT items, bytes, chunks, updated_at FROM upsc_reports WHERE key = ?", [key]).rows
        if not meta:
            print(f"- {key}: not stored"); continue
        items, size, chunks, upd = meta[0]
        parts = up.execute("SELECT data FROM upsc_report_chunks WHERE key = ? ORDER BY n", [key]).rows
        pdf = b"".join(bytes(r[0]) for r in parts)
        (out / (key.replace(":", "_") + ".pdf")).write_bytes(pdf)
        print(f"- {key}: {items} items, {len(pdf) // 1024} KB (stored {size // 1024} KB, {chunks} chunks)")
finally:
    close_all()
