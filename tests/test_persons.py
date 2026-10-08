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


if __name__ == "__main__":
    unittest.main()
