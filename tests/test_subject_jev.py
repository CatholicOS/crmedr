import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import mentions_jev as mj  # noqa: E402
import subject_jev as sj  # noqa: E402

LA = ("In monasterio Condatiscensi in Iura, sancti Eugéndi, abbátis Condatiscénsis, qui vitam duxit austeram; "
      "obiit senex. Item commemoratio aliorum.")
EUGENDUS = {"id": "mr:0101-eugendus", "name": "Eugendus", "kind": "person", "feminine": False, "surname": None,
            "roles": [{"role": "abbas", "printed": "abbátis", "occurrence": 0}],
            "places": [{"kind": "monastery", "grammar": "adjective-person", "printed": "Condatiscénsis",
                        "occurrence": 0, "nominative": "Condatiscum", "genitive": None,
                        "adjective": "Condatiscensis", "en": "Condat", "it": "Condat"}]}
OP = {"op": "rename", "id": "mr:0101-eugendus", "new_id": "mr:0101-eugendus-abbas-condatiscensis",
      "uid": "subject:mr:0101-eugendus", "class": "role-place", "confidence": "medium",
      "candidates": [
          {"new_id": "mr:0101-eugendus-abbas-condatiscensis", "category": "role-place", "weak": False,
           "labels": {"la": "Sanctus Eugendus abbas Condatiscensis", "en": "Saint Eugendus, abbot of Condat",
                      "it": "Sant’Eugendo, abate di Condat"}, "basis": "text", "certain": True},
          {"new_id": "mr:0101-eugendus-condatiscensis", "category": "place-adjective", "weak": False,
           "labels": {"la": "Sanctus Eugendus Condatiscensis", "en": "Saint Eugendus of Condat",
                      "it": "Sant’Eugendo di Condat"}, "basis": "text", "certain": True}],
      "reasoning": "", "subject_la": "Sanctus Eugendus", "decision": None}
PICK_C0 = {"type": "choice", "choice": "c0", "probabilities": {"c0": 0.95, "c1": 0.05}, "confidence": 0.9}

POP = {"op": "resolve_person", "id": "mr:0101-eugendus|Eugendus", "eulogy": "mr:0101-eugendus", "day": "01-01",
       "typology": "dies_natalis", "name": "Eugendus", "companions": ["Lupicinus"],
       "candidates": [
           {"wikidata": "Q1", "label": "Eugendus", "description": "abbot", "names": ["Eugendus"], "human": True,
            "statuses": ["Q43115"], "born": "", "died": "0510-01-01", "feast": "", "source": "search",
            "evidence": ["human", "status", "name", "death"]},
           {"wikidata": "Q2", "label": "Oyend", "description": "saint", "names": [], "human": True,
            "statuses": ["Q43115"], "born": "", "died": "", "feast": "", "source": "relatives",
            "evidence": ["human", "status"]}],
       "decision": None, "edited": None}
KIND_PERSON = {"type": "choice", "choice": "person", "probabilities": {"person": 0.97}, "confidence": 0.95}


def item(choice, p=0.92):
    return {"type": "choice", "choice": choice, "probabilities": {choice: p}, "confidence": 0.9}


class ClauseTest(unittest.TestCase):
    def test_the_sentence_holding_the_first_cited_form(self):
        self.assertEqual(sj.clause(LA, EUGENDUS),
                         "In monasterio Condatiscensi in Iura, sancti Eugéndi, abbátis Condatiscénsis, "
                         "qui vitam duxit austeram;")

    def test_without_cited_forms_the_sentence_of_the_name(self):
        record = dict(EUGENDUS, roles=[], places=[])
        self.assertTrue(sj.clause(LA, record).startswith("In monasterio"))
        self.assertEqual(sj.clause("Primo. Item sancti Eugendi.", record), "Item sancti Eugendi.")

    def test_at_most_400_characters_around_the_form(self):
        text = "x " * 300 + "abbátis Condatiscénsis " + "y " * 300 + "."
        out = sj.clause(text, EUGENDUS)
        self.assertLessEqual(len(out), 400)
        self.assertIn("abbátis", out)

    def test_vernacular_clause(self):
        en = "At Rome, Saint Peter. In the monastery of Condat, Saint Eugendus, abbot; he lived austerely."
        self.assertEqual(sj.vernacular_clause(en, "Saint Eugendus", "", "Sant’Eugendo"),
                         "In the monastery of Condat, Saint Eugendus, abbot;")
        self.assertEqual(sj.vernacular_clause("", "Saint Eugendus", "A Condat, sant’Eugendo, abate.", "Sant’Eugendo"),
                         "A Condat, sant’Eugendo, abate.")
        self.assertEqual(sj.vernacular_clause("Nothing here.", "Saint Eugendus", "", None), "")


