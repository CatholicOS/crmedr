import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import mentions_italian as mi  # noqa: E402
import mentions_jev as mj  # noqa: E402
import suggest_mentions as sm  # noqa: E402

IT = "martyrologium_romanum_2004_it_IT"
FN = {"footnote": 1}
CTX = "santi Potamia, Pompea, Rodana"


def op(reasoning, name="Pompeia", form="Pompea", decision=None, edited=None, oid="a"):
    i = CTX.index(form) if form else None
    return {"op": "add_mention", "id": oid, "kind": "person", "edition": IT, "eulogy": "mr:0602-x", "where": FN,
            "name": name, "form": form, "start": 100 + i if form else None, "end": 100 + i + len(form) if form else None,
            "context": CTX, "context_start": 100, "reasoning": reasoning, "decision": decision, "edited": edited}


DATA = {"persons": {"mr:0602-x": [{"name": "Potamia", "where": FN}, {"name": "Pompeia", "where": FN},
                                  {"name": "Rodana", "where": FN}]},
        "latin": {"mr:0602-x": []},
        "italian": {"mr:0602-x": [{"kind": "person", "where": FN, "name": "Potamia", "start": 106, "end": 113},
                                  {"kind": "person", "where": FN, "name": "Rodana", "start": 123, "end": 129}]},
        "names": mi.ItalianNames({}, {})}
POSITION = "Pompeia was not found by name: proposed by its place in the list"


class StubClient:
    """Answers every span question with `pick` at `confidence`."""

    def __init__(self, pick="c1", confidence=0.9, error=None):
        self.pick, self.confidence, self.error, self.bodies = pick, confidence, error, []

    def ask(self, body):
        self.bodies.append(body)
        if self.error:
            raise self.error
        q = next(iter(body["questions"]))
        options = list(body["questions"][q]["criteria"])
        probs = {o: (0.9 if o == self.pick else 0.1 / (len(options) - 1)) for o in options}
        return {"model": "jev-1.14.0", "answers": {q: {"type": "choice", "choice": self.pick,
                                                      "probabilities": probs, "confidence": self.confidence}}}


class SuggestTest(unittest.TestCase):
    def test_writes_a_suggestion_at_or_above_the_threshold(self):
        ops = [op(POSITION)]
        counts = sm.suggest_ops(ops, DATA, StubClient("c1", 0.9), 0.8)
        self.assertEqual(ops[0]["suggested"]["decision"], "accept")
        self.assertEqual(counts, {"suggested": 1, "below": 0, "skipped": 0, "errors": 0})

    def test_a_stale_suggestion_is_removed_and_decisions_are_kept(self):
        ops = [op(POSITION, decision="reject", edited={"reason": "x"})]
        ops[0]["suggested"] = {"decision": "accept", "probability": 0.99, "confidence": 0.99, "model": "old"}
        counts = sm.suggest_ops(ops, DATA, StubClient("c1", 0.5), 0.8)
        self.assertNotIn("suggested", ops[0])
        self.assertEqual((ops[0]["decision"], ops[0]["edited"]), ("reject", {"reason": "x"}))
        self.assertEqual(counts["below"], 1)

    def test_an_out_of_scope_card_is_skipped_without_a_request(self):
        client = StubClient()
        counts = sm.suggest_ops([op("Pompeia is named inside a place phrase, which was kept")], DATA, client, 0.0)
        self.assertEqual((counts["skipped"], client.bodies), (1, []))

    def test_an_api_error_leaves_the_card_without_a_suggestion(self):
        ops = [op(POSITION)]
        counts = sm.suggest_ops(ops, DATA, StubClient(error=mj.TypeSafeError("HTTP 400: too long")), 0.0)
        self.assertNotIn("suggested", ops[0])
        self.assertEqual(counts["errors"], 1)

    def test_a_refused_key_stops_the_run(self):
        with self.assertRaises(mj.KeyRefused):
            sm.suggest_ops([op(POSITION)], DATA, StubClient(error=mj.KeyRefused("refused")), 0.0)


class EvaluateTest(unittest.TestCase):
    def test_the_curators_decision_with_an_edit_on_the_proposed_span_as_accept(self):
        self.assertEqual(sm.curator_decision(op(POSITION, decision="accept")), ("accept",))
        same = op(POSITION, decision="edit")
        same["edited"] = {"start": same["start"], "end": same["end"], "form": "Pompea"}
        self.assertEqual(sm.curator_decision(same), ("accept",))
        self.assertEqual(sm.curator_decision(op(POSITION, decision="edit", edited={"start": 1, "end": 4, "form": "x"})),
                         ("edit", 1, 4))

    def test_rows_and_the_report(self):
        ops = [op(POSITION, decision="accept", oid="a"), op(POSITION, decision="reject", oid="b"),
               op(POSITION, decision=None, oid="c")]
        rows = sm.evaluate_ops(ops, DATA, StubClient("c1", 0.9))
        self.assertEqual([r["id"] for r in rows], ["a", "b"])  # undecided cards are not evaluated
        text = sm.report(rows, [0.0, 0.95])
        self.assertIn("position: 2 cards", text)
        self.assertIn("≥0.00: 2 suggested (100%), 1 agree (50%)", text)
        self.assertIn("≥0.95: 0 suggested (0%)", text)
        self.assertIn("b: decided ('reject',), suggested ('accept',) p=0.9", text)



class NoKeyTest(unittest.TestCase):
    """Review finding: without a key, suggest must stop before touching any card."""

    def test_no_key_and_uncached_stops_before_any_card_changes(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            client = mj.TypeSafe(None, Path(d))
            ops = [op(POSITION)]
            ops[0]["suggested"] = {"decision": "accept", "probability": 0.95, "confidence": 0.95, "model": "m"}
            with self.assertRaises(mj.TypeSafeError):
                sm.suggest_ops(ops, DATA, client, 0.9)
            self.assertEqual(ops[0]["suggested"]["confidence"], 0.95)

    def test_evaluate_stops_too(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(mj.TypeSafeError):
                sm.evaluate_ops([op(POSITION, decision="accept")], DATA, mj.TypeSafe(None, Path(d)))


class EvaluateErrorsTest(unittest.TestCase):
    """Review finding: a card the API failed on is reported, not scored as no suggestion."""

    def test_an_error_is_kept_on_the_row_and_reported(self):
        rows = sm.evaluate_ops([op(POSITION, decision="accept", oid="a")], DATA,
                               StubClient(error=mj.TypeSafeError("HTTP 400: too long")))
        self.assertEqual(rows[0]["error"], "HTTP 400: too long")
        self.assertIn("errors:\n  a: HTTP 400: too long", sm.report(rows, [0.0]))

if __name__ == "__main__":
    unittest.main()
