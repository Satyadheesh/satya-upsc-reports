"""Orchestrator: starts the pipeline jobs when they are due, instead of GitHub's own scheduler.

Started every hour by cron-job.org (and by GitHub's schedule as a backup), and by a job that just finished
(--event <job>-done:<run id>). Each run looks at the jobs' recent runs on GitHub and starts what is due.
It never starts a job that is already running or queued, and it keeps no state of its own: everything is
read from GitHub (run history) and from the code repos (latest commits), so a missed hour simply catches up.

Rules (UTC times; IST = UTC + 5:30):
  * notes, ssc ............ every 6 hours (their own loops continue until the backlog is done)
  * alerts ................ every hourly check (top-news alerts, shadow mode: admin chat only)
  * kit, hindi, reports ... soon after the job they depend on finished new work (and is no longer looping),
                            and at least every 6 hours
  * nightly (21 UTC) ...... study kit full scan, PDF reports nightly scope
  * archive ............... once a month, on the 30th (last day in February) from 06:00 IST: last month + this month
  * checks on change ...... when a job's prompt/model code changed since its check last ran: notes eval,
                            Hindi quality test / token check, study kit preview, SSC preview
  * timeline follows ...... every hourly check: the site sends due timeline-update notifications
Telegram and Instagram are not handled here (they keep their own triggers).

Usage: python tools/orchestrator.py [--event notes-done:123456] [--dry-run]
Env: SAT_TOKEN (Satyadheesh repos), HINDI_TOKEN (SatyaDheesh-Hindi repos).
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

SAT, HINDI = "sat", "hindi"
SVC, REP, HIN = "Satyadheesh/satya-upsc-service", "Satyadheesh/satya-upsc-reports", "SatyaDheesh-Hindi/Hindi"
H = 3600

JOBS = {
    # name: repo, workflow, token, every (s), depends on, inputs for a normal start
    "notes":   dict(repo=SVC, wf="upsc_pipeline.yml", tok=SAT, every=6 * H, after=[], inputs={}),
    "ssc":     dict(repo=REP, wf="sscca.yml", tok=SAT, every=6 * H, after=[], inputs={}),
    "kit":     dict(repo=REP, wf="study_kit.yml", tok=SAT, every=6 * H, after=["notes"], inputs={}),
    "hindi":   dict(repo=HIN, wf="hindi_service.yml", tok=HINDI, every=6 * H, after=["notes", "kit"], inputs={}),
    "reports": dict(repo=REP, wf="reports.yml", tok=SAT, every=6 * H, after=["kit", "hindi"], inputs={"scope": "recent"}),
    # top-news alerts, shadow mode (picks go to the admin Telegram chat only): every hourly check
    "alerts":  dict(repo=REP, wf="alerts.yml", tok=SAT, every=50 * 60, after=[], inputs={}),
}
NIGHTLY_HOUR = 21  # 02:30 IST
NIGHTLY = [  # job, inputs, text in the run's title that marks it as the nightly run
    ("kit", {"full": "true"}, "full scan"),
    ("reports", {"scope": "nightly"}, "nightly"),
]
# Report PDF backup: on the 30th of each month (the last day in February), from 06:00 IST; it backs up last month and
# this month so far (Yash, 17 Oct 2026)
ARCHIVE = dict(repo=REP, wf="archive.yml", tok=SAT, day=30, from_hour_ist=6)
# IndexNow (Bing & co. learn about new/changed pages): the site's own endpoint, 5 times a day. GitHub's hourly schedule
# for it fired only ~5 times a day anyway; the endpoint sends only what changed, so this is plenty.
INDEXNOW_URL = "https://satyadheesh.in/api/indexnow"
INDEXNOW_HOURS = {1, 5, 9, 13, 17}  # UTC; not 21 (the nightly jobs)
# Timeline-follow notifications: the site's job sends what is due (its own limits: 6 h per story, 2 h per device,
# none 22:00-07:00 IST). Every hourly check.
TIMELINE_RUN_URL = "https://satyadheesh.in/api/notifications/timeline-run"
UPSC_RUN_URL = "https://satyadheesh.in/api/notifications/upsc-run"
# Cloudflare refuses Python's default user agent ("error code: 1010"): calls to the site say who they are
SITE_UA = "SatyaDheesh-Orchestrator/1.0 (+https://satyadheesh.in)"
CHECKS = [  # check, code repo, paths, workflow to run, its repo, token, inputs
    ("notes eval", "Satyadheesh/satya-upsc-service-core", ["analyzer.py", "syllabus.py", "eval"],
     "upsc_eval.yml", SVC, SAT, {}),
    ("Hindi quality test", "SatyaDheesh-Hindi/Hindi-core", ["hindi_core.py", "prompts", "glossary", "quality/panel.json"],
     "hindi_quality_test.yml", HIN, HINDI, {}),
    ("Hindi token check", "SatyaDheesh-Hindi/Hindi-core", ["quality/token_check.py"],
     "hindi_token_check.yml", HIN, HINDI, {}),
    ("study kit preview", "Satyadheesh/satya-upsc-reports-core", ["kit/prompt.py", "kit/judge.py", "kit/validate.py", "kit/model.py"],
     "study_kit.yml", REP, SAT, {"preview": "6"}),
    ("SSC preview", "Satyadheesh/satya-upsc-reports-core",
     ["kit/run_ssc.py", "kit/ssc.py", "kit/ssc_guard.py", "kit/ssc_validate.py", "sscca/gate.py", "sscca/select.py", "sscca/run.py"],
     "sscca.yml", REP, SAT, {"preview": "true"}),
]
# Code changes from before the orchestrator existed are not re-checked (they shipped under the old setup).
CHECKS_SINCE = datetime(2026, 10, 13, tzinfo=timezone.utc).timestamp()
RETRY_AFTER = 2 * H  # a job whose last run failed is tried again at most this often
ACTIVE = {"queued", "in_progress", "waiting", "requested", "pending"}

TOKENS = {SAT: os.environ.get("SAT_TOKEN", ""), HINDI: os.environ.get("HINDI_TOKEN", "")}
NOW = time.time()
DRY = "--dry-run" in sys.argv
EVENT = sys.argv[sys.argv.index("--event") + 1] if "--event" in sys.argv else ""
NOTIFYING_RUN = int(EVENT.split(":")[1]) if ":" in EVENT and EVENT.split(":")[1].isdigit() else None
summary, started = [], []


def api(tok, path, method="GET", body=None):
    req = urllib.request.Request(f"https://api.github.com{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None)
    req.add_header("Authorization", f"Bearer {TOKENS[tok]}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
                return json.loads(data) if data else {}
        except urllib.error.HTTPError as e:
            if e.code < 500 or attempt == 2:
                raise RuntimeError(f"{method} {path}: HTTP {e.code} {e.read()[:200]!r}")
        except urllib.error.URLError as e:
            if attempt == 2:
                raise RuntimeError(f"{method} {path}: {e}")
        time.sleep(3 * (attempt + 1))


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() if s else 0.0


def ago(t):
    if not t:
        return "never"
    m = int((NOW - t) / 60)
    return f"{m} min ago" if m < 120 else f"{m // 60} h ago"


_runs = {}


def runs(repo, wf, tok):
    """Recent runs of a workflow, newest first: dicts with id, created, updated, status, conclusion, title."""
    key = (repo, wf)
    if key not in _runs:
        d = api(tok, f"/repos/{repo}/actions/workflows/{wf}/runs?per_page=50")
        out = []
        for r in d.get("workflow_runs", []):
            status, concl = r["status"], r.get("conclusion")
            if NOTIFYING_RUN and r["id"] == NOTIFYING_RUN:  # the run that called us is finishing right now
                status, concl = "completed", "success"
            out.append(dict(id=r["id"], created=ts(r["created_at"]), updated=ts(r["updated_at"]),
                            status=status, conclusion=concl, title=r.get("display_title") or ""))
        _runs[key] = out
    return _runs[key]


def start(name, repo, wf, tok, inputs, why):
    if any(s[1] == repo and s[2] == wf for s in started):
        return  # never start the same workflow twice in one check
    started.append((name, repo, wf, why))
    if DRY:
        print(f"DRY RUN: would start {name} ({repo} {wf} {inputs}) because {why}")
        return
    api(tok, f"/repos/{repo}/actions/workflows/{wf}/dispatches", "POST", {"ref": "main", "inputs": inputs})
    print(f"started {name} ({repo} {wf} {inputs}): {why}")


def regular(r):
    """A normal production run: not a preview/check run, not a partial rebuild (e.g. reports 'only :ssc')."""
    t = r["title"].lower()
    return "preview" not in t and "only " not in t


def is_active(rs):
    return any(r["status"] in ACTIVE for r in rs)


def last_success(rs, predicate=lambda r: True):
    return next((r for r in rs if r["status"] == "completed" and r["conclusion"] == "success" and predicate(r)), None)


def plan_jobs():
    for name, j in JOBS.items():
        rs = runs(j["repo"], j["wf"], j["tok"])
        normal = [r for r in rs if regular(r)]
        active = is_active(normal)
        ok = last_success(normal)
        last_any = normal[0] if normal else None
        state, why = "ok", ""
        if active:
            state = "running"
        else:
            since_ok = NOW - ok["created"] if ok else 1e12
            since_any = NOW - last_any["created"] if last_any else 1e12
            failing = last_any and last_any["status"] == "completed" and last_any["conclusion"] not in ("success", "cancelled", "skipped")
            for dep in j["after"]:
                d = JOBS[dep]
                drs = [r for r in runs(d["repo"], d["wf"], d["tok"]) if regular(r)]
                dok = last_success(drs)
                # the job it depends on finished new work after this job last started, and is not looping any more
                if dok and not is_active(drs) and (not last_any or dok["updated"] > last_any["created"]):
                    why = f"{dep} finished new work {ago(dok['updated'])}"
                    break
            if not why and since_ok >= j["every"]:
                why = f"no successful run for {int(since_ok // H) if since_ok < 1e11 else 'many'} h (every {j['every'] // H} h)"
            if why and failing and since_any < RETRY_AFTER:
                state, why = "failing, waiting to retry", ""
            if why:
                state = "due"
                start(name, j["repo"], j["wf"], j["tok"], j["inputs"], why)
        summary.append((name, state, ago(ok["created"]) if ok else "never",
                        (last_any["conclusion"] or last_any["status"]) if last_any else "-", why))


def plan_nightly():
    t = datetime.fromtimestamp(NOW, timezone.utc)
    if t.hour != NIGHTLY_HOUR:
        return
    for name, inputs, mark in NIGHTLY:
        j = JOBS[name]
        rs = runs(j["repo"], j["wf"], j["tok"])
        done_today = any(mark in r["title"] and NOW - r["created"] < 20 * H for r in rs)
        if done_today:
            continue
        if is_active([r for r in rs if regular(r)]):
            summary.append((f"{name} (nightly)", "waiting: a run is in progress", "", "", ""))
            continue  # the next hourly check is still 21 UTC only if we are early; otherwise tomorrow
        start(f"{name} nightly", j["repo"], j["wf"], j["tok"], inputs, "nightly run")
        summary.append((f"{name} (nightly)", "due", "", "", "nightly run"))


def plan_indexnow():
    t = datetime.fromtimestamp(NOW, timezone.utc)
    if EVENT or t.hour not in INDEXNOW_HOURS:  # the hourly check only, not the runs started by finishing jobs
        return
    if DRY:
        summary.append(("IndexNow", "due", "", "", "dry run: not called"))
        return
    try:
        with urllib.request.urlopen(urllib.request.Request(INDEXNOW_URL, method="POST", data=b"", headers={"User-Agent": SITE_UA}), timeout=60) as r:
            body = json.loads(r.read() or b"{}")
        summary.append(("IndexNow", f"HTTP {r.status}", "", "", f"submitted {body.get('submitted', '?')} of {body.get('due', '?')}"
                        + (" (still running on the server)" if body.get("pending") else "")))
    except Exception as e:
        summary.append(("IndexNow", "call failed", "", "", str(e)[:120]))


def call_site_job(name, url):
    """POST one of the site's notification jobs (auth: REVALIDATE_SECRET) and record its answer."""
    secret = os.environ.get("REVALIDATE_SECRET", "")
    if not secret:
        summary.append((name, "skipped", "", "", "REVALIDATE_SECRET not set"))
        return
    if DRY:
        summary.append((name, "due", "", "", "dry run: not called"))
        return
    try:
        req = urllib.request.Request(url, method="POST", data=b"",
                                     headers={"Authorization": f"Bearer {secret}", "User-Agent": SITE_UA})
        with urllib.request.urlopen(req, timeout=90) as r:
            res = json.loads(r.read() or b"{}")
        summary.append((name, "ok", "", "", ", ".join(f"{k} {v}" for k, v in res.items())[:150]))
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"::notice title={name}::" + json.dumps(res)[:400])
    except Exception as e:
        detail = ""
        if isinstance(e, urllib.error.HTTPError):
            try:
                detail = f" HTTP {e.code}: {e.read()[:200]!r}"
            except Exception:
                detail = f" HTTP {e.code}"
        summary.append((name, "failed", "", "", (str(e) + detail)[:200]))
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"::warning title={name}::{str(e)[:150]}{detail}")


