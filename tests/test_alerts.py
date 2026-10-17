import time
import unittest
import zlib

from alerts import signals as S
from alerts.pick import summary_text

NOW = 1792200000


def art(i, title, src, cat="economy", cluster=None, ago=1800, ents=False):
    return dict(id=i, cluster=cluster, source=src, at=NOW - ago, category=cat, geo=None, civic=False, title=title,
                url="", india_ents=ents, source_name=f"s{src}")


class Alerts(unittest.TestCase):
    def test_same_story_from_two_outlets_is_one_story(self):
        g = S.stories([art(1, "Petrol price cut by Rs 2 per litre across India from Friday", 1, cluster="a"),
                       art(2, "Petrol price cut by Rs 2 per litre across India from Friday, says oil ministry", 2, cluster="b"),
                       art(3, "Kerala police arrest two in theft case", 3, cat="crime", cluster="c")])
        self.assertEqual(sorted(len(x) for x in g), [1, 2])

    def test_daily_life_national_beats_local_crime_and_foreign(self):
        fuel = S.stories([art(1, "Petrol and diesel prices cut nationwide from Friday", 1),
                          art(2, "Petrol, diesel prices cut nationwide", 2)])[0]
        crime = S.stories([art(3, "Man arrested for theft in Kochi", 3, cat="crime")])[0]
        foreign = S.stories([art(4, "Brazil election results announced", 4, cat="international")])[0]
        sf, sc, so = (S.score(g, NOW, {}, {})[0] for g in (fuel, crime, foreign))
        self.assertGreaterEqual(sf, 6)
        self.assertLess(sc, 6)
        self.assertLess(so, 0)

    def test_coverage_counts_reports_about_the_same_thing(self):
        arts = [art(1, "Mumbai Police order actor Imran Khan to leave India by October 28", 1),
                art(2, "Imran Khan to challenge FRRO deportation order in Bombay High Court", 2),
                art(3, "Senior lawyer defends notice to Imran Khan over deportation", 3),
                art(4, "OCI cardholder Imran Khan deportation row: what the law says", 4),
                art(5, "Kerala police arrest two in theft case", 5, cat="crime"),
                art(6, "Sensex gains 300 points in early trade", 6)]
        groups = S.stories(arts)
        cov = S.coverage(groups)
        by_title = {g[0]["title"]: cov[i] for i, g in enumerate(groups)}
        self.assertGreaterEqual(by_title["Imran Khan to challenge FRRO deportation order in Bombay High Court"], 2)
        self.assertEqual(by_title["Kerala police arrest two in theft case"], 0)
        g = [x for x in groups if x[0]["id"] == 6][0]
        self.assertEqual(S.score(g, NOW, {}, {}, related=7)[0] - S.score(g, NOW, {}, {})[0], 4)

    def test_text_of(self):
        self.assertEqual(S.text_of(zlib.compress("hello world".encode())), "hello world")
        self.assertEqual(S.text_of(None), "")

    def test_summary(self):
        rows = [dict(decision="picked", decided_at=NOW, line_en="Fuel cheaper by Rs 2 from Friday", importance=8, why="x",
                     judged_at=NOW),
                dict(decision="rejected", decided_at=NOW, line_en="Minister criticises rival", importance=3,
                     why="routine politics", judged_at=NOW)]
        t = summary_text(rows, NOW - 3600)
        self.assertIn("Would have sent", t)
        self.assertIn("routine politics", t)
