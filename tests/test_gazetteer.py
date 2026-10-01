import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import gazetteer_text as gt  # noqa: E402


class FoldTest(unittest.TestCase):
    def test_fold(self):
        self.assertEqual(gt.fold("  Fictópoli  Ǽquæ  Nell’ "), "fictopoli aequae nell'")

    def test_country_of(self):
        self.assertEqual(gt.country_of("Francia"), "FR")
        self.assertEqual(gt.country_of("viet nam"), "VN")
        self.assertIsNone(gt.country_of("Fictia"))
        self.assertIn("DE", gt.ISO_CODES)


class ParseItalianTest(unittest.TestCase):
    def test_plain_place_and_region(self):
        p = gt.parse_italian("A Fictopoli in Fictia")
        self.assertEqual(p, {"heads": ["Fictopoli"], "regions": ["Fictia"], "claims": []})

    def test_elided_lead_and_modern_claim(self):
        p = gt.parse_italian("Presso Fictopoli nel Fictiense, nell’odierna Germania")
        self.assertEqual(p["heads"], ["Fictopoli"])
        self.assertEqual(p["regions"], ["Fictiense"])
        self.assertEqual(p["claims"], ["DE"])

    def test_claim_forms(self):
        for it in ("A Fictopoli in Fictia, ora in Francia", "A Fictopoli sempre in Francia",
                   "A Fictopoli ancora in Francia", "A Fictopoli nel territorio dell’odierna Francia",
                   "A Fictopoli in Fictia, in Francia", "A Fictopoli nell’attuale Francia"):
            self.assertEqual(gt.parse_italian(it)["claims"], ["FR"], it)
        self.assertEqual(gt.parse_italian("Presso Fictopoli nel Fictiense, nell’odierno Belgio")["claims"], ["BE"])
        self.assertEqual(gt.parse_italian("A Fictopoli nel Fictiense, ora Viet Nam")["claims"], ["VN"])

    def test_site_heads(self):
        self.assertEqual(gt.parse_italian("Nel monastero di Fictiaco in Fictia")["heads"],
                         ["monastero di Fictiaco", "Fictiaco"])
        self.assertEqual(gt.parse_italian("Nell’isola di Fictosa nel Mare Fictum")["heads"],
                         ["isola di Fictosa", "Fictosa"])
        self.assertEqual(gt.parse_italian("In località Fictana in Fictia")["heads"],
                         ["località Fictana", "Fictana"])
        self.assertEqual(
            gt.parse_italian("Nel monastero delle monache fittizie di Fictiaco in Fictia")["heads"],
            ["monastero delle monache fittizie di Fictiaco", "Fictiaco"])

    def test_multiword_head_kept(self):
        self.assertEqual(gt.parse_italian("A Fictopoli di Fictaria in Fictia")["heads"],
                         ["Fictopoli di Fictaria"])

    def test_lowercase_head_dropped_and_lowercase_region_ignored(self):
        p = gt.parse_italian("All’ancora in mare davanti a Fictopoli sulla costa fittizia")
        self.assertEqual(p["heads"], [])
        self.assertEqual(p["regions"], [])

    def test_vicino_a_is_a_connector_and_a_lead(self):
        p = gt.parse_italian("Vicino a Fictopoli presso Fictaria in Fictia")
        self.assertEqual(p["heads"], ["Fictopoli"])
        self.assertEqual(p["regions"], ["Fictaria", "Fictia"])


class LatinNominativesTest(unittest.TestCase):
    def test_endings(self):
        self.assertIn("fictinium", gt.latin_nominatives("Fictínii in Fíctia"))
        self.assertIn("fictopolis", gt.latin_nominatives("Fictópoli"))
        self.assertIn("ficta", gt.latin_nominatives("Fictæ in Fíctia"))
        self.assertIn("fictanum", gt.latin_nominatives("Fictáni"))
        self.assertIn("fictago", gt.latin_nominatives("Fictágine"))
        self.assertIn("fictii", gt.latin_nominatives("Fictiis"))

    def test_skips_lowercase_and_lead_words(self):
        noms = gt.latin_nominatives("In monastério Fictiacénsi")
        self.assertNotIn("in", noms)
        self.assertNotIn("monasterium", noms)
        self.assertIn("fictiacensis", noms)
