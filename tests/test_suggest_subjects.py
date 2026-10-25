import contextlib
import copy
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import mentions_jev as mj  # noqa: E402
import suggest_subjects as ss  # noqa: E402
from test_subject_jev import EUGENDUS, LA, OP, POP, ROP  # noqa: E402

DATA = {"la": {"mr:0101-eugendus": LA}, "en": {}, "it": {},
        "labels": {"en": {"mr:0101-eugendus": "Saint Eugendus"}, "it": {}},
        "items": {"mr:0101-eugendus": {"Lupicinus": {"wikidata": "Q9", "status": "reviewed"}}}}
RECORDS = ss.index_records([EUGENDUS])


class StubClient:
    """Answers every choice question with its option `picks[question]` (else the first option) at
    probability `p`, and every noul with `noul`."""

    def __init__(self, picks=None, p=0.95, noul=0.9, error=None, model="jev-1.14.0"):
        self.picks, self.p, self.noul, self.error, self.bodies = picks or {}, p, noul, error, []
        self.model = model

    def ask(self, body):
        self.bodies.append(body)
        if self.error:
            raise self.error
        answers = {}
        for q, spec in body["questions"].items():
            if spec["type"] == "noul":
                answers[q] = {"type": "noul", "noul": self.noul}
            elif spec["type"] == "score":
                answers[q] = {"type": "score", "score": 3, "probabilities": {"3": 0.9}, "confidence": 0.9}
            else:
                pick = self.picks.get(q, next(iter(spec["criteria"])))
                answers[q] = {"type": "choice", "choice": pick, "probabilities": {pick: self.p}, "confidence": 0.9}
        return {"model": self.model, "answers": answers}


