"""Instagram captions: a hook line, the 5 stories with their GS paper and why each matters, the quiz prompt,
where to get the PDF, and hashtags. Plain text (Instagram shows no links in captions); max 2,200 characters."""
from reports.render import MONTHS_HI

MAX = 2200
TAGS = {  # 4-5 tags that match the audience (13 was too many); keywords in the first lines matter more for search
    "en": ["#UPSC", "#UPSCCurrentAffairs", "#UPSCPrelims", "#CurrentAffairs", "#SatyaDheesh"],
    "hi": ["#UPSCHindi", "#यूपीएससी", "#करेंटअफेयर्स", "#UPSC", "#SatyaDheesh"],
}
PAPER_TAG = {"GS1": "#GS1", "GS2": "#GS2", "GS3": "#GS3", "GS4": "#GS4"}


def _date(d, hi):
    return f"{d.day} {MONTHS_HI[d.month - 1]} {d.year}" if hi else f"{d.day} {d.strftime('%B')} {d.year}"


def _short(s, n):
    s = " ".join(str(s or "").split())
    if len(s) <= n:
        return s
    for sep in (". ", "। ", "; ", ", "):
        k = s.rfind(sep, 0, n)
        if k > n // 2:
            return s[:k].rstrip(" ,;") + ("." if sep == ". " else "।" if sep == "। " else "")
    return ""  # no clean place to cut: leave the line out rather than end it mid-sentence


def caption(day, stories, has_quiz, lang, is_today=True):
    hi = lang == "hi"
    head = ((f"{stories[0]['title']} — और आज की {len(stories) - 1} और ज़रूरी ख़बरें | यूपीएससी करेंट अफेयर्स, {_date(day, True)}") if hi
            else f"{stories[0]['title']} — and {len(stories) - 1} more UPSC stories you can’t skip, {_date(day, False)}")
    lines = [head, ""]
    for k, s in enumerate(stories, 1):
        lines.append(f"{k}. {s['title']} ({s['paper']})")
        why = _short(s['why'], 170)
        if why:
            lines.append(f"   {why}")
    lines.append("")
    if has_quiz:
        lines.append("क्विज़ स्लाइड पर है — स्वाइप करने से पहले अपना उत्तर कमेंट करें।" if hi
                     else "Quiz on the slides — comment your answer before you swipe to it.")
    lines.append("पूरी पीडीएफ (सार + विस्तृत, हिंदी और अंग्रेज़ी) हर सुबह 5 बजे टेलीग्राम पर: @satyadheesh (लिंक बायो में)" if hi
                 else "Full PDF (Brief + Detailed, English and Hindi) every morning at 5 AM on Telegram: @satyadheesh (link in bio)")
    lines.append("दोहराव के लिए सेव करें · रोज़ के यूपीएससी नोट्स के लिए फ़ॉलो करें।" if hi
                 else "Save for revision · follow for daily UPSC notes.")
    tags = " ".join(TAGS[lang])
    text = "\n".join(lines) + "\n\n" + tags
    while len(text) > MAX and len(lines) > 4:  # drop the 'why' lines from the bottom up if ever too long
        lines = [l for l in lines if not l.startswith("   ")][: len(lines)]
        text = "\n".join(lines) + "\n\n" + tags
    return text[:MAX]
