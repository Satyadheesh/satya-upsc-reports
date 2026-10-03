import datetime as dt
import unittest

from ig.caption import MAX, caption
from ig.post import tidy, today_period
from ig.slides import slides_html

DAY = dt.date(2026, 10, 3)
ST = [{"title": f"Story {k} about the Chenab Bridge and Vande Bharat at 100 kmph", "why": "Why it matters. " * 6,
       "paper": "GS3", "subject": "economy", "facts": [("Figure", "100 kmph on the Chenab Bridge")]} for k in range(1, 6)]
Q = {"question": "Consider the following statements:", "statements": ["A is B.", "C is D."],
     "options": ["1 only", "2 only", "Both 1 and 2", "Neither 1 nor 2"], "answer": 2, "explanation": "Both are correct."}


class IGPost(unittest.TestCase):
    def test_slides_count_and_language(self):
        for lang in ("en", "hi"):
            html, n = slides_html(DAY, ST, Q, lang)
            self.assertEqual(n, 9)  # cover + 5 + quiz + answer + CTA (Instagram max 10)
            self.assertEqual(html.count('<section class="s'), 9)
            self.assertIn(f'lang="{lang}"', html)
        self.assertEqual(slides_html(DAY, ST[:3], None, "en")[1], 5)

    def test_caption(self):
        for lang in ("en", "hi"):
            c = caption(DAY, ST, True, lang)
            self.assertLessEqual(len(c), MAX)
            self.assertIn("@satyadheesh", c)
            self.assertIn("#GS3", c)
            self.assertNotIn("http", c)

    def test_tidy_never_cuts_mid_word(self):
        self.assertEqual(tidy("One sentence here. Second one is longer and longer.", 30), "One sentence here.")
        self.assertFalse(tidy("word " * 60, 40).endswith("…"))

    def test_today_is_ist(self):
        p = today_period(int(dt.datetime(2026, 10, 3, 19, 0, tzinfo=dt.timezone.utc).timestamp()))  # 00:30 IST 4 Oct
        self.assertEqual(p["key"], "2026-10-04")