class SuggestTest(unittest.TestCase):
    def test_writes_jev_at_or_above_the_threshold_and_keeps_the_rest(self):
        ops = [copy.deepcopy(OP), copy.deepcopy(POP)]
        ops[1]["suggested"] = {"wikidata": "Q1"}
        counts = ss.suggest_ops(ops, DATA, RECORDS, StubClient(), 0.9)
        self.assertEqual(counts, {"suggested": 2, "below": 0, "flagged": 0, "skipped": 0, "errors": 0})
        self.assertEqual(ops[0]["jev"]["decision"], "accept")
        self.assertEqual(ops[1]["jev"]["decision"], "accept")
        self.assertEqual(ops[1]["suggested"], {"wikidata": "Q1"})  # verify-suggestions' own, untouched
        self.assertIsNone(ops[0]["decision"])

    def test_only_the_clause_is_sent_and_companions_carry_their_items(self):
        client = StubClient()
        ss.suggest_ops([copy.deepcopy(OP), copy.deepcopy(POP)], DATA, RECORDS, client, 0.9)
        self.assertNotIn("obiit senex", json.dumps(client.bodies, ensure_ascii=False))
        self.assertEqual(client.bodies[1]["state"]["companions"], [{"name": "Lupicinus", "wikidata": "Q9"}])

    def test_below_the_threshold_is_removed_and_decisions_are_kept(self):
        ops = [dict(copy.deepcopy(OP), decision="edit", edited={"new_id": "mr:0101-x"},
                    jev={"decision": "accept", "probability": 0.99})]
        counts = ss.suggest_ops(ops, DATA, RECORDS, StubClient(p=0.5), 0.9)
        self.assertNotIn("jev", ops[0])
        self.assertEqual((ops[0]["decision"], ops[0]["edited"]), ("edit", {"new_id": "mr:0101-x"}))
        self.assertEqual(counts["below"], 1)

    def test_a_record_flag_is_written_without_a_suggestion(self):
        ops = [copy.deepcopy(OP)]
        counts = ss.suggest_ops(ops, DATA, RECORDS, StubClient(noul=0.2, model="jev-1.15.0"), 0.9)
        self.assertEqual(ops[0]["jev"]["flags"], ["record:roles[0]", "record:places[0]"])
        self.assertNotIn("decision", ops[0]["jev"])
        self.assertEqual(ops[0]["jev"]["model"], "jev-1.15.0")  # the model that answered
        self.assertEqual(ops[0]["jev"]["scores"], {c["new_id"]: 3 for c in OP["candidates"]})
        self.assertEqual(counts["flagged"], 1)

    def test_a_suggestion_carries_the_clarity_scores(self):
        ops = [copy.deepcopy(OP)]
        ss.suggest_ops(ops, DATA, RECORDS, StubClient(), 0.9)
        self.assertEqual(ops[0]["jev"]["scores"], {c["new_id"]: 3 for c in OP["candidates"]})

    def test_month_scope(self):
        client = StubClient()
        other = dict(copy.deepcopy(POP), id="mr:0201-eugendus|Eugendus", eulogy="mr:0201-eugendus")
        ops = [copy.deepcopy(OP), copy.deepcopy(POP), other]
        counts = ss.suggest_ops(ops, DATA, RECORDS, client, 0.0, month="02")
        self.assertEqual((counts["skipped"], len(client.bodies)), (3, 0))  # no February text, no request
        counts = ss.suggest_ops(ops, DATA, RECORDS, StubClient(), 0.0, month="01")
        self.assertEqual((counts["suggested"], counts["skipped"]), (2, 1))
        self.assertNotIn("jev", ops[2])

    def test_suggest_asks_relabel(self):
        client = StubClient(picks={"pick": "c1"})
        ops = [copy.deepcopy(OP), copy.deepcopy(ROP), copy.deepcopy(POP)]
        counts = ss.suggest_ops(ops, DATA, RECORDS, client, 0.9)
        self.assertEqual(counts["suggested"], 3)
        self.assertEqual(ss.family(ops[1]), "relabel")
        self.assertEqual(set(client.bodies[1]["questions"]), {"clarity_c0", "clarity_c1", "clarity_c2", "pick"})
        self.assertEqual((ops[1]["jev"]["decision"], ops[1]["jev"]["labels"]), ("edit", ROP["candidates"][1]["labels"]))
        self.assertEqual(ops[1]["jev"]["scores"], [3, 3, 3])
        self.assertIsNone(ops[1]["decision"])
        ops = [copy.deepcopy(ROP)]
        self.assertEqual(ss.suggest_ops(ops, DATA, RECORDS, StubClient(p=0.5), 0.9)["below"], 1)
        self.assertNotIn("jev", ops[0])
        counts = ss.suggest_ops([copy.deepcopy(ROP)], DATA, RECORDS, StubClient(), 0.0, persons=True)
        self.assertEqual(counts["skipped"], 1)  # relabels are asked with the renames, not with --persons

    def test_a_rename_without_a_record_is_skipped_without_a_request(self):
        client = StubClient()
        counts = ss.suggest_ops([dict(copy.deepcopy(OP), id="mr:0102-x")], DATA, RECORDS, client, 0.0)
        self.assertEqual((counts["skipped"], client.bodies), (1, []))

    def test_persons_only(self):
        client = StubClient()
        counts = ss.suggest_ops([copy.deepcopy(OP), copy.deepcopy(POP)], DATA, RECORDS, client, 0.0, persons=True)
        self.assertEqual((counts["skipped"], len(client.bodies)), (1, 1))

    def test_an_api_error_is_counted_and_the_run_continues(self):
        class Flaky(StubClient):
            def ask(self, body):
                if not self.bodies:
                    self.bodies.append(body)
                    raise mj.TypeSafeError("HTTP 400: too long")
                return super().ask(body)
        ops = [copy.deepcopy(OP), copy.deepcopy(POP)]
        with contextlib.redirect_stderr(io.StringIO()) as err:
            counts = ss.suggest_ops(ops, DATA, RECORDS, Flaky(), 0.0)
        self.assertIn("mr:0101-eugendus: HTTP 400: too long", err.getvalue())
        self.assertNotIn("jev", ops[0])
        self.assertIn("jev", ops[1])
        self.assertEqual(counts["errors"], 1)

    def test_a_refused_key_stops_the_run(self):
        with self.assertRaises(mj.KeyRefused):
            ss.suggest_ops([copy.deepcopy(OP)], DATA, RECORDS, StubClient(error=mj.KeyRefused("refused")), 0.0)

    def test_no_key_and_uncached_stops_before_any_op_changes(self):
        with tempfile.TemporaryDirectory() as d:
            ops = [dict(copy.deepcopy(OP), jev={"decision": "accept", "probability": 0.95})]
            with self.assertRaises(mj.TypeSafeError):
                ss.suggest_ops(ops, DATA, RECORDS, mj.TypeSafe(None, Path(d)), 0.9)
            self.assertEqual(ops[0]["jev"]["probability"], 0.95)


