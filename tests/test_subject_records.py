import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import subject_records as sr  # noqa: E402
from body_places import half_month  # noqa: E402

# Invented Latin, not the 2004 text: only the two cited forms are real.
TEXT = "Memoria Eugéndi, viri sancti, qui abbátis Condatiscénsis munus gessit."


def rec(**kw):
    return {"id": "mr:0101-eugendus", "name": "Eugendus", "kind": "person", "surname": None,
            "feminine": False, "roles": [{"role": "abbas", "printed": "abbátis", "occurrence": 0}],
            "places": [{"kind": "monastery", "printed": "Condatiscénsis", "occurrence": 0,
                        "grammar": "adjective-person", "nominative": "Condatiscum",
                        "adjective": "condatiscensis", "en": "Condat", "it": "Condat"}],
            "cognomen": None, "relations": [], "death_year": None, "role_en": "abbot", "role_it": "abate", **kw}


class CheckRecord(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(sr.check_record(rec(), TEXT), [])

    def test_genitive_is_optional(self):
        r = rec()
        r["places"][0]["genitive"] = None
        self.assertEqual(sr.check_record(r, TEXT), [])

    def test_printed_not_in_text(self):
        r = rec()
        r["places"][0]["printed"] = "Condatisci"
        self.assertIn("places[0]: printed form not in the text", sr.check_record(r, TEXT))

    def test_occurrence_out_of_range(self):
        r = rec()
        r["places"][0]["occurrence"] = 1  # "Condatiscénsis" occurs once
        self.assertIn("places[0]: occurrence 1 of 1", sr.check_record(r, TEXT))

    def test_role_form_mismatch(self):
        r = rec()
        r["roles"][0]["role"] = "episcopus"
        self.assertIn("roles[0]: abbátis is not a form of episcopus", sr.check_record(r, TEXT))

    def test_bad_enums(self):
        r = rec(kind="saint")
        r["places"][0]["grammar"] = "adjective"
        errs = sr.check_record(r, TEXT)
        self.assertIn("kind: saint", errs)
        self.assertIn("places[0]: grammar adjective", errs)

    def test_adjective_required_for_adjective_grammar(self):
        r = rec()
        r["places"][0]["adjective"] = None
        self.assertIn("places[0]: adjective missing", sr.check_record(r, TEXT))

    def test_adjective_stem_must_match_printed(self):
        r = rec()
        r["places"][0]["adjective"] = "pictaviensis"
        self.assertIn("places[0]: adjective pictaviensis does not match Condatiscénsis",
                      sr.check_record(r, TEXT))

    def test_role_forms_cover_cleric_roles(self):
        self.assertTrue(set(sr.CLERIC_ROLES) <= set(sr.ROLE_FORMS))
        self.assertIn("abbatem", sr.ROLE_FORMS["abbas"])


    def test_non_object_roles_and_places_are_reported(self):
        errs = sr.check_record(rec(roles=["abbas"], places=[None]), TEXT)
        self.assertIn("roles[0]: not an object", errs)
        self.assertIn("places[0]: not an object", errs)
        self.assertIn("roles: not a list", sr.check_record(rec(roles="abbas"), TEXT))


class Persons(unittest.TestCase):
    PERSONS = [{"name": "Eugendus"}, {"name": "Maria"}, {"name": "Maria", "n": 2}]

    def test_the_name_must_be_a_person_of_the_eulogy(self):
        self.assertEqual(sr.person_errors(rec(), self.PERSONS), [])
        self.assertEqual(sr.person_errors(rec(name="Lupicinus"), self.PERSONS),
                         ["name: Lupicinus is not a person of this eulogy in data/persons.json"])
        self.assertEqual(sr.person_errors(rec(name="Maria", n=2), self.PERSONS), [])
        self.assertEqual(sr.person_errors(rec(name="Maria", n=3), self.PERSONS),
                         ["n: Maria#3 is not a person of this eulogy in data/persons.json"])

    def test_person_record(self):
        first, second = rec(name="Maria", death_year=300), rec(name="Maria", n=2, death_year=304)
        self.assertIs(sr.person_record([first, second], "Maria", 2), second)
        self.assertIs(sr.person_record([second, first], "Maria"), first)
        self.assertEqual(sr.person_record([rec()], "Lupicinus"),
                         {"id": "mr:0101-eugendus", "name": "Lupicinus", "kind": "person"})
        self.assertIsNone(sr.person_record([first, second], "Lupicinus"))
        self.assertIsNone(sr.person_record([], "Lupicinus"))


    def test_check_records_reports_malformed_entries(self):
        texts, persons = {"mr:0101-eugendus": TEXT}, {"mr:0101-eugendus": [{"name": "Eugendus"}]}
        lines = sr.check_records([rec(), "x", rec(id=["mr:0101-eugendus"]), rec(id="mr:0101-nemo")], texts, persons)
        self.assertEqual(lines, ["records[1]: not an object", "['mr:0101-eugendus'] [Eugendus]: id: no such eulogy",
                                 "mr:0101-nemo [Eugendus]: id: no such eulogy"])

    def test_check_records_reports_a_second_record_of_the_same_person(self):
        texts = {"mr:0101-eugendus": TEXT}
        persons = {"mr:0101-eugendus": [{"name": "Eugendus"}, {"name": "Eugendus", "n": 2}]}
        lines = sr.check_records([rec(), rec(n=2), rec()], texts, persons)
        self.assertEqual(lines, ["mr:0101-eugendus [Eugendus]: a second record of Eugendus"])

    def test_n_null_is_the_first_person(self):
        self.assertEqual(sr.person_key({"name": "Eugendus", "n": None}), "Eugendus")


class Brief(unittest.TestCase):
    def test_half_month(self):
        entries = [{"id": "mr:0101-a"}, {"id": "mr:0101-b", "same_eulogy": ["mr:0202-b"]},
                   {"id": "mr:0116-c"}, {"id": "mr:0101-old", "deprecated": True}]
        texts = {"mr:0101-a": "A", "mr:0101-b": "B", "mr:0116-c": "C"}
        items = {"mr:0101-a": {"Aus": {"wikidata": "Q1", "status": "auto"}, "Bus": {"status": "unresolved"}}}
        out = sr.brief(*half_month("01", "a"), texts, {"mr:0101-a": "IT"}, {}, {"mr:0101-a": [{"name": "Aus"}]},
                       {"mr:0101-a": "Sanctus A"}, entries, items)
        self.assertEqual([o["id"] for o in out], ["mr:0101-a", "mr:0101-b"])
        self.assertEqual(out[0]["la_text"], "A")
        self.assertEqual(out[0]["it_text"], "IT")
        self.assertEqual(out[0]["person_items"], {"Aus": items["mr:0101-a"]["Aus"]})
        self.assertEqual(out[0]["subject_la"], "Sanctus A")
        self.assertEqual(out[1]["same_eulogy"], ["mr:0202-b"])
        self.assertEqual(out[1]["person_items"], {})


if __name__ == "__main__":
    unittest.main()
