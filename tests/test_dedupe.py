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


class OddTopStories2(unittest.TestCase):
    def test_more(self):
        from reports.data import upsc_title, demotion, clean_title
        why = "The Embassy of India in Oman reported the evacuation of Indian nationals from Salalah."
        t, src = upsc_title("The Embassy of India in Oman reported on Friday, October 2, 2026", None, why, True)
        self.assertEqual(src, "why")
        self.assertEqual(demotion("IFCI, New India Assurance, other stocks drop up to 3% as NSE makes a muted market debut", None), 1)
        self.assertEqual(clean_title("Developing El NiÃ±o becomes strongest on record"), "Developing El Niño becomes strongest on record")
        self.assertEqual(clean_title("India’s bid"), "India’s bid")


class SscItems(unittest.TestCase):
    def test_before_runner_start_uses_old_cards(self):
        from reports import data
        self.assertIsNone(data.ssc_items(None, {"kind": "monthly", "start": data.SSC_CA_FROM - 1, "end": data.SSC_CA_FROM + 9}))

    def _items(self, rows, kind="daily", start_off=0):
        from reports import data
        T0 = data.SSC_CA_FROM

        class C:
            def execute(self, sql, args):
                class R:
                    pass
                R.rows = [(r[0], T0 + r[1], *r[2:]) for r in rows if args[0] <= T0 + r[1] < args[1]]
                return R()
        p = {"kind": kind, "start": T0 + start_off, "end": T0 + start_off + 86400}
        return data.ssc_items(C(), p)

    def test_one_card_per_story_best_first(self):
        items = self._items([
            (1, 1000, "c1", "award", 5, "X wins Nobel Prize in Physics", "Who won?", "X", "k", "", "f"),
            (2, 1100, "c1", "award", 5, "X wins the Nobel Prize in Physics", "Who won?", "X", "k", "", "f"),
            (3, 1200, None, "sports", 4, "India wins hockey Asia Cup", "Which country?", "India", "k", "", "f"),
            (4, 1300, None, "award", 3, "Y gets Booker", "Who got Booker?", "Y", "k", "", "f"),
            (5, 1300, None, "bogus", 5, "Z", "Q?", "A", "k", "", "f"),
        ])
        self.assertEqual([i["id"] for i in items], [3, 1, 4])  # sports 05 before awards 07; one Nobel card
        self.assertEqual(items[0]["ssc_topic"], ("05", "Sports"))
        self.assertTrue(items[1]["src_url"].endswith("/news/1"))

    def test_same_story_other_outlet_and_day_left_out(self):
        nobel = ("Francis Halzen wins 2026 Nobel Prize in Physics for IceCube neutrino work",
                 "Who won the 2026 Nobel Prize in Physics?", "Francis Halzen")
        items = self._items([
            (1, 3600, "a", "award", 5, *nobel, "", "", "f"),  # day 1
            (2, 86400 + 3600, "b", "award", 5, nobel[0].replace("wins", "bags"), "Who won the Physics Nobel 2026?",
             "Francis Halzen", "", "", "f"),  # day 2, another outlet
            (3, 86400 + 7200, "c", "economy", 5, "RBI raises repo rate by 25 bps to 5.5%",
             "By how many basis points did RBI raise the repo rate?", "25 bps", "", "", "f"),
        ], start_off=86400)
        self.assertEqual([i["id"] for i in items], [3])

    def test_static_gk_once_and_empty_key_dropped(self):
        items = self._items([
            (1, 100, None, "award", 5, "A wins Nobel Prize in Physics", "Who won the Nobel Prize in Physics?", "A",
             "Awarded for neutrino astronomy", "", "f"),
            (2, 200, None, "scheme", 4, "Rs 45 crore sanctioned for Tadepalligudem station under Amrit Bharat",
             "Under which scheme was ₹45 crore sanctioned for Tadepalligudem station?", "Amrit Bharat Station Scheme",
             "Sanctioned amount is ₹45 crore", "", "f"),
            (3, 300, None, "science_space", 4, "ISRO tests Gaganyaan crew module parachutes at Babina range",
             "Where did ISRO test the Gaganyaan crew module parachutes?", "Babina", "Integrated main parachute test", "", "f"),
            (4, 400, None, "science_space", 4, "ISRO launches PSLV-C62 carrying EOS-10 from Sriharikota",
             "Which satellite did ISRO's PSLV-C62 carry?", "EOS-10", "Launched from the first launch pad", "", "f"),
        ])
        k = {i["id"]: i["ssc_kit"] for i in items}
        self.assertIn("Raman", k[1]["static_gk_en"])
        self.assertEqual(sorted(bool(k[i]["static_gk_en"]) for i in (3, 4)), [False, True])  # ISRO line once
        self.assertEqual(k[2]["key_fact_en"], "")   # repeats the question
        self.assertEqual(k[1]["key_fact_en"], "Awarded for neutrino astronomy")
