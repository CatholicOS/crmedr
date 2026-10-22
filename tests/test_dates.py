import json
import sys
import tempfile
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


class EditionBoundsTest(unittest.TestCase):
    KEYS = {"martyrologium_romanum_1630": {"mr:0101-a"},
            "martyrologium_romanum_1914_en_unofficial": {"mr:0101-a", "mr:0102-twin"}}

    def test_oldest_edition_wins(self):
        self.assertEqual(d.edition_bounds([{"id": "mr:0101-a"}], self.KEYS), {"mr:0101-a": 1630})

    def test_bound_through_deprecated_twin(self):
        entries = [{"id": "mr:0101-b", "same_eulogy": ["mr:0102-twin"]}]
        self.assertEqual(d.edition_bounds(entries, self.KEYS), {"mr:0101-b": 1914})

    def test_the_1749_folder_bounds_nothing(self):
        keys = {"martyrologium_romanum_1749": {"mr:0131-ioannes-bosco"}}
        self.assertEqual(d.edition_bounds([{"id": "mr:0131-ioannes-bosco"}], keys), {})

    def test_absent_everywhere(self):
        self.assertEqual(d.edition_bounds([{"id": "mr:0101-c"}], self.KEYS), {})

    def test_deprecated_entries_get_no_bound(self):
        self.assertEqual(d.edition_bounds([{"id": "mr:0101-a", "deprecated": True}], self.KEYS), {})

    def test_edition_keys_skips_non_day_values(self):
        with tempfile.TemporaryDirectory() as t:
            folder = Path(t) / "data" / "editions" / "martyrologium_romanum_1914_en_unofficial"
            folder.mkdir(parents=True)
            (folder / "01.json").write_text(json.dumps(
                {"mensis": "Januarius", "1": {"titulus": "t", "elogia": {"mr:0101-a": "x"}}}))
            keys = d.edition_keys(Path(t))
        self.assertEqual(keys["martyrologium_romanum_1914_en_unofficial"], {"mr:0101-a"})
        self.assertEqual(keys["martyrologium_romanum_1630"], set())


class BuildDatesTest(unittest.TestCase):
    ID = "mr:0101-fictitius"
    TYPOLOGY = {ID: "dies_natalis"}

    def build(self, deaths=(), bound=None, curated=None):
        persons = {self.ID: [{"name": f"P{i}", "where": "text"} for i in range(len(deaths))]}
        items = {self.ID: {f"P{i}": {"wikidata": f"Q{i + 1}"} for i in range(len(deaths))}}
        details = {f"Q{i + 1}": died(y) for i, y in enumerate(deaths)}
        bounds = {self.ID: bound} if bound else {}
        return d.build_dates({self.ID}, self.TYPOLOGY, persons, items, details, bounds, curated or {})

    def test_curated_wins(self):
        curated = {self.ID: {"year": 431, "basis": "event", "note": "Council of Ephesus"}}
        self.assertEqual(self.build([304], curated=curated)[self.ID],
                         {"year": 431, "basis": "event", "source": "curated", "note": "Council of Ephesus"})

    def test_curated_null_removes(self):
        self.assertEqual(self.build([304], bound=1630, curated={self.ID: None}), {})

    def test_wikidata_over_edition(self):
        self.assertEqual(self.build([304], bound=1630)[self.ID],
                         {"year": 304, "basis": "death", "source": "wikidata"})

    def test_edition_only(self):
        self.assertEqual(self.build(bound=1630)[self.ID], {"to": 1630, "basis": "death", "source": "edition"})

    def test_curated_unknown_id_fails(self):
        with self.assertRaisesRegex(ValueError, "mr:0101-renamed"):
            self.build(curated={"mr:0101-renamed": {"year": 1}})

    def test_after_bound_check(self):
        wd = {self.ID: {"year": 1700}}
        self.assertEqual(d.checks(wd, {self.ID: 1630})["after_bound"], [(self.ID, 1700, 1630)])

    def test_wide_check(self):
        wd = {self.ID: {"from": 304, "to": 900}}
        self.assertEqual(d.checks(wd, {})["wide"], [(self.ID, 304, 900)])

    def test_check_sees_curated_overridden(self):
        persons = {self.ID: [{"name": "P0", "where": "text"}]}
        items = {self.ID: {"P0": {"wikidata": "Q1"}}}
        wd = d.death_dates({self.ID}, persons, items, {"Q1": died(1700)})
        self.assertEqual(d.checks(wd, {self.ID: 1630})["after_bound"], [(self.ID, 1700, 1630)])

    def test_committed_dates_are_current(self):
        self.assertEqual(d.main(["--check", str(ROOT)]), 0)


if __name__ == "__main__":
    unittest.main()
