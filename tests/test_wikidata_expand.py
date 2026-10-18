import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from wikidata import SAINT_STATUSES, Wikidata, WikidataError  # noqa: E402


def claim(qid):
    return {"mainsnak": {"datavalue": {"value": {"id": qid}}}}


def item(qid, label, claims=None):
    return {"id": qid, "labels": {"en": {"value": label}}, "claims": claims or {}}


ENTITIES = {
    "Q2652595": item("Q2652595", "René Lego", {"P3373": [claim("Q52161488")], "P361": [claim("Q99")]}),
    "Q52161488": item("Q52161488", "Brother", {"P31": [claim("Q5")]}),
    "Q77": item("Q77", "Fellow martyr", {"P31": [claim("Q5")]}),
    "Q208542": item("Q208542", "Theotokos"),
    "Q300": item("Q300", "Jean Martin", {"P31": [claim("Q5")], "P411": [claim("Q2369287")]}),
}


def bindings(rows):
    return {"results": {"bindings": rows}}


def uri(qid):
    return {"value": "http://www.wikidata.org/entity/" + qid}


class Fake:
    def __init__(self, sparql=None, search=None):
        self.urls, self.sparql, self.search = [], sparql or bindings([]), search or {}

    def __call__(self, url):
        self.urls.append(url)
        if "query.wikidata.org" in url:
            return self.sparql
        if "wbsearchentities" in url:
            return {"search": [{"id": q} for q in self.search]}
        ids = url.split("ids=")[1].split("&")[0].split("%7C")
        return {"entities": {q: ENTITIES[q] for q in ids if q in ENTITIES}}


class ExpandTest(unittest.TestCase):
    def wd(self, fetch):
        return Wikidata(Path(tempfile.mkdtemp()), fetch=fetch)

    def test_relatives(self):
        fake = Fake(bindings([{"m": uri("Q77")}, {"m": uri("Q2652595")}]))
        out = self.wd(fake).relatives("Q2652595")
        self.assertEqual([(c["wikidata"], c["source"]) for c in out],
                         [("Q52161488", "companion:P3373"), ("Q77", "companion:P361")])
        self.assertTrue(out[0]["human"])
        self.assertTrue(any("wd%3AQ99" in u for u in fake.urls))

    def test_saints_by_death_day(self):
        rows = [{"p": uri("Q300"), "l": {"value": "Jean Martin"}},
                {"p": uri("Q300"), "l": {"value": "Ioannes"}},
                {"p": uri("Q77"), "l": {"value": "Émile"}}]
        fake = Fake(bindings(rows))
        out = self.wd(fake).saints_by_death_day(1, 1, ["Jean", "Ioannes", "John"])
        self.assertEqual([(c["wikidata"], c["source"]) for c in out], [("Q300", "sparql")])
        query = next(u for u in fake.urls if "query.wikidata.org" in u)
        self.assertIn("MONTH%28%3Fd%29+%3D+1", query)
        self.assertIn("wd%3AQ2369287", query)
        self.assertEqual(len(SAINT_STATUSES), 10)

    def test_saints_fold_and_year(self):
        rows = [{"p": uri(f"Q{i}"), "l": {"value": "Émile"}} for i in range(1000, 1040)]
        out = self.wd(Fake(bindings(rows))).saints_by_death_day(2, 3, ["emile"], year=300)
        self.assertEqual(out, [])  # the fake knows none of them, so nothing is summarized
        rows = [{"p": uri("Q300"), "l": {"value": "Émile"}}]
        self.assertEqual(len(self.wd(Fake(bindings(rows))).saints_by_death_day(2, 3, ["emile"])), 1)

    def test_titles(self):
        out = self.wd(Fake(search=["Q208542"])).title_candidates("Theotokos")
        self.assertEqual([(c["wikidata"], c["source"], c["human"]) for c in out],
                         [("Q208542", "title", False)])

    def test_error_propagates(self):
        def boom(url):
            raise WikidataError("down")
        with self.assertRaises(WikidataError):
            self.wd(boom).saints_by_death_day(1, 1, ["Jean"])
        with self.assertRaises(WikidataError):
            self.wd(boom).relatives("Q1")


if __name__ == "__main__":
    unittest.main()
