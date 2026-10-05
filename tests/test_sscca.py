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


    def test_foreign_needs_importance_4(self):
        art = "MADRID: Pedro Sanchez called a snap election for November 29 after the housing bill failed."
        f = "Pedro Sanchez called a snap election for November 29 after the housing bill failed."
        self.assertFalse(gate.check(M(ans(topic="international", importance=3, fact=f)), "t", art)["keep"])

    def test_foreign_minor_appointment(self):
        art = "Karoline Leavitt was named a Fox News contributor from November 1, the network said."
        f = "Karoline Leavitt was named a Fox News contributor from November 1, the network said."
        r = gate.check(M(ans(topic="appointment", importance=4, fact=f)), "Leavitt joins Fox", art)  # scope international
        self.assertEqual(r["why"], "foreign appointment, not a top post")

    def test_indian_ceo_kept(self):
        art = "Anup Bagchi, an ICICI Group veteran, joined HDFC Bank as MD & CEO for a three-year term starting October 2."
        r = gate.check(M(ans(topic="appointment", importance=4, scope="national", fact=art)), "Bagchi HDFC Bank", art)
        self.assertTrue(r["keep"], r["why"])

    def test_local_news(self):
        art = "Nine snakeboats will compete in the Champions Boat League on the Meenachil river in Kottayam on October 24."
        r = gate.check(M(ans(topic="sports", importance=3, scope="national", fact=art)), "Boat league", art)
        self.assertEqual(r["why"], "local news, importance 3")

    def test_verdict_may_quote_a_claim(self):
        art = "The Supreme Court dismissed the Centre's plea, which claimed the High Court had no jurisdiction, on Monday."
        r = gate.check(M(ans(topic="law_verdict", importance=4, scope="national", fact=art)), "SC verdict", art)
        self.assertTrue(r["keep"], r["why"])
