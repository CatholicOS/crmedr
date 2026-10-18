import sys
import tempfile
import unittest
import urllib.parse
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


def died(qid, label, value="0510-01-01T00:00:00Z", calendar="Q1985727", precision=11, status="Q43115"):
    """A row of the death-day query."""
    return {"p": uri(qid), "l": {"value": label}, "s": uri(status), "d": {"value": value},
            "prec": {"value": str(precision)}, "cal": uri(calendar)}


class Fake:
    def __init__(self, sparql=None, search=None, entities=None):
        self.urls, self.sparql, self.search = [], sparql or bindings([]), search or {}
        self.entities = {**ENTITIES, **(entities or {})}

    def __call__(self, url):
        self.urls.append(url)
        if "query.wikidata.org" in url:
            return self.sparql
        if "wbsearchentities" in url:
            return {"search": [{"id": q} for q in self.search]}
        ids = url.split("ids=")[1].split("&")[0].split("%7C")
        return {"entities": {q: self.entities[q] for q in ids if q in self.entities}}


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

    def query(self, fake):
        return urllib.parse.unquote_plus(next(u for u in fake.urls if "query.wikidata.org" in u))

    def test_saints_by_death_day(self):
        rows = [died("Q300", "Jean Martin"), died("Q300", "Ioannes"), died("Q77", "Émile")]
        fake = Fake(bindings(rows))
        out = self.wd(fake).saints_by_death_day(1, 1, ["Jean", "Ioannes", "John"])
        self.assertEqual([(c["wikidata"], c["source"]) for c in out], [("Q300", "sparql")])
        query = self.query(fake)
        self.assertIn("p:P570/psv:P570 [wikibase:timeValue ?d; wikibase:timePrecision ?prec; "
                      "wikibase:timeCalendarModel ?cal]", query)
        self.assertIn("?prec >= 11", query)
        # Gregorian: the day itself; Julian: from two days before to thirteen after
        self.assertIn("?cal = wd:Q1985727 && MONTH(?d) = 1 && DAY(?d) = 1 || ?cal = wd:Q1985786 && "
                      "(MONTH(?d) = 12 && DAY(?d) >= 30 && DAY(?d) <= 31 || "
                      "MONTH(?d) = 1 && DAY(?d) >= 1 && DAY(?d) <= 14)", query)
        for prefix in ("p:", "psv:", "wikibase:"):
            self.assertIn(f"PREFIX {prefix} ", query)
        self.assertNotIn("YEAR(?d)", query)
        self.assertIn("wd:Q2369287", query)
        self.assertEqual(len(SAINT_STATUSES), 10)

    def test_year_filter_when_given(self):
        rows = [died("Q300", "Émile", "0300-02-03T00:00:00Z"), died("Q301", "Émile", "0301-02-03T00:00:00Z")]
        fake = Fake(bindings(rows), entities={"Q301": item("Q301", "Émile")})
        out = self.wd(fake).saints_by_death_day(2, 3, ["emile"], year=300)
        self.assertIn("YEAR(?d) >= 299 && YEAR(?d) <= 301", self.query(fake))
        self.assertEqual([c["wikidata"] for c in out], ["Q300"])  # the year itself, checked here

    def test_julian_date_on_the_day_kept_and_year_precision_dropped(self):
        # Sava II died 8 February 1271 (Julian); the query service returns 15 February.
        rows = [died("Q300", "Sava", "1271-02-15T00:00:00Z", calendar="Q1985786"),
                died("Q301", "Sava", "1271-02-15T00:00:00Z"),          # Gregorian: the 15th, not the 8th
                died("Q302", "Sava", "1271-02-08T00:00:00Z", precision=9)]  # the year alone
        entities = {q: item(q, "Sava") for q in ("Q301", "Q302")}
        out = self.wd(Fake(bindings(rows), entities=entities)).saints_by_death_day(2, 8, ["Sava"])
        self.assertEqual([c["wikidata"] for c in out], ["Q300"])
        rows = [died("Q302", "Sava", "1271-01-01T00:00:00Z", precision=9)]
        self.assertEqual(self.wd(Fake(bindings(rows), entities=entities)).saints_by_death_day(1, 1, ["Sava"]), [])

    def test_cap_keeps_the_best_ranked(self):
        qids = [f"Q{i}" for i in range(1000, 1040)]
        rows = [died(q, "Martinus" if q in ("Q1038", "Q1039") else "Martialis") for q in qids]
        rows.append(died("Q1037", "Martialis", status="Q2369287"))  # two statuses
        fake = Fake(bindings(rows), entities={q: item(q, "M") for q in qids})
        out = self.wd(fake).saints_by_death_day(1, 1, ["mart"], matches=lambda names: "Martinus" in names)
        got = [c["wikidata"] for c in out]
        self.assertEqual(len(got), 25)
        self.assertEqual(got[:3], ["Q1038", "Q1039", "Q1037"])  # the name, then the statuses
        self.assertEqual(got[3:], qids[:22])

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
