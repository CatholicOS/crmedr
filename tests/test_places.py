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

    def test_place_name_opening_with_a_capitalized_saint(self):
        self.assertEqual(p.opening_phrase("Sancti Fictitii Fani in Fictia, transitus sancti Ficti."),
                         "Sancti Fictitii Fani in Fictia")
        self.assertEqual(p.opening_phrase("Sancti Fictii in Fictonia, beati Fictitii, presbyteri."),
                         "Sancti Fictii in Fictonia")
        self.assertIsNone(p.opening_phrase("Sancti Fictitii, episcopi, qui sancti Ficti discipulus fuit."))
        self.assertIsNone(p.opening_phrase("Sanctorum martyrum Fictorum, quorum passio fertur."))

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

    def test_printed_misprint_of_an_honorific_ends_the_phrase(self):
        text = "In vico Ficto item in Fictia, betárum mártyrum Fictarum."
        self.assertIsNone(p.opening_phrase(text))
        self.assertEqual(p.opening_phrase(text, p.STOP_WORDS | {"betarum"}), "In vico Ficto item in Fictia")

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
        items, unresolved, _ = self.run_leads()
        self.assertEqual(items["mr:0101-a"], {"role": "death", "la": "Fictopoli in Fictia", "source": "lead"})
        self.assertEqual(items["mr:0101-b"],
                         {"role": "burial", "la": "Fictopoli in Fictia", "source": "lead", "via": "mr:0101-a"})

    def test_bare_back_references_are_reported_explicitly(self):
        _, _, bare = self.run_leads()
        self.assertEqual(bare, {"mr:0101-b", "mr:0101-c"})      # d is an extended Ibidem, not bare

    def test_chain_points_to_the_root(self):
        items, _, _ = self.run_leads()
        self.assertEqual(items["mr:0101-c"]["via"], "mr:0101-a")
        self.assertEqual(items["mr:0101-c"]["la"], "Fictopoli in Fictia")

    def test_extended_ibidem_keeps_its_phrase(self):
        items, _, _ = self.run_leads()
        self.assertEqual(items["mr:0101-d"],
                         {"role": "death", "la": "Ibídem in cœmetério Ficti", "source": "lead", "via": "mr:0101-a"})

    def test_bare_back_reference_after_an_extended_one_uses_it(self):
        order = [("mr:0103-a", 1, 3), ("mr:0103-d", 1, 3), ("mr:0103-x", 1, 3)]
        texts = {
            "mr:0103-a": "Fictopoli in Fictia, sancti Fictitii A.",
            "mr:0103-d": "Ibídem in cœmetério Ficti, sancti Ficti D.",
            "mr:0103-x": "Ibídem, sanctæ Fictæ X.",
        }
        items, _, _ = p.lead_items(order, texts, {k: "dies_natalis" for k in texts}, not_a_place={})
        self.assertEqual(items["mr:0103-d"]["via"], "mr:0103-a")
        self.assertEqual(items["mr:0103-x"],
                         {"role": "death", "la": "Ibídem in cœmetério Ficti", "source": "lead", "via": "mr:0103-d"})

    def test_no_place_and_unresolved_first_of_day(self):
        items, unresolved, _ = self.run_leads()
        self.assertNotIn("mr:0101-e", items)
        self.assertNotIn("mr:0102-f", items)
        self.assertEqual(unresolved, ["mr:0102-f"])

    def test_extended_back_reference_without_antecedent_is_kept_and_reported(self):
        order = [("mr:0104-d", 1, 4)]
        texts = {"mr:0104-d": "Ibídem in cœmetério Ficti, sancti Ficti D."}
        items, unresolved, _ = p.lead_items(order, texts, {"mr:0104-d": "dies_natalis"}, not_a_place={})
        self.assertEqual(items["mr:0104-d"], {"role": "death", "la": "Ibídem in cœmetério Ficti", "source": "lead"})
        self.assertEqual(unresolved, ["mr:0104-d"])

    def test_not_a_place(self):
        items, _, _ = self.run_leads(not_a_place={"mr:0102-g": "a time phrase"})
        self.assertNotIn("mr:0102-g", items)

    def test_every_typology_maps_to_a_role(self):
        for value, role in p.ROLE_OF_TYPOLOGY.items():
            items, _, _ = p.lead_items([("mr:0101-a", 1, 1)], TEXTS, {"mr:0101-a": value}, not_a_place={})
            self.assertEqual(items["mr:0101-a"]["role"], role)
            self.assertIn(role, p.ROLES)


