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


class XrefTest(unittest.TestCase):
    def test_relative_days_cross_month_and_leap_day(self):
        self.assertEqual(t.resolve_xref(fold("natalis sancti Ficti, cuius memoria cras agitur."), 1, 31),
                         ((2, 1), None))
        self.assertEqual(t.resolve_xref(fold("natalis sancti Ficti, cuius memoria pridie huius diei agitur."), 3, 1),
                         ((2, 29), None))
        self.assertEqual(t.resolve_xref(fold("passio sancti Ficti, eius memoria perendie celebratur."), 9, 14),
                         ((9, 16), None))
        self.assertEqual(t.resolve_xref(fold("quorum memoria hodie celebratur."), 9, 20), ((9, 20), None))

    def test_ordinal_dates(self):
        self.assertEqual(t.resolve_xref(fold("cuius memoria die vigesima quarta mensis iulii celebratur."), 12, 24),
                         ((7, 24), None))
        self.assertEqual(t.resolve_xref(fold("cuius memoria die undevicesima octobris agitur."), 12, 7),
                         ((10, 19), None))

    def test_event_named_by_the_cross_reference(self):
        self.assertEqual(
            t.resolve_xref(fold("cuius memoria agitur die depositionis Annecii, vigesimo quarto ianuarii."), 12, 28),
            ((1, 24), "depositio"))
        self.assertEqual(
            t.resolve_xref(fold("cuius memoria die tertia septembris, scilicet die ordinationis eius, recolitur."), 3, 12),
            ((9, 3), "ordinatio"))

    def test_unresolvable(self):
        self.assertIsNone(t.resolve_xref(fold("eius memoria fideliter servatur."), 7, 20))
        self.assertIsNone(t.resolve_xref(fold("cuius memoria die tricesima februarii agitur."), 1, 1))
        self.assertIsNone(t.resolve_xref(fold("Romae, sancti Ficti."), 1, 1))

    def test_find_targets(self):
        e = {
            "mr:1228-fictitius": (12, 28, fold("natalis sancti Fictitii, cuius memoria die vigesima quarta ianuarii agitur.")),
            "mr:0124-fictitius": (1, 24, fold("Romae, sancti Fictitii.")),
            "mr:0124-alius": (1, 24, fold("Memoria sancti Alii.")),
            # same slug beats the memoria-headed candidate
            "mr:0310-socius": (3, 10, fold("passio beati Socii, cuius memoria cras agitur.")),
            "mr:0311-caput-et-socii": (3, 11, fold("Memoria sanctorum Capitis et sociorum.")),
            "mr:0311-alter": (3, 11, fold("Romae, sancti Alteri.")),
            # two memoria-headed candidates: ambiguous
            "mr:0501-ambiguus": (5, 1, fold("natalis sancti Ambigui, cuius memoria cras agitur.")),
            "mr:0502-a": (5, 2, fold("Memoria sancti A.")),
            "mr:0502-b": (5, 2, fold("Memoria sancti B.")),
            # no date
            "mr:0720-elias": (7, 20, fold("Commemoratio sancti Eliae, cuius memoria fideliter servatur.")),
        }
        targets, unresolved = t.find_offday_targets(e)
        self.assertEqual(targets, {
            "mr:0124-fictitius": ("celebratio", "mr:1228-fictitius"),
            "mr:0311-caput-et-socii": ("celebratio", "mr:0310-socius"),
        })
        self.assertEqual([u[0] for u in unresolved], ["mr:0501-ambiguus", "mr:0720-elias"])

    def test_hodie_never_targets_the_source(self):
        e = {
            "mr:0920-source": (9, 20, fold("Seuli, sanctorum martyrum, quorum memoria hodie celebratur.")),
            "mr:0920-caput": (9, 20, fold("Memoria sanctorum Capitis et sociorum.")),
        }
        targets, unresolved = t.find_offday_targets(e)
        self.assertEqual(targets, {"mr:0920-caput": ("celebratio", "mr:0920-source")})
        self.assertEqual(unresolved, [])


if __name__ == "__main__":
    unittest.main()
