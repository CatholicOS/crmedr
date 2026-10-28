import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import name_forms as nf  # noqa: E402


def persons(*names):
    return [{"name": n, "where": "text"} for n in names]


class PairsTest(unittest.TestCase):
    def test_the_first_names_pair_when_the_other_words_agree(self):
        self.assertEqual(nf.first_name_pair("Ioannes Speed", "Saint John Speed"), ("ioannes", "John"))
        self.assertEqual(nf.first_name_pair("Ioannes Speed", "Saint John Smith"), None)
        self.assertEqual(nf.first_name_pair("Ioannes Theophanes Venard", "Saint John Theophane Vénard"), None)

    def test_a_group_subject_gives_its_first_person(self):
        self.assertEqual(nf.first_name_pair("Paulus Miki", "Saints Paul Miki and companions"), ("paulus", "Paul"))
        self.assertEqual(nf.first_name_pair("Paulus Miki", "Santi Paolo Miki e compagni"), ("paulus", "Paolo"))

    def test_an_elided_italian_title(self):
        self.assertEqual(nf.first_name_pair("Alphonsus Rodriguez", "Sant’Alfonso Rodriguez"), ("alphonsus", "Alfonso"))

    def test_one_word_names_give_no_pair(self):
        self.assertIsNone(nf.first_name_pair("Ioannes", "Saint John"))


class HarvestTest(unittest.TestCase):
    PERSONS = {"mr:1": persons("Ioannes Speed"), "mr:2": persons("Ioannes Larke"), "mr:3": persons("Amata Lopez"),
               "mr:4": persons("Martha Wang"), "mr:5": persons("Martha Ruiz"), "mr:6": [{"name": "Petrus Ruiz",
                                                                                        "where": {"footnote": 1}}]}
    EN = {"mr:1": "Saint John Speed", "mr:2": "Saint John Larke", "mr:3": "Blessed Martha Lopez",
          "mr:4": "Saint Martha Wang", "mr:5": "Blessed Martha Ruiz", "mr:6": "Saint Peter Ruiz"}

    def test_forms_by_count_and_another_names_form_seen_once_dropped(self):
        forms = nf.harvest(self.PERSONS, {"en": self.EN, "it": {}})
        self.assertEqual(forms["ioannes"], {"en": [["John", 2]]})
        # A religious name (Amata, called Martha): Martha is another Latin first name.
        self.assertNotIn("amata", forms)
        # A footnote name is no subject.
        self.assertNotIn("petrus", forms)

    def test_a_form_seen_twice_is_kept_though_another_names(self):
        persons_ = dict(self.PERSONS, **{"mr:7": persons("Amata Diaz")})
        forms = nf.harvest(persons_, {"en": dict(self.EN, **{"mr:7": "Blessed Martha Diaz"}), "it": {}})
        self.assertEqual(forms["amata"], {"en": [["Martha", 2]]})

    def test_a_form_seen_once_that_is_another_latin_names_form_is_dropped(self):
        # Angelus, called Benedict in religion: Benedict is Benedictus's.
        forms = nf.harvest({"mr:1": persons("Angelus Rossi"), "mr:2": persons("Benedictus Biscop"),
                            "mr:3": persons("Angelus Bianchi")},
                           {"en": {"mr:1": "Blessed Benedict Rossi", "mr:2": "Saint Benedict Biscop",
                                   "mr:3": "Blessed Angelo Bianchi"}, "it": {}})
        self.assertEqual(forms["angelus"], {"en": [["Angelo", 1]]})
        self.assertEqual(forms["benedictus"], {"en": [["Benedict", 1]]})

    def test_a_form_seen_once_that_is_any_persons_latin_name_is_dropped(self):
        # Franciscus, called Tobias in religion; Catharina, Gertrude; Amata, Marta: Tobias, Gertrudis
        # and Martha are names the Martyrology gives other persons, in a footnote too.
        others = {"mr:9": [{"name": n, "where": {"footnote": 1}} for n in ("Tobias", "Gertrudis", "Martha")]}
        forms = nf.harvest({**others, "mr:1": persons("Franciscus Sanchez"), "mr:2": persons("Catharina Jarrige"),
                            "mr:3": persons("Amata Cerretelli")},
                           {"en": {"mr:1": "Blessed Tobias Sanchez", "mr:2": "Blessed Gertrude Jarrige"},
                            "it": {"mr:3": "Beata Marta Cerretelli"}})
        self.assertEqual(forms, {})

    def test_a_form_like_the_latin_itself_is_left_out(self):
        forms = nf.harvest({"mr:1": persons("Maria Wang")}, {"en": {"mr:1": "Saint Maria Wang"}, "it": {}})
        self.assertNotIn("maria", forms)


if __name__ == "__main__":
    unittest.main()
