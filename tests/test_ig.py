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
            self.assertLessEqual(c.count("#"), 5)
            self.assertNotIn("…", c)
            self.assertNotIn("http", c)

    def test_tidy_never_cuts_mid_word(self):
        self.assertEqual(tidy("One sentence here. Second one is longer and longer.", 30), "One sentence here.")
        self.assertFalse(tidy("word " * 60, 40).endswith("…"))

    def test_today_is_ist(self):
        p = today_period(int(dt.datetime(2026, 10, 3, 19, 0, tzinfo=dt.timezone.utc).timestamp()))  # 00:30 IST 4 Oct
        self.assertEqual(p["key"], "2026-10-04")


class Formats(unittest.TestCase):
    def test_number_of_the_day(self):
        from ig.formats import qotd_html, qotd_number, qotd_caption
        st = [{"title": "RBI raises rates", "why": "GS3 topic.", "paper": "GS3", "subject": "economy",
               "facts": [("Body", "MPC — sets rates"), ("Figure", "7.1% — the revised GDP growth forecast for 2026-27.")]}]
        hi = [{**st[0], "title": "RBI ने दरें बढ़ाईं", "facts": [("आँकड़ा", "7.1% — वर्ष 2026-27 के लिए संशोधित GDP विकास पूर्वानुमान।")]}]
        en, h = qotd_number(st, hi)
        self.assertEqual(en["number"], "7.1%")
        self.assertEqual(h["number"], "7.1%")
        html, n = qotd_html(en, "en")
        self.assertEqual(n, 2)
        self.assertEqual(html.count('<section class="s'), 2)
        self.assertLessEqual(qotd_caption(en, "en").count("#"), 5)

    def test_ssc_quiz_carousel(self):
        from ig.formats import ssc_caption, ssc_quiz_html
        quiz = [(f"Question {k}?", ["A", "B", "C", "D"], k % 4) for k in range(5)]
        html, n = ssc_quiz_html(quiz, [""] * 5, "en", "9 October 2026")
        self.assertEqual(n, 8)  # cover + 5 + answers + CTA, under Instagram's 10
        self.assertEqual(html.count('<section class="s'), 8)
        self.assertIn("5/5", ssc_caption(quiz, "en", "9 October 2026"))

    def test_medal_options(self):
        from reports.render import ssc_quiz
        its = [{"ssc_kit": {"question_en": "Which medal did India win at the Chess Olympiad?", "answer_en": "Bronze"},
                "ssc_topic": ("05", "Sports")}]
        q = ssc_quiz(its, 1, "k", [])
        self.assertEqual(q[0][1], ["Gold", "Silver", "Bronze", "No medal"])
        self.assertEqual(q[0][2], 2)

    def test_slots(self):
        from ig.post import SLOTS, post_key
        self.assertEqual(len(SLOTS), 6)
        self.assertEqual(post_key("upsc", "2026-10-10", "en"), "ig:daily:2026-10-10:en")  # old key kept
        self.assertEqual(post_key("ssc", "2026-10-10", "hi"), "ig:ssc:2026-10-10:hi")


class NumberScore(unittest.TestCase):
    def test_telling_numbers_win(self):
        from ig.formats import number_score
        self.assertGreater(number_score("13.37 crore", "names deleted in the Special Intensive Revision"),
                           number_score("5", "members of the committee"))
        self.assertLess(number_score("2026", "the year of the Census"), 0)
        self.assertLess(number_score("Article 201", "reservation of Bills"), 0)
        self.assertGreaterEqual(number_score("9,000+ deaths", "total fatalities by March 2026"), 2)
        self.assertGreaterEqual(number_score("891", "Asiatic lions, the highest count ever recorded", 3), 2)


class Explain(unittest.TestCase):
    def parts(self, back=2, dims=2, issue="Judicial review of reservation limits"):
        return {"id": 1, "title": "SC upholds strike-down of 34% BC quota", "paper": "GS2", "subject": "polity", "issue": issue,
                "why": "The Supreme Court upheld a High Court ruling that struck down a 34% reservation for Backward Classes in local bodies.",
                "fact_box": "The court ruled that the State failed to provide empirical data to justify breaching the 50% ceiling. " * 2,
                "mains": "Examine the constitutional validity of exceeding the 50% reservation ceiling.",
                "facts": [("Concept", "50% ceiling — the limit on reservations"), ("Body", "Supreme Court")],
                "dims": ["Balancing empirical data requirements with State autonomy in local body quotas"] * dims,
                "back": [(1790000000 + k * 86400 * 5, f"Earlier step {k} in the reservation story.") for k in range(back)],
                "mcq": None, "published_at": 1791489835}

    def test_slides(self):
        from ig.explain import explain_caption, explain_html
        for lang in ("en", "hi"):
            html, n = explain_html(self.parts(), Q, lang)
            self.assertEqual(n, 7)  # cover, what, backstory, why it matters, prelims, quiz, answer
            self.assertEqual(html.count('<section class="s'), 7)
            html, n = explain_html(self.parts(back=1, dims=0), None, lang)
            self.assertEqual(n, 4)  # no backstory (one step is not a story), no quiz; Mains question stays
            self.assertIn("A new explainer" if lang == "en" else "हर सुबह", html)
            c = explain_caption(self.parts(), True, lang)
            self.assertLessEqual(len(c), 2200)
            self.assertNotIn("Both 1 and 2", c)  # never the answer in the caption
            self.assertNotIn("…", c)

    def test_topic_of(self):
        from ig.explain import topic_of
        self.assertEqual(topic_of("Monetary policy and currency management: a key GS3 topic on inflation."),
                         "Monetary policy and currency management")
        self.assertIsNone(topic_of("A GS2 case study."))

    def test_candidate_needs_more_than_the_news(self):
        from ig.explain import candidate
        it = {"id": 1, "title": "T", "title_en": "T", "paper": "GS2", "subject": "polity", "why": "w" * 80, "fact_box": "f" * 120,
              "mains": "M?", "pointers": [], "published_at": 1791489835,
              "kit": {"short_title": "Short", "takeaway": "Topic here: a GS2 case study.", "facts": [], "mcq": None}}
        self.assertIsNone(candidate(it, None, {}, 0)[0])
        self.assertIsNotNone(candidate(it, None, {"dims": ["a" * 30, "b" * 30]}, 0)[0])
