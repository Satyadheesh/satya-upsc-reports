"""Cutting text for slides and captions without cutting a sentence in the middle."""
import re

END = re.compile(r"(?<=[.!?।])(?=\s|$)")
ABBR = re.compile(r"(?:\b(?:Rs|No|Nos|Dr|Mr|Mrs|Ms|St|vs|Jr|Sr|Govt|Art|Sec|approx|etc)|\b[A-Z]|(?:^|\s)(?:एस|पी|एम|एन|आर|डॉ|ए|बी|सी|डी|जे|के|एल|टी|वी|यू|एच|जी))\.$")  # initials: 'S. Jaishankar', 'एस. जयशंकर'


def tidy(s, n):
    """Whole sentences, about n characters: the sentences that fit in n, or the first sentence if it ends by 1.4 n
    (a sentence is never cut in the middle just to save a few words). Only text with no sentence end near n is cut,
    at a clause end, else at a word; never mid-word, no '…'."""
    s = " ".join(str(s or "").split())
    if len(s) <= n:
        return s
    ends = sentence_ends(s)
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


WHOLE = re.compile(r"[.!?।)\"'’”]$|\d{4}$")


def looks_whole(s):
    """False for text that stops mid-sentence ('… revealed that the Beti Bachao'): about 2% of older notes' why-in-news
    were saved cut off by the note writer. A trailing year ('… Amendment Bill, 2026') counts as whole."""
    return bool(WHOLE.search(" ".join(str(s or "").split())))


def sentence_ends(s):
    return [m.start() for m in END.finditer(s) if not ABBR.search(s[: m.start()])]


def first_sentence(s, n=230):
    """The first sentence, whole ('Minister S. Jaishankar' is not two sentences); a longer one is cut back at its
    last clause, or None when there is no clean place to cut."""
    s = " ".join(str(s or "").split())
    ends = sentence_ends(s)
    first = s[: ends[0]] if ends else s
    if len(first) <= n:
        return first
    k = max(first.rfind(", ", 0, n), first.rfind("; ", 0, n))
    return first[:k] if k > n // 2 else None
