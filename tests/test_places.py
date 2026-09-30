import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import extract_places as p  # noqa: E402


class OpeningPhraseTest(unittest.TestCase):
    def test_base_copy_keeps_length_case_and_ligatures(self):
        self.assertEqual(p.base_copy("Fictópoli Sanctórum sanctæ"), "Fictopoli Sanctorum sanctæ")
        self.assertEqual(len(p.base_copy("Fictópoli ǽ")), len("Fictópoli ǽ"))

    def test_lowercase_honorific_ends_the_phrase(self):
        self.assertEqual(p.opening_phrase("Fictopoli in Fictia, sancti Fictitii, episcopi."),
                         "Fictopoli in Fictia")

    def test_capitalized_saint_in_a_place_name_stays(self):
        self.assertEqual(
            p.opening_phrase("In monasterio Sancti Ficti ad Fictum flumen, depositio beati Fictitii."),
            "In monasterio Sancti Ficti ad Fictum flumen")

    def test_capitalized_stop_word_at_start_means_no_place(self):
        self.assertIsNone(p.opening_phrase("Sancti Fictitii, episcopi."))
        self.assertIsNone(p.opening_phrase("Memória sancti Fictitii, episcopi."))

    def test_printed_accents_kept_and_ligature_stop_word(self):
        self.assertEqual(p.opening_phrase("Fictópoli in Gállia, sanctæ Fictæ, vírginis."),
                         "Fictópoli in Gállia")
        self.assertEqual(p.opening_phrase("Fictópoli, beátæ Fictæ."), "Fictópoli")

    def test_marker_word_ends_the_phrase(self):
        self.assertEqual(p.opening_phrase("Fictopoli, translátio sancti Ficti."), "Fictopoli")

    def test_time_tail_is_stripped(self):
        self.assertEqual(p.opening_phrase("Fictopoli item in Fictia, eódem die et anno, sanctárum Fictarum."),
                         "Fictopoli item in Fictia")
        self.assertEqual(p.opening_phrase("Ibídem, eódem die, sanctárum Fictarum."), "Ibídem")

    def test_item_before_a_commemoration_means_also_not_a_place(self):
        self.assertIsNone(p.opening_phrase("Item commemorátio sancti Fictitii, episcopi."))
        self.assertIsNone(p.opening_phrase("Item commemorántur plurimi Ficti."))
        self.assertEqual(p.opening_phrase("Item, sancti Fictitii, episcopi."), "Item")
        self.assertEqual(p.opening_phrase("Ibídem commemorátio sancti Fictitii."), "Ibídem")

    def test_more_stop_words(self):
        self.assertEqual(p.opening_phrase("Apud Fictopolim, dormítio sanctæ Fictæ."), "Apud Fictopolim")
        self.assertIsNone(p.opening_phrase("Sanctíssimi Nóminis Ficti, quod fictum est."))
        self.assertEqual(p.opening_phrase("In ecclesia Sanctíssimæ Fictitatis, sancti Ficti."),
                         "In ecclesia Sanctíssimæ Fictitatis")

    def test_clause_after_a_comma_is_cut(self):
        self.assertEqual(p.opening_phrase("In monasterio Fictensi, quod condiderat, in Fictia, sancti Ficti."),
                         "In monasterio Fictensi")
        self.assertEqual(p.opening_phrase("Fictopoli in Fictia, sub Fictio imperatore, sanctorum Fictorum."),
                         "Fictopoli in Fictia")
        self.assertEqual(p.opening_phrase("In loco Ficto, in eádem persecutióne, beatorum Fictorum."),
                         "In loco Ficto")
        self.assertEqual(p.opening_phrase("Ibídem, octo post annis, beati Ficti."), "Ibídem")
        self.assertEqual(p.opening_phrase("Ibídem, Fictorni, decem et septem post annis, beati Ficti."),
                         "Ibídem, Fictorni")
        # a locative after a comma is part of the place
        self.assertEqual(p.opening_phrase("Fictopoli, in Fictia, sancti Ficti."), "Fictopoli, in Fictia")

    def test_no_stop_word_means_no_place(self):
        self.assertIsNone(p.opening_phrase("Fictis transactis temporibus Fictus nascitur."))

    def test_split_lead(self):
        self.assertEqual(p.split_lead("Ibídem"), ("back", None))
        self.assertEqual(p.split_lead("Item"), ("back", None))
        self.assertEqual(p.split_lead("Item Fictópoli"), ("place", "Fictópoli"))
        self.assertEqual(p.split_lead("Item, in Fictia"), ("place", "in Fictia"))
        self.assertEqual(p.split_lead("Ibídem in cœmetério Ficti"), ("extend", "Ibídem in cœmetério Ficti"))
        self.assertEqual(p.split_lead("Fictopoli in Fictia"), ("place", "Fictopoli in Fictia"))


