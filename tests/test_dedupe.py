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
