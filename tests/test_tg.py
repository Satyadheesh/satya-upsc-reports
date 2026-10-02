import datetime as dt
import unittest

from tg.content import CAPTION_MAX, caption, poll_from_kit
from tg.periods import file_key, ist_date, period_for, target_ts

SUN_0450_IST = int(dt.datetime(2026, 10, 3, 23, 20, tzinfo=dt.timezone.utc).timestamp())  # Sun 4 Oct 04:50 IST
MON_0420_IST = int(dt.datetime(2026, 10, 4, 22, 50, tzinfo=dt.timezone.utc).timestamp())  # Mon 5 Oct 04:20 IST


class T(unittest.TestCase):
    def test_daily_is_yesterday_ist(self):
        self.assertEqual(period_for("daily", SUN_0450_IST)["key"], "2026-10-03")
        self.assertEqual(period_for("daily", MON_0420_IST)["key"], "2026-10-04")

    def test_weekly_is_current_iso_week(self):
        p = period_for("weekly", SUN_0450_IST)
        self.assertEqual(p["key"], "2026-W40")
        self.assertEqual(ist_date(p["start"]), dt.date(2026, 9, 28))
        self.assertEqual(file_key(p, "hi"), "weekly:2026-W40:hi")

    def test_target_is_exact_ist_minute(self):
        t = target_ts(MON_0420_IST, "05:00")
        self.assertEqual(dt.datetime.fromtimestamp(t, dt.timezone.utc), dt.datetime(2026, 10, 4, 23, 30, tzinfo=dt.timezone.utc))

    def test_caption_fits(self):
        p = period_for("daily", SUN_0450_IST)
        heads = [("A very long headline about something important " * 3, "GS2")] * 5
        for hi in (False, True):
            c = caption(p, 60, heads, hi=hi)
            self.assertLessEqual(len(c), CAPTION_MAX)
            self.assertIn("satyadheesh.in", c)

    def test_poll_statements(self):
        mcq = {"type": "statements", "question": "Consider the following statements:", "statements": ["A is B.", "C is D."],
               "ask": "Which of the statements given above is/are correct?", "options": ["1 only", "2 only", "Both 1 and 2", "Neither 1 nor 2"],
               "answer": 1, "explanation": "Statement 2 is correct."}
        p = poll_from_kit(mcq)
        self.assertIn("1. A is B.", p["question"])
        self.assertEqual(p["correct"], 1)

    def test_poll_too_long_skipped(self):
        mcq = {"type": "single", "question": "Q?" + "x" * 400, "options": ["a", "b", "c", "d"], "answer": 0, "explanation": "e"}
        self.assertIsNone(poll_from_kit(mcq))


if __name__ == "__main__":
    unittest.main()


class Editions(unittest.TestCase):
    """Brief + Detailed are both posted; the old single PDF stands in for Detailed."""

    class FakeDB:
        def __init__(self, stored):
            self.stored = stored  # key -> bytes

        def execute(self, sql, args):
            class R:
                pass
            r = R()
            key = args[0]
            if "FROM upsc_reports" in sql:
                r.rows = [(1, 12, 0)] if key in self.stored else []
            else:
                r.rows = [(self.stored[key],)] if key in self.stored else []
            return r

    def test_both_editions(self):
        from tg.content import read_editions
        db = self.FakeDB({"daily:2026-10-03:hi:brief": b"%PDF-B", "daily:2026-10-03:hi:detailed": b"%PDF-D"})
        pdfs, meta = read_editions(db, "daily:2026-10-03:hi")
        self.assertEqual([ed for _, ed in pdfs], ["brief", "detailed"])
        self.assertEqual(meta["items"], 12)

    def test_old_single_pdf_is_detailed(self):
        from tg.content import read_editions
        pdfs, _ = read_editions(self.FakeDB({"daily:2026-10-03:en": b"%PDF-X"}), "daily:2026-10-03:en")
        self.assertEqual([ed for _, ed in pdfs], ["detailed"])

    def test_nothing_stored(self):
        from tg.content import read_editions
        self.assertEqual(read_editions(self.FakeDB({}), "daily:2026-10-03:hi"), ([], None))

    def test_file_names(self):
        from tg.periods import file_name
        p = period_for("daily", SUN_0450_IST)
        self.assertTrue(file_name(p, "hi", "detailed").endswith("2026-10-03-Hindi.pdf"))
        self.assertIn("-Detailed-", file_name(p, "hi", "detailed"))
        self.assertIn("-Brief-", file_name(p, "en", "brief"))

    def test_caption_both_fits(self):
        p = period_for("daily", SUN_0450_IST)
        heads = [("A very long headline about something important " * 3, "GS2")] * 5
        for hi in (False, True):
            c = caption(p, 60, heads, hi=hi, both=True)
            self.assertLessEqual(len(c), CAPTION_MAX)
            self.assertIn("Detailed" if not hi else "विस्तृत", c)
