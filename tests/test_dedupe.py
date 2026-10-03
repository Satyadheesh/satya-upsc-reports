import unittest

from reports.data import same_headline, uncut


class SameStory(unittest.TestCase):
    """Reviewer, 3 Oct: the Ladakh '28 features' story twice (GS1 + GS3, a day apart)."""

    def test_same_story_across_papers(self):
        self.assertTrue(same_headline("India identifies 28 strategic places and geographical features on official Survey of India map",
                                      "India identifies 28 geographical features on SoI map following PLA troop movements"))

    def test_different_stories_kept(self):
        self.assertFalse(same_headline("Supreme Court dismisses plea against Bihar SIR", "Supreme Court dismisses plea on UPI charge"))
        self.assertFalse(same_headline("RBI keeps repo rate unchanged in 2026 review", "SEBI eases 2026 rules for mutual funds"))

    def test_cut_off_text_trimmed(self):
        self.assertEqual(uncut("The court ruled on the plea, citing Article 21, and asked the Centre to respo…"),
                         "The court ruled on the plea, citing Article 21")
        self.assertEqual(uncut("Complete sentence."), "Complete sentence.")


class SameEditions(unittest.TestCase):
    """Yash, 3 Oct: the Hindi and English reports differed (headline, why it matters, number of the day)."""

    def test_kit_part_only_one_language_has_is_dropped_from_both(self):
        from reports.data import same_kit
        en = {"short_title": "A", "takeaway": "T", "brief_lead": "L", "brief_text": "B", "mcq": {"q": 1},
              "facts": [{"label": "Figure", "text": "13.3 crore — names"}, {"label": "Place", "text": "X — y"}]}
        hi = {"short_title": "ए", "takeaway": "टी", "brief_lead": None, "brief_text": None, "mcq": None,
              "facts": [{"label": "Figure", "text": "13.3 करोड़ — नाम"}, {"label": "Place", "text": "एक्स — वाई"}]}
        e, h = same_kit(en, hi)
        self.assertIsNone(e["mcq"]); self.assertIsNone(h["mcq"])
        self.assertIsNone(e["brief_lead"]); self.assertIsNone(h["brief_lead"])
        self.assertEqual([f["label"] for f in h["facts"]], ["Figure", "Place"])
        self.assertEqual(same_kit(en, None), (None, None))

    def test_facts_that_cannot_be_matched_are_dropped_from_both(self):
        from reports.data import same_kit
        e, h = same_kit({"short_title": "A", "facts": [{"label": "Act", "text": "a"}]}, {"short_title": "ए", "facts": []})
        self.assertIsNone(e["facts"]); self.assertIsNone(h["facts"])


class Headline(unittest.TestCase):
    def test_off_topic_headline_replaced_by_why_in_news(self):
        from reports.data import upsc_title
        t, src = upsc_title("Sarvjeet Singh Virk, Co-founder & MD of Shoonya", None,
                            "SEBI's FY25-26 study revealed that 87.7% of individual equity derivative traders incurred net losses.", True)
        self.assertEqual(src, "why")
        self.assertIn("87.7%", t)
        self.assertNotIn("…", t)
