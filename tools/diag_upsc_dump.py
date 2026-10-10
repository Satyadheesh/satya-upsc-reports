"""READ-ONLY: dump the UPSC report items (reports.data.Window, English and Hindi) of a few periods to
/tmp/diag_out/upsc_dump.json.gz, so selection and rendering changes can be replayed offline. PERIODS env:
'daily:2026-10-09 weekly:2026-W41'."""
import gzip
import json
import os
import pathlib

from common.db import close_all, main_db, translation_db, upsc_db
from reports.data import Window
from reports.periods import parse

PERIODS = (os.environ.get("PERIODS") or "daily:2026-10-08 daily:2026-10-09 weekly:2026-W41 monthly:2026-09").split()
out = pathlib.Path("/tmp/diag_out"); out.mkdir(exist_ok=True)
try:
    ps = [parse(*x.split(":", 1)) for x in PERIODS]
    w = Window(upsc_db(), main_db(), min(p["start"] for p in ps), max(p["end"] for p in ps), translation_db())
    res = {}
    for p in ps:
        res[p["kind"] + ":" + p["key"]] = {"en": w.period(p, "en"), "hi": w.period(p, "hi")}
        print(p["key"], len(res[p["kind"] + ":" + p["key"]]["en"]), "en items")
    (out / "upsc_dump.json.gz").write_bytes(gzip.compress(json.dumps(res, ensure_ascii=False, default=str).encode()))
finally:
    close_all()
