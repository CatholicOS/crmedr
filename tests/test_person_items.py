import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import wikidata as wd  # noqa: E402


def time(t, precision=11):
    return {"mainsnak": {"datavalue": {"value": {"time": t, "precision": precision}}}}


def item(qid, value):
    return {"mainsnak": {"datavalue": {"value": {"id": value}}}}


RAW = {
    "id": "Q380649",
    "labels": {"en": {"value": "Paul Miki"}, "it": {"value": "Paolo Miki"}},
    "aliases": {"la": [{"value": "Paulus Miki"}]},
    "descriptions": {"en": {"value": "Japanese Jesuit martyr"}},
    "claims": {"P31": [item("x", "Q5")], "P411": [item("x", "Q43115")],
               "P569": [time("+1564-00-00T00:00:00Z", 9)], "P570": [time("+1597-02-05T00:00:00Z")],
               "P841": [item("x", "Q2915")]},
}


class SummarizePersonTest(unittest.TestCase):
    def test_summary(self):
        s = wd.summarize_person(RAW)
        self.assertEqual(s["wikidata"], "Q380649")
        self.assertEqual(s["label"], "Paul Miki")
        self.assertTrue(s["human"])
        self.assertEqual(s["statuses"], ["Q43115"])
        self.assertEqual(s["born"], "1564")
        self.assertEqual(s["died"], "1597-02-05")
        self.assertEqual(s["feast"], ["Q2915"])
        self.assertEqual(sorted(s["names"]), ["Paolo Miki", "Paul Miki", "Paulus Miki"])


class PersonSearchTest(unittest.TestCase):
    def test_searches_each_language_and_summarizes(self):
        calls = []

        def fetch(url):
            calls.append(url)
            if "wbsearchentities" in url:
                return {"search": [{"id": "Q380649"}]}
            return {"entities": {"Q380649": RAW}}

        with tempfile.TemporaryDirectory() as d:
            client = wd.Wikidata(Path(d), fetch=fetch)
            found = client.person_candidates("Paulus Miki")
        self.assertEqual([c["wikidata"] for c in found], ["Q380649"])
        searched = [u for u in calls if "wbsearchentities" in u]
        self.assertEqual(len(searched), 3)
        self.assertTrue(any("language=la" in u for u in searched))