class RenameRequestTest(unittest.TestCase):
    def test_rename_request_shape(self):
        body = sj.rename_request(OP, EUGENDUS, "…sancti Eugéndi, abbátis Condatiscénsis…", "")
        self.assertEqual(body["model"], mj.MODEL)
        self.assertEqual(body["questions"]["pick"]["type"], "choice")
        self.assertEqual(set(body["questions"]["pick"]["criteria"]), {"c0", "c1"})
        self.assertEqual(len(body["questions"]["clarity_c0"]["criteria"]), 4)
        self.assertNotIn("la_text", json.dumps(body))           # only the clause is sent
        self.assertEqual(set(body["questions"]), {"place_grammar_0", "field_roles_0", "field_places_0",
                                                  "clarity_c0", "clarity_c1", "pick"})
        self.assertEqual(set(body["questions"]["place_grammar_0"]["criteria"]),
                         {"adjective-person", "adjective-noun", "locative", "genitive", "ablative"})
        self.assertEqual(body["questions"]["field_places_0"]["type"], "noul")
        self.assertIn("`record.places[0].nominative`", body["questions"]["field_places_0"]["instructions"])
        self.assertIn("monastery", body["questions"]["field_places_0"]["instructions"])
        self.assertIn("`record.roles[0].role`", body["questions"]["field_roles_0"]["instructions"])
        self.assertEqual(body["state"]["candidates"]["c1"]["new_id"], "mr:0101-eugendus-condatiscensis")
        # The record's own grammar label is not sent: Jev answers the place grammar unprompted.
        self.assertNotIn("grammar", body["state"]["record"]["places"][0])


class RenameSuggestionTest(unittest.TestCase):
    def test_accept(self):
        s = sj.rename_suggestion(OP, {"pick": PICK_C0, "field_places_0": {"type": "noul", "noul": 0.9}})
        self.assertEqual((s["decision"], s["probability"], s["model"]), ("accept", 0.95, mj.MODEL))
        self.assertNotIn("new_id", s)

    def test_edit_suggestion(self):
        s = sj.rename_suggestion(OP, {"pick": {"type": "choice", "choice": "c1", "probabilities": {"c1": 0.93}, "confidence": 0.9},
                                      "field_places_0": {"type": "noul", "noul": 0.97}})
        self.assertEqual((s["decision"], s["new_id"]), ("edit", OP["candidates"][1]["new_id"]))

    def test_record_flag_blocks(self):
        answers = {"pick": PICK_C0, "field_places_0": {"type": "noul", "noul": 0.2}}
        self.assertIsNone(sj.rename_suggestion(OP, answers))
        self.assertEqual(sj.record_flags(answers), ["record:places[0]"])

    def test_unknown_pick_ignored(self):
        self.assertIsNone(sj.rename_suggestion(OP, {"pick": item("c7")}))
        self.assertIsNone(sj.rename_suggestion(OP, {}))

    def test_clarity_scores_by_new_id(self):
        answers = {"pick": PICK_C0, "clarity_c0": {"type": "score", "score": 3, "probabilities": {"3": 0.8}},
                   "clarity_c1": {"type": "score", "score": 1, "probabilities": {"1": 0.6}}}
        s = sj.rename_suggestion(OP, answers)
        self.assertEqual(s["scores"], {"mr:0101-eugendus-abbas-condatiscensis": 3,
                                       "mr:0101-eugendus-condatiscensis": 1})
        del answers["clarity_c1"]
        self.assertEqual(sj.clarity_scores(OP, answers), {"mr:0101-eugendus-abbas-condatiscensis": 3})

    def test_a_grammar_disagreement_is_flagged_without_blocking(self):
        answers = {"pick": PICK_C0, "place_grammar_0": item("locative", 0.8)}
        s = sj.rename_suggestion(OP, answers, record=EUGENDUS)
        self.assertEqual((s["decision"], s["flags"]), ("accept", ["grammar:places[0]:locative"]))


