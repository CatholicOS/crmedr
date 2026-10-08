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
        self.assertEqual(issues, {"uncertain": [], "skipped": [], "socii_without_names": False})

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


if __name__ == "__main__":
    unittest.main()
