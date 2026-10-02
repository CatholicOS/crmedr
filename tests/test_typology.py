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

    def test_relative_pronoun_in_place_phrase_does_not_cut_lead(self):
        self.assertEqual(cls("Fictopoli, via quae Ficta dicitur, depositio sancti Fictitii."),
                         ("depositio", "marker:depositio"))
        self.assertEqual(cls("In monasterio Fictensi, quod condidit, translatio beati Fictitii."),
                         ("translatio", "marker:translatio"))

    def test_dedication_day_is_dedicatio(self):
        self.assertEqual(cls("Festum sancti Fictitii in die dedicationis basilicae Fictensis."),
                         ("dedicatio", "dedication-day"))
        self.assertEqual(cls("Fictopoli, commemoratio sancti Fictitii, qui die anniversaria dedicationis ecclesiae colitur."),
                         ("dedicatio", "dedication-day"))
        # It outranks FEAST_IDS, but not a hand override.
        self.assertEqual(cls("Festum sancti Fictitii in die dedicationis basilicae.", feast_ids={"mr:0101-fictitius"}),
                         ("dedicatio", "dedication-day"))
        self.assertEqual(cls("Festum sancti Fictitii in die dedicationis basilicae.",
                             overrides={"mr:0101-fictitius": "celebratio"}),
                         ("celebratio", "override"))

    def test_day_after_a_dedication_is_not_dedicatio(self):
        value, rule = cls("Memoria sancti Fictitii, postridie dedicationis basilicae Fictensis.")
        self.assertNotEqual(value, "dedicatio")
        self.assertNotIn(rule, ("dedication-day", "marker:dedicationis"))

    def test_relative_clause_after_place_honorific_does_not_cut_lead(self):
        self.assertEqual(cls("In monasterio sancti Ficti, quod condidit, depositio beati Fictitii, abbatis."),
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
        self.assertEqual(t.resolve_xref(fold("natalis sancti Ficti, eius memoria pridie huius diei colitur."), 3, 1),
                         ((2, 29), None))
        self.assertEqual(t.resolve_xref(fold("passio sancti Ficti, eius memoria perendie colitur."), 9, 14),
                         ((9, 16), None))
        self.assertEqual(t.resolve_xref(fold("quorum memoria hodie colitur."), 9, 20), ((9, 20), None))

    def test_ordinal_dates(self):
        self.assertEqual(t.resolve_xref(fold("cuius memoria die vigesima tertia mensis iunii colitur."), 12, 24),
                         ((6, 23), None))
        self.assertEqual(t.resolve_xref(fold("cuius memoria die undevicesima novembris colitur."), 12, 7),
                         ((11, 19), None))

    def test_event_named_by_the_cross_reference(self):
        self.assertEqual(
            t.resolve_xref(fold("cuius memoria colitur die depositionis Fictopoli, vigesimo quinto martii."), 12, 28),
            ((3, 25), "depositio"))
        self.assertEqual(
            t.resolve_xref(fold("cuius memoria die quinta maii, nempe die ordinationis, colitur."), 3, 12),
            ((5, 5), "ordinatio"))

    def test_unresolvable(self):
        self.assertIsNone(t.resolve_xref(fold("eius memoria pie servatur."), 7, 20))
        self.assertIsNone(t.resolve_xref(fold("cuius memoria die tricesima februarii agitur."), 1, 1))
        self.assertIsNone(t.resolve_xref(fold("Romae, sancti Ficti."), 1, 1))

    def test_find_targets(self):
        e = {
            "mr:1228-fictitius": (12, 28, fold("natalis sancti Fictitii, cuius memoria die vicesima quarta ianuarii colitur.")),
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
            "mr:0720-elias": (7, 20, fold("Commemoratio sancti Fictii, cuius memoria pie servatur.")),
        }
        targets, unresolved = t.find_offday_targets(e)
        self.assertEqual(targets, {
            "mr:0124-fictitius": ("celebratio", "mr:1228-fictitius"),
            "mr:0311-caput-et-socii": ("celebratio", "mr:0310-socius"),
        })
        self.assertEqual([u[0] for u in unresolved], ["mr:0501-ambiguus", "mr:0720-elias"])

    def test_hodie_never_targets_the_source(self):
        e = {
            "mr:0920-source": (9, 20, fold("Fictopoli, sanctorum martyrum, quorum memoria hodie colitur.")),
            "mr:0920-caput": (9, 20, fold("Memoria sanctorum Capitis et sociorum.")),
        }
        targets, unresolved = t.find_offday_targets(e)
        self.assertEqual(targets, {"mr:0920-caput": ("celebratio", "mr:0920-source")})
        self.assertEqual(unresolved, [])


class OutputTest(unittest.TestCase):
    CURRENT = {"mr:0101-fictitius": (1, 1), "mr:0102-alius": (1, 2)}
    TEXTS = {
        "mr:0101-fictitius": "Romae, depositio sancti Fictitii, cuius memoria cras agitur.",
        "mr:0102-alius": "Memoria sancti Alii, episcopi.",
    }

    def test_build(self):
        r = t.build(self.CURRENT, self.TEXTS, feast_ids=set(), overrides={})
        self.assertEqual(r["typology"], {"mr:0101-fictitius": "depositio", "mr:0102-alius": "celebratio"})
        self.assertEqual(r["rules"]["mr:0102-alius"], "off-day:mr:0101-fictitius")
        self.assertEqual(r["multi"], {"mr:0101-fictitius": ["depositio", "memoria"]})

    def test_validate_rejects_bad_data(self):
        ids = set(self.CURRENT)
        good = {"mr:0101-fictitius": "depositio", "mr:0102-alius": "celebratio"}
        t.validate(good, ids, {"mr:0103-vetus"}, feast_ids=set(), overrides={})
        with self.assertRaises(AssertionError):
            t.validate({"mr:0101-fictitius": "depositio"}, ids, set(), feast_ids=set(), overrides={})
        with self.assertRaises(AssertionError):
            t.validate({**good, "mr:0102-alius": "festum"}, ids, set(), feast_ids=set(), overrides={})
        with self.assertRaises(AssertionError):
            t.validate(good, ids, set(), feast_ids=set(), overrides={"mr:9999-nemo": "depositio"})
        with self.assertRaises(AssertionError):
            t.validate(good, ids, set(), feast_ids={"mr:9999-nemo"}, overrides={})
        with self.assertRaises(AssertionError):
            t.validate(good, ids, {"mr:0101-fictitius"}, feast_ids=set(), overrides={})

    def test_render_json_is_sorted_and_complete(self):
        import json
        out = json.loads(t.render_json({"mr:0102-b": "depositio", "mr:0101-a": "dies_natalis"}))
        self.assertEqual(out["values"], t.VALUES)
        self.assertEqual(list(out["typology"]), ["mr:0101-a", "mr:0102-b"])

    def test_report_lists_default_entries_with_event_word_outside_lead(self):
        current = {"mr:0103-tertius": (1, 3)}
        texts = {"mr:0103-tertius": "Romae, sancti Tertii, cuius translatio mense fictio colitur."}
        r = t.build(current, texts, feast_ids=set(), overrides={})
        self.assertEqual(r["typology"], {"mr:0103-tertius": "dies_natalis"})
        self.assertEqual(r["hidden"], {"mr:0103-tertius": ["translatio"]})
        report = t.render_report(r)
        self.assertIn("## Default entries with an event word outside the lead", report)
        self.assertIn("| `mr:0103-tertius` | translatio |", report)

    def test_report_has_ids_but_no_text(self):
        r = t.build(self.CURRENT, self.TEXTS, feast_ids=set(), overrides={})
        report = t.render_report(r)
        self.assertIn("`mr:0102-alius`", report)
        self.assertIn("| depositio | 1 |", report)
        self.assertNotIn("Fictitii", report)
        self.assertNotIn("episcopi", report)


if __name__ == "__main__":
    unittest.main()


class NoLatinTextTest(unittest.TestCase):
    def test_twin_text_fills_in(self):
        entries = [
            {"id": "mr:0610-x", "month": 6, "day": 10, "same_eulogy": ["mr:1210-x"]},
            {"id": "mr:1210-x", "month": 12, "day": 10, "same_eulogy": ["mr:0610-x"]},
            {"id": "mr:0101-y", "month": 1, "day": 1},
        ]
        got = t.latin_texts(entries, {"mr:0610-x": "Augustae Taurinorum, beati X.", "mr:0101-y": "Romae."})
        self.assertEqual(got["mr:1210-x"], "Augustae Taurinorum, beati X.")
        self.assertEqual(got["mr:0101-y"], "Romae.")

    def test_cei_only_eulogies_have_typology_overrides(self):
        self.assertEqual(t.TYPOLOGY_OVERRIDES["mr:0712-proclus-et-hilarion"], "dies_natalis")
        self.assertEqual(t.TYPOLOGY_OVERRIDES["mr:0825-eusebius-et-socii"], "depositio")
        self.assertEqual(t.TYPOLOGY_OVERRIDES["mr:0709-maria-a-iesu-crucifixo-petkovic"], "dies_natalis")