class PrintOrderTest(unittest.TestCase):
    def test_print_only_entry_takes_its_printed_slot(self):
        entries = [
            {"id": "mr:0104-x", "month": 1, "day": 4, "entry": 1},
            {"id": "mr:0104-y", "month": 1, "day": 4, "entry": 2},
            {"id": "mr:0104-late", "month": 1, "day": 4, "entry": None},
            {"id": "mr:0104-unknown", "month": 1, "day": 4, "entry": None},
            {"id": "mr:0103-z", "month": 1, "day": 3, "entry": 5},
        ]
        order = p.print_order(entries)
        self.assertEqual([m for m, _, _ in order],
                         ["mr:0103-z", "mr:0104-x", "mr:0104-y", "mr:0104-late", "mr:0104-unknown"])
        self.assertEqual(order[0], ("mr:0103-z", 1, 3))

    def test_no_print_positions_table(self):
        self.assertFalse(hasattr(p, "PRINT_POSITION"))


MISPRINTS = [
    {"id": "mr:0101-a", "edition": "martyrologium_romanum_2004", "printed": "betárum",
     "intended": "beatárum", "verified": "print"},
    {"id": "mr:0101-b", "edition": "martyrologium_romanum_2004_it_IT", "printed": "desposizione",
     "intended": "deposizione", "verified": "print"},
]
MTEXTS = {
    "martyrologium_romanum_2004": {"mr:0101-a": "Fictopoli, betárum Fictarum.", "mr:0101-b": "Fictopoli, sancti Ficti."},
    "martyrologium_romanum_2004_it_IT": {"mr:0101-a": "A Fictopoli, beate Fitte.", "mr:0101-b": "A Fictopoli, desposizione di san Fitto."},
}


