import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import extract_mentions as em  # noqa: E402
import mentions_italian as mi  # noqa: E402

LA = {
    "mr:0102-argeus-et-socii": "Sancti Argeus, Narcissus et Marcellinus",
    "mr:0131-ioannes-bosco": "Sanctus Ioannes Bosco",
    "mr:0319-ioseph": "Sanctus Ioseph",
    "mr:0601-iosephus-gomez": "Beatus Iosephus Gomez",
    "mr:0514-iusta-et-heredina": "Sanctae Iusta et Heredina",
}
IT = {
    "mr:0102-argeus-et-socii": "Santi Argeo, Narciso e Marcellino",
    "mr:0131-ioannes-bosco": "San Giovanni Bosco",
    "mr:0319-ioseph": "San Giuseppe",
    "mr:0601-iosephus-gomez": "Beato Giuseppe Gomez",
    "mr:0514-iusta-et-heredina": "Sante Giusta ed Eredina",
}


class SubjectNamesTest(unittest.TestCase):
    def test_the_names_a_subject_lists(self):
        self.assertEqual(mi.subject_names("Santi Argeo, Narciso e Marcellino", "it"), ["Argeo", "Narciso", "Marcellino"])
        self.assertEqual(mi.subject_names("Sant’Almachio", "it"), ["Almachio"])
        self.assertEqual(mi.subject_names("Sante Giusta ed Eredina", "it"), ["Giusta", "Eredina"])
        self.assertEqual(mi.subject_names("Santi Paolo Miki e compagni", "it"), ["Paolo Miki"])
        self.assertEqual(mi.subject_names("Sancti Paulus Miki et socii", "la"), ["Paulus Miki"])


class ItalianNamesTest(unittest.TestCase):
    names = mi.ItalianNames(LA, IT)

    def test_a_person_named_in_the_subject_has_the_italian_subject_form_first(self):
        self.assertEqual(self.names.forms("mr:0102-argeus-et-socii", "Narcissus")[0], "Narciso")
        self.assertEqual(self.names.forms("mr:0514-iusta-et-heredina", "Heredina")[0], "Eredina")

    def test_leading_words_are_translated_and_the_rest_kept_as_printed(self):
        # Iosephus → Giuseppe and Ioannes → Giovanni are learned from the pairs; the surname is kept.
        self.assertEqual(self.names.forms("mr:0101-x", "Iosephus Ioannes Bosco"),
                         ["Giuseppe Giovanni Bosco", "Giuseppe Ioannes Bosco", "Iosephus Ioannes Bosco"])

    def test_the_untranslated_ends_a_surname_search_anchors_on(self):
        self.assertEqual(self.names.surname("Iosephus Maria Gomez"), ["Maria Gomez", "Gomez"])
        self.assertEqual(self.names.surname("Ioannes"), [])


class RunsTest(unittest.TestCase):
    def test_name_runs_hold_particles_and_a_parenthesis(self):
        t = ("I loro nomi sono: santi Girolamo da Weert, Teodorico van der Eem, Pietro d’Assche e "
             "Cornelio de Wijck; Maria Anna (Maria Amandina) Giuliani, vergine.")
        self.assertEqual([t[a:b] for a, b in mi.runs(t)],
                         ["I", "Girolamo da Weert", "Teodorico van der Eem", "Pietro d’Assche", "Cornelio de Wijck",
                          "Maria Anna (Maria Amandina) Giuliani"])

    def test_a_surname_match_is_widened_to_its_list_item(self):
        t = "beati Germano di Gesù e Maria Osés Sainz, sacerdote"
        span = mi.surname_span(t, ["Osés Sáinz"], [], ["Germano"])
        self.assertEqual(t[span[0]:span[1]], "Germano di Gesù e Maria Osés Sainz")

    def test_position_pairs_a_gap_with_as_many_free_names(self):
        t = "santi Zaccaria, Vezio Epagato, Ottobre, Filomeno"
        found = {0: (6, 14), 3: (41, 49)}
        self.assertEqual({i: t[a:b] for i, (a, b) in mi.by_position(t, [0, 1, 2, 3], found, list(found.values())).items()},
                         {1: "Vezio Epagato", 2: "Ottobre"})

    def test_position_proposes_nothing_when_the_counts_differ(self):
        t = "santi Zaccaria, Vezio Epagato, Ottobre, Filomeno"
        found = {0: (6, 14), 3: (41, 49)}
        self.assertEqual(mi.by_position(t, [0, 1, 3], {0: (6, 14), 2: (41, 49)}, list(found.values())), {})


class ItalianEulogyTest(unittest.TestCase):
    names = mi.ItalianNames(LA, IT)

    def italian(self, mrid, persons, text, notes=(), rank=None):
        ps = em.italian_persons({mrid: persons}, self.names, rank or {}, {})[mrid]
        return em.eulogy_mentions(text, list(notes), [], ps, lang="it", place_qid=lambda la: None,
                                  person_qid=lambda key: None)

    def test_persons_are_marked_under_their_italian_forms_with_their_latin_names(self):
        text = "Nel territorio di Cori, santi Argéo, Narciso e Marcellino, martiri."
        ms, review, _ = self.italian("mr:0102-argeus-et-socii", [
            {"name": n, "where": "text"} for n in ("Argeus", "Narcissus", "Marcellinus")], text)
        self.assertEqual([(m["name"], m["form"]) for m in ms],
                         [("Argeus", "Argéo"), ("Narcissus", "Narciso"), ("Marcellinus", "Marcellino")])
        self.assertEqual(review, [])

    def test_a_byname_printed_apart_is_marked_by_the_given_name(self):
        names = mi.ItalianNames({"mr:0107-canutus-lavard": "Sanctus Canutus Lavard"},
                                {"mr:0107-canutus-lavard": "San Canuto Lavard"})
        ps = em.italian_persons({"mr:0107-canutus-lavard": [{"name": "Canutus Lavard", "where": "text"}]}, names, {}, {})
        ms, _, hows = em.eulogy_mentions("Presso Ringsted, san Canuto, detto Lavard: duca.", [], [],
                                         ps["mr:0107-canutus-lavard"], lang="it", place_qid=lambda la: None,
                                         person_qid=lambda key: None)
        self.assertEqual([m["form"] for m in ms], ["Canuto"])
        self.assertIn(("person", True, "given name"), hows)

    def test_a_list_name_not_found_is_proposed_by_its_place_in_the_list(self):
        mrid = "mr:0602-pothinus-et-socii"
        persons = [{"name": n, "where": {"footnote": 1}} for n in ("Zacharias", "October", "Philomenus")]
        latin = {mrid: [{"kind": "person", "name": n, "where": {"footnote": 1}, "start": i}
                        for i, n in enumerate(("Zacharias", "October", "Philomenus"))]}
        names = mi.ItalianNames({"mr:0101-a": "Sancti Zacharias et Philomenus"}, {"mr:0101-a": "Santi Zaccaria e Filomeno"})
        ps = em.italian_persons({mrid: persons}, names, latin, {})[mrid]
        note = "I loro nomi sono: santi Zaccaria, Ottobre, Filomeno."
        ms, review, _ = em.eulogy_mentions("Testo.", [note], [], ps, lang="it", place_qid=lambda la: None,
                                           person_qid=lambda key: None)
        self.assertEqual([m["form"] for m in ms], ["Zaccaria", "Filomeno"])
        self.assertEqual([(r["name"], r["form"]) for r in review], [("October", "Ottobre")])
        self.assertIn("its place in the list", review[0]["reasoning"])


if __name__ == "__main__":
    unittest.main()
