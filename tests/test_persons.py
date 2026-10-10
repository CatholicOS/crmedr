import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import persons_text as pt  # noqa: E402


class NameKeyTest(unittest.TestCase):
    def test_folds_accents_case_and_latin_letters(self):
        self.assertEqual(pt.name_key("Ioánnes Iosephus"), pt.name_key("joannes josephus"))
        self.assertEqual(pt.name_key("Vincentius"), pt.name_key("Uincentius"))
        self.assertEqual(pt.name_key("Cæcilia"), "caecilia")


class SubjectNamesTest(unittest.TestCase):
    def test_single_and_pair(self):
        self.assertEqual(pt.subject_names("mr:0101-basilius", "Sanctus Basilius"), ["Basilius"])
        self.assertEqual(pt.subject_names("mr:0927-cosmas-et-damianus", "Sancti Cosmas et Damianus"),
                         ["Cosmas", "Damianus"])
        self.assertEqual(pt.subject_names("mr:0101-x", "Beatae Anatolia, Victoria et Audax"),
                         ["Anatolia", "Victoria", "Audax"])

    def test_companions_are_not_a_name(self):
        self.assertEqual(pt.subject_names("mr:0206-paulus-miki-et-socii", "Sancti Paulus Miki et socii"),
                         ["Paulus Miki"])

    def test_celebrations_name_no_one_unless_listed(self):
        self.assertEqual(pt.subject_names("mr:1225-nativitas-domini", "Nativitas Domini"), [])
        self.assertEqual(pt.subject_names("mr:0125-conversio-pauli-apostoli", "Conversio Sancti Pauli Apostoli"),
                         ["Paulus"])

    def test_groups_name_no_one(self):
        self.assertEqual(pt.subject_names("mr:1228-innocentes", "Sancti Innocentes"), [])
        self.assertEqual(pt.subject_names("mr:0309-quadraginta-milites-sebastes",
                                          "Sancti Quadraginta Milites Sebastes"), [])

    def test_the_virgin_is_maria_and_other_marias_are_themselves(self):
        self.assertEqual(pt.subject_names("mr:0211-maria-de-lourdes", "Beata Maria de Lourdes"), ["Maria"])
        self.assertEqual(pt.subject_names("mr:0815-assumptio-beatae-mariae-virginis",
                                          "Assumptio Beatae Mariae Virginis"), ["Maria"])
        self.assertEqual(pt.subject_names("mr:0909-maria-de-la-cabeza", "Beata Maria de La Cabeza"),
                         ["Maria de La Cabeza"])
        self.assertEqual(pt.subject_names("mr:0820-maria-de-mattias", "Sancta Maria de Mattias"),
                         ["Maria de Mattias"])


class FootnoteNamesTest(unittest.TestCase):
    def test_openings_groups_descriptors_and_particles(self):
        names, skipped = pt.footnote_names(
            "Quorum nomina: sancti Ioannes de Goto Soan, Iacobus Kisai, religiosi e Societate Iesu; "
            "Martinus ab Ascensione Aguirre, Franciscus Blanco, presbyteri ex Ordine Fratrum Minorum; "
            "Michael Kozaki et Thomas, eius filius, neophytae.")
        self.assertEqual(names, ["Ioannes de Goto Soan", "Iacobus Kisai", "Martinus ab Ascensione Aguirre",
                                 "Franciscus Blanco", "Michael Kozaki", "Thomas"])
        self.assertEqual(skipped, [])

    def test_other_openings_and_accents(self):
        self.assertEqual(pt.footnote_names("Quarum nómina: beatae Maria Fortunata Viti, Anna Rosa.")[0],
                         ["Maria Fortunata Viti", "Anna Rosa"])
        self.assertEqual(pt.footnote_names("Inter quos: Petrus Fictus, presbyter.")[0], ["Petrus Fictus"])

    def test_a_particle_that_is_a_latin_word_keeps_the_name(self):
        self.assertEqual(pt.footnote_names("Quorum nomina: Franciscus a Sancto Michaele de la Parilla.")[0],
                         ["Franciscus a Sancto Michaele de la Parilla"])

    def test_a_segment_without_a_name_is_reported_not_written(self):
        names, skipped = pt.footnote_names("Quorum nomina: Petrus Fictus; 3 alii.")
        self.assertEqual(names, ["Petrus Fictus"])
        self.assertEqual(skipped, ["3 alii"])

    def test_no_opening_reads_nothing(self):
        self.assertEqual(pt.footnote_names("Cf. Acta Sanctorum."), ([], ["Cf. Acta Sanctorum."]))


