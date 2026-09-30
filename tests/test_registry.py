import json
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
            with self.assertRaises(AssertionError):
                r.load_typology(Path(d), {"mr:0101-fictitius"})

    def test_markdown_has_typology_column(self):
        with tempfile.TemporaryDirectory() as d:
            r.write_markdown(r.add_typology([dict(ENTRY)], {"mr:0101-fictitius": "depositio"}), Path(d))
            md = (Path(d) / "registry" / "01-january.md").read_text(encoding="utf-8")
        self.assertIn("| Day | Entry | ID | * | Country | Typology | Notes |", md)
        self.assertIn("| 1 | 1 | `mr:0101-fictitius` |  | IT | depositio | n |", md)
        self.assertIn("`Typology`", md)


if __name__ == "__main__":
    unittest.main()