DAY1 = [("mr:0101-a", 1, 1), ("mr:0101-b", 1, 1), ("mr:0101-c", 1, 1), ("mr:0101-d", 1, 1), ("mr:0101-e", 1, 1)]
TEXTS = {
    "mr:0101-a": "Fictopoli in Fictia, sancti Fictitii A.",
    "mr:0101-b": "Ibídem, beáti Ficti B.",
    "mr:0101-c": "Ibídem, sanctæ Fictæ C.",
    "mr:0101-d": "Ibídem in cœmetério Ficti, sancti Ficti D.",
    "mr:0101-e": "Sancti Fictitii E., episcopi.",
    "mr:0102-f": "Item, sancti Ficti F.",
    "mr:0102-g": "In octava Ficti, sancti Ficti G.",
}
TYP = {k: "dies_natalis" for k in TEXTS}
TYP["mr:0101-b"] = "depositio"


class LeadItemsTest(unittest.TestCase):
    def run_leads(self, order=None, not_a_place=None):
        order = order or DAY1 + [("mr:0102-f", 1, 2), ("mr:0102-g", 1, 2)]
        return p.lead_items(order, TEXTS, TYP, not_a_place=not_a_place or {})

    def test_place_and_back_references(self):
        items, unresolved = self.run_leads()
        self.assertEqual(items["mr:0101-a"], {"role": "death", "la": "Fictopoli in Fictia", "source": "lead"})
        self.assertEqual(items["mr:0101-b"],
                         {"role": "burial", "la": "Fictopoli in Fictia", "source": "lead", "via": "mr:0101-a"})

    def test_chain_points_to_the_root(self):
        items, _ = self.run_leads()
        self.assertEqual(items["mr:0101-c"]["via"], "mr:0101-a")
        self.assertEqual(items["mr:0101-c"]["la"], "Fictopoli in Fictia")

    def test_extended_ibidem_keeps_its_phrase(self):
        items, _ = self.run_leads()
        self.assertEqual(items["mr:0101-d"],
                         {"role": "death", "la": "Ibídem in cœmetério Ficti", "source": "lead", "via": "mr:0101-a"})

    def test_no_place_and_unresolved_first_of_day(self):
        items, unresolved = self.run_leads()
        self.assertNotIn("mr:0101-e", items)
        self.assertNotIn("mr:0102-f", items)
        self.assertEqual(unresolved, ["mr:0102-f"])

    def test_not_a_place(self):
        items, _ = self.run_leads(not_a_place={"mr:0102-g": "a time phrase"})
        self.assertNotIn("mr:0102-g", items)

    def test_every_typology_maps_to_a_role(self):
        for value, role in p.ROLE_OF_TYPOLOGY.items():
            items, _ = p.lead_items([("mr:0101-a", 1, 1)], TEXTS, {"mr:0101-a": value}, not_a_place={})
            self.assertEqual(items["mr:0101-a"]["role"], role)
            self.assertIn(role, p.ROLES)


class CuratedTest(unittest.TestCase):
    TEXT = {"mr:0101-a": "Fictopoli in Fictia, sancti Fictitii, qui in Fictonia natus est."}
    LEADS = {"mr:0101-a": {"role": "death", "la": "Fictopoli in Fictia", "source": "lead"}}

    def errors(self, items, mrid="mr:0101-a"):
        return p.validate_curated({mrid: items}, self.TEXT, {"mr:0101-a"}, self.LEADS)

    def test_verbatim_item_is_valid(self):
        self.assertEqual(self.errors([{"role": "birth", "la": "in Fictonia"}]), [])

    def test_invalid_items(self):
        self.assertTrue(self.errors([{"role": "birth", "la": "in Fictlandia"}]))
        self.assertTrue(self.errors([{"role": "nativity", "la": "in Fictonia"}]))
        self.assertTrue(self.errors([{"role": "death", "la": "Fictopoli in Fictia"}]))
        self.assertTrue(self.errors([{"role": "birth", "la": "in Fictonia", "note": "x"}]))
        self.assertTrue(self.errors([{"role": "birth", "la": "in Fictonia"}], mrid="mr:0102-x"))
        long_text = {"mr:0101-a": "Fictopoli, sancti Ficti, " + " ".join(["in Fictia"] * 7) + "."}
        self.assertTrue(p.validate_curated({"mr:0101-a": [{"role": "birth", "la": " ".join(["in Fictia"] * 7)}]},
                                           long_text, {"mr:0101-a"}, {}))