LEXICON = {pt.name_key(w): w for w in
           ["Paulus", "Ioannes", "Leo", "Felix", "Clemens", "Agatha", "Basilius", "Miki", "Chong", "Ha", "Sang",
            "Petrus", "Brito", "Iacobus"]}


class NominativeTest(unittest.TestCase):
    def test_declensions_resolved_by_the_lexicon(self):
        self.assertEqual(pt.nominative("Pauli", LEXICON), "Paulus")
        self.assertEqual(pt.nominative("Ioánnis", LEXICON), "Ioannes")
        self.assertEqual(pt.nominative("Leónis", LEXICON), "Leo")
        self.assertEqual(pt.nominative("Felícis", LEXICON), "Felix")
        self.assertEqual(pt.nominative("Cleméntis", LEXICON), "Clemens")
        self.assertEqual(pt.nominative("Ágathæ", LEXICON), "Agatha")
        self.assertEqual(pt.nominative("Basílii", LEXICON), "Basilius")

    def test_an_undeclined_name_is_itself(self):
        self.assertEqual(pt.nominative("Miki", LEXICON), "Miki")

    def test_unknown_or_ambiguous_is_none(self):
        self.assertIsNone(pt.nominative("Fictiánis", LEXICON))
        both = dict(LEXICON, **{pt.name_key("Paulius"): "Paulius"})  # Pauli: Paulus or Paulius
        self.assertIsNone(pt.nominative("Pauli", both))


class TextCompanionsTest(unittest.TestCase):
    def test_the_opening_group_of_names(self):
        names, uncertain = pt.text_companions(
            "Romæ, sanctórum mártyrum Pauli, Ioánnis et Leónis, qui sub Diocletiáno passi sunt.", LEXICON)
        self.assertEqual(names, ["Paulus", "Ioannes", "Leo"])
        self.assertEqual(uncertain, [])

    def test_multiword_names_particles_and_et_sociorum(self):
        names, _ = pt.text_companions(
            "In Corea, sanctórum Pauli Chong Ha Sang et Ioánnis de Brito et sociórum.", LEXICON)
        self.assertEqual(names, ["Paulus Chong Ha Sang", "Ioannes de Brito"])

    def test_an_uncertain_form_is_reported_not_guessed(self):
        names, uncertain = pt.text_companions("Sanctórum Pauli et Fictiánis, mártyrum.", LEXICON)
        self.assertEqual(names, ["Paulus"])
        self.assertEqual(uncertain, ["Fictiánis"])

    def test_no_plural_honorific_reads_nothing(self):
        self.assertEqual(pt.text_companions("Romæ, sancti Pauli, mártyris.", LEXICON), ([], []))


import extract_persons as ep  # noqa: E402

FOOT = {"mr:0206-paulus-miki-et-socii": [{"mark": "2", "after": "x", "text":
        "Quorum nomina: sancti Ioannes de Goto Soan, Paulus Miki; Thomas, eius filius."}]}


class EulogyPersonsTest(unittest.TestCase):
    def test_subjects_then_text_then_footnote_without_repeats(self):
        lex = ep.build_lexicon({"mr:0206-paulus-miki-et-socii": "Sancti Paulus Miki et socii"}, FOOT)
        persons, issues = ep.eulogy_persons(
            "mr:0206-paulus-miki-et-socii", "Sancti Paulus Miki et socii",
            "Nagasákii, sanctórum mártyrum Pauli Miki et sociórum.", FOOT["mr:0206-paulus-miki-et-socii"],
            lex, {})
        self.assertEqual(persons, [
            {"name": "Paulus Miki", "where": "text"},
            {"name": "Ioannes de Goto Soan", "where": {"footnote": 1}},
            {"name": "Thomas", "where": {"footnote": 1}},
        ])
        self.assertEqual(issues, {"uncertain": [], "skipped": [], "printed_twice": [], "socii_without_names": False})

    def test_a_curated_entry_replaces_extraction(self):
        persons, _ = ep.eulogy_persons("mr:1003-duo-ewaldi", "Duo Ewaldi", "…", [], {},
                                       {"mr:1003-duo-ewaldi": [{"name": "Ewaldus", "where": "text"}]})
        self.assertEqual(persons, [{"name": "Ewaldus", "where": "text"}])

    def test_et_socii_with_no_names_found_is_flagged(self):
        _, issues = ep.eulogy_persons("mr:0101-x-et-socii", "Sancti X et socii", "Romæ, sancti X et sociórum.",
                                      [], {}, {})
        self.assertTrue(issues["socii_without_names"])


