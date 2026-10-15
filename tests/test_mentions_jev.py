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


import mentions_italian as mi  # noqa: E402

NAMES = mi.ItalianNames({"mr:0101-a": "Sanctae Pompeia et Potamia"}, {"mr:0101-a": "Sante Pompea e Potamia"})
PERSONS = [{"name": "Potamia", "where": FN}, {"name": "Pompeia", "where": FN}, {"name": "Rodana", "where": FN}]
LATIN = [{"kind": "person", "where": FN, "name": n, "start": i} for i, n in enumerate(["Potamia", "Pompeia", "Rodana"])]


class RequestTest(unittest.TestCase):
    def test_a_span_card_asks_one_choice_over_its_candidates_and_none(self):
        op = card("Pompeia was not found by name: proposed by its place in the list")
        body, cands = mj.request_for(op, PERSONS, LATIN, [mark("Potamia", op["context"], "Potamia")], NAMES)
        self.assertEqual(body["model"], "jev-1.14.0")
        self.assertEqual(list(body["questions"]), ["span"])
        q = body["questions"]["span"]
        self.assertEqual(q["type"], "choice")
        self.assertEqual(list(q["criteria"]), [c["id"] for c in cands] + ["none"])
        state = body["state"]
        self.assertEqual(state["person"], {"latin_name": "Pompeia", "italian_forms": ["Pompea", "Pompeia"]})
        self.assertEqual(state["where"], "footnote 1")
        self.assertEqual(state["proposed"], "Pompea")
        self.assertEqual(state["neighbours"]["before"], {"latin_name": "Potamia", "marked_as": "Potamia"})
        self.assertEqual(state["candidates"], {c["id"]: {"words": c["words"], "at": c["at"]} for c in cands})
        self.assertEqual([p["latin_name"] for p in state["persons_in_this_place"]], ["Potamia", "Pompeia", "Rodana"])

    def test_a_repeat_card_asks_the_identity_choice_without_candidates(self):
        op = card("Pothinus matched again: mark it if it names this person once more", name="Pothinus",
                  form="Potino", context="il nonagenario vescovo Potino rese", where="text")
        body, cands = mj.request_for(op, [{"name": "Pothinus", "where": "text"}], [], [], NAMES)
        self.assertEqual(list(body["questions"]), ["identity"])
        self.assertEqual(list(body["questions"]["identity"]["criteria"]),
                         ["same_person", "another_person", "not_this_person"])
        self.assertNotIn("candidates", body["state"])
        self.assertEqual(cands, [])

    def test_out_of_scope_or_no_candidate_gives_no_request(self):
        self.assertEqual(mj.request_for(card("Pompeia is named inside a place phrase"), PERSONS, LATIN, [], NAMES),
                         (None, []))
        op = card("Helpis was not found", name="Helpis", form=None, context="sono: santi e martiri")
        self.assertEqual(mj.request_for(op, PERSONS, LATIN, [], NAMES), (None, []))


def choice(pick, probabilities, confidence=0.9):
    return {"type": "choice", "choice": pick, "probabilities": probabilities, "confidence": confidence}


class SuggestionTest(unittest.TestCase):
    def setUp(self):
        self.op = card("Pompeia was not found by name: proposed by its place in the list")
        self.cands = mj.candidates(self.op, [mark("Potamia", self.op["context"], "Potamia"),
                                             mark("Rodana", self.op["context"], "Rodana")])

    def test_the_proposed_candidate_is_an_accept(self):
        s = mj.suggestion(self.op, choice("c1", {"c1": 0.93, "c2": 0.05, "none": 0.02}), self.cands, "jev-1.14.0")
        self.assertEqual(s, {"decision": "accept", "probability": 0.93, "confidence": 0.9, "model": "jev-1.14.0"})

    def test_another_candidate_is_an_edit_with_its_span(self):
        s = mj.suggestion(self.op, choice("c2", {"c1": 0.1, "c2": 0.85, "none": 0.05}), self.cands, "jev-1.14.0")
        c2 = self.cands[1]
        self.assertEqual((s["decision"], s["start"], s["end"], s["form"]), ("edit", c2["start"], c2["end"], "Biblis"))

    def test_none_is_a_reject(self):
        s = mj.suggestion(self.op, choice("none", {"c1": 0.1, "c2": 0.1, "none": 0.8}), self.cands, "jev-1.14.0")
        self.assertEqual(s["decision"], "reject")

    def test_repeat_answers(self):
        op = card("Pothinus matched again: mark it if it names this person once more", name="Pothinus",
                  form="Potino", context="vescovo Potino rese", where="text")
        probs = {"same_person": 0.8, "another_person": 0.15, "not_this_person": 0.05}
        self.assertEqual(mj.suggestion(op, choice("same_person", probs), [], "m")["decision"], "accept")
        self.assertEqual(mj.suggestion(op, choice("another_person", probs), [], "m")["decision"], "reject")
        self.assertEqual(mj.suggestion(op, choice("not_this_person", probs), [], "m")["decision"], "reject")

    def test_an_unknown_option_gives_no_suggestion(self):
        self.assertIsNone(mj.suggestion(self.op, choice("c9", {"c9": 1.0}), self.cands, "m"))
        self.assertIsNone(mj.suggestion(self.op, {"type": "noul", "noul": 0.9}, self.cands, "m"))

