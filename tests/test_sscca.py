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


    def test_us_national_act(self):
        art = "Saving the home helped President Johnson sign the National Historic Preservation Act in the United States."
        r = gate.check(M(ans(topic="law_verdict", importance=3, scope="national", fact=art)), "US preservation law", art)
        self.assertFalse(r["keep"])


class OnStory(unittest.TestCase):
    def test_side_mention_rejected(self):
        card = {"ssc_question": "Who won the 2026 Nobel Prize in Chemistry?", "ssc_answer": "Henri Kagan and Kenso Soai"}
        fact = "Henri Kagan and Kenso Soai won the 2026 Nobel Prize in Chemistry for chiral catalysis."
        self.assertEqual(gate.card_ok(card, fact, "Jessica Hische's new AI logo for Meta sparks public anger", fact),
                         "card is not about the headline story")
        self.assertEqual(gate.card_ok(card, fact, "Kagan and Soai win Chemistry Nobel for chiral catalysis", fact), "")

    def test_foreign_national_award_and_not_yet(self):
        f = "Donald Trump announced that Roger Clemens would receive the Presidential Medal of Freedom at the White House."
        self.assertEqual(gate.rules("award", 4, "international", f, "Trump names Medal of Freedom winners", f),
                         "foreign national award")
        f2 = "The Norwegian Nobel Committee will announce the Nobel Peace Prize on October 9 in Oslo."
        self.assertEqual(gate.rules("award", 4, "international", f2, "Nobel Peace Prize on Friday", f2), "award not given yet")


class Quiz(unittest.TestCase):
    def test_options_same_kind_no_duplicates(self):
        from reports.render import ssc_quiz, ssc
        from reports.periods import parse
        its = [{"ssc_kit": {"question_en": "What is the repo rate?", "answer_en": "5.5%"}, "ssc_topic": ("10", "Economy")},
               {"ssc_kit": {"question_en": "Who won the Nobel Peace Prize 2026?", "answer_en": "Navi Pillay"},
                "ssc_topic": ("07", "Awards")}]
        pool = [("a", "5.50%", "10"), ("b", "4%", "10"), ("c", "8.2%", "10"), ("d", "6.25%", "10"),
                ("Who won e?", "Anne Carson", "07"), ("Who won f?", "Francis Halzen", "07"), ("Who won g?", "Justice Karl Deisseroth", "07")]
        q = ssc_quiz(its, 5, "k", pool)
        self.assertEqual(len(q), 2)
        rate = [x for x in q if "repo" in x[0]][0]
        self.assertNotIn("5.50%", rate[1])
        self.assertEqual(rate[1][rate[2]], "5.5%")
        who = [x for x in q if "Nobel" in x[0]][0]
        self.assertIn("Karl Deisseroth", who[1])  # titles stripped
        html = ssc(parse("weekly", "2026-W41"), its, 2)
        self.assertIn("Week 41", html)
        self.assertIn("satyadheesh.in/ssc", html)
        self.assertIn("1 item<", html)


class HindiSsc(unittest.TestCase):
    def _en(self):
        from reports.data import SscCards
        its = SscCards([
            {"id": 1, "published_at": 1790900000, "ssc_topic": ("07", "Awards & Honours"), "importance": 5, "title": "t",
             "ssc_kit": {"question_en": "Who won the Nobel Peace Prize 2026?", "answer_en": "Navi Pillay", "key_fact_en": "k",
                         "static_gk_en": "The Nobel Peace Prize is awarded in Oslo; Indian laureates: Mother Teresa (1979), Kailash Satyarthi (2014)"}},
            {"id": 2, "published_at": 1790900000, "ssc_topic": ("10", "Economy & Budget"), "importance": 5, "title": "t",
             "ssc_kit": {"question_en": "What is the repo rate?", "answer_en": "5.5%", "key_fact_en": "", "static_gk_en": ""}}])
        return its

    def _trans(self, rows):
        class T:
            def execute(self, sql, args):
                class R:
                    pass
                R.rows = [r for r in rows if r[0] in args]
                return R()
        return T()

    def test_ready_and_static_hindi(self):
        from reports.data import ssc_items_hi
        from reports.periods import parse
        from reports.render import ssc
        tr = self._trans([(1, "2026 का नोबेल शांति पुरस्कार किसे मिला?", "नवनेथम पिल्लै", "कुंजी", "Who won the Nobel Peace Prize 2026?"),
                          (2, "रेपो दर कितनी है?", "5.5%", "", "What is the repo rate?")])
        hi, share = ssc_items_hi(self._en(), tr)
        self.assertEqual(share, 1.0)
        self.assertIn("ओस्लो", hi[0]["ssc_kit"]["static_gk_hi"])
        html = ssc(parse("daily", "2026-10-09"), hi, 2, "hi")
        self.assertIn("नवनेथम पिल्लै", html)
        self.assertIn("एसएससी सीजीएल", html)
        self.assertNotIn("Navi Pillay", html)

    def test_not_ready_or_stale(self):
        from reports.data import ssc_items_hi
        tr = self._trans([(1, "प्रश्न?", "उत्तर", "", "An older question?")])  # card rewritten since
        self.assertEqual(ssc_items_hi(self._en(), tr), (None, 0.0))