class ValidateTest(unittest.TestCase):
    def test_rejects_bad_data(self):
        good = {"mr:0206-paulus-miki-et-socii": [{"name": "Ioannes de Goto Soan", "where": {"footnote": 1}}]}
        self.assertEqual(ep.validate(good, FOOT, {"mr:0206-paulus-miki-et-socii"}), [])
        self.assertTrue(ep.validate({"mr:9999-nemo": [{"name": "Nemo", "where": "text"}]}, {}, set()))
        self.assertTrue(ep.validate({"mr:0206-paulus-miki-et-socii": [
            {"name": "Petrus Fictus", "where": {"footnote": 1}}]}, FOOT, {"mr:0206-paulus-miki-et-socii"}))
        self.assertTrue(ep.validate({"mr:0206-paulus-miki-et-socii": [
            {"name": "Thomas", "where": {"footnote": 2}}]}, FOOT, {"mr:0206-paulus-miki-et-socii"}))
        self.assertTrue(ep.validate({"mr:0206-paulus-miki-et-socii": [
            {"name": "Thomas", "where": "text"}, {"name": "Thomas", "where": {"footnote": 1}}]},
            FOOT, {"mr:0206-paulus-miki-et-socii"}))


class ValidateParenthesesTest(unittest.TestCase):
    def test_a_name_read_across_a_parenthesis_is_printed(self):
        foot = {"mr:1124-x-et-socii": [{"mark": "1", "after": "x", "text": "Quorum nomina: Dominicus Nguyen Van (Doan) Xuyen."}]}
        self.assertEqual(ep.validate({"mr:1124-x-et-socii": [{"name": "Dominicus Nguyen Van Xuyen", "where": {"footnote": 1}}]},
                                     foot, {"mr:1124-x-et-socii"}), [])


class RenderTest(unittest.TestCase):
    def test_json_shape(self):
        import json
        doc = json.loads(ep.render_json({"mr:0101-basilius": [{"name": "Basilius", "where": "text"}]}))
        self.assertIn("$comment", doc)
        self.assertEqual(doc["editions"]["martyrologium_romanum_2004"]["mr:0101-basilius"][0]["name"], "Basilius")


