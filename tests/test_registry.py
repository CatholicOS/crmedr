import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import extract_registry as r  # noqa: E402  (must import without openpyxl)

ENTRY = {"id": "mr:0101-fictitius", "month": 1, "day": 1, "entry": 1,
         "asterisk": False, "country": "IT", "note": "n"}


class RegistryTypologyTest(unittest.TestCase):
    def test_add_typology_inserts_after_country(self):
        out = r.add_typology([dict(ENTRY)], {"mr:0101-fictitius": "depositio"})
        self.assertEqual(list(out[0]), ["id", "month", "day", "entry", "asterisk", "country", "typology", "note"])
        self.assertEqual(out[0]["typology"], "depositio")

    def test_add_typology_is_idempotent_and_skips_untagged(self):
        once = r.add_typology([dict(ENTRY)], {"mr:0101-fictitius": "depositio"})
        twice = r.add_typology(once, {"mr:0101-fictitius": "depositio"})
        self.assertEqual(once, twice)
        self.assertEqual(list(twice[0]).count("typology"), 1)
        self.assertNotIn("typology", r.add_typology([dict(ENTRY)], {})[0])

    def test_load_typology_missing_file(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(r.load_typology(Path(d), {"mr:0101-fictitius"}), {})

    def test_load_typology_stale_file_fails(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "data").mkdir()
            (Path(d) / "data" / "typology.json").write_text(
                json.dumps({"typology": {"mr:0101-other": "depositio"}}), encoding="utf-8")
            with self.assertRaisesRegex(AssertionError, r"(?s)move data/typology\.json aside.*"
                                        r"extract_registry\.py.*extract_typology\.py.*extract_registry\.py"):
                r.load_typology(Path(d), {"mr:0101-fictitius"})

    def test_markdown_has_typology_column(self):
        with tempfile.TemporaryDirectory() as d:
            r.write_markdown(r.add_typology([dict(ENTRY)], {"mr:0101-fictitius": "depositio"}), Path(d))
            md = (Path(d) / "registry" / "01-january.md").read_text(encoding="utf-8")
        self.assertIn("| Day | Entry | ID | * | Country | Typology | Notes |", md)
        self.assertIn("| 1 | 1 | `mr:0101-fictitius` |  | IT | depositio | n |", md)
        self.assertIn("`Typology`", md)


PLACES = {"mr:0101-fictitius": [{"role": "death", "la": "Fictopoli", "source": "lead"}]}


class RegistryPlacesTest(unittest.TestCase):
    def test_add_places_after_typology(self):
        e = r.add_typology([dict(ENTRY)], {"mr:0101-fictitius": "depositio"})
        out = r.add_places(e, PLACES)
        self.assertEqual(list(out[0]), ["id", "month", "day", "entry", "asterisk", "country",
                                        "typology", "places", "note"])

    def test_add_places_without_typology_goes_after_country(self):
        out = r.add_places([dict(ENTRY)], PLACES)
        self.assertEqual(list(out[0])[5:7], ["country", "places"])

    def test_add_places_is_idempotent_and_skips_placeless(self):
        once = r.add_places([dict(ENTRY)], PLACES)
        self.assertEqual(r.add_places(once, PLACES), once)
        self.assertNotIn("places", r.add_places([dict(ENTRY)], {})[0])

    def test_add_places_drops_a_stale_key(self):
        once = r.add_places([dict(ENTRY)], PLACES)
        self.assertNotIn("places", r.add_places(once, {})[0])

    def test_place_roles_must_match_typology(self):
        r.check_place_roles(PLACES, {"mr:0101-fictitius": "dies_natalis"})
        with self.assertRaisesRegex(AssertionError, "extract_places"):
            r.check_place_roles(PLACES, {"mr:0101-fictitius": "depositio"})
        curated = {"mr:0101-fictitius": [{"role": "birth", "la": "Fictia", "source": "curated"}]}
        r.check_place_roles(curated, {"mr:0101-fictitius": "depositio"})   # curated roles are free

    def test_recovery_mentions_both_files(self):
        self.assertRegex(r.RECOVERY, r"(?s)typology\.json.*places\.json.*extract_registry.*"
                                     r"extract_typology.*extract_places.*extract_registry")

    def test_load_places(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(r.load_places(Path(d), {"mr:0101-fictitius"}), {})
            (Path(d) / "data").mkdir()
            (Path(d) / "data" / "places.json").write_text(json.dumps({"places": PLACES}), encoding="utf-8")
            self.assertEqual(r.load_places(Path(d), {"mr:0101-fictitius", "mr:0102-x"}), PLACES)
            with self.assertRaisesRegex(AssertionError, "move data/places.json aside"):
                r.load_places(Path(d), {"mr:0102-x"})



class IdCorrectionsAppliedTest(unittest.TestCase):
    """No workbook ID that ID_CORRECTIONS replaces may survive in the data."""

    def test_no_corrected_source_id_remains(self):
        root = Path(__file__).resolve().parent.parent
        files = ["data/martyrology_ids.json", "data/typology.json", "data/places.json",
                 "i18n/la.json", "i18n/it.json", "i18n/en.json"]
        text = "\n".join((root / f).read_text(encoding="utf-8") for f in files)
        leftovers = sorted(old for old in r.ID_CORRECTIONS if f'"{old}"' in text)
        self.assertEqual(leftovers, [])

    def test_registry_markdown_ids_are_canonical(self):
        """The month tables are checked too: every ID they show is in the registry."""
        root = Path(__file__).resolve().parent.parent
        canonical = {e["id"] for e in json.load(open(root / "data" / "martyrology_ids.json",
                                                      encoding="utf-8"))["entries"]}
        shown = set()
        for path in sorted((root / "registry").glob("*.md")):
            shown.update(re.findall(r"`(mr:[^`]+)`", path.read_text(encoding="utf-8")))
        self.assertTrue(shown)
        self.assertEqual(sorted(shown - canonical), [])

    def test_stephanus_fanus_is_corrected(self):
        self.assertEqual(r.ID_CORRECTIONS.get("mr:1130-stephanus-fanus"), "mr:1130-cuthbertus-mayne")

class PlaceLeadCorrections25Test(unittest.TestCase):
    """#25: Leonard's deprecated ID became current; three deprecated IDs were coined."""

    def test_registry(self):
        root = Path(__file__).resolve().parent.parent
        entries = {e["id"]: e for e in json.load(open(root / "data" / "martyrology_ids.json"))["entries"]}
        self.assertFalse(entries["mr:1126-leonardus-a-portu-mauritio"].get("deprecated"))
        for mr_id in ("mr:0320-photina-et-socii", "mr:0823-philippus-benizi", "mr:0324-pigmenius"):
            self.assertTrue(entries[mr_id]["deprecated"], mr_id)
        self.assertEqual(r.ID_CORRECTIONS["mr:1126-bonaventura"], "mr:1126-leonardus-a-portu-mauritio")


if __name__ == "__main__":
    unittest.main()
