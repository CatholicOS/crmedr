import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import subject_records as sr  # noqa: E402
from body_places import half_month  # noqa: E402

TEXT = "In monastério Condatiscénsi in Gállia, sancti Eugéndi, abbátis Condatiscénsis, ..."


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


class Brief(unittest.TestCase):
    def test_half_month(self):
        entries = [{"id": "mr:0101-a"}, {"id": "mr:0101-b", "same_eulogy": ["mr:0202-b"]},
                   {"id": "mr:0116-c"}, {"id": "mr:0101-old", "deprecated": True}]
        texts = {"mr:0101-a": "A", "mr:0101-b": "B", "mr:0116-c": "C"}
        items = {"mr:0101-a": {"Aus": {"wikidata": "Q1", "status": "auto"}}}
        out = sr.brief(*half_month("01", "a"), texts, {"mr:0101-a": "IT"}, {}, {"mr:0101-a": [{"name": "Aus"}]},
                       {"mr:0101-a": "Sanctus A"}, entries, items)
        self.assertEqual([o["id"] for o in out], ["mr:0101-a", "mr:0101-b"])
        self.assertEqual(out[0]["la_text"], "A")
        self.assertEqual(out[0]["it_text"], "IT")
        self.assertEqual(out[0]["person_items"], items["mr:0101-a"])
        self.assertEqual(out[0]["subject_la"], "Sanctus A")
        self.assertEqual(out[1]["same_eulogy"], ["mr:0202-b"])
        self.assertEqual(out[1]["person_items"], {})


if __name__ == "__main__":
    unittest.main()
