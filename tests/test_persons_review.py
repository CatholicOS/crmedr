import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import persons_review as pr  # noqa: E402
import persons_text as pt  # noqa: E402

LEXICON = {pt.name_key(w): w for w in ["Berardus", "Otho", "Petrus", "Thomas", "Thoma", "Alexander", "Victor"]}
LA = ("Apud urbem Maróchium in Mauretánia, pássio sanctórum mártyrum Berárdi, Othónis, Petri, presbyterórum, "
      "Accúrsii et Adiúti, religiosórum, ex Ordine Minórum.")
IT = ("Presso la città di Marrakesch nell’odierno Marocco, passione dei santi martiri Berardo, Ottone, Pietro, "
      "sacerdoti, Accorsio e Adiuto, religiosi, dell’Ordine dei Minori.")


class GuessesTest(unittest.TestCase):
    def test_a_genitive_gives_its_possible_nominatives_without_stress_accents(self):
        self.assertEqual(pr.guesses("Accúrsii", {}, Counter())[0], "Accursius")
        self.assertEqual(pr.guesses("Adiúti", {}, Counter())[:2], ["Adiutus", "Adiutius"])
        self.assertIn("Capito", pr.guesses("Capitónis", {}, Counter()))

    def test_third_declension_genitives(self):
        self.assertEqual(pr.guesses("Felicitátis", {}, Counter())[0], "Felicitas")
        self.assertEqual(pr.guesses("Audífacis", {}, Counter())[0], "Audifax")
        self.assertEqual(pr.guesses("Victóris", {}, Counter())[0], "Victor")

    def test_a_second_declension_name_in_er_after_a_consonant_only(self):
        self.assertEqual(pr.guesses("Alexándri", LEXICON, Counter())[0], "Alexander")
        self.assertEqual(pr.guesses("Alexándri", {}, Counter())[0], "Alexander")
        self.assertEqual(pr.guesses("Agathodóri", {}, Counter())[0], "Agathodorus")
        self.assertNotIn("Agathodoer", pr.guesses("Agathodóri", {}, Counter()))

    def test_a_genitive_in_idis_is_first_read_in_is(self):
        self.assertEqual(pr.guesses("Páusidis", {}, Counter())[0], "Pausis")

    def test_of_two_known_names_the_commoner_first(self):
        self.assertEqual(pr.guesses("Thomæ", LEXICON, Counter({"Thomas": 40, "Thoma": 1}))[:2], ["Thomas", "Thoma"])

    def test_a_word_with_no_genitive_ending_is_kept_as_printed(self):
        self.assertEqual(pr.guesses("Ménard", {}, Counter()), ["Ménard"])


class ItalianFormTest(unittest.TestCase):
    def test_the_italian_word_the_name_begins_like(self):
        self.assertEqual(pr.italian_form("Accursius", IT), "Accorsio")
        self.assertEqual(pr.italian_form("Adiutus", IT), "Adiuto")

    def test_spelling_differences_are_read_through(self):
        self.assertEqual(pr.italian_form("Phlegon", "dei santi Asincrito, Flegonte ed Erme"), "Flegonte")

    def test_of_two_words_alike_the_one_most_like_the_whole_name(self):
        self.assertEqual(pr.italian_form("Victor", "dei santi Vittorino, Vittore, Niceforo"), "Vittore")

    def test_no_word_alike_gives_none(self):
        self.assertIsNone(pr.italian_form("Accursius", "dei santi Berardo e Ottone"))


