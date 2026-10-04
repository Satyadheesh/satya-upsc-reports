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

    def test_headline_as_question(self):
        """Question that is a headline (no interrogative starter) should be rejected."""
        card = {
            "ssc_question": "India releases Great Indian Bustards in Desert National Park?",
            "ssc_answer": "Great Indian Bustards",
            "key_fact": "Two male birds released.",
            "static_gk": "Desert National Park is in Jaisalmer, Rajasthan.",
        }
        with self.assertRaises(SscInvalid):
            validate_ssc_card(card, self.note, lang="en")

    def test_sentence_as_answer(self):
        """Answer that is a sentence fragment with verbs should be rejected."""
        card = {
            "ssc_question": "What was launched for Telangana government hospitals?",
            "ssc_answer": "The NEHS was launched on July 17 for Telangana gov",
            "key_fact": "919 hospitals now offer cashless treatment.",
            "static_gk": "Telangana capital: Hyderabad.",
        }
        with self.assertRaises(SscInvalid):
            validate_ssc_card(card, self.note, lang="en")

    def test_answer_too_long(self):
        """Answer with more than 10 words should be rejected."""
        card = {
            "ssc_question": "Who became the first woman Director General of CISF?",
            "ssc_answer": "Senior IPS officer Neena Singh was appointed as the new DG of CISF",
            "key_fact": "1989-batch IPS officer of Rajasthan cadre.",
            "static_gk": "CISF HQ: New Delhi.",
        }
        with self.assertRaises(SscInvalid):
            validate_ssc_card(card, self.note, lang="en")

    def test_field_repetition_kf_equals_q(self):
        """key_fact that is just a copy of the question should be rejected."""
        card = {
            "ssc_question": "Who became the first woman Director General of CISF?",
            "ssc_answer": "Neena Singh",
            "key_fact": "Who became the first woman Director General of CISF",
            "static_gk": "CISF HQ: New Delhi.",
        }
        with self.assertRaises(SscInvalid):
            validate_ssc_card(card, self.note, lang="en")

    def test_field_repetition_sgk_equals_kf(self):
        """static_gk identical to key_fact should be rejected."""
        card = {
            "ssc_question": "Who became the first woman Director General of CISF?",
            "ssc_answer": "Neena Singh",
            "key_fact": "CISF HQ: New Delhi",
            "static_gk": "CISF HQ: New Delhi",
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