class MisprintTest(unittest.TestCase):
    def test_valid_records(self):
        self.assertEqual(p.validate_misprints(MISPRINTS, MTEXTS, {"mr:0101-a", "mr:0101-b"}), [])

    def test_invalid_records(self):
        ids = {"mr:0101-a", "mr:0101-b"}
        bad = [dict(MISPRINTS[0], printed="betorum")]                          # not in the text
        self.assertTrue(p.validate_misprints(bad, MTEXTS, ids))
        twice = {**MTEXTS, "martyrologium_romanum_2004": {"mr:0101-a": "betárum, betárum."}}
        self.assertTrue(p.validate_misprints(MISPRINTS[:1], twice, ids))      # occurs twice
        self.assertTrue(p.validate_misprints([dict(MISPRINTS[0], edition="x")], MTEXTS, ids))
        self.assertTrue(p.validate_misprints([dict(MISPRINTS[0], id="mr:0102-z")], MTEXTS, ids))
        self.assertTrue(p.validate_misprints([{"id": "mr:0101-a"}], MTEXTS, ids))
        self.assertTrue(p.validate_misprints(list(reversed(MISPRINTS)), MTEXTS, ids))   # unsorted

    def test_whole_word_count_and_short_phrases(self):
        ids = {"mr:0101-a"}
        texts = {"martyrologium_romanum_2004_it_IT": {"mr:0101-a": "A Fittopoli nell territorio dell’odierna Fittia, nell Fittonia."}}
        rec = lambda printed: [{"id": "mr:0101-a", "edition": "martyrologium_romanum_2004_it_IT",
                                "printed": printed, "intended": "x", "verified": "print"}]
        self.assertEqual(p.validate_misprints(rec("nell territorio"), texts, ids), [])
        self.assertTrue(p.validate_misprints(rec("nell"), texts, ids))                 # 2 whole-word hits
        self.assertEqual(p.validate_misprints(rec("dell’odierna"), texts, ids), [])    # elision is part of the word
        self.assertTrue(p.validate_misprints(rec("Fitt"), texts, ids))                 # a substring is not a word
        self.assertTrue(p.validate_misprints(rec("A Fittopoli nell territorio"), texts, ids))   # over 3 words

    def test_duplicated_entries(self):
        entries = [{"id": "mr:0101-a", "month": 1, "day": 1, "unnumbered": True},
                   {"id": "mr:0102-x", "month": 1, "day": 2},
                   {"id": "mr:0102-y", "month": 1, "day": 2}]
        texts = {"martyrologium_romanum_2004_it_IT": {"mr:0101-a": "A Fictopoli, san Fitto."}}
        rec = {"id": "mr:0101-a", "edition": "martyrologium_romanum_2004_it_IT",
               "month": 1, "day": 2, "before_entry": 1, "verified": "print"}
        self.assertEqual(p.validate_duplicated_entries([rec], entries, texts), [])
        self.assertEqual(p.validate_duplicated_entries([dict(rec, before_entry=3)], entries, texts), [])
        self.assertTrue(p.validate_duplicated_entries([dict(rec, before_entry=4)], entries, texts))  # past the day's end
        self.assertTrue(p.validate_duplicated_entries([dict(rec, before_entry=True)], entries, texts))  # a bool is not an int
        self.assertTrue(p.validate_duplicated_entries([dict(rec, day=1)], entries, texts))           # its own day
        self.assertTrue(p.validate_duplicated_entries([dict(rec, day=3)], entries, texts))           # an empty day
        self.assertTrue(p.validate_duplicated_entries([dict(rec, id="mr:0101-z")], entries, texts))
        self.assertTrue(p.validate_duplicated_entries([dict(rec, edition="x")], entries, texts))
        self.assertTrue(p.validate_duplicated_entries([dict(rec, id="mr:0102-x", day=1)], entries, texts))  # no text
        self.assertTrue(p.validate_duplicated_entries([{"id": "mr:0101-a"}], entries, texts))

    def test_stop_words_per_edition(self):
        self.assertEqual(p.misprint_stop_words(MISPRINTS, p.EDITION_LA, p.STOP_WORDS), {"betarum"})
        self.assertEqual(p.misprint_stop_words(MISPRINTS, p.EDITION_LA, {"sancti"}), set())
        self.assertEqual(p.misprint_stop_words(MISPRINTS, p.EDITION_IT, {"deposizione"}), {"desposizione"})

    def test_load_misprints(self):
        import json, tempfile
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(p.load_misprints(Path(d)), [])
            (Path(d) / "data").mkdir()
            (Path(d) / "data" / "misprints.json").write_text(json.dumps({"misprints": MISPRINTS}), encoding="utf-8")
            self.assertEqual(p.load_misprints(Path(d)), MISPRINTS)

    def test_repository_file_is_valid_shape(self):
        import json
        path = Path(__file__).resolve().parent.parent / "data" / "misprints.json"
        records = json.load(open(path, encoding="utf-8"))["misprints"]
        self.assertEqual([(r["id"], r["edition"]) for r in records],
                         sorted((r["id"], r["edition"]) for r in records))
        self.assertTrue(all(set(r) == p.MISPRINT_KEYS for r in records))
        self.assertEqual({r["printed"] for r in records},
                         {"betárum", "Marcellino", "desposizione", "comemorazione", "Mel", "nell territorio",
                          "nell’odiena", "un Inghilterra", "Inghiltera", "vicno", "prospicente",
                          "Bellrreguart"})


