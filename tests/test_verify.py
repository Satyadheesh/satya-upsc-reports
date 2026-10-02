import unittest

from kit.verify import _truths, check


class FakeModel:
    def __init__(self, out):
        self.out = out

    def json(self, *a, **k):
        return self.out


NOTE = {"title": "T", "why_in_news": "W", "fact_box": "F", "prelims_pointers": []}
SINGLE = {"type": "single", "question": "Q?", "options": ["x", "y", "z", "w"], "answer": 2, "explanation": "e"}
ST = {"type": "statements", "question": "Consider:", "statements": ["a", "b", "c"],
      "options": ["1 only", "1 and 3 only", "2 and 3 only", "1, 2 and 3"], "answer": 1}


class T(unittest.TestCase):
    def test_truths(self):
        self.assertEqual(_truths(ST), [True, False, True])
        self.assertEqual(_truths({**ST, "statements": ["a", "b"], "options": ["1 only", "2 only", "Both 1 and 2", "Neither 1 nor 2"], "answer": 2}), [True, True])

    def test_single_ok(self):
        self.assertIsNone(check(FakeModel({"answer": "c", "also_correct": [], "reason": ""}), NOTE, SINGLE))

    def test_single_wrong_key(self):
        self.assertIn("blind check", check(FakeModel({"answer": "a", "also_correct": [], "reason": ""}), NOTE, SINGLE))

    def test_single_ambiguous(self):
        self.assertIn("also supported", check(FakeModel({"answer": "c", "also_correct": ["b"], "reason": ""}), NOTE, SINGLE))

    def test_statements_ok(self):
        out = {"statements": [{"n": 1, "verdict": "true"}, {"n": 2, "verdict": "false"}, {"n": 3, "verdict": "true"}], "reason": ""}
        self.assertIsNone(check(FakeModel(out), NOTE, ST))

    def test_statements_mismatch(self):
        out = {"statements": [{"n": 1, "verdict": "true"}, {"n": 2, "verdict": "true"}, {"n": 3, "verdict": "true"}], "reason": ""}
        self.assertIn("statement 2", check(FakeModel(out), NOTE, ST))

    def test_statements_not_in_note(self):
        out = {"statements": [{"n": 1, "verdict": "true"}, {"n": 2, "verdict": "not in note"}, {"n": 3, "verdict": "true"}], "reason": ""}
        self.assertIn("can't be checked", check(FakeModel(out), NOTE, ST))


if __name__ == "__main__":
    unittest.main()