class CueTest(unittest.TestCase):
    def test_cues_outside_the_opening_phrase(self):
        text = "Fictopoli, sancti Ficti, qui in Fictonia natus, episcopus Fictensis, ibi obiit."
        self.assertEqual(p.cue_roles(text), ["birth", "death", "ministry"])
        self.assertEqual(p.cue_roles("Fictopoli, sancti Ficti, martyris."), [])


class BuildTest(unittest.TestCase):
    ORDER = [("mr:0101-a", 1, 1), ("mr:0101-b", 1, 1), ("mr:0101-e", 1, 1)]
    TX = {
        "mr:0101-a": "Fictopoli in Fictia, sancti Fictitii, qui in Fictonia natus est.",
        "mr:0101-b": "Ibídem, beáti Ficti B.",
        "mr:0101-e": "Sancti Fictitii E., episcopi.",
    }
    TY = {"mr:0101-a": "dies_natalis", "mr:0101-b": "depositio", "mr:0101-e": "celebratio"}
    CUR = {"mr:0101-a": [{"role": "birth", "la": "in Fictonia"}]}

    def build(self, curated=None):
        return p.build(self.ORDER, self.TX, self.TY, self.CUR if curated is None else curated, not_a_place={})

    def test_build(self):
        r = self.build()
        self.assertEqual(r["places"]["mr:0101-a"], [
            {"role": "death", "la": "Fictopoli in Fictia", "source": "lead"},
            {"role": "birth", "la": "in Fictonia", "source": "curated"},
        ])
        self.assertEqual(r["no_place"], ["mr:0101-e"])
        self.assertEqual(r["candidates"], {"mr:0101-a": ["birth"]})
        self.assertEqual(r["curated_ids"], {"mr:0101-a"})

    def test_validate(self):
        ids = set(self.TX)
        r = self.build()
        p.validate(r, self.TX, ids, {"mr:0199-old"}, self.TY, self.CUR, long_ok={})
        bad = self.build()
        bad["places"]["mr:0101-a"][0]["role"] = "burial"   # disagrees with typology
        with self.assertRaises(AssertionError):
            p.validate(bad, self.TX, ids, set(), self.TY, self.CUR, long_ok={})
        bad = self.build()
        bad["places"]["mr:0101-b"][0]["la"] = "Fictlandia"   # not verbatim in the via text
        with self.assertRaises(AssertionError):
            p.validate(bad, self.TX, ids, set(), self.TY, self.CUR, long_ok={})
        with self.assertRaises(AssertionError):
            p.validate(r, self.TX, ids, {"mr:0101-a"}, self.TY, self.CUR, long_ok={})
        with self.assertRaises(AssertionError):
            p.validate(r, self.TX, ids, set(), self.TY, {"mr:0101-a": [{"role": "x", "la": "y"}]}, long_ok={})

    def test_long_lead_needs_allow_list(self):
        tx = {"mr:0101-a": " ".join(["In Fictia"] * 7) + ", sancti Ficti."}
        order, ty = [("mr:0101-a", 1, 1)], {"mr:0101-a": "dies_natalis"}
        r = p.build(order, tx, ty, {}, not_a_place={})
        self.assertEqual([k for k, _ in r["long"]], ["mr:0101-a"])
        with self.assertRaises(AssertionError):
            p.validate(r, tx, {"mr:0101-a"}, set(), ty, {}, long_ok={})
        p.validate(r, tx, {"mr:0101-a"}, set(), ty, {}, long_ok={"mr:0101-a": "reason"})

    def test_render_json(self):
        import json
        out = json.loads(p.render_json(self.build()["places"]))
        self.assertEqual(out["roles"], p.ROLES)
        self.assertEqual(list(out["places"]), ["mr:0101-a", "mr:0101-b"])

    def test_report_flags_comma_clauses(self):
        tx = {"mr:0101-a": "Fictopoli, Fictorni, sancti Ficti."}
        r = p.build([("mr:0101-a", 1, 1)], tx, {"mr:0101-a": "dies_natalis"}, {}, not_a_place={})
        report = p.render_report(r)
        self.assertIn("## Opening places with a comma", report)
        self.assertIn("- `mr:0101-a`: Fictopoli, Fictorni", report)
        self.assertEqual(r["comma"], [("mr:0101-a", "Fictopoli, Fictorni")])

    def test_report(self):
        report = p.render_report(self.build())
        self.assertIn("| death | 1 |", report)
        self.assertIn("## Curation candidates", report)
        self.assertIn("| `mr:0101-a` | birth | yes |", report)
        self.assertIn("`mr:0101-e`", report)
        self.assertNotIn("Fictitii", report)


if __name__ == "__main__":
    unittest.main()
