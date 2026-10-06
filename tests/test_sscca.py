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
        self.assertFalse(r["keep"])

    def test_verdict_may_quote_a_claim(self):
        art = "The Supreme Court dismissed the Centre's plea, which claimed the High Court had no jurisdiction, on Monday."
        r = gate.check(M(ans(topic="law_verdict", importance=4, scope="national", fact=art)), "SC verdict", art)
        self.assertTrue(r["keep"], r["why"])


    def test_minor_foreign_sports(self):
        art = "Novak Djokovic defeated top seed Alexander Zverev 6-4, 6-3 to reach the China Open semifinals on Sunday."
        r = gate.check(M(ans(topic="sports", importance=3, scope="international", fact=art)), "Djokovic beats Zverev", art)
        self.assertFalse(r["keep"])

    def test_big_event_state_host_kept(self):
        art = "Telangana will host the eighth edition of the Khelo India Youth Games with over 7,500 athletes in 27 sports."
        r = gate.check(M(ans(topic="sports", importance=3, scope="national", fact=art)), "Khelo India Youth Games", art)
        self.assertTrue(r["keep"], r["why"])

    def test_state_share_of_central_scheme(self):
        art = ("Chief Minister N. Chandrababu Naidu and Union Minister Shivraj Singh Chouhan launched the PMAY-G 2.0 "
               "project for three lakh houses in Burripalem, Andhra Pradesh, on Saturday.")
        r = gate.check(M(ans(topic="scheme", importance=3, scope="national", fact=art)), "PMAY-G 2.0 in Andhra", art)
        self.assertEqual(r["why"], "local news, importance 3")

    def test_speech_is_not_a_fact(self):
        art = "Shaktikanta Das said Viksit Bharat by 2047 is achievable with 7.9 per cent annual growth, at the conclave."
        r = gate.check(M(ans(topic="economy", importance=4, scope="national", fact=art)), "Das on growth", art)
        self.assertFalse(r["keep"])

    def test_market_news(self):
        art = "The RBI's Monetary Policy Committee began its three-day meeting on October 5, the central bank said."
        r = gate.check(M(ans(topic="economy", importance=5, scope="national", fact=art)),
                       "Nifty 50 and Sensex open higher as RBI begins MPC meeting", art)
        self.assertEqual(r["why"], "market news")


class Card(unittest.TestCase):
    def test_answer_from_the_news(self):
        c = {"ssc_question": "Who won the 2026 Nobel Prize in Medicine?", "ssc_answer": "Karl Deisseroth, Peter Hegemann and Georg Nagel"}
        self.assertEqual(gate.card_ok(c, ans()["fact"], "Medicine Nobel", ART), "")

    def test_static_trivia_rejected(self):
        c = {"ssc_question": "Who created the Nobel Prize?", "ssc_answer": "Alfred Nobel"}
        f = "Nobel Prize winners will be announced this week, with each prize worth $1.21 million."
        self.assertEqual(gate.card_ok(c, f, "Nobel winners to be announced", f), "card answer is not in the news fact")

    def test_role_must_be_in_article(self):
        c = {"ssc_question": "Who is the Union Minister for MSME who felicitated the team?", "ssc_answer": "Kondapalli Srinivas"}
        f = "Kondapalli Srinivas, Minister for MSME, felicitated the Indian visually impaired T20 World Cup team."
        self.assertIn("Union Minister", gate.card_ok(c, f, "Team felicitated", f))

    def test_number_answer(self):
        c = {"ssc_question": "What was the gross GST collection?", "ssc_answer": "₹12.46 lakh crore"}
        f = "Gross GST collections reached ₹12.46 lakh crore in April-September, up 9.1%."
        self.assertEqual(gate.card_ok(c, f, "GST collections", f), "")


    def test_foreign_law_needs_indian_link(self):
        art = "California became the first US state to pass the No Robo Bosses Act, limiting AI in hiring decisions."
        r = gate.check(M(ans(topic="law_verdict", importance=3, scope="national", fact=art)), "California AI law", art)
        self.assertEqual(r["why"], "no Indian link")

    def test_hearing_is_not_a_verdict(self):
        art = "The Supreme Court on Monday struck a note of caution as it hears a challenge to the Vande Mataram Act."
        r = gate.check(M(ans(topic="law_verdict", importance=3, scope="national", fact=art)),
                       "Supreme Court hears challenge to Vande Mataram law", art)
        self.assertFalse(r["keep"])

    def test_india_in_foreign_sports_kept(self):
        art = "India and Pakistan will face off for the Asian Games 2026 men's cricket gold medal in Japan on Sunday."
        r = gate.check(M(ans(topic="sports", importance=3, scope="international", fact=art)), "India v Pakistan final", art)
        self.assertTrue(r["keep"], r["why"])

    def test_claim_in_headline(self):
        art = "The ₹1-lakh-crore Global Horticulture Hub was launched at Madanapalle on Saturday by the Chief Minister."
        r = gate.check(M(ans(topic="scheme", importance=4, scope="national", fact=art)),
                       "Jairam Ramesh claims crowd shouted for jobs at horticulture hub launch", art)
        self.assertFalse(r["keep"])

    def test_quoted_name_in_answer(self):
        c = {"ssc_question": "Which exercise did the Indian and UAE armies begin?", "ssc_answer": "Mountain Guardian"}
        f = "The Indian and UAE armies began ‘Exercise Mountain Guardian’ in Uttarakhand on Monday."
        self.assertEqual(gate.card_ok(c, f, "Exercise begins", f), "")


    def test_union_ministry_is_indian(self):
        art = "The Union Law Ministry published rules for the National Tribunals Commission to oversee 16 tribunals."
        r = gate.check(M(ans(topic="law_verdict", importance=4, scope="national", fact=art)), "Tribunal rules notified", art)
        self.assertTrue(r["keep"], r["why"])
