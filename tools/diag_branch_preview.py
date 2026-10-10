"""READ-ONLY: render report PDFs with the code of another branch, store nothing. URLS input (space-separated):
  branch=student periods=daily:2026-10-09,weekly:2026-W41 only=:ssc recheck=1
The branch is checked out in /tmp/br; reports.build runs there with --preview; with recheck=1 the SSC cards that
the branch's code checks would drop are left out (as `sscca.recheck --apply` would) and a dry-run recheck report is
written. PDFs land in /tmp/diag_out (the diag workflow publishes them to the previews branch)."""
import os
import pathlib
import subprocess
import sys

opts = dict(x.split("=", 1) for x in (os.environ.get("URLS") or "").split() if "=" in x)
branch = opts.get("branch", "student")
periods = opts.get("periods", "daily:2026-10-09").replace(",", " ")
only = opts.get("only", "")
out = pathlib.Path("/tmp/diag_out"); out.mkdir(exist_ok=True)


def run(cmd, **kw):
    print("$", cmd if isinstance(cmd, str) else " ".join(cmd), flush=True)
    r = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True, **kw)
    print((r.stdout or "")[-6000:], (r.stderr or "")[-3000:], flush=True)
    return r.returncode


run(f"git fetch -q origin {branch} && rm -rf /tmp/br && git worktree add -f /tmp/br FETCH_HEAD")
run(f"{sys.executable} -m pip install -q -r /tmp/br/requirements.txt playwright")
run(f"{sys.executable} -m playwright install --with-deps chromium > /tmp/pw.log 2>&1; tail -2 /tmp/pw.log")
runner = r'''
import sys, os
sys.path.insert(0, "/tmp/br")
os.chdir("/tmp/br")
from reports import data
if os.environ.get("RECHECK") == "1":
    from sscca.gate import TOPICS, card_ok, rules
    from sscca.articles import load
    cache = {}
    def keep(c):
        a = cache.get(c["article_id"])
        if a is None:
            a = cache[c["article_id"]] = load([c["article_id"]]).get(c["article_id"]) or {"body": ""}
        text = a["body"][:2500]
        why = rules(c["topic"], int(c["importance"] or 0), "", c["fact"] or "", c["title"] or "", text) or \
              card_ok({"ssc_question": c["question"], "ssc_answer": c["answer"]}, c["fact"] or "", c["title"] or "", text)
        return not why or why.startswith(("state news", "foreign news", "local news"))  # scope is not stored here
    data.SSC_CARD_FILTER = keep
from reports import build
sys.argv = ["build", "--period", os.environ["PERIODS"], "--preview", "/tmp/diag_out"] + (["--only", os.environ["ONLY"]] if os.environ.get("ONLY") else [])
build.main()
'''
pathlib.Path("/tmp/run_prev.py").write_text(runner)
env = {**os.environ, "PERIODS": periods, "ONLY": only, "RECHECK": opts.get("recheck", "1"), "PYTHONPATH": "/tmp/br"}
code = run([sys.executable, "/tmp/run_prev.py"], env=env)
if opts.get("recheck", "1") == "1":
    run([sys.executable, "-m", "sscca.recheck", "--days", "10", "--md", "/tmp/diag_out/recheck.md"], cwd="/tmp/br",
        env={**os.environ, "PYTHONPATH": "/tmp/br"})
for f in sorted(out.iterdir()):
    print(f"- {f.name}: {f.stat().st_size // 1024} KB")
sys.exit(0 if code == 0 else 1)
