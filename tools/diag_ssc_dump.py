"""READ-ONLY: dump the SSC runner's rows (ssc_ca) of the last DAYS days with article bodies to
/tmp/diag_out/ssc_dump.json.gz, so gate/card/selection changes can be replayed offline."""
import gzip
import json
import os
import pathlib
import time

from common.db import close_all, upsc_db
from sscca.articles import load

DAYS = int(os.environ.get("DAYS") or 12)
out = pathlib.Path("/tmp/diag_out"); out.mkdir(exist_ok=True)
up = upsc_db()
try:
    now = int(time.time())
    cols = ["article_id", "published_at", "cluster_id", "status", "attempts", "topic", "importance", "scope", "fact",
            "title", "question", "answer", "key_fact", "static_gk", "reason", "prompt_version"]
    rows = [dict(zip(cols, r)) for r in up.execute(
        f"SELECT {', '.join(cols)} FROM ssc_ca WHERE published_at >= ? ORDER BY published_at DESC", [now - DAYS * 86400]).rows]
    want = [r["article_id"] for r in rows if r["status"] == "card" or (
        r["reason"] and not str(r["reason"]).startswith(("model: no", "duplicate", "importance")))]
    arts = load(want) if want else {}
    for r in rows:
        a = arts.get(r["article_id"])
        if a:
            r["body"] = a["body"][:2500]
            r["original_title"] = a["original_title"]
            r["category"] = a["category"]
    (out / "ssc_dump.json.gz").write_bytes(gzip.compress(json.dumps(rows, ensure_ascii=False).encode()))
    from collections import Counter
    print(f"{len(rows)} rows, {len(arts)} with bodies; status {Counter(r['status'] for r in rows)}")
finally:
    close_all()
