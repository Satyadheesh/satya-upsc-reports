import unittest

from kit.validate import Invalid, validate

NOTE = {
    "article_id": 128866, "title": "80% of Mumbaikars refuse 0.4% MDR on UPI payments above ₹2,000",
    "why_in_news": "The Ministry of Finance notified a framework to introduce a 0.4% Merchant Discount Rate (MDR) on UPI payments above ₹2,000.",
    "fact_box": "The Ministry of Finance notified S.O. 5067(E) on September 14, 2026, making the 0.4% MDR effective from October 15, 2026. "
                "The MDR is capped at ₹300 per transaction for payments of ₹75,000 and above.",
    "prelims_pointers": [{"type": "body", "text": "NPCI (National Payments Corporation of India) provides state-wise UPI transaction data"},
                         {"type": "data_fact", "text": "MDR of 0.4% applies to person-to-merchant (P2M) UPI payments above ₹2,000"}],
    "mains_question": "Discuss the implications of a fee-based structure for UPI payments.", "keywords": ["MDR", "Digital Payments"],
}
BASE = {
    "short_title": "UPI to carry a 0.4% MDR on merchant payments above ₹2,000",
    "takeaway": "Ends zero-MDR UPI: financial inclusion vs a sustainable payments system.",
    "brief": {"lead": "UPI charge", "text": "0.4% MDR on merchant payments above ₹2,000 from 15 October."},
    "facts": [{"label": "Figure", "text": "MDR capped at ₹300 per transaction for payments of ₹75,000 and above"},
              {"label": "Body", "text": "NPCI — National Payments Corporation of India, publishes state-wise UPI data"},
              {"label": "Person", "text": "Nirmala Sitharaman is the Finance Minister of India"},
              {"label": "Figure", "text": "MDR capped at ₹500 per transaction"}],
}
SINGLE = {**BASE, "mcq": {"question": "From 15 October 2026, a Merchant Discount Rate on UPI applies to payments above:",
                          "correct": "₹2,000", "distractors": ["₹500", "₹5,000", "₹10,000"],
                          "explanation": "The notification applies the 0.4% MDR to P2M UPI payments above ₹2,000."}}
STATEMENTS = {**BASE, "mcq": {"stem": "With reference to the new MDR on UPI payments, consider the following statements",
                              "statements": [{"text": "The 0.4% MDR applies to person-to-merchant payments above ₹2,000.", "true": True},
                                             {"text": "The MDR is capped at ₹300 per transaction for payments of ₹75,000 and above.", "true": True},
                                             {"text": "The MDR also applies to person-to-person UPI transfers.", "true": False}],
                              "explanation": "Statements 1 and 2 are correct; the charge applies only to merchant payments."}}


class T(unittest.TestCase):
    def test_single(self):
        k = validate(SINGLE, NOTE, 128866, "single")
        m = k["mcq"]
        self.assertEqual(m["options"][m["answer"]], "₹2,000")
        self.assertEqual(len(set(m["options"])), 4)
        self.assertEqual(k["brief_lead"], "UPI charge:")

    def test_facts_drop_trivia_and_ungrounded(self):
        k = validate(SINGLE, NOTE, 128866, "single")
        texts = " ".join(f["text"] for f in k["facts"])
        self.assertNotIn("Finance Minister of India", texts)
        self.assertNotIn("₹500", texts)
        self.assertEqual(len(k["facts"]), 2)

    def test_statements_answer_built_from_flags(self):
        m = validate(STATEMENTS, NOTE, 128866, "statements")["mcq"]
        self.assertEqual(m["options"][m["answer"]], "1 and 2 only")
        self.assertEqual(len(m["options"]), 4)
        self.assertTrue(m["question"].endswith(":"))

    def test_two_statements(self):
        raw = {**STATEMENTS, "mcq": {**STATEMENTS["mcq"], "statements": STATEMENTS["mcq"]["statements"][1:]}}
        m = validate(raw, NOTE, 128866, "statements")["mcq"]
        self.assertEqual(m["options"][m["answer"]], "1 only")

    def test_ungrounded_title_number(self):
        with self.assertRaises(Invalid):
            validate({**SINGLE, "short_title": "UPI to carry a 0.9% MDR on payments above ₹2,000"}, NOTE, 1, "single")

    def test_rounding_allowed(self):
        note = {**NOTE, "fact_box": NOTE["fact_box"] + " Outstanding e-challans total ₹49,194.05 crore."}
        validate({**SINGLE, "short_title": "UPI MDR at 0.4%; e-challan dues of ₹49,194 crore"}, note, 1, "single")
        with self.assertRaises(Invalid):
            validate({**SINGLE, "short_title": "UPI MDR at 0.4%; e-challan dues of ₹48,000 crore"}, note, 1, "single")

    def test_duplicate_options(self):
        bad = {**SINGLE, "mcq": {**SINGLE["mcq"], "distractors": ["₹500", "₹500", "₹10,000"]}}
        with self.assertRaises(Invalid):
            validate(bad, NOTE, 1, "single")

    def test_answer_not_in_note(self):
        bad = {**SINGLE, "mcq": {**SINGLE["mcq"], "correct": "Reserve Bank of India sandbox"}}
        with self.assertRaises(Invalid):
            validate(bad, NOTE, 1, "single")

    def test_all_false(self):
        sts = [{**s, "true": False} for s in STATEMENTS["mcq"]["statements"]]
        with self.assertRaises(Invalid):
            validate({**STATEMENTS, "mcq": {**STATEMENTS["mcq"], "statements": sts}}, NOTE, 1, "statements")

    def test_answer_positions_vary(self):
        pos = {validate(SINGLE, NOTE, aid, "single")["mcq"]["answer"] for aid in range(1, 40)}
        self.assertGreaterEqual(len(pos), 3)


if __name__ == "__main__":
    unittest.main()
