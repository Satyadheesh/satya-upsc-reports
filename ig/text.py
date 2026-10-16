"""Cutting text for slides and captions without cutting a sentence in the middle."""
import re

END = re.compile(r"(?<=[.!?।])(?=\s|$)")
ABBR = re.compile(r"(?:\b(?:Rs|No|Nos|Dr|Mr|Mrs|Ms|St|vs|Jr|Sr|Govt|Art|Sec|approx|etc)|\b[A-Z])\.$")


def tidy(s, n):
    """Whole sentences, about n characters: the sentences that fit in n, or the first sentence if it ends by 1.4 n
    (a sentence is never cut in the middle just to save a few words). Only text with no sentence end near n is cut,
    at a clause end, else at a word; never mid-word, no '…'."""
    s = " ".join(str(s or "").split())
    if len(s) <= n:
        return s
    ends = [m.start() for m in END.finditer(s) if not ABBR.search(s[: m.start()])]
    fits = [k for k in ends if n // 3 < k <= n]
    if fits:
        return s[: fits[-1]]
    over = [k for k in ends if n < k <= int(n * 1.4)]
    if over:
        return s[: over[0]]
    if len(s) <= int(n * 1.4):
        return s
    for sep in ("; ", ", ", " — "):
        k = s.rfind(sep, 0, n)
        if k > n // 2:
            return s[:k].rstrip(" ,;")
    return s[: s.rfind(" ", 0, n)]
