import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from extract_subjects import fold  # noqa: E402
import extract_typology as t  # noqa: E402


def cls(text, mrid="mr:0101-fictitius", offday=None, feast_ids=(), overrides=None):
    return t.classify(mrid, fold(text), offday=offday or {},
                      feast_ids=set(feast_ids), overrides=overrides or {})


class ClassifyTest(unittest.TestCase):
    def test_unmarked_is_dies_natalis(self):
        self.assertEqual(cls("Romae, sancti Fictitii, episcopi."), ("dies_natalis", "default"))

    def test_marker_in_lead(self):
        self.assertEqual(cls("Romae, depositio sancti Fictitii, episcopi."),
                         ("depositio", "marker:depositio"))

    def test_folds_ligatures(self):
        self.assertEqual(cls("Romæ, translátio sanctæ Fictæ, vírginis."),
                         ("translatio", "marker:translatio"))

    def test_genitive_marker(self):
        self.assertEqual(cls("Memoria sancti Fictitii, episcopi, in die depositionis eius."),
                         ("depositio", "marker:depositionis"))
        self.assertEqual(cls("Festum dedicationis basilicae Fictae."),
                         ("dedicatio", "marker:dedicationis"))

    def test_commemoratio_without_honorific(self):
        self.assertEqual(cls("Commemoratio omnium fidelium defunctorum."),
                         ("commemoratio", "marker:commemoratio"))

    def test_marker_after_relative_pronoun_is_ignored(self):
        self.assertEqual(cls("Romae, sancti Fictitii, qui festum agebat et passio eius nota est."),
                         ("dies_natalis", "default"))

    def test_saint_named_natalis_is_not_a_marker(self):
        self.assertEqual(cls("Andegavi, beati Natalis Ficti, presbyteri."),
                         ("dies_natalis", "default"))

    def test_place_name_honorific_does_not_hide_marker(self):
        self.assertEqual(cls("In monasterio sancti Ficti, depositio beati Fictitii, abbatis."),
                         ("depositio", "marker:depositio"))

    def test_precedence(self):
        text = "Romae, depositio sancti Fictitii."
        self.assertEqual(cls(text, feast_ids={"mr:0101-fictitius"}), ("celebratio", "feast"))
        self.assertEqual(cls(text, offday={"mr:0101-fictitius": ("celebratio", "mr:0301-fictitius")},
                             feast_ids={"mr:0101-fictitius"}),
                         ("celebratio", "off-day:mr:0301-fictitius"))
        self.assertEqual(cls(text, overrides={"mr:0101-fictitius": "translatio"},
                             offday={"mr:0101-fictitius": ("celebratio", "mr:0301-fictitius")}),
                         ("translatio", "override"))

    def test_has_feast_head(self):
        self.assertTrue(t.has_feast_head(fold("Memoria sancti Fictitii, episcopi.")))
        self.assertFalse(t.has_feast_head(fold("Romae, sancti Fictitii, qui memoria dignus est.")))

    def test_markers_in(self):
        self.assertEqual(t.markers_in(fold("Romae, natalis sancti Ficti, cuius memoria cras agitur.")),
                         ["memoria", "natalis"])


if __name__ == "__main__":
    unittest.main()