class RecordForTest(unittest.TestCase):
    def test_a_person_card_takes_its_own_record_else_only_the_kind(self):
        self.assertIs(ss.record_for(POP, RECORDS), EUGENDUS)
        other = dict(POP, id="mr:0101-eugendus|Lupicinus", name="Lupicinus")
        self.assertEqual(ss.record_for(other, RECORDS),
                         {"id": "mr:0101-eugendus", "name": "Lupicinus", "kind": "person"})
        second = dict(EUGENDUS, n=2, death_year=520)
        records = ss.index_records([EUGENDUS, second])
        self.assertIs(ss.record_for(dict(POP, n=2), records), second)
        self.assertIsNone(ss.record_for(other, records))


class EvaluateTest(unittest.TestCase):
    def test_curator_outcomes(self):
        self.assertEqual(ss.curator_outcome(dict(OP, decision="accept")), OP["new_id"])
        self.assertEqual(ss.curator_outcome(dict(OP, decision="edit", edited={"new_id": "mr:0101-x"})), "mr:0101-x")
        self.assertEqual(ss.curator_outcome(dict(POP, decision="accept")), "Q1")
        self.assertEqual(ss.curator_outcome(dict(POP, decision="accept", suggested={"wikidata": "Q2"})), "Q2")
        self.assertEqual(ss.curator_outcome(dict(POP, decision="edit", edited={"wikidata": "Q7"})), "Q7")
        self.assertIsNone(ss.curator_outcome(dict(POP, decision="reject", edited={"reason": "x"})))

    def test_relabel_outcomes(self):
        labels, current = ROP["labels"], ROP["current"]
        other = ROP["candidates"][1]["labels"]
        self.assertEqual(ss.curator_outcome(dict(ROP, decision="accept")), labels)
        self.assertEqual(ss.curator_outcome(dict(ROP, decision="edit", edited={"labels": other})), other)
        self.assertEqual(ss.curator_outcome(dict(ROP, decision="reject")), current)
        self.assertEqual(ss.suggested_outcome(ROP, {"decision": "accept"}), labels)
        self.assertEqual(ss.suggested_outcome(ROP, {"decision": "edit", "labels": other}), other)
        self.assertEqual(ss.suggested_outcome(ROP, {"decision": "reject"}), current)

    def test_rows_and_the_report_per_question_family(self):
        ops = [dict(copy.deepcopy(OP), decision="accept"),
               dict(copy.deepcopy(POP), decision="edit", edited={"wikidata": "Q2"}),
               dict(copy.deepcopy(POP), id="undecided")]
        rows = ss.evaluate_ops(ops, DATA, RECORDS, StubClient(p=0.92))
        self.assertEqual([r["family"] for r in rows], ["rename", "person"])  # undecided ops are not evaluated
        text = ss.report(rows, [0.0, 0.95])
        self.assertIn("rename: 1 cards", text)
        self.assertIn("person: 1 cards", text)
        self.assertIn("≥0.00: 1 suggested (100%), 1 agree (100%)", text)
        self.assertIn("≥0.95: 0 suggested (0%)", text)
        self.assertIn("mr:0101-eugendus|Eugendus: decided Q2, suggested Q1 p=0.92", text)


class OutputTest(unittest.TestCase):
    def test_a_change_set_inside_a_work_tree_is_refused(self):
        here = Path(__file__).resolve()
        with self.assertRaises(SystemExit):
            ss.main(["suggest", str(here), str(here), str(here.parent)])

    def test_a_bad_month_is_refused(self):
        with self.assertRaisesRegex(SystemExit, "expected MM"):
            ss.main(["suggest", "/a.json", "/r.json", "/texts", "--month", "1"])


if __name__ == "__main__":
    unittest.main()