class DraftTest(unittest.TestCase):
    def test_the_list_read_on_past_the_unknown_names_with_their_italian_forms(self):
        op = pr.draft_op("mr:0116-berardus-et-socii", "Sancti Berardus et socii", LA, IT, LEXICON, Counter())
        self.assertEqual(op["op"], "set_persons")
        self.assertEqual(op["uid"], "persons:mr:0116-berardus-et-socii")
        self.assertEqual(op["current"], ["Berardus", "Otho", "Petrus"])
        self.assertEqual(op["unread"], ["Accúrsii", "Adiúti"])
        self.assertEqual([(p["name"], p.get("it")) for p in op["persons"]],
                         [("Berardus", None), ("Otho", None), ("Petrus", None), ("Accursius", "Accorsio"),
                          ("Adiutus", "Adiuto")])
        self.assertEqual(op["persons"][3]["printed"], "Accúrsii")
        self.assertEqual(op["persons"][3]["alternatives"], [])  # "-ii": only -ius
        self.assertEqual(op["persons"][4]["alternatives"], ["Adiutius"])
        self.assertEqual(op["context"], {"la": LA, "it": IT})
        self.assertIsNone(op["decision"])

    def test_a_eulogy_read_in_full_has_no_card(self):
        self.assertIsNone(pr.draft_op("mr:0101-x-et-socii", "Sancti Berardus et socii",
                                      "Romæ, sanctórum Berárdi et Petri, mártyrum.", "", LEXICON, Counter()))


class ApplyTest(unittest.TestCase):
    OP = {"op": "set_persons", "uid": "persons:mr:0116-b-et-socii", "id": "mr:0116-b-et-socii",
          "persons": [{"name": "Berardus"}, {"name": "Accursius", "it": "Accorsio", "printed": "Accúrsii",
                                             "alternatives": ["Accursus"]}]}
    PERSONS = {"mr:0116-b-et-socii": [{"name": "Berardus", "where": "text"},
                                       {"name": "Paulus", "where": {"footnote": 1}}]}

    def test_an_accepted_list_replaces_the_text_persons_and_keeps_the_footnotes(self):
        cs = {"schema": "crmedr-changeset/v1", "operations": [dict(self.OP, decision="accept")]}
        curated, n = pr.apply_decisions(cs, {"$comment": "c"}, self.PERSONS)
        self.assertEqual(n, 1)
        self.assertEqual(curated["mr:0116-b-et-socii"],
                         [{"name": "Berardus", "where": "text"}, {"name": "Accursius", "where": "text", "it": "Accorsio"},
                          {"name": "Paulus", "where": {"footnote": 1}}])
        self.assertEqual(curated["$comment"], "c")

    def test_an_edited_list_numbers_a_name_given_twice(self):
        edited = {"persons": [{"name": "Serenus"}, {"name": "Serenus"}, {"name": "Accursius", "it": ""}]}
        cs = {"schema": "crmedr-changeset/v1", "operations": [dict(self.OP, decision="edit", edited=edited)]}
        curated, _ = pr.apply_decisions(cs, {}, {})
        self.assertEqual(curated["mr:0116-b-et-socii"],
                         [{"name": "Serenus", "where": "text"}, {"name": "Serenus", "n": 2, "where": "text"},
                          {"name": "Accursius", "where": "text"}])

    def test_an_edit_keeps_the_other_names_of_a_drafted_person(self):
        op = dict(self.OP, persons=[{"name": "Marina", "also": ["Margarita"]}], decision="edit",
                  edited={"persons": [{"name": "Marina"}, {"name": "Petrus"}]})
        curated, _ = pr.apply_decisions({"schema": "crmedr-changeset/v1", "operations": [op]}, {}, {})
        self.assertEqual(curated["mr:0116-b-et-socii"],
                         [{"name": "Marina", "also": ["Margarita"], "where": "text"}, {"name": "Petrus", "where": "text"}])

    def test_a_rejected_or_undecided_card_changes_nothing(self):
        cs = {"schema": "crmedr-changeset/v1",
              "operations": [dict(self.OP, decision="reject"), dict(self.OP, decision=None, uid="x")]}
        self.assertEqual(pr.apply_decisions(cs, {}, self.PERSONS), ({}, 0))

    def test_an_edit_with_no_persons_is_an_error(self):
        cs = {"schema": "crmedr-changeset/v1",
              "operations": [dict(self.OP, decision="edit", edited={"persons": [{"name": " "}]})]}
        with self.assertRaises(ValueError):
            pr.apply_decisions(cs, {}, {})


if __name__ == "__main__":
    unittest.main()
