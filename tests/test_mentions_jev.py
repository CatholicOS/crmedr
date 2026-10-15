import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import mentions_jev as mj  # noqa: E402

IT = "martyrologium_romanum_2004_it_IT"
FN = {"footnote": 1}


def card(reasoning, name="Pompeia", n=None, form="Pompea", context="santi Potamia, Pompea, Rodana, Biblis",
         context_start=100, start=None, end=None, where=FN):
    op = {"op": "add_mention", "kind": "person", "edition": IT, "eulogy": "mr:0602-x", "where": where,
          "name": name, "form": form, "context": context, "context_start": context_start, "reasoning": reasoning,
          "decision": None, "edited": None}
    if n:
        op["n"] = n
    if form is not None:
        i = context.index(form)
        op["start"], op["end"] = context_start + i, context_start + i + len(form)
    else:
        op["start"] = op["end"] = None
    if start is not None:
        op["start"], op["end"] = start, end
    return op


def mark(name, context, word, context_start=100, n=None, where=FN, kind="person"):
    i = context.index(word)
    m = {"kind": kind, "where": where, "start": context_start + i, "end": context_start + i + len(word), "name": name}
    if n:
        m["n"] = n
    return m


class CardKindTest(unittest.TestCase):
    def test_the_three_kinds_and_the_rest(self):
        self.assertEqual(mj.card_kind(card("Pothinus matched again: mark it if it names this person once more")), "repeat")
        self.assertEqual(mj.card_kind(card("Pompeia was not found by name: proposed by its place in the list")), "position")
        self.assertEqual(mj.card_kind(card("Helpis was not found", form=None)), "not_found")
        self.assertIsNone(mj.card_kind(card("Pompeia is named inside a place phrase, which was kept")))
        self.assertIsNone(mj.card_kind(dict(card("Pompeia was not found"), edition="martyrologium_romanum_2004")))
        self.assertIsNone(mj.card_kind(dict(card("Pompeia was not found"), kind="place")))


class PlacePersonsTest(unittest.TestCase):
    def test_persons_of_the_cards_place_in_latin_print_order(self):
        persons = [{"name": "Rodana", "where": FN}, {"name": "Potamia", "where": FN}, {"name": "Pothinus", "where": "text"},
                   {"name": "Pompeia", "where": FN}, {"name": "Biblis", "where": FN}]
        latin = [{"kind": "person", "where": FN, "name": "Potamia", "start": 5},
                 {"kind": "person", "where": FN, "name": "Pompeia", "start": 9},
                 {"kind": "person", "where": FN, "name": "Rodana", "start": 15}]
        ordered = mj.place_persons(card("x proposed by its place in the list"), persons, latin)
        # Unmarked in the Latin (Biblis) last, in persons.json order.
        self.assertEqual([p["name"] for p in ordered], ["Potamia", "Pompeia", "Rodana", "Biblis"])


class NeighboursTest(unittest.TestCase):
    def test_the_persons_before_and_after_with_their_marked_words_inside_the_context(self):
        op = card("Pompeia was not found by name: proposed by its place in the list")
        ordered = [{"name": "Potamia", "where": FN}, {"name": "Pompeia", "where": FN}, {"name": "Rodana", "where": FN}]
        it_marks = [mark("Potamia", op["context"], "Potamia")]  # Rodana not marked
        self.assertEqual(mj.neighbours(op, ordered, it_marks),
                         {"before": {"latin_name": "Potamia", "marked_as": "Potamia"},
                          "after": {"latin_name": "Rodana", "marked_as": None}})

    def test_a_mark_outside_the_context_is_not_quoted(self):
        op = card("Pompeia was not found by name: proposed by its place in the list")
        ordered = [{"name": "Potamia", "where": FN}, {"name": "Pompeia", "where": FN}]
        far = {"kind": "person", "where": FN, "name": "Potamia", "start": 10, "end": 17}
        self.assertEqual(mj.neighbours(op, ordered, [far])["before"], {"latin_name": "Potamia", "marked_as": None})

    def test_the_first_of_a_list_has_no_before(self):
        op = card("Pompeia was not found by name: proposed by its place in the list")
        self.assertIsNone(mj.neighbours(op, [{"name": "Pompeia", "where": FN}], [])["before"])


class CandidatesTest(unittest.TestCase):
    def test_free_name_runs_of_the_context_in_utf16_eulogy_offsets(self):
        op = card("Pompeia was not found by name: proposed by its place in the list")
        ctx = op["context"]
        it_marks = [mark("Potamia", ctx, "Potamia"), mark("Rodana", ctx, "Rodana")]
        cands = mj.candidates(op, it_marks)
        self.assertEqual([(c["id"], c["words"]) for c in cands], [("c1", "Pompea"), ("c2", "Biblis")])
        self.assertEqual((cands[0]["start"], cands[0]["end"]), (op["start"], op["end"]))
        self.assertEqual(cands[0]["at"], ctx.index("Pompea"))

    def test_the_cards_own_person_does_not_hide_a_candidate(self):
        # A decided card whose decision was applied: Pompeia is marked now, and must stay a candidate.
        op = card("Pompeia was not found by name: proposed by its place in the list")
        it_marks = [mark("Pompeia", op["context"], "Pompea")]
        self.assertIn("Pompea", [c["words"] for c in mj.candidates(op, it_marks)])

    def test_another_n_of_the_same_name_does_hide_it(self):
        op = card("Pompeia was not found by name: proposed by its place in the list", n=2)
        it_marks = [mark("Pompeia", op["context"], "Pompea")]  # the first Pompeia
        self.assertNotIn("Pompea", [c["words"] for c in mj.candidates(op, it_marks)])

    def test_offsets_are_utf16_across_a_non_bmp_character(self):
        ctx = "𝔄 santi Potamia, Pompea"
        op = card("Pompeia was not found by name: proposed by its place in the list", context=ctx, form=None,
                  start=None, end=None)
        cands = mj.candidates(op, [])
        pompea = next(c for c in cands if c["words"] == "Pompea")
        # 𝔄 is two UTF-16 code units: the eulogy offset is one more than the code-point index.
        self.assertEqual(pompea["start"], 100 + ctx.index("Pompea") + 1)
        self.assertEqual(pompea["at"], ctx.index("Pompea"))


if __name__ == "__main__":
    unittest.main()
