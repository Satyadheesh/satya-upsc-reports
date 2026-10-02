"""What goes into a post: the stored report PDF, a caption with the top stories, and quiz polls from the study kit."""
import html
import json
import re

from common.db import in_chunks

from .periods import file_key, page_url, title

CAPTION_MAX = 1024           # Telegram limit for document captions
POLL_Q, POLL_OPT, POLL_EXPL = 300, 100, 200
LIVE_BLOG = re.compile(r"\blive\b|live updates|as it happened", re.I)


def esc(s):
    return html.escape(str(s or ""), quote=False)


def clean_title(t):
    t = re.sub(r"\*\*|__|`", "", " ".join(str(t or "").split())).strip()
    return t[:-1] if t.endswith(".") else t


def read_report(upsc, period_key_base):
    """Prefer the redesigned Brief (…:brief); fall back to the old full report while the Brief isn't stored."""
    pdf, meta = read_pdf(upsc, period_key_base + ":brief")
    if pdf is not None:
        return pdf, meta, "brief"
    pdf, meta = read_pdf(upsc, period_key_base)
    return pdf, meta, "full"


def read_pdf(upsc, key):
    """The PDF the report builder stored, or None (Hindi is only stored once >= 80% translated)."""
    meta = upsc.execute("SELECT chunks, items, updated_at FROM upsc_reports WHERE key = ?", [key]).rows
    if not meta:
        return None, None
    rows = upsc.execute("SELECT data FROM upsc_report_chunks WHERE key = ? ORDER BY n", [key]).rows
    data = b"".join(bytes(r[0]) for r in rows)
    if len(rows) != meta[0][0] or not data.startswith(b"%PDF"):
        return None, None
    return data, {"items": meta[0][1], "updated_at": meta[0][2]}


def top_notes(upsc, period, n=5):
    rows = upsc.execute(
        "SELECT article_id, gs_paper, upsc_score, event_id FROM upsc_articles INDEXED BY idx_upsc_pub "
        "WHERE published_at >= ? AND published_at < ? ORDER BY upsc_score DESC, published_at DESC LIMIT 60",
        [period["start"], period["end"]]).rows
    return [{"id": r[0], "paper": r[1], "score": r[2], "event": r[3]} for r in rows]


def headlines(main, trans, notes, n=5, hi=False):
    """Top n distinct stories (one per event), with English or Hindi titles."""
    if not notes:
        return []
    ids = [x["id"] for x in notes]
    en = {r[0]: clean_title(r[1] or r[2]) for r in in_chunks(main, "SELECT id, rephrased_title, title FROM articles WHERE id IN ({ph})", ids)}
    hi_t = {}
    if hi and trans is not None:
        hi_t = {r[0]: clean_title(r[1]) for r in in_chunks(trans, "SELECT article_id, rephrased_title_hi FROM translations "
                                                                  "WHERE article_id IN ({ph})", ids) if r[1]}
    out, seen = [], set()
    for x in notes:
        t = hi_t.get(x["id"]) if hi else en.get(x["id"])
        if not t or LIVE_BLOG.search(en.get(x["id"], "")) or (x["event"] and x["event"] in seen):
            continue
        seen.add(x["event"])
        out.append((t, x["paper"]))
        if len(out) == n:
            break
    return out


def caption(period, items, heads, hi=False):
    head = f"<b>{esc(title(period, hi))}</b>\n"
    head += (f"<i>सत्याधीश · {items} नोट्स</i>\n\n" if hi else f"<i>SatyaDheesh · {items} notes</i>\n\n")
    foot = (f"\n<a href=\"{page_url(period, True)}\">ऑनलाइन पढ़ें</a> · <a href=\"https://satyadheesh.in/upsc/reports?lang=hi\">सभी रिपोर्ट</a>"
            if hi else
            f"\n<a href=\"{page_url(period)}\">Read online</a> · <a href=\"https://satyadheesh.in/upsc/reports\">All reports</a>")
    label = "मुख्य ख़बरें:\n" if hi else "Top stories:\n"
    lines = []
    for i, (t, paper) in enumerate(heads, 1):
        line = f"{i}. {esc(t)} <i>({paper})</i>\n"
        if len(head + label + "".join(lines) + line + foot) > CAPTION_MAX:
            break
        lines.append(line)
    return head + (label + "".join(lines) if lines else "") + foot


def _clip(s, n):
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def poll_from_kit(mcq):
    """Telegram quiz poll fields from a stored kit MCQ, or None if it doesn't fit Telegram's limits."""
    if mcq.get("type") == "statements":
        q = mcq["question"] + "\n" + "\n".join(f"{i + 1}. {s}" for i, s in enumerate(mcq["statements"])) + "\n" + mcq["ask"]
    else:
        q = mcq["question"]
    if len(q) > POLL_Q or any(len(o) > POLL_OPT for o in mcq["options"]):
        return None
    return {"question": q, "options": mcq["options"], "correct": int(mcq["answer"]),
            "explanation": _clip(mcq.get("explanation"), POLL_EXPL)}


def quiz_polls(upsc, period, n=5):
    try:
        rows = upsc.execute(
            "SELECT a.gs_paper, k.mcq FROM upsc_articles a JOIN upsc_kit k ON k.article_id = a.article_id "
            "WHERE a.published_at >= ? AND a.published_at < ? AND k.status = 'done' "
            "ORDER BY a.upsc_score DESC, a.published_at DESC LIMIT 80", [period["start"], period["end"]]).rows
    except Exception as e:  # study kit table not created yet
        print(f"quiz skipped: {e}")
        return []
    polls, papers = [], {}
    for paper, mcq in rows:
        try:
            p = poll_from_kit(json.loads(mcq))
        except (TypeError, ValueError, KeyError):
            continue
        if p and papers.get(paper, 0) < 2:  # spread across GS papers
            polls.append(p)
            papers[paper] = papers.get(paper, 0) + 1
        if len(polls) == n:
            break
    return polls
