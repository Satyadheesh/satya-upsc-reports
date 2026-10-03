"""Instagram captions: a hook line, the 5 stories with their GS paper and why each matters, the quiz prompt,
where to get the PDF, and hashtags. Plain text (Instagram shows no links in captions); max 2,200 characters."""
from reports.render import MONTHS_HI

MAX = 2200
TAGS = {
    "en": ["#UPSC", "#UPSCCurrentAffairs", "#CurrentAffairs", "#UPSCPrelims", "#UPSCMains", "#IAS", "#CivilServices",
           "#DailyCurrentAffairs", "#UPSC2027", "#StatePSC", "#SatyaDheesh"],
    "hi": ["#UPSC", "#UPSCHindi", "#करेंटअफेयर्स", "#यूपीएससी", "#CurrentAffairsHindi", "#IASHindi", "#UPSCPrelims",
           "#DailyCurrentAffairs", "#UPSC2027", "#StatePSC", "#SatyaDheesh"],
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
    k = s.rfind(" ", 0, n)
    return s[:k] + " …"


def caption(day, stories, has_quiz, lang, is_today=True):
    hi = lang == "hi"
    head = ((f"{'आज' if is_today else 'दिन'} की 5 ज़रूरी ख़बरें — यूपीएससी करेंट अफेयर्स | {_date(day, True)}") if hi
            else f"{'Today’s' if is_today else 'The day’s'} 5 for UPSC — current affairs, {_date(day, False)}")
    lines = [head, ""]
    for k, s in enumerate(stories, 1):
        lines.append(f"{k}. {s['title']} ({s['paper']})")
        lines.append(f"   {_short(s['why'], 170)}")
    lines.append("")
    if has_quiz:
        lines.append("क्विज़ स्लाइड पर है — स्वाइप करने से पहले अपना उत्तर कमेंट करें।" if hi
                     else "Quiz on the slides — comment your answer before you swipe to it.")
    lines.append("पूरी पीडीएफ (सार + विस्तृत, हिंदी और अंग्रेज़ी) हर सुबह 5 बजे टेलीग्राम पर: @satyadheesh (लिंक बायो में)" if hi
                 else "Full PDF (Brief + Detailed, English and Hindi) every morning at 5 AM on Telegram: @satyadheesh (link in bio)")
    lines.append("दोहराव के लिए सेव करें · रोज़ के यूपीएससी नोट्स के लिए फ़ॉलो करें।" if hi
                 else "Save for revision · follow for daily UPSC notes.")
    papers = sorted({s["paper"] for s in stories if s["paper"] in PAPER_TAG})
    tags = " ".join(TAGS[lang] + [PAPER_TAG[p] for p in papers])
    text = "\n".join(lines) + "\n\n" + tags
    while len(text) > MAX and len(lines) > 4:  # drop the 'why' lines from the bottom up if ever too long
        lines = [l for l in lines if not l.startswith("   ")][: len(lines)]
        text = "\n".join(lines) + "\n\n" + tags
    return text[:MAX]
