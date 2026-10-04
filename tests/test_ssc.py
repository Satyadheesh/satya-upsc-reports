import unittest

from kit.ssc import (
    SscInvalid,
    build_messages,
    schema,
    validate_ssc_card,
)


class TestSsc(unittest.TestCase):
    def setUp(self):
        self.note = {
            "title": "Neena Singh appointed first woman Director General of CISF",
            "why_in_news": "Senior IPS officer Neena Singh was appointed DG of CISF in 2024.",
            "fact_box": "1989-batch IPS officer, Rajasthan cadre.",
            "prelims_pointers": [{"type": "person", "text": "Neena Singh"}],
        }

    def test_valid_en(self):
        card = {
            "ssc_question": "Who became the first woman Director General of CISF?",
            "ssc_answer": "Neena Singh",
            "key_fact": "1989-batch IPS officer of Rajasthan cadre.",
            "static_gk": "CISF raised 1969 under CISF Act 1968; HQ: New Delhi.",
        }
        res = validate_ssc_card(card, self.note, lang="en")
        self.assertEqual(res["ssc_answer"], "Neena Singh")

    def test_missing_question_mark(self):
        card = {
            "ssc_question": "Who became the first woman Director General of CISF",
            "ssc_answer": "Neena Singh",
            "key_fact": "1989-batch officer.",
            "static_gk": "CISF HQ: New Delhi.",
        }
        with self.assertRaises(SscInvalid):
            validate_ssc_card(card, self.note, lang="en")

    def test_leakage(self):
        card = {
            "ssc_question": "Who named Neena Singh was appointed DG of CISF?",
            "ssc_answer": "Neena Singh",
            "key_fact": "1989-batch officer.",
            "static_gk": "CISF HQ: New Delhi.",
        }
        with self.assertRaises(SscInvalid):
            validate_ssc_card(card, self.note, lang="en")

    def test_hallucinated_digit(self):
        card = {
            "ssc_question": "Who became the first woman Director General of CISF?",
            "ssc_answer": "Neena Singh",
            "key_fact": "Served for 99 years in service.",  # 99 not in note
            "static_gk": "CISF HQ: New Delhi.",
        }
        with self.assertRaises(SscInvalid):
            validate_ssc_card(card, self.note, lang="en")

    def test_schema(self):
        sc_en = schema("en")
        self.assertEqual(sc_en["properties"]["ssc_question"]["maxLength"], 120)
        self.assertEqual(sc_en["properties"]["ssc_answer"]["maxLength"], 50)
        self.assertEqual(sc_en["properties"]["key_fact"]["maxLength"], 120)
        self.assertEqual(sc_en["properties"]["static_gk"]["maxLength"], 140)

    def test_messages(self):
        msgs = build_messages(self.note, lang="en")
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["role"], "user")
        self.assertIn("Neena Singh", msgs[0]["content"])
        self.assertIn("<note>", msgs[0]["content"])


if __name__ == "__main__":
    unittest.main()
