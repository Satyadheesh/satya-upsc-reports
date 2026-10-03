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


class OddTopStories(unittest.TestCase):
    def test_not_headlines_fall_back_to_why(self):
        from reports.data import upsc_title
        why = "India and Liberia set up a Group of Friends at the 81st UN General Assembly to address maritime security."
        for bad in ('At the 81st UN General Assembly, India and Liberia established a "group',
                    "On 13 September 2026, Indian High Commissioner Dinesh Trivedi met with high-level",
                    "Under a free trade agreement, India will export up to 1.64 million",
                    "Donald Trump Xi Jinping LIVE Updates: US-China Summit Key Announcements",
                    "Sarvjeet Singh Virk, Co-founder & MD of Shoonya"):
            t, src = upsc_title(bad + " India Liberia maritime", None, why, True) if "LIVE" in bad or "Virk" in bad else upsc_title(bad, None, why + " " + bad, True)
            self.assertEqual(src, "why", bad)
        t, src = upsc_title("RBI issues norms on capital requirements for market risk under Basel III for banks", None,
                            "RBI issued new norms to align market risk capital requirements with Basel III standards.", True)
        self.assertEqual(src, "headline")

    def test_demotion(self):
        from reports.data import demotion, by_importance
        self.assertEqual(demotion("Paytm shares plummet after government RuPay, UPI fee move", None), 0)  # government move
        self.assertEqual(demotion("HAL shares rise 2% as firm hands over 3 aerospace platforms to IAF. What is Goldman Sachs saying?", None), 1)
        self.assertEqual(demotion("Sarvjeet Singh Virk, Co-founder & MD of Shoonya", None), 1)
        self.assertEqual(demotion("Iran war live: Tehran sets terms for peace", None), 1)
        self.assertEqual(demotion("Sebi approves new rules to widen investment avenues", None), 0)
        self.assertEqual(demotion("Supreme Court Collegium recommends three High Court Chiefs", None), 0)
        a = {"score": 4, "demote": 1, "related": 3, "published_at": 2}
        b = {"score": 4, "demote": 0, "related": 0, "published_at": 1}
        c = {"score": 3, "demote": 0, "related": 0, "published_at": 1}
        self.assertEqual(sorted([a, c, b], key=by_importance), [b, a, c])
