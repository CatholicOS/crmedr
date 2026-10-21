import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import gazetteer_jev as gj  # noqa: E402
import mentions_jev as mj  # noqa: E402

OP = {"op": "resolve_place", "id": "place:tyburni", "la": "Tybúrni", "it": ["Tyburn"], "occurrences": ["mr:0101-a"],
      "candidates": [
          {"wikidata": "Q1", "label": "Tyburn", "description": "place in London", "country": "GB",
           "countries": ["GB"], "la": "Tiburnum", "p9314": None, "coords": [51.5, -0.16],
           "types": ["Q486972"], "evidence": []},
          {"wikidata": "Q2", "label": "Tyburn stream", "description": "stream", "country": None,
           "countries": [], "la": None, "p9314": None, "coords": [51.5, -0.15],
           "types": ["Q47521"], "evidence": []}]}


def choice(option, p, confidence=0.9):
    return {"type": "choice", "choice": option, "probabilities": {option: p}, "confidence": confidence}


def answers(pick, kind, p):
    return {"pick": choice(pick, p), "kind": choice(kind, 0.95)}


class ClauseTest(unittest.TestCase):
    def test_latin_clause_holds_the_phrase(self):
        text = "Romæ, sancti X. Tybúrni in Anglia, beati Y, presbyteri."
        self.assertEqual(gj.latin_clause(text, "Tybúrni"), "Tybúrni in Anglia, beati Y, presbyteri.")

    def test_latin_clause_folded_match(self):
        self.assertIn("Tyburni", gj.latin_clause("Primo. Tyburni in Anglia, beati Y.", "Tybúrni"))

    def test_latin_clause_falls_back_to_the_first_sentence(self):
        self.assertEqual(gj.latin_clause("Primo. Secundo.", "Nusquam"), "Primo.")
        self.assertEqual(gj.latin_clause("", "Nusquam"), "")

    def test_long_sentence_windows_around_the_phrase(self):
        exact = gj.latin_clause("Romae " * 100 + "Tybúrni in Anglia", "Tybúrni")
        self.assertLessEqual(len(exact), 400)
        self.assertIn("Tybúrni", exact)
        folded = gj.latin_clause("Romæ " * 100 + "Tæburni in Anglia", "Taeburni")
        self.assertLessEqual(len(folded), 400)
        self.assertIn("Tæburni", folded)

    def test_english_clause_names_a_candidate_or_italian_head(self):
        en = "At Rome, Saint X. At Tyburn in London, Blessed Y, priest."
        self.assertEqual(gj.english_clause(en, OP), "At Tyburn in London, Blessed Y, priest.")
        self.assertEqual(gj.english_clause("Primo. Secundo.", OP), "Primo.")
        self.assertEqual(gj.english_clause("", OP), "")


    def test_english_clause_matches_whole_words_only(self):
        op = dict(OP, it=[], candidates=[{"wikidata": "Q9", "label": "Ur"}])
        en = "Primo. Saint Murray suffered. At Ur in Chaldea, Abraham."
        self.assertEqual(gj.english_clause(en, op), "At Ur in Chaldea, Abraham.")

    def test_english_clause_window_keeps_the_place_name(self):
        en = "Saint X " + "and companions " * 40 + "suffered at Tyburn in London."
        clause = gj.english_clause(en, OP)
        self.assertLessEqual(len(clause), 400)
        self.assertIn("Tyburn", clause)


class RequestTest(unittest.TestCase):
    def test_candidate_fields_sent(self):
        sent = gj.place_request(OP, "", "")["state"]["candidates"]["c0"]
        self.assertEqual(set(sent), {"wikidata", "label", "description", "country", "la", "p9314"})

    def test_request_shape(self):
        body = gj.place_request(OP, "la clause", "en clause")
        self.assertEqual(body["model"], mj.MODEL)
        self.assertEqual(set(body["questions"]), {"kind", "pick"})
        self.assertEqual(list(body["questions"]["pick"]["criteria"]), ["c0", "c1", "none"])
        self.assertNotIn("coords", json.dumps(body["state"]))
        self.assertEqual(body["state"]["candidates"]["c0"]["wikidata"], "Q1")

    def test_request_without_candidates_asks_kind_only(self):
        self.assertEqual(set(gj.place_request(dict(OP, candidates=[]), "", "")["questions"]), {"kind"})


class SuggestionTest(unittest.TestCase):
    def test_pick_default_is_accept(self):
        s = gj.place_suggestion(OP, answers("c0", "place", 0.93))
        self.assertEqual((s["decision"], s["wikidata"], s["country"], s["kind"]), ("accept", "Q1", "GB", "place"))

    def test_pick_default_is_suggested_when_present(self):
        op = dict(OP, suggested={"wikidata": "Q2"})
        self.assertEqual(gj.place_suggestion(op, answers("c1", "place", 0.8))["decision"], "accept")

    def test_pick_other_is_edit_without_country(self):
        s = gj.place_suggestion(OP, answers("c1", "place", 0.8))
        self.assertEqual((s["decision"], s["wikidata"]), ("edit", "Q2"))
        self.assertNotIn("country", s)

    def test_none_is_reject(self):
        s = gj.place_suggestion(OP, answers("none", "place", 0.7))
        self.assertEqual((s["decision"], s["reason"]), ("reject", gj.NONE_REASON))

    def test_non_place_kind_is_reject_with_its_reason(self):
        s = gj.place_suggestion(OP, answers("c0", "people", 0.9))
        self.assertEqual((s["decision"], s["reason"], s["kind"]), ("reject", gj.KIND_REASONS["people"], "people"))
        self.assertEqual(s["probability"], 0.95)

    def test_kind_only_place_has_no_decision(self):
        s = gj.place_suggestion(dict(OP, candidates=[]), {"kind": choice("place", 0.88)})
        self.assertEqual((s["kind"], s["probability"]), ("place", 0.88))
        self.assertNotIn("decision", s)

    def test_kind_only_people_is_reject(self):
        s = gj.place_suggestion(dict(OP, candidates=[]), {"kind": choice("people", 0.9)})
        self.assertEqual((s["decision"], s["reason"]), ("reject", gj.KIND_REASONS["people"]))

    def test_unknown_option_is_none(self):
        self.assertIsNone(gj.place_suggestion(OP, answers("c9", "place", 0.9)))


if __name__ == "__main__":
    unittest.main()


class PickConventionTest(unittest.TestCase):
    def test_pick_question_carries_the_curators_convention(self):
        text = gj.place_request(OP, "la clause", "en clause")["questions"]["pick"]["instructions"]
        for phrase in ("as it is today", "a separate site from today's town", "names a building",
                       "historical territory", "the near place is not that other one"):
            self.assertIn(phrase, text)
        self.assertNotIn("same spot (", text)
