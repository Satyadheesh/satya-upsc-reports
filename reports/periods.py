"""Report periods in IST, same keys as the site: daily YYYY-MM-DD, weekly YYYY-Www (ISO, Mon–Sun), monthly YYYY-MM."""
import datetime as dt

IST = 19800
DAY = 86400


def ist_date(ts):
    return dt.datetime.fromtimestamp(ts + IST, dt.timezone.utc).date()


def midnight(d):
    return int(dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc).timestamp()) - IST


def make(kind, first, last, **extra):
    key = (first.isoformat() if kind == "daily" else
           f"{first.isocalendar()[0]}-W{first.isocalendar()[1]:02d}" if kind == "weekly" else f"{first.year}-{first.month:02d}")
    p = {"kind": kind, "key": key, "first": first, "last": last, "start": midnight(first), "end": midnight(last) + DAY}
    if kind == "weekly":
        p["week"] = first.isocalendar()[1]
    p.update(extra)
    return p


def daily(d):
    return make("daily", d, d)


def weekly(d):
    mon = d - dt.timedelta(days=d.weekday())
    return make("weekly", mon, mon + dt.timedelta(days=6))


def monthly(d):
    first = d.replace(day=1)
    nxt = (first + dt.timedelta(days=32)).replace(day=1)
    return make("monthly", first, nxt - dt.timedelta(days=1))


def parse(kind, key):
    if kind == "daily":
        return daily(dt.date.fromisoformat(key))
    if kind == "weekly":
        y, w = key.split("-W")
        return weekly(dt.date.fromisocalendar(int(y), int(w), 1))
    y, m = key.split("-")
    return monthly(dt.date(int(y), int(m), 1))


def periods_for(scope, now):
    """recent (every 2 h): today and yesterday only (cheap on DB reads).
    nightly: last 8 days, this + last week; monthly reports only on Sundays (this month) and on the
    1st/2nd (the month that just ended), because a month of notes is the most expensive read.
    all: 60 days, 9 weeks, 3 months."""
    today = ist_date(now)
    days = {"recent": 2, "nightly": 8, "all": 60}[scope]
    weeks = {"recent": 0, "nightly": 2, "all": 9}[scope]
    months = {"recent": 0, "nightly": 2, "all": 3}[scope]
    out = [daily(today - dt.timedelta(days=i)) for i in range(days)]
    out += [weekly(today - dt.timedelta(weeks=i)) for i in range(weeks)]
    if scope == "nightly":
        if today.weekday() == 6:
            out.append(monthly(today))
        if today.day <= 2:
            out.append(monthly(today.replace(day=1) - dt.timedelta(days=1)))
        return out
    m = today
    for _ in range(months):
        out.append(monthly(m))
        m = m.replace(day=1) - dt.timedelta(days=1)
    return out