class ItalianPhraseTest(unittest.TestCase):
    def test_lowercase_honorific_and_markers_end_the_phrase(self):
        self.assertEqual(p.italian_phrase("A Fittopoli in Fittia, san Fitto, vescovo."), "A Fittopoli in Fittia")
        self.assertEqual(p.italian_phrase("Nel cenobio di Fittaco, beata Fitta."), "Nel cenobio di Fittaco")
        self.assertEqual(p.italian_phrase("A Fittopoli, anniversario della nascita al cielo del beato Fitto."), "A Fittopoli")
        self.assertEqual(p.italian_phrase("A Fittopoli, martirio dei santi Fitti."), "A Fittopoli")

    def test_capitalized_saint_in_a_place_name_stays(self):
        self.assertEqual(p.italian_phrase("A San Fittorino nelle Fittie, beato Fitto."), "A San Fittorino nelle Fittie")

    def test_lowercase_saint_after_a_preposition_is_part_of_the_place(self):
        self.assertEqual(p.italian_phrase("A Fittopoli presso san Fittino, san Fitto, papa."),
                         "A Fittopoli presso san Fittino")
        self.assertEqual(p.italian_phrase("Nel monastero di sant’Ilario presso Fittopoli, beato Fitto."),
                         "Nel monastero di sant’Ilario presso Fittopoli")
        self.assertEqual(p.italian_phrase("A Fittopoli san Fitto, vescovo."), "A Fittopoli")

    def test_time_opening_is_not_a_place(self):
        self.assertIsNone(p.italian_phrase("Nello stesso giorno, san Fitto."))
        self.assertIsNone(p.italian_phrase("Sempre nello stesso giorno, san Fitto."))
        self.assertIsNone(p.italian_phrase("Nello stesso giorno, trent’anni dopo, san Fitto."))

    def test_capitalized_stop_word_at_start_means_no_phrase(self):
        self.assertIsNone(p.italian_phrase("Memoria di san Fitto, vescovo."))
        self.assertIsNone(p.italian_phrase("Parimenti si commemorano i santi Fitti."))

    def test_modern_hints_after_a_comma_are_kept(self):
        self.assertEqual(p.italian_phrase("A Fittopoli in Fittia, nell’odierna Fittonia, san Fitto."),
                         "A Fittopoli in Fittia, nell’odierna Fittonia")
        self.assertEqual(p.italian_phrase("A Fittopoli, ora in Fittonia, sempre in Fittia, beato Fitto."),
                         "A Fittopoli, ora in Fittonia, sempre in Fittia")

    def test_clauses_after_a_comma_are_cut(self):
        self.assertEqual(p.italian_phrase("A Fittopoli, dove si era rifugiato, san Fitto."), "A Fittopoli")
        self.assertEqual(p.italian_phrase("A Fittopoli, trent’anni più tardi, beato Fitto."), "A Fittopoli")
        self.assertEqual(p.italian_phrase("A Fittopoli, sotto il medesimo re, beato Fitto."), "A Fittopoli")
        self.assertEqual(p.italian_phrase("Nel cenobio di Fittaco, da lui fondato, san Fitto."), "Nel cenobio di Fittaco")
        self.assertEqual(p.italian_phrase("A Fittopoli, trecentosei santi martiri."), "A Fittopoli")

    def test_naming_clause_is_kept(self):
        self.assertEqual(p.italian_phrase("In località Fittia, chiamata poi Fittopoli, in Fittonia, san Fitto."),
                         "In località Fittia, chiamata poi Fittopoli, in Fittonia")

    def test_more_locative_openers(self):
        self.assertEqual(p.italian_phrase("A Fittopoli, a tre miglia da Fittia, san Fitto."),
                         "A Fittopoli, a tre miglia da Fittia")
        self.assertEqual(p.italian_phrase("A Fittopoli, a 3 miglia da Fittia, san Fitto."),
                         "A Fittopoli, a 3 miglia da Fittia")
        self.assertEqual(p.italian_phrase("A Fittopoli, al 120 miglio della via Fittia, san Fitto."),
                         "A Fittopoli, al 120 miglio della via Fittia")
        self.assertEqual(p.italian_phrase("Nel cenobio di Fittaco, sull’isola di Fitta, beato Fitto."),
                         "Nel cenobio di Fittaco, sull’isola di Fitta")
        self.assertEqual(p.italian_phrase("A Fittopoli, dal lato del Fittone, beato Fitto."),
                         "A Fittopoli, dal lato del Fittone")

    def test_year_or_hatred_of_the_faith_is_cut(self):
        self.assertEqual(p.italian_phrase("A Fittopoli, nel 1597, san Fitto."), "A Fittopoli")
        self.assertEqual(p.italian_phrase("A Fittopoli, nell’anno 1597, san Fitto."), "A Fittopoli")
        self.assertEqual(p.italian_phrase("A Fittopoli, in odio alla fede, beati Fitti."), "A Fittopoli")

    def test_sempre_and_back_references(self):
        self.assertEqual(p.italian_phrase("Sempre a Fittopoli, san Fitto."), "a Fittopoli")
        self.assertEqual(p.italian_phrase("Ancora a Fittopoli, beato Fitto."), "a Fittopoli")
        self.assertIsNone(p.italian_phrase("Nello stesso luogo, san Fitto."))
        self.assertIsNone(p.italian_phrase("Nella stessa città, beata Fitta."))
        self.assertIsNone(p.italian_phrase("Sempre nello stesso luogo, san Fitto."))
        self.assertIsNone(p.italian_phrase("Nello stesso luogo, dieci anni dopo, sante Fitte."))
        self.assertEqual(p.italian_phrase("A Fittopoli, giorno e anno, sante Fitte."), "A Fittopoli")

    def test_no_text(self):
        self.assertIsNone(p.italian_phrase(None))
        self.assertIsNone(p.italian_phrase(""))

    def test_misprinted_stop_word(self):
        text = "A Fittopoli in Fittia desposizione di san Fitto."
        self.assertEqual(p.italian_phrase(text, p.STOP_WORDS_IT | {"desposizione"}), "A Fittopoli in Fittia")