class PersonRequestTest(unittest.TestCase):
    def test_person_request_shape(self):
        body = sj.person_request(POP, EUGENDUS, "sancti Eugéndi, abbátis", [{"name": "Lupicinus", "wikidata": "Q9"}])
        self.assertEqual(body["model"], mj.MODEL)
        self.assertEqual(set(body["questions"]["item"]["criteria"]), {"q0", "q1", "none"})
        self.assertEqual(set(body["questions"]["kind"]["criteria"]),
                         {"person", "celebration_or_title", "anonymous_group", "not_identifiable"})
        self.assertEqual(body["state"]["candidates"]["q1"]["wikidata"], "Q2")
        self.assertEqual(body["state"]["companions"], [{"name": "Lupicinus", "wikidata": "Q9"}])

    def test_without_a_record(self):
        body = sj.person_request(POP, None, "sancti Eugéndi", [])
        self.assertNotIn("record", body["state"])


class PersonSuggestionTest(unittest.TestCase):
    def test_preselected_is_what_an_accept_applies(self):
        self.assertEqual(sj.preselected(POP), "Q1")  # candidates[0], as _resolve applies an accept
        self.assertEqual(sj.preselected(dict(POP, suggested={"wikidata": "Q2"})), "Q2")
        self.assertIsNone(sj.preselected(dict(POP, candidates=[])))

    def test_accept_and_edit_carry_the_item(self):
        s = sj.person_suggestion(POP, {"item": item("q0"), "kind": KIND_PERSON})
        self.assertEqual((s["decision"], s["wikidata"], s["source"], s["probability"]),
                         ("accept", "Q1", "search", 0.92))
        s = sj.person_suggestion(POP, {"item": item("q1"), "kind": KIND_PERSON})
        self.assertEqual((s["decision"], s["wikidata"], s["source"]), ("edit", "Q2", "relatives"))

    def test_the_first_passing_candidate_is_not_preselected(self):
        # candidates[0] fails a rule and candidates[1] passes them all: an accept applies
        # candidates[0], so picking the passing one is an edit.
        op = dict(POP, candidates=[dict(POP["candidates"][0], wikidata="Q5", evidence=["human"]),
                                   dict(POP["candidates"][1], evidence=["human", "status", "name", "death"])])
        s = sj.person_suggestion(op, {"item": item("q1"), "kind": KIND_PERSON})
        self.assertEqual((s["decision"], s["wikidata"]), ("edit", "Q2"))
        s = sj.person_suggestion(op, {"item": item("q0"), "kind": KIND_PERSON})
        self.assertEqual((s["decision"], s["wikidata"]), ("accept", "Q5"))

    def test_suggested_is_what_an_accept_applies(self):
        op = dict(POP, suggested={"wikidata": "Q2"})
        self.assertEqual(sj.person_suggestion(op, {"item": item("q1"), "kind": KIND_PERSON})["decision"], "accept")
        self.assertEqual(sj.person_suggestion(op, {"item": item("q0"), "kind": KIND_PERSON})["decision"], "edit")

    def test_an_item_for_a_name_read_as_no_person_is_flagged(self):
        title = item("celebration_or_title", 0.9)
        s = sj.person_suggestion(POP, {"item": item("q0"), "kind": title})
        self.assertEqual((s["decision"], s["wikidata"], s["flags"]), ("accept", "Q1", ["kind:celebration_or_title"]))
        self.assertNotIn("flags", sj.person_suggestion(POP, {"item": item("q0"), "kind": KIND_PERSON}))
        self.assertNotIn("flags", sj.person_suggestion(POP, {"item": item("none"), "kind": title}))

    def test_unknown_pick_ignored(self):
        self.assertIsNone(sj.person_suggestion(POP, {"item": {"type": "choice", "choice": "q9", "probabilities": {"q9": 1}, "confidence": 1},
                                                      "kind": KIND_PERSON}))

    def test_none_is_reject(self):
        s = sj.person_suggestion(POP, {"item": item("none", 0.96), "kind": KIND_PERSON})
        self.assertEqual((s["decision"], s["probability"]), ("reject", 0.96))
        self.assertTrue(s["reason"])

    def test_not_identifiable_is_reject(self):
        s = sj.person_suggestion(POP, {"item": item("q0"), "kind": item("not_identifiable", 0.91)})
        self.assertEqual((s["decision"], s["probability"], s["kind"]), ("reject", 0.91, "not_identifiable"))


if __name__ == "__main__":
    unittest.main()
