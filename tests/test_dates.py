import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import extract_dates as d  # noqa: E402


def died(year, precision="year", circa=False):
    return {"died": {"year": year, "precision": precision, "circa": circa}}


class DeathDateTest(unittest.TestCase):
    def date(self, *deaths):
        persons = [{"name": f"P{i}", "where": "text"} for i in range(len(deaths))]
        items = {f"P{i}": {"wikidata": f"Q{i + 1}", "status": "auto"}
                 for i, x in enumerate(deaths) if x is not None}
        details = {f"Q{i + 1}": x for i, x in enumerate(deaths) if x is not None}
        return d.death_date(persons, items, details)

    def test_year_precision(self):
        self.assertEqual(self.date(died(304)), {"year": 304})

    def test_decade(self):
        self.assertEqual(self.date(died(1930, "decade")), {"from": 1930, "to": 1939})

    def test_ad_century(self):
        self.assertEqual(self.date(died(400, "century")), {"from": 301, "to": 400})
        self.assertEqual(self.date(died(1401, "century")), {"from": 1401, "to": 1500})

    def test_bc_century(self):
        self.assertEqual(self.date(died(-100, "century")), {"from": -100, "to": -1})

    def test_circa_kept(self):
        self.assertEqual(self.date(died(250, circa=True)), {"year": 250, "circa": True})

    def test_several_persons_range(self):
        self.assertEqual(self.date(died(304), died(310)), {"from": 304, "to": 310})

    def test_some_persons_undated(self):
        self.assertEqual(self.date(None, died(304)), {"year": 304})

    def test_item_without_details(self):
        persons = [{"name": "P0", "where": "text"}]
        items = {"P0": {"wikidata": "Q9", "status": "auto"}}
        self.assertIsNone(d.death_date(persons, items, {}))

    def test_repeated_name_key(self):
        persons = [{"name": "Felix", "where": "text"}, {"name": "Felix", "n": 2, "where": "text"}]
        items = {"Felix": {"wikidata": "Q1"}, "Felix#2": {"wikidata": "Q2"}}
        details = {"Q1": died(304), "Q2": died(305)}
        self.assertEqual(d.death_date(persons, items, details), {"from": 304, "to": 305})

    def test_basis_from_typology(self):
        self.assertEqual(d.with_basis({"year": 304}, "depositio"), {"year": 304, "basis": "deposition"})
        self.assertEqual(d.with_basis({"year": 304}, "commemoratio"), {"year": 304})
        self.assertEqual(d.with_basis({"year": 431, "basis": "event"}, "celebratio"),
                         {"year": 431, "basis": "event"})


if __name__ == "__main__":
    unittest.main()