class FirstRunFindingsTest(unittest.TestCase):
    """Found by the first run on the 2004 texts."""

    def test_a_name_never_opens_with_a_particle(self):
        names, skipped = pt.footnote_names(
            "Quorum nomina: Ioannes Fictus, e Congregatione Missionis; Paulus Alter, e Societate Iesu.")
        self.assertEqual(names, ["Ioannes Fictus", "Paulus Alter"])
        self.assertEqual(skipped, [])

    def test_a_religious_name_run_into_a_genitive_name_is_reported(self):
        lex = {pt.name_key(w): w for w in ["Teresia", "Sancto", "Augustino", "Maria", "Magdalena", "Rosa"]}
        names, uncertain = pt.text_companions(
            "Arausióne, beatárum Teresiæ a Sancto Augustíno Maríæ Magdalénæ Lidoine et Rosæ, vírginum.", lex)
        self.assertEqual(names, ["Rosa"])
        self.assertEqual(uncertain, ["Teresia a Sancto Augustino Maríæ"])

    def test_hebrew_names_decline_too(self):
        lex = {pt.name_key(w): w for w in ["Michael", "Samuel", "Simeon", "David", "Leo"]}
        self.assertEqual(pt.nominative("Michaélis", lex), "Michael")
        self.assertEqual(pt.nominative("Samuélis", lex), "Samuel")
        self.assertEqual(pt.nominative("Simeónis", lex), "Simeon")
        self.assertEqual(pt.nominative("Davídis", lex), "David")
        self.assertEqual(pt.nominative("Leónis", lex), "Leo")

    def test_an_unknown_genitive_after_a_particle_is_reported(self):
        lex = {pt.name_key(w): w for w in ["Maria", "Columna", "Martinez", "Ioannes", "Brito"]}
        names, uncertain = pt.text_companions(
            "Valéntiæ, beatárum Maríæ a Columna Iacóbæ Martinez et Ioánnis de Brito, mártyrum.", lex)
        self.assertEqual(names, ["Ioannes de Brito"])
        self.assertEqual(uncertain, ["Maria a Columna Iacóbæ"])

    def test_a_footnote_name_printed_in_the_genitive_is_reported(self):
        names, skipped = pt.footnote_names(
            "Quarum nomina: Teresiæ Henricæ ab Annuntiatione Faurie, Mariæ; Anna Rosa.")
        self.assertEqual(names, ["Anna Rosa"])
        self.assertEqual(skipped, ["Teresiæ Henricæ ab Annuntiatione Faurie", "Mariæ"])

    def test_a_descriptor_after_a_comma_starts_no_name_in_the_text(self):
        lex = {pt.name_key(w): w for w in ["Michael", "Carvalho", "Petrus"]}
        names, _ = pt.text_companions("Nagasákii, beatórum Michaélis Carvalho, e Societáte Iesu, et Petri.", lex)
        self.assertEqual(names, ["Michael Carvalho", "Petrus"])

    def test_groups_named_by_a_number_or_plurimi_name_no_one(self):
        self.assertEqual(pt.subject_names("mr:0205-plurimi-martyres-ponti", "Sancti Plurimi Martyres Ponti"), [])
        self.assertEqual(pt.subject_names("mr:0220-quinque-martyres-tyri", "Sancti Quinque Martyres Tyri"), [])
        self.assertEqual(pt.subject_names("mr:0814-octingenti-martyres-hydrunti", "Sancti Octingenti Martyres Hydrunti"), [])
        self.assertEqual(pt.subject_names("mr:0407-ducenti-milites-martyres-sinopes",
                                          "Sancti Ducenti Milites Martyres Sinopes"), [])

    def test_the_declined_nominative_wins_over_a_known_genitive(self):
        lex = {pt.name_key(w): w for w in ["Maria", "Mariae", "Franciscus", "Francisci"]}
        self.assertEqual(pt.nominative("Maríæ", lex), "Maria")
        self.assertEqual(pt.nominative("Francísci", lex), "Franciscus")

    def test_an_uncertain_word_drops_its_whole_name_and_known_words_keep_their_spelling(self):
        lex = {pt.name_key(w): w for w in ["Teresia", "Sancto", "Augustino", "Maria", "Anna"]}
        names, uncertain = pt.text_companions(
            "Compéndii, sanctárum Teresiæ a Sancto Augustíno, Fictiánæ Secúndæ et Maríæ Annæ, vírginum.", lex)
        self.assertEqual(names, ["Teresia a Sancto Augustino", "Maria Anna"])
        self.assertEqual(uncertain, ["Fictiánæ"])


