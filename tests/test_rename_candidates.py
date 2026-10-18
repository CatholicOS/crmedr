import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import rename_candidates as rc  # noqa: E402


class Forms(unittest.TestCase):
    def test_ensis(self):
        self.assertEqual(rc.adjective_slug("Condatiscénsis", False), "condatiscensis")

    def test_ensis_feminine_unchanged(self):
        self.assertEqual(rc.adjective_slug("Condatiscénsis", True), "condatiscensis")

    def test_feminine_anus(self):
        self.assertEqual(rc.adjective_slug("Ancyránus", True), "ancyrana")

    def test_masculine_ina(self):
        self.assertEqual(rc.adjective_slug("Alexandrína", False), "alexandrinus")

    def test_known_genitive(self):
        self.assertEqual(rc.genitive_slug({"nominative": "Treviri", "genitive": None}), ("trevirorum", True))

    def test_record_genitive_uncertain(self):
        self.assertEqual(rc.genitive_slug({"nominative": "Metae", "genitive": "Metarum"}), ("metarum", False))

    def test_no_genitive(self):
        self.assertEqual(rc.genitive_slug({"nominative": "X", "genitive": None}), (None, False))

    def test_genitive_key_missing(self):
        self.assertEqual(rc.genitive_slug({"nominative": "X"}), (None, False))

    def test_roles(self):
        self.assertIn("abbas", rc.CLERIC_ROLES)
        self.assertEqual(rc.WEAK_ROLES, {"martyr", "virgo", "confessor"})


if __name__ == "__main__":
    unittest.main()
