"""Reel scripts introduce every person on first mention (tools/reel_scorer.intro_problems / tags_for_cards)."""
import unittest

from tools.reel_scorer import intro_problems, tags_for_cards, people_block
import tools.reel_scorer as rs


class IntroCheck(unittest.TestCase):
    def test_introduced(self):
        sc = {"people": [{"name_hi": "संजय राउत", "role_hi": "शिवसेना (UBT) के सांसद"}],
              "hook_say": "शिवसेना (UBT) के सांसद संजय राउत ने बड़ा दावा किया है।", "core_say": "राउत ने कहा कि ऑडियो फ़र्ज़ी है।",
              "twist_say": "", "engagement_say": ""}
        self.assertEqual(intro_problems(sc), [])
        self.assertEqual(tags_for_cards(sc), {"hook": [{"name": "संजय राउत", "role": "शिवसेना (UBT) के सांसद"}]})

    def test_not_introduced(self):
        sc = {"people": [{"name_hi": "संजय राउत", "role_hi": "शिवसेना (UBT) के सांसद"}],
              "hook_say": "संजय राउत ने बड़ा दावा किया है।", "core_say": "", "twist_say": "", "engagement_say": ""}
        self.assertEqual(len(intro_problems(sc)), 1)

    def test_shared_surname_is_not_another_person(self):
        known = [{"name_hi": "पियूष गोयल", "role_hi": "वाणिज्य मंत्री"}]
        sc = {"people": [{"name_hi": "ब्रिजेश गोयल", "role_hi": "सीटीआई चेयरमैन"}],
              "hook_say": "सीटीआई चेयरमैन ब्रिजेश गोयल ने कहा। गोयल ने लिखा।", "core_say": "", "twist_say": "", "engagement_say": ""}
        self.assertEqual(intro_problems(sc, known), [])

    def test_library_person_missing_from_people(self):
        known = [{"name_hi": "देवेंद्र फडणवीस", "role_hi": "महाराष्ट्र के मुख्यमंत्री"}]
        sc = {"people": [], "hook_say": "फडणवीस ने जवाब दिया।", "core_say": "", "twist_say": "", "engagement_say": ""}
        self.assertEqual(len(intro_problems(sc, known)), 1)
        sc["hook_say"] = "महाराष्ट्र के मुख्यमंत्री देवेंद्र फडणवीस ने जवाब दिया।"
        self.assertEqual(intro_problems(sc, known), [])

    def test_too_many_people(self):
        ppl = [{"name_hi": n, "role_hi": "नेता"} for n in ("राम कुमार", "श्याम लाल", "मोहन दास", "सीता देवी")]
        sc = {"people": ppl, "hook_say": " ".join(f"नेता {p['name_hi']}" for p in ppl), "core_say": "", "twist_say": "",
              "engagement_say": ""}
        self.assertTrue(any("at most 3" in p for p in intro_problems(sc)))

    def test_people_block_matches_name_not_descriptive_alias(self):
        rs._PEOPLE = [{"name": "Krishna Byre Gowda", "name_hi": "कृष्णा बायरे गौड़ा", "role_hi": "मंत्री", "party": "INC",
                       "keys": {"krishna byre gowda", "gowda"}},
                      {"name": "Devendra Fadnavis", "name_hi": "देवेंद्र फडणवीस", "role_hi": "महाराष्ट्र के मुख्यमंत्री",
                       "party": "BJP", "keys": {"devendra fadnavis", "fadnavis"}}]
        block, found = people_block("Bengaluru Development plan", "Fadnavis said on Friday")
        self.assertEqual([p["name"] for p in found], ["Devendra Fadnavis"])
        self.assertIn("महाराष्ट्र के मुख्यमंत्री", block)
        rs._PEOPLE = None


if __name__ == "__main__":
    unittest.main()



def test_latin_problems():
    from tools.reel_scorer import latin_problems
    sc = {"core_say": "कोर्ट ने चार महीने की deadline दी, ED और KPSC जांच करेंगे।", "core_points_hi": ["9 साल", "wetlands बचेंगे"],
          "people": [{"name_hi": "x", "role_hi": "Rafale"}], "hook_say": "तालाब बचेंगे।"}
    probs = latin_problems(sc)
    assert len(probs) == 2
    assert probs[0].startswith("core_say: deadline")          # ED / KPSC (short forms) are fine
    assert probs[1].startswith("core_points_hi: wetlands")
    assert latin_problems({"hook_say": "सब ठीक है।"}) == []