class ReviewFindingsTest(unittest.TestCase):
    """Found by the final review on the real data; each a name written wrong, twice, or not at all."""

    # 1: a name the read breaks off is reported, never written half; a genitive in -ae is ambiguous
    def test_a_name_broken_off_is_reported_not_written(self):
        lex = {pt.name_key(w): w for w in ["Richardus", "Iulianus", "Xystus", "Ioannes", "Cornelius"]}
        names, uncertain = pt.text_companions("Valéntiæ, beatórum Richárdi de los Ríos Fabregat et Iuliáni, mártyrum.", lex)
        self.assertEqual(names, ["Richardus de los Ríos Fabregat", "Iulianus"])
        names, uncertain = pt.text_companions("Romæ, sanctórum Xysti papæ Secúndi et sociórum.", lex)
        self.assertEqual(names, [])
        self.assertEqual(uncertain, ["Xystus"])

    def test_andreae_is_ambiguous_between_andrea_and_andreas(self):
        lex = {pt.name_key(w): w for w in ["Andrea", "Andreas"]}
        self.assertIsNone(pt.nominative("Andréæ", lex))

    # 2: "a Iesu et Maria" is one religious name; shared surnames are reported
    def test_et_inside_a_religious_name_does_not_split(self):
        names, _ = pt.footnote_names("Quarum nomina: Maria Raymunda a Iesu et Maria Kukolowicz, Anna Rosa.")
        self.assertEqual(names, ["Maria Raymunda a Iesu et Maria Kukolowicz", "Anna Rosa"])

    def test_two_religious_names_joined_by_et_are_two_persons(self):
        names, _ = pt.footnote_names(
            "Quorum nomina: Thomas a Sancto Hyacintho et Antonius a Sancto Dominico, Maria Daniela a Iesu et Maria Immaculata Jozwik.")
        self.assertEqual(names, ["Thomas a Sancto Hyacintho", "Antonius a Sancto Dominico",
                                 "Maria Daniela a Iesu et Maria Immaculata Jozwik"])

    def test_first_names_sharing_a_surname_are_reported(self):
        names, skipped = pt.footnote_names(
            "Quarum nomina: Ioanna, Magdalena et Petrina Sailland d'Espinatz, sorores; Maria et Renata Grillard; Anna Rosa.")
        self.assertEqual(names, ["Anna Rosa"])
        self.assertEqual(skipped, ["Ioanna", "Magdalena et Petrina Sailland d'Espinatz", "Maria et Renata Grillard"])

    # 3: groups, and a singular honorific never splits
    def test_more_groups_and_singular_subjects(self):
        self.assertEqual(pt.subject_names("mr:1216-plurimae-virgines-africa", "Sanctae Plurimae Virgines Africa"), [])
        self.assertEqual(pt.subject_names("mr:0630-protomartyres-sanctae-romanae-ecclesiae",
                                          "Sancti Protomartyres Sanctae Romanae Ecclesiae"), [])
        self.assertEqual(pt.subject_names("mr:0724-modestinus-a-iesu-et-maria", "Beatus Modestinus a Iesu et Maria"),
                         ["Modestinus a Iesu et Maria"])
        self.assertEqual(pt.subject_names("mr:1229-david-rex-et-propheta", "Sanctus David Rex et Propheta"), ["David"])

    # 5: descriptors before a name, parentheses inside it, descriptors between names in the text
    def test_a_name_after_a_leading_descriptor_is_read(self):
        names, _ = pt.footnote_names(
            "Quorum nomina: sancti episcopi Aloysius Versiglia, presbyteri Caesidius Giacomantonio, "
            "necnon Maria a Pace, atque Agatha Lin; filii eius Dominicus, religiosi e Societate Iesu.")
        self.assertEqual(names, ["Aloysius Versiglia", "Caesidius Giacomantonio", "Maria a Pace", "Agatha Lin", "Dominicus"])

    def test_parentheses_do_not_cut_a_name(self):
        names, _ = pt.footnote_names("Quorum nomina: Dominicus Nguyen Van (Doan) Xuyen, Maria (Clara) Nanetti.")
        self.assertEqual(names, ["Dominicus Nguyen Van Xuyen", "Maria Nanetti"])

    def test_a_singular_descriptor_between_names_in_the_text_is_skipped(self):
        lex = {pt.name_key(w): w for w in ["Thomas", "Bosgrave", "Patricius", "Salmon"]}
        names, _ = pt.text_companions("Dorcestriæ, beatórum Thomæ Bosgrave, presbýteri, et Patrícii Salmon, mártyrum.", lex)
        self.assertEqual(names, ["Thomas Bosgrave", "Patricius Salmon"])

    # 7: the report never quotes the print
    def test_the_report_quotes_no_printed_form(self):
        import extract_persons as ep
        report = ep.render_report({"mr:0101-x-et-socii": [{"name": "X", "where": "text"}]},
                                  {"mr:0101-x-et-socii": {"uncertain": ["Accúrsii"], "skipped": ["beatæ Teresiæ"],
                                                          "socii_without_names": True}})
        self.assertNotIn("Accúrsii", report)
        self.assertNotIn("Teresiæ", report)
        self.assertIn("mr:0101-x-et-socii", report)


