"""IST periods matching the site's reports: daily = IST calendar day, weekly = ISO week Mon–Sun IST."""
import datetime as dt

IST = 19800
DAY = 86400
MONTHS_HI = ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"]


def ist_date(ts):
    return dt.datetime.fromtimestamp(ts + IST, dt.timezone.utc).date()


def ist_midnight(d):
    return int(dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc).timestamp()) - IST


def target_ts(now, hhmm):
    """Today's (IST) hh:mm as a unix time."""
    h, m = (int(x) for x in hhmm.split(":"))
    return ist_midnight(ist_date(now)) + h * 3600 + m * 60


def period_for(kind, now):
    """daily: yesterday (complete by 5 AM). weekly: the current ISO week (Mon–Sat done by Sunday morning).
    monthly: the month that just ended (posted on the 1st)."""
    today = ist_date(now)
    if kind == "monthly":
        last = today.replace(day=1) - dt.timedelta(days=1)
        first = last.replace(day=1)
        start = ist_midnight(first)
        return {"kind": kind, "key": first.strftime("%Y-%m"), "start": start, "end": ist_midnight(today.replace(day=1)),
                "first": first, "last": last}
    if kind == "daily":
        d = today - dt.timedelta(days=1)
        start = ist_midnight(d)
        return {"kind": kind, "key": d.isoformat(), "start": start, "end": start + DAY, "first": d, "last": d}
    y, w, _ = today.isocalendar()
    mon = dt.date.fromisocalendar(y, w, 1)
    start = ist_midnight(mon)
    return {"kind": kind, "key": f"{y}-W{w:02d}", "start": start, "end": start + 7 * DAY, "first": mon,
            "last": mon + dt.timedelta(days=6), "week": w}


def _d(d, hi, short=False):
    if hi:
        return f"{d.day} {MONTHS_HI[d.month - 1]}"
    return f"{d.day} {d.strftime('%b' if short else '%B')}"


def label(p, hi=False):
    if p["kind"] == "monthly":
        f = p["first"]
        return f"{MONTHS_HI[f.month - 1]} {f.year}" if hi else f"{f.strftime('%B')} {f.year}"
    if p["kind"] == "daily":
        return f"{_d(p['first'], hi)} {p['first'].year}"
    a, b = _d(p["first"], hi, short=True), f"{_d(p['last'], hi, short=True)} {p['last'].year}"
    return f"सप्ताह {p['week']} · {a} – {b}" if hi else f"Week {p['week']} · {a} – {b}"


def title(p, hi=False):
    if hi:
        k = {"weekly": "साप्ताहिक ", "monthly": "मासिक "}.get(p["kind"], "")
        return f"यूपीएससी {k}करेंट अफेयर्स — {label(p, True)}"
    k = {"weekly": "Weekly ", "monthly": "Monthly "}.get(p["kind"], "")
    return f"UPSC {k}Current Affairs — {label(p)}"


def file_key(p, lang):
    return f"{p['kind']}:{p['key']}:{lang}"


def file_name(p, lang, edition="full"):
    k = {"daily": "Daily", "weekly": "Weekly", "monthly": "Monthly"}[p["kind"]]
    ed = {"brief": "-Brief", "detailed": "-Detailed"}.get(edition, "")
    return f"SatyaDheesh-UPSC-{k}{ed}-Current-Affairs-{p['key']}{'-Hindi' if lang == 'hi' else ''}.pdf"


def page_url(p, hi=False):
    sub = {"daily": "", "weekly": "week/", "monthly": "month/"}[p["kind"]]
    base = f"https://satyadheesh.in/upsc/current-affairs/{sub}{p['key']}"
    return base + ("?lang=hi" if hi else "")
