import unittest

from sscca import gate

ART = ("STOCKHOLM: Karl Deisseroth, Peter Hegemann, and Georg Nagel were awarded the Nobel Prize in Physiology or "
       "Medicine on Monday for optogenetics. Experts expect more prizes for the field.")


class M:
    def __init__(self, r):
        self.r = r

    def json(self, *a, **k):
        return self.r


def ans(**kw):
    r = {"ssc": True, "topic": "award", "importance": 5, "scope": "international",
         "fact": "Karl Deisseroth, Peter Hegemann and Georg Nagel were awarded the Nobel Prize in Physiology or Medicine on Monday."}
    r.update(kw)
    return r


class Gate(unittest.TestCase):
    def test_kept(self):
        self.assertTrue(gate.check(M(ans()), "Medicine Nobel", ART)["keep"])

    def test_model_no(self):
        self.assertEqual(gate.check(M(ans(ssc=False)), "t", ART)["why"], "model: no")

    def test_paraphrase_rejected(self):
        r = gate.check(M(ans(fact="Three scientists shared the medicine prize this year for their work.")), "t", ART)
        self.assertFalse(r["keep"])

    def test_forecast_rejected(self):
        r = gate.check(M(ans(topic="award", fact="Experts expect more prizes for the field.")), "t", ART)
        self.assertFalse(r["keep"])

    def test_state_needs_importance_4(self):
        self.assertFalse(gate.check(M(ans(scope="state", importance=3)), "t", ART)["keep"])
        self.assertTrue(gate.check(M(ans(scope="state", importance=4)), "t", ART)["keep"])

    def test_topic_words(self):
        r = gate.check(M(ans(topic="sports")), "t", ART)  # an award sentence is not a sports result
        self.assertFalse(r["keep"])