def plan_timeline_follows():
    if EVENT:  # the hourly check only
        return
    call_site_job("timeline follows", TIMELINE_RUN_URL)
    call_site_job("upsc digests", UPSC_RUN_URL)   # "Notify me of new notes" on /upsc: one digest a day per topic


def plan_archive():
    import calendar
    ist = datetime.fromtimestamp(NOW + 19800, timezone.utc)  # IST clock
    day = min(ARCHIVE["day"], calendar.monthrange(ist.year, ist.month)[1])
    if ist.day < day or (ist.day == day and ist.hour < ARCHIVE["from_hour_ist"]):
        return
    due_at = datetime(ist.year, ist.month, day, ARCHIVE["from_hour_ist"], tzinfo=timezone.utc).timestamp() - 19800
    rs = runs(ARCHIVE["repo"], ARCHIVE["wf"], ARCHIVE["tok"])
    if is_active(rs) or last_success(rs, lambda r: r["created"] >= due_at):
        return
    recent_fail = next((r for r in rs if r["created"] >= due_at and NOW - r["created"] < 6 * H), None)
    if recent_fail:
        return
    start("archive", ARCHIVE["repo"], ARCHIVE["wf"], ARCHIVE["tok"], {}, "this month's backup (from the 30th) has not run yet")
    summary.append(("archive", "due", "", "", "monthly, 30th"))