class ItalianAlignmentTest(unittest.TestCase):
    ORDER = [("mr:0105-a", 1, 5), ("mr:0105-b", 1, 5), ("mr:0105-c", 1, 5), ("mr:0105-e", 1, 5)]
    TX = {
        "mr:0105-a": "Fictopoli in Fictia, sancti Fictitii A.",
        "mr:0105-b": "Ibídem, beáti Ficti B.",
        "mr:0105-c": "Ficticastro, sancti Ficti C.",
        "mr:0105-e": "Sancti Fictitii E.",
    }
    IT = {
        "mr:0105-a": "A Fittopoli in Fittia, ora in Fittonia, san Fitto A.",
        "mr:0105-b": "Nello stesso luogo, beato Fitto B.",
        "mr:0105-e": "A Fittocastro, san Fitto E.",
    }
    TY = {k: "dies_natalis" for k in TX}

    def build(self, it=None, curated=None):
        return p.build(self.ORDER, self.TX, self.TY, curated or {}, not_a_place={},
                       texts_it=self.IT if it is None else it)

    def test_alignment(self):
        r = self.build()
        a, b = r["places"]["mr:0105-a"][0], r["places"]["mr:0105-b"][0]
        self.assertEqual(list(a), ["role", "la", "it", "source"])
        self.assertEqual(a["it"], "A Fittopoli in Fittia, ora in Fittonia")
        self.assertEqual(list(b), ["role", "la", "it", "source", "via"])
        self.assertEqual(b["it"], a["it"])                           # bare Latin back-reference: root's it
        self.assertNotIn("it", r["places"]["mr:0105-c"][0])        # no Italian text
        self.assertEqual(r["no_it"], ["mr:0105-c"])
        self.assertEqual(r["it_only"], [("mr:0105-e", "A Fittocastro")])

    def test_root_without_it(self):
        r = self.build(it={"mr:0105-b": "Nello stesso luogo, beato Fitto B."})
        self.assertNotIn("it", r["places"]["mr:0105-a"][0])
        self.assertNotIn("it", r["places"]["mr:0105-b"][0])
        p.validate(r, self.TX, set(self.TX), set(), self.TY, {}, long_ok={}, texts_it=self.IT)

    def test_validate_it(self):
        ids = set(self.TX)
        r = self.build()
        p.validate(r, self.TX, ids, set(), self.TY, {}, long_ok={}, texts_it=self.IT)
        bad = self.build(); bad["places"]["mr:0105-a"][0]["it"] = "A Fittonia"            # not verbatim
        with self.assertRaises(AssertionError):
            p.validate(bad, self.TX, ids, set(), self.TY, {}, long_ok={}, texts_it=self.IT)
        bad = self.build(); bad["places"]["mr:0105-b"][0]["it"] = "Nello stesso luogo"    # not the root's it
        with self.assertRaises(AssertionError):
            p.validate(bad, self.TX, ids, set(), self.TY, {}, long_ok={}, texts_it=self.IT)
        long_it = {"mr:0105-a": " ".join(["A Fittia"] * 11) + ", san Fitto."}
        bad = self.build(it=long_it)
        with self.assertRaises(AssertionError):
            p.validate(bad, self.TX, ids, set(), self.TY, {}, long_ok={}, texts_it=long_it)

    def test_curated_it(self):
        tx = {"mr:0105-a": "Fictopoli, sancti Ficti, qui in Fictonia natus est."}
        it = {"mr:0105-a": "A Fittopoli, san Fitto, nato in Fittonia."}
        ok = {"mr:0105-a": [{"role": "birth", "la": "in Fictonia", "it": "in Fittonia"}]}
        self.assertEqual(p.validate_curated(ok, tx, {"mr:0105-a"}, {}, it), [])
        bad = {"mr:0105-a": [{"role": "birth", "la": "in Fictonia", "it": "in Fittlandia"}]}
        self.assertTrue(p.validate_curated(bad, tx, {"mr:0105-a"}, {}, it))
        r = p.build([("mr:0105-a", 1, 5)], tx, {"mr:0105-a": "dies_natalis"}, ok, not_a_place={}, texts_it=it)
        self.assertEqual(r["places"]["mr:0105-a"][1],
                         {"role": "birth", "la": "in Fictonia", "it": "in Fittonia", "source": "curated"})

    def test_it_ending_in_a_function_word_is_rejected(self):
        it = {"mr:0105-a": "A Fittopoli presso, san Fitto A.", "mr:0105-b": "Nello stesso luogo, beato Fitto B."}
        r = self.build(it=it)
        self.assertEqual(r["places"]["mr:0105-a"][0]["it"], "A Fittopoli presso")
        with self.assertRaisesRegex(AssertionError, "ends in"):
            p.validate(r, self.TX, set(self.TX), set(), self.TY, {}, long_ok={}, texts_it=it)

    def test_not_a_place_is_not_listed_as_italian_only(self):
        r = p.build(self.ORDER, self.TX, self.TY, {}, not_a_place={"mr:0105-e": "a time phrase"},
                    texts_it=self.IT)
        self.assertEqual(r["it_only"], [])

    def test_curated_entry_is_not_listed_as_italian_only(self):
        cur = {"mr:0105-e": [{"role": "death", "la": "Fictitii", "it": "A Fittocastro"}]}
        r = self.build(curated=cur)
        self.assertEqual(r["it_only"], [])

    def test_json_comment_mentions_it(self):
        import json
        self.assertIn("(it)", json.loads(p.render_json({}))["$comment"])

    def test_report_sections(self):
        report = p.render_report(self.build())
        self.assertIn("## Latin places without an Italian phrase", report)
        self.assertIn("`mr:0105-c`", report)
        self.assertIn("## Italian places without a Latin place", report)
        self.assertIn("- `mr:0105-e`: A Fittocastro", report)

    def test_without_italian_texts_nothing_changes(self):
        r = p.build(self.ORDER, self.TX, self.TY, {}, not_a_place={})
        self.assertFalse(any("it" in it for its in r["places"].values() for it in its))


