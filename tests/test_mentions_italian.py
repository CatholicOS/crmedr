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

    def test_a_curated_italian_form_comes_first(self):
        # Accursius is no subject: the Italian Accorsio comes from data/persons_curated.json.
        names = mi.ItalianNames(LA, IT, {"mr:0116-b-et-socii": {"Accursius": "Accorsio"}})
        self.assertEqual(names.forms("mr:0116-b-et-socii", "Accursius")[0], "Accorsio")
        self.assertEqual(names.forms("mr:0116-b-et-socii", "Adiutus"), ["Adiutus"])

    def test_the_curated_italian_forms_of_the_persons(self):
        curated = {"$comment": "x", "mr:0116-b-et-socii": [{"name": "Berardus", "where": "text"},
                                                            {"name": "Accursius", "where": "text", "it": "Accorsio"}]}
        self.assertEqual(mi.curated_forms(curated), {"mr:0116-b-et-socii": {"Accursius": "Accorsio"}})

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

    def test_a_run_goes_on_over_the_e_of_gesu_e_maria(self):
        # "di Gesù e Maria" is one religious name (or one institution's), never two names.
        t = "beati Modestino di Gesù e Maria (Nemo) Fictor e Pietro Nemo, sacerdoti."
        self.assertEqual([t[a:b] for a, b in mi.runs(t)], ["Modestino di Gesù e Maria (Nemo) Fictor", "Pietro Nemo"])

    def test_runs_go_on_over_elided_and_long_particles(self):
        t = ("I loro nomi sono: beate Eufrasia dell’Immacolata Concezione (Maria) Nemo, Maria dello Spirito "
             "Santo (Angelica) Fictor, religiose dell’Ordine dei Frati Minori.")
        self.assertEqual([t[a:b] for a, b in mi.runs(t)],
                         ["I", "Eufrasia dell’Immacolata Concezione (Maria) Nemo",
                          "Maria dello Spirito Santo (Angelica) Fictor", "Frati Minori"])

    def test_a_surname_match_that_opens_its_item_is_not_widened_over_the_one_before(self):
        t = "beate Maria della Pace (Anna) Nemo, Maria di Gesù (Irma) Fictor, vergini"
        span = mi.surname_span(t, ["Fictor"], [], ["Maria"])
        self.assertEqual(t[span[0]:span[1]], "Maria di Gesù (Irma) Fictor")
        t = "beate Maria Luisa (Anna) Nemo e Maria Agostina (Rosa) Fictor, vergini"
        span = mi.surname_span(t, ["Fictor"], [], ["Maria"])
        self.assertEqual(t[span[0]:span[1]], "Maria Agostina (Rosa) Fictor")

    def test_a_surname_match_is_widened_to_its_list_item(self):
        t = "beati Germano di Gesù e Maria Osés Sainz, sacerdote"
        span = mi.surname_span(t, ["Osés Sáinz"], [], ["Germano"], joined=True)  # "Germanus a Iesu et Maria"
        self.assertEqual(t[span[0]:span[1]], "Germano di Gesù e Maria Osés Sainz")

    def test_position_pairs_a_gap_with_as_many_free_names(self):
        t = "santi Zaccaria, Vezio Epagato, Ottobre, Filomeno"
        found = {0: (6, 14), 3: (41, 49)}
        self.assertEqual({i: t[a:b] for i, (a, b) in mi.by_position(t, [0, 1, 2, 3], found, list(found.values())).items()},
                         {1: "Vezio Epagato", 2: "Ottobre"})

    def test_position_pairs_by_given_name_when_the_counts_differ(self):
        # More name runs than persons ("Frati Minori"): each person takes the next run that opens with
        # one of their given names, in order.
        t = "beati Domenico da Nemo, dell’Ordine dei Frati Minori; Tommaso di San Fictor e Lucia Luisa; Giovanni Tomachi"
        found = {3: (t.index("Giovanni"), len(t))}
        given = [["Domenico"], ["Tommaso"], ["Lucia"], ["Giovanni"]]
        self.assertEqual({i: t[a:b] for i, (a, b) in mi.by_position(t, [0, 1, 2, 3], found, list(found.values()),
                                                                     given).items()},
                         {0: "Domenico da Nemo", 1: "Tommaso di San Fictor", 2: "Lucia Luisa"})

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


    def test_a_list_name_is_looked_for_between_its_found_neighbours(self):
        # A list prints its persons in the Latin order: the sons Domenico and Tommaso take the words
        # printed after their father, never the first Domenico of the list, and no repeat is proposed
        # as the same person (in a list it is another one).
        mrid = "mr:0908-a-et-socii"
        names = mi.ItalianNames(
            {"mr:0101-a": "Sancti Dominicus, Thomas, Ioannes Tomachi et Ludovicus Higashi"},
            {"mr:0101-a": "Santi Domenico, Tommaso, Giovanni Tomachi e Ludovico Higashi"})
        order = [("Dominicus de Nagasakio", None), ("Ioannes Tomachi", None), ("Dominicus", None),
                 ("Thomas", None), ("Ludovicus Higashi", None), ("Dominicus", 2)]
        persons = [{"name": n, **({"n": k} if k else {}), "where": {"footnote": 1}} for n, k in order]
        latin = {mrid: [{"kind": "person", "name": n, **({"n": k} if k else {}), "where": {"footnote": 1}, "start": i}
                        for i, (n, k) in enumerate(order)]}
        ps = em.italian_persons({mrid: persons}, names, latin, {})[mrid]
        note = ("I loro nomi sono: beati Domenico da Nagasaki, religioso; Giovanni Tomachi e i suoi figli "
                "Domenico e Tommaso; Ludovico Higashi e suo figlio Domenico.")
        ms, review, _ = em.eulogy_mentions("Testo.", [note], [], ps, lang="it", place_qid=lambda la: None,
                                           person_qid=lambda key: None)
        at = {(m["name"], m.get("n")): m["start"] for m in ms}
        self.assertEqual(at[("Dominicus", None)], note.index("Domenico e Tommaso"))
        self.assertEqual(at[("Thomas", None)], note.index("Tommaso;"))
        self.assertEqual(at[("Dominicus", 2)], note.rindex("Domenico"))
        self.assertEqual([(r["name"], r["form"]) for r in review], [("Dominicus de Nagasakio", "Domenico da Nagasaki")])
        self.assertIn("its place in the list", review[0]["reasoning"])

    def test_a_religious_name_is_widened_over_the_secular_name_and_surname_after_it(self):
        # The Italian subject gives the religious name alone ("Amata di Gesù"); the text prints the
        # secular name and the surname after it, which belong to the mark.
        mrid = "mr:0716-maria-rosa-de-gordon-et-socii"
        names = mi.ItalianNames({mrid: "Beatae Maria Rosa de Gordon et socii"}, {mrid: "Beate Amata di Gesù e compagne"})
        ps = em.italian_persons({mrid: [{"name": "Maria Rosa de Gordon", "where": "text"}]}, names, {}, {})[mrid]
        for text, form in (("A Orange, beate Amata di Gesù (Maria Rosa) de Gordon e sei compagne, vergini.",
                            "Amata di Gesù (Maria Rosa) de Gordon"),
                           ("A Orange, beate Amata di Gesù (Anna) Fictor e sei compagne, vergini.", "Amata di Gesù"),
                           # an honorific before the run is never taken in
                           ("A Orange, Santa Amata di Gesù (Maria Rosa) de Gordon, vergine.",
                            "Amata di Gesù (Maria Rosa) de Gordon")):
            ms, _, _ = em.eulogy_mentions(text, [], [], ps, lang="it", place_qid=lambda la: None,
                                          person_qid=lambda key: None)
            self.assertEqual([m["form"] for m in ms], [form])

    def test_a_secular_name_found_in_its_parenthesis_is_widened_to_the_whole_name(self):
        mrid = "mr:0723-a-et-socii"
        names = mi.ItalianNames({"mr:0101-a": "Sanctus Emmanuel"}, {"mr:0101-a": "Sant’Emanuele"})
        ps = em.italian_persons({mrid: [{"name": "Emmanuel Perez Gimenez", "where": "text"}]}, names, {}, {})[mrid]
        for text, form in (("Presso Nemo, beati Alfonso (Emanuele) Pérez Giménez, sacerdote, e compagni.",
                            "Alfonso (Emanuele) Pérez Giménez"),
                           ("Presso Nemo, beati Germano di Gesù e Maria (Emanuele) Pérez Giménez, sacerdote.",
                            "Germano di Gesù e Maria (Emanuele) Pérez Giménez")):
            ms, _, _ = em.eulogy_mentions(text, [], [], ps, lang="it", place_qid=lambda la: None,
                                          person_qid=lambda key: None)
            self.assertEqual([m["form"] for m in ms], [form])

    def test_a_misprinted_name_is_found_as_printed(self):
        mrid = "mr:0602-a-et-socii"
        names = mi.ItalianNames({"mr:0101-a": "Sanctae Æmilia et Potamia"}, {"mr:0101-a": "Sante Emilia e Potamia"})
        order = [("Æmilia", None), ("Potamia", None), ("Æmilia", 2)]
        persons = [{"name": n, **({"n": k} if k else {}), "where": {"footnote": 1}} for n, k in order]
        latin = {mrid: [{"kind": "person", "name": n, **({"n": k} if k else {}), "where": {"footnote": 1}, "start": i}
                        for i, (n, k) in enumerate(order)]}
        misprints = [{"id": mrid, "edition": "martyrologium_romanum_2004_it_IT", "footnote": 1,
                      "printed": "Emillia", "intended": "Emilia"}]
        ps = em.italian_persons({mrid: persons}, names, latin, {}, misprints)[mrid]
        note = "I loro nomi sono: sante Emillia, Potamia, un’altra Emilia."
        ms, review, _ = em.eulogy_mentions("Testo.", [note], [], ps, lang="it", place_qid=lambda la: None,
                                           person_qid=lambda key: None)
        self.assertEqual([(m["name"], m.get("n"), m["form"]) for m in ms],
                         [("Æmilia", None, "Emillia"), ("Potamia", None, "Potamia"), ("Æmilia", 2, "Emilia")])
        self.assertEqual(review, [])


if __name__ == "__main__":
    unittest.main()