import json  # noqa: E402
import tempfile  # noqa: E402

BODY = {"model": "jev-1.14.0", "state": {"context": "x"}, "questions": {"span": {"type": "choice"}}}
OK = (200, json.dumps({"model": "jev-1.14.0", "answers": {"span": {"type": "choice"}}}).encode())


class FakePost:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []

    def __call__(self, url, data, key):
        self.calls.append((url, json.loads(data), key))
        return self.responses.pop(0)


class ClientTest(unittest.TestCase):
    def client(self, post, key="sk-secret"):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.slept = []
        return mj.TypeSafe(key, Path(self.tmp.name), post=post, sleep=self.slept.append)

    def test_asks_once_then_reads_the_cache(self):
        post = FakePost(OK)
        ts = self.client(post)
        self.assertEqual(ts.ask(BODY)["model"], "jev-1.14.0")
        self.assertTrue(ts.cached(BODY))
        ts.ask(BODY)
        self.assertEqual(len(post.calls), 1)
        self.assertEqual(post.calls[0][0], "https://api.typesafe.ai/v1/systemone")

    def test_the_cache_key_changes_with_the_question(self):
        other = json.loads(json.dumps(BODY))
        other["questions"]["span"]["instructions"] = "reworded"
        self.assertNotEqual(mj.cache_key(BODY), mj.cache_key(other))
        self.assertEqual(mj.cache_key(BODY), mj.cache_key(json.loads(json.dumps(BODY))))

    def test_retries_overload_with_backoff(self):
        post = FakePost((429, b"{}"), (529, b"{}"), OK)
        self.client(post).ask(BODY)
        self.assertEqual(self.slept, [1, 2])

    def test_a_refused_key_stops_and_never_shows_the_key(self):
        ts = self.client(FakePost((401, b'{"error": "bad key"}')))
        with self.assertRaises(mj.KeyRefused) as e:
            ts.ask(BODY)
        self.assertNotIn("sk-secret", str(e.exception))

    def test_a_bad_request_is_an_error_with_the_apis_message(self):
        ts = self.client(FakePost((400, b'{"error": "max_tokens_exceeded"}')))
        with self.assertRaises(mj.TypeSafeError) as e:
            ts.ask(BODY)
        self.assertIn("max_tokens_exceeded", str(e.exception))
        self.assertNotIsInstance(e.exception, mj.KeyRefused)

    def test_gives_up_after_the_attempts(self):
        ts = self.client(FakePost(*[(503, b"{}")] * 5))
        with self.assertRaises(mj.TypeSafeError):
            ts.ask(BODY)
        self.assertEqual(len(self.slept), 5)

    def test_no_key_is_an_error_only_when_a_request_is_needed(self):
        post = FakePost(OK)
        with_key = self.client(post)
        with_key.ask(BODY)  # fills the cache
        without = mj.TypeSafe(None, Path(self.tmp.name), post=FakePost())
        self.assertEqual(without.ask(BODY)["model"], "jev-1.14.0")
        with self.assertRaises(mj.TypeSafeError):
            without.ask(dict(BODY, state={"context": "y"}))

    def test_the_key_from_the_environment_else_the_file(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "api_key"
            f.write_text("from-file\n")
            self.assertEqual(mj.api_key({"TYPESAFE_API_KEY": "from-env"}, f), "from-env")
            self.assertEqual(mj.api_key({}, f), "from-file")
            self.assertIsNone(mj.api_key({}, Path(d) / "missing"))

if __name__ == "__main__":
    unittest.main()
