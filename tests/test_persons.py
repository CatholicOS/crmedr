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


if __name__ == "__main__":
    unittest.main()