def plan_checks():
    for name, code_repo, paths, wf, repo, tok, inputs in CHECKS:
        latest = 0.0
        for p in paths:
            cs = api(tok, f"/repos/{code_repo}/commits?sha=main&per_page=1&path={urllib.parse.quote(p)}")
            if cs:
                latest = max(latest, ts(cs[0]["commit"]["committer"]["date"]))
        rs = runs(repo, wf, tok)
        if "preview" in inputs:
            rs = [r for r in rs if "preview" in r["title"].lower()]
        last = rs[0]["created"] if rs else 0.0
        if latest > max(last, CHECKS_SINCE) and not is_active(rs):
            start(name, repo, wf, tok, inputs, f"code changed {ago(latest)}, last check {ago(last)}")
            summary.append((name, "due", "", "", "code changed"))


def main():
    for k, v in TOKENS.items():
        if not v:
            sys.exit(f"missing token: {k}")
    errors = []
    for step in (plan_jobs, plan_nightly, plan_indexnow, plan_timeline_follows, plan_archive, plan_checks):
        try:
            step()
        except Exception as e:  # one failing part must not stop the others
            errors.append(f"{step.__name__}: {e}")
            print(f"ERROR {step.__name__}: {e}")
    lines = [f"### Orchestrator {datetime.fromtimestamp(NOW, timezone.utc):%Y-%m-%d %H:%M} UTC"
             + (f" (event: {EVENT})" if EVENT else "") + (" — DRY RUN" if DRY else ""), "",
             "| job | state | last success | last run | why started |", "|---|---|---|---|---|"]
    lines += [f"| {a} | {b} | {c} | {d} | {e} |" for a, b, c, d, e in summary]
    lines += ["", f"Started: {', '.join(s[0] for s in started) or 'nothing'}"]
    lines += [f"- ERROR {e}" for e in errors]
    text = "\n".join(lines)
    print(text)
    if os.environ.get("GITHUB_ACTIONS"):  # one-line annotations: readable through the API without the log
        print("::notice title=orchestrator states::" + "; ".join(f"{x[0]}={x[1]}" for x in summary))
        print("::notice title=orchestrator started::" + ("; ".join(f"{x[0]} ({x[3]})" for x in started) or "nothing")
              + (" [dry run]" if DRY else ""))
        for e in errors:
            print(f"::error title=orchestrator::{e}")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(text + "\n")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