class CuratedTest(unittest.TestCase):
    TEXT = {"mr:0101-a": "Fictopoli in Fictia, sancti Fictitii, qui in Fictonia natus est."}
    LEADS = {"mr:0101-a": {"role": "death", "la": "Fictopoli in Fictia", "source": "lead"}}

    def errors(self, items, mrid="mr:0101-a"):
        return p.validate_curated({mrid: items}, self.TEXT, {"mr:0101-a"}, self.LEADS)

    def test_verbatim_item_is_valid(self):
        self.assertEqual(self.errors([{"role": "birth", "la": "in Fictonia"}]), [])

    def test_empty_la_is_rejected(self):
        for la in ("", "   "):
            errors = self.errors([{"role": "birth", "la": la}])
            self.assertEqual(len(errors), 1)
            self.assertIn("empty", errors[0])

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
        self.assertEqual(p.cue_matches(text),
                         {"birth": ["natus"], "death": ["obiit"], "ministry": ["episcopus fictensis"]})
        self.assertEqual(p.cue_matches("Fictopoli, sancti Ficti, martyris."), {})


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
        self.assertEqual(r["candidates"], {"mr:0101-a": {"birth": ["natus"]}})
        self.assertEqual(r["day_of"]["mr:0101-b"], (1, 1))
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

    def test_validate_ties_via_to_its_entry(self):
        ids = set(self.TX)
        bad = self.build()
        bad["places"]["mr:0101-b"][0]["la"] = "Fictia"          # in the via text, but not the root's la
        with self.assertRaisesRegex(AssertionError, "root"):
            p.validate(bad, self.TX, ids, set(), self.TY, self.CUR, long_ok={})
        bad = self.build()
        bad["day_of"]["mr:0101-a"] = (1, 2)                       # via on another day
        with self.assertRaisesRegex(AssertionError, "same day"):
            p.validate(bad, self.TX, ids, set(), self.TY, self.CUR, long_ok={})
        bad = self.build()
        bad["places"]["mr:0101-b"][0]["via"] = "mr:0101-zz"      # via with no text
        with self.assertRaisesRegex(AssertionError, "mr:0101-zz"):
            p.validate(bad, self.TX, ids, set(), self.TY, self.CUR, long_ok={})

    def test_extended_back_reference_la_must_be_verbatim(self):
        order = [("mr:0103-a", 1, 3), ("mr:0103-d", 1, 3)]
        tx = {"mr:0103-a": "Fictopoli in Fictia, sancti Fictitii A.",
              "mr:0103-d": "Ibídem in cœmetério Ficti, sancti Ficti D."}
        ty = {k: "dies_natalis" for k in tx}
        r = p.build(order, tx, ty, {}, not_a_place={})
        p.validate(r, tx, set(tx), set(), ty, {}, long_ok={})
        r["places"]["mr:0103-d"][0]["la"] = "Ibídem in cœmetério Fictonis"
        with self.assertRaisesRegex(AssertionError, "not verbatim"):
            p.validate(r, tx, set(tx), set(), ty, {}, long_ok={})

    def test_report_marks_kept_extended_back_reference(self):
        tx = {"mr:0104-d": "Ibídem in cœmetério Ficti, sancti Ficti D."}
        r = p.build([("mr:0104-d", 1, 4)], tx, {"mr:0104-d": "dies_natalis"}, {}, not_a_place={})
        self.assertIn("- `mr:0104-d` (kept its own phrase)", p.render_report(r))

    def test_check_typology_coverage(self):
        p.check_typology({"mr:0101-a": "dies_natalis"}, {"mr:0101-a"})
        with self.assertRaisesRegex(AssertionError, "move data/typology.json aside"):
            p.check_typology({"mr:0101-a": "dies_natalis"}, {"mr:0101-a", "mr:0101-b"})

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
        self.assertIn("| `mr:0101-a` | birth (natus) | yes |", report)
        self.assertIn("`mr:0101-e`", report)
        self.assertNotIn("Fictitii", report)


if __name__ == "__main__":
    unittest.main()