class SamePersonTest(unittest.TestCase):
    # 4: a fuller or shorter form of a subject is the same person, in the subject's form
    def test_a_footnote_name_extending_a_subject_is_not_added(self):
        import extract_persons as ep
        foot = [{"mark": "1", "after": "x", "text": "Quarum nomina: Rosalia Clotildis a Sancta Pelagia Bes, Anna Rosa."}]
        persons, _ = ep.eulogy_persons("mr:0711-rosalia-clotildis-a-sancta-pelagia-et-socii",
                                       "Beatae Rosalia Clotildis a Sancta Pelagia et sociae", "…", foot, {}, {})
        self.assertEqual([p["name"] for p in persons], ["Rosalia Clotildis a Sancta Pelagia", "Anna Rosa"])


class RepeatedNamesTest(unittest.TestCase):
    """Persons who share a name in one eulogy (2026-10-10 spec)."""

    def test_person_key(self):
        self.assertEqual(pt.person_key({"name": "Felix", "where": "text"}), "Felix")
        self.assertEqual(pt.person_key({"name": "Felix", "n": 2, "where": "text"}), "Felix#2")
        self.assertIsNone(pt.person_key({"kind": "place"}))

    def test_a_name_after_alius_or_adhuc_is_read(self):
        names, skipped = pt.footnote_names(
            "Quorum nomina: Felix; alius Felix, Emeritus; Rogatianus, alius Rogatianus, adhuc Rogatianus alius, "
            "Iulia altera.")
        self.assertEqual(names, ["Felix", "Felix", "Emeritus", "Rogatianus", "Rogatianus", "Rogatianus", "Iulia"])
        self.assertEqual(skipped, [])

    def test_every_occurrence_in_one_footnote_list_is_a_person(self):
        import extract_persons as ep
        foot = [{"mark": "1", "after": "x", "text":
                 "Quorum nomina: Felix, Secunda; alius Felix, Rogatus; Felix, Secunda."}]
        persons, _ = ep.eulogy_persons("mr:0212-x-et-socii", "", "…", foot, {}, {})  # no subject: footnote only
        self.assertEqual(persons, [
            {"name": "Felix", "where": {"footnote": 1}},
            {"name": "Secunda", "where": {"footnote": 1}},
            {"name": "Felix", "n": 2, "where": {"footnote": 1}},
            {"name": "Rogatus", "where": {"footnote": 1}},
            {"name": "Felix", "n": 3, "where": {"footnote": 1}},
            {"name": "Secunda", "n": 2, "where": {"footnote": 1}},
        ])
        self.assertEqual([list(p) for p in persons][2], ["name", "n", "where"])

    def test_a_subject_named_again_in_a_footnote_is_one_person(self):
        import extract_persons as ep
        foot = [{"mark": "1", "after": "x", "text": "Quorum nomina: Paulus Miki, Thomas."},
                {"mark": "2", "after": "y", "text": "Quorum nomina: Thomas, Paulus Miki."}]
        persons, _ = ep.eulogy_persons("mr:0206-paulus-miki-et-socii", "Sancti Paulus Miki et socii", "…",
                                       foot, {}, {})
        self.assertEqual(persons, [{"name": "Paulus Miki", "where": "text"},
                                   {"name": "Thomas", "where": {"footnote": 1}}])

    def test_a_repeat_in_a_footnote_list_is_another_person_even_when_the_name_was_listed_before(self):
        import extract_persons as ep
        # The subject Felix, named again in the footnote list, then "alius Felix": another person.
        foot = [{"mark": "1", "after": "x", "text": "Quorum nomina: Felix, Victor, alius Felix."}]
        persons, _ = ep.eulogy_persons("mr:0101-felix-et-socii", "Sancti Felix et socii", "…", foot, {}, {})
        self.assertEqual(persons, [{"name": "Felix", "where": "text"}, {"name": "Victor", "where": {"footnote": 1}},
                                   {"name": "Felix", "n": 2, "where": {"footnote": 1}}])
        # Felix in footnote 1, then "Felix, alius Felix" in footnote 2: the first is him again, the second another.
        foot = [{"mark": "1", "after": "x", "text": "Quorum nomina: Felix."},
                {"mark": "2", "after": "y", "text": "Quorum nomina: Felix, alius Felix."}]
        persons, _ = ep.eulogy_persons("mr:0101-x-et-socii", "", "…", foot, {}, {})
        self.assertEqual(persons, [{"name": "Felix", "where": {"footnote": 1}},
                                   {"name": "Felix", "n": 2, "where": {"footnote": 2}}])

    def test_a_name_printed_twice_in_a_row_without_alius_counts_once_and_is_reported(self):
        twice = []
        names, skipped = pt.footnote_names("Quorum nomina: Dominicus Toai, Emmanuel Le Phung, Emmanuel Le Phung, "
                                           "Felix; alius Felix, Rogatianus, Rogatianus alius.", printed_twice=twice)
        self.assertEqual(names, ["Dominicus Toai", "Emmanuel Le Phung", "Felix", "Felix", "Rogatianus", "Rogatianus"])
        self.assertEqual((skipped, twice), ([], ["Emmanuel Le Phung"]))

    def test_a_marked_repeat_in_the_text_is_read_and_marked(self):
        lex = {pt.name_key(w): w for w in ["Theodorus", "Ioannes", "Petrus"]}
        marked = []
        names, uncertain = pt.text_companions(
            "Hierosólymæ, sanctórum Theodóri, Theodóri alteríus, Ioánnis, Ioánnis alteríus et Petri, mártyrum.",
            lex, marked=marked)
        self.assertEqual((names, uncertain), (["Theodorus", "Theodorus", "Ioannes", "Ioannes", "Petrus"], []))
        self.assertEqual(marked, [1, 3])

    def test_a_marked_repeat_in_the_text_is_another_person(self):
        import extract_persons as ep
        lex = {pt.name_key(w): w for w in ["Callinicus", "Theodorus", "Ioannes"]}
        persons, issues = ep.eulogy_persons(
            "mr:1106-callinicus-et-socii", "Sancti Callinicus et socii",
            "Hierosólymæ, sanctórum Calliníci, Theodóri, Theodóri alteríus et Ioánnis, mártyrum.", [], lex, {})
        self.assertEqual(persons, [{"name": "Callinicus", "where": "text"}, {"name": "Theodorus", "where": "text"},
                                   {"name": "Theodorus", "n": 2, "where": "text"}, {"name": "Ioannes", "where": "text"}])
        self.assertEqual(issues["printed_twice"], [])

    def test_a_name_printed_twice_is_an_issue_for_the_report(self):
        import extract_persons as ep
        foot = [{"mark": "1", "after": "x", "text": "Quorum nomina: Emmanuel Le Phung, Emmanuel Le Phung, Felix."}]
        persons, issues = ep.eulogy_persons("mr:1124-x-et-socii", "", "…", foot, {}, {})
        self.assertEqual([p["name"] for p in persons], ["Emmanuel Le Phung", "Felix"])
        self.assertEqual(issues["printed_twice"], ["Emmanuel Le Phung"])
        report = ep.render_report({"mr:1124-x-et-socii": persons}, {"mr:1124-x-et-socii": issues}, noted=set())
        self.assertIn("mr:1124-x-et-socii: Emmanuel Le Phung (needs a curator note)", report)
        report = ep.render_report({"mr:1124-x-et-socii": persons}, {"mr:1124-x-et-socii": issues},
                                  noted={"mr:1124-x-et-socii"})
        self.assertIn("mr:1124-x-et-socii: Emmanuel Le Phung (noted)", report)

    def test_the_numbering_of_a_name_is_checked(self):
        import extract_persons as ep
        foot = {"mr:0212-x": [{"mark": "1", "after": "x", "text": "Quorum nomina: Felix; alius Felix; Felix."}]}

        def errors(persons):
            return ep.validate({"mr:0212-x": persons}, foot, {"mr:0212-x"})

        f1 = {"name": "Felix", "where": {"footnote": 1}}
        self.assertEqual(errors([f1, dict(f1, n=2), dict(f1, n=3)]), [])
        self.assertTrue(errors([f1, dict(f1, n=3)]))                 # a gap
        self.assertTrue(errors([f1, dict(f1, n=2), dict(f1, n=2)]))  # a duplicate
        self.assertTrue(errors([dict(f1, n=1)]))                     # n is written only from 2
        self.assertTrue(errors([f1, dict(f1, n="2")]))               # not an integer
        self.assertTrue(errors([f1, dict(f1, n=True)]))              # nor a boolean
        self.assertTrue(errors([dict(f1, name="Felix#2")]))          # # is the key's separator


if __name__ == "__main__":
    unittest.main()
