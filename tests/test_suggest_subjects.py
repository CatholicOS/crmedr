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
import subject_jev as sj  # noqa: E402
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

    def test_below_the_threshold_is_removed(self):
        ops = [dict(copy.deepcopy(OP), jev={"decision": "accept", "probability": 0.99})]
        counts = ss.suggest_ops(ops, DATA, RECORDS, StubClient(p=0.5), 0.9)
        self.assertNotIn("jev", ops[0])
        self.assertEqual(counts["below"], 1)

    def test_decided_and_prefilled_cards_are_never_rewritten(self):
        jev = {"decision": "accept", "probability": 0.99}
        decided = dict(copy.deepcopy(OP), decision="edit", edited={"new_id": "mr:0101-x"}, jev=dict(jev))
        prefilled = dict(copy.deepcopy(ROP), decision=None, prefilled="jev", jev=dict(jev))
        before = copy.deepcopy([decided, prefilled])
        client = StubClient(p=0.5)
        counts = ss.suggest_ops([decided, prefilled], DATA, RECORDS, client, 0.9)
        self.assertEqual([decided, prefilled], before)
        self.assertEqual((counts["skipped"], client.bodies), (2, []))

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

    def test_suggest_leaves_relabels_untouched(self):
        # The subject follows the ID: Jev's rename pick chooses the pairing, no relabel request.
        client = StubClient(picks={"pick": "c1"})
        stale = dict(copy.deepcopy(ROP), jev={"decision": "accept", "probability": 0.99})
        ops = [copy.deepcopy(OP), copy.deepcopy(ROP), copy.deepcopy(POP), stale]
        before = copy.deepcopy(ops[1]), copy.deepcopy(ops[3])
        counts = ss.suggest_ops(ops, DATA, RECORDS, client, 0.9)
        self.assertEqual((counts["suggested"], counts["skipped"], len(client.bodies)), (2, 2, 2))
        self.assertIsNone(ss.family(ROP))
        self.assertEqual((ops[1], ops[3]), before)
        self.assertFalse(any(hasattr(sj, f) for f in ("relabel_request", "relabel_suggestion", "relabel_scores")))

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

    def test_rows_and_the_report_per_question_family(self):
        ops = [dict(copy.deepcopy(OP), decision="accept"),
               dict(copy.deepcopy(POP), decision="edit", edited={"wikidata": "Q2"}),
               dict(copy.deepcopy(POP), id="undecided"), dict(copy.deepcopy(ROP), decision="accept")]
        rows = ss.evaluate_ops(ops, DATA, RECORDS, StubClient(p=0.92))
        # undecided ops are not evaluated, nor a relabel (it follows the rename)
        self.assertEqual([r["family"] for r in rows], ["rename", "person"])
        text = ss.report(rows, [0.0, 0.95])
        self.assertIn("rename: 1 cards", text)
        self.assertIn("person: 1 cards", text)
        self.assertIn("≥0.00: 1 suggested (100%), 1 agree (100%)", text)
        self.assertIn("≥0.95: 0 suggested (0%)", text)
        self.assertIn("mr:0101-eugendus|Eugendus: decided Q2, suggested Q1 p=0.92", text)


class PrefillTest(unittest.TestCase):
    @staticmethod
    def cand(new_id, category, weak=False, certain=True):
        return {"new_id": new_id, "category": category, "weak": weak, "certain": certain, "labels": {}}

    def rename(self, *cands, new_id=None, **extra):
        return {"op": "rename", "id": "mr:0101-x", "new_id": new_id or cands[0]["new_id"],
                "candidates": list(cands), "decision": None, **extra}

    def test_rename_rule_accepts_the_op_s_own_new_id(self):
        op = self.rename(self.cand("mr:0101-x-a", "surname"))
        self.assertEqual(ss.prefill_ops([op]), {"rename": 1})
        self.assertEqual((op["decision"], op["prefilled"]), ("accept", "rule"))
        self.assertNotIn("edited", op)

    def test_rename_rule_edits_to_the_other_candidate(self):
        op = self.rename(self.cand("mr:0101-x-a", "role-place"), self.cand("mr:0101-x-b", "papa"),
                         new_id="mr:0101-x-a")
        ss.prefill_ops([op])
        self.assertEqual((op["decision"], op["edited"], op["prefilled"]),
                         ("edit", {"new_id": "mr:0101-x-b"}, "rule"))

    def test_first_category_in_order_wins_and_an_uncertain_genitive_is_taken(self):
        op = self.rename(self.cand("mr:0101-x-g", "place-genitive", certain=False),
                         self.cand("mr:0101-x-a", "place-adjective"), new_id="mr:0101-x-g")
        ss.prefill_ops([op])
        self.assertEqual(op["edited"], {"new_id": "mr:0101-x-a"})
        lone = self.rename(self.cand("mr:0101-x-g", "place-genitive", certain=False))
        ss.prefill_ops([lone])
        self.assertEqual(lone["decision"], "accept")

    def test_weak_or_uncertain_not_prefilled(self):
        weak = self.rename(self.cand("mr:0101-x-r", "twin", weak=True))
        two = self.rename(self.cand("mr:0101-x-a", "surname"), self.cand("mr:0101-x-b", "surname"))
        other = self.rename(self.cand("mr:0101-x-r", "role-place"))
        self.assertEqual(ss.prefill_ops([weak, two, other]), {})
        for op in (weak, two, other):
            self.assertIsNone(op["decision"])
            self.assertNotIn("prefilled", op)

    def person(self, jev):
        op = copy.deepcopy(POP)
        op["jev"] = jev
        return op

    def test_person_accept_edit_and_reject_at_the_threshold(self):
        acc = self.person({"decision": "accept", "wikidata": "Q1", "probability": 0.9})
        edt = self.person({"decision": "edit", "wikidata": "Q2", "probability": 0.95})
        rej = self.person({"decision": "reject", "reason": "Jev: none", "probability": 0.92})
        self.assertEqual(ss.prefill_ops([acc, edt, rej]), {"resolve_person": 3})
        self.assertEqual((acc["decision"], acc.get("edited"), acc["prefilled"]), ("accept", None, "jev"))
        self.assertEqual((edt["decision"], edt["edited"]), ("edit", {"wikidata": "Q2"}))
        self.assertEqual((rej["decision"], rej["edited"]), ("reject", {"reason": "Jev: none"}))

    def test_person_below_threshold_or_not_a_human_saint_candidate_is_left(self):
        low = self.person({"decision": "accept", "wikidata": "Q1", "probability": 0.8})
        notc = self.person({"decision": "edit", "wikidata": "Q99", "probability": 0.99})
        bare = self.person({"decision": "edit", "wikidata": "Q3", "probability": 0.99})
        bare["candidates"].append({"wikidata": "Q3", "human": True, "evidence": ["human"]})
        self.assertEqual(ss.prefill_ops([low, notc, bare]), {})
        self.assertTrue(all(op["decision"] is None for op in (low, notc, bare)))

    def test_relabel_never_prefilled(self):
        # The subject card is never prefilled, whatever its jev and its rename's prefill.
        ruled = self.rename(self.cand("mr:0101-eugendus-a", "surname"))
        ruled["id"] = "mr:0101-eugendus"
        rop = dict(copy.deepcopy(ROP), jev={"decision": "accept", "probability": 0.99})
        before = copy.deepcopy(rop)
        self.assertEqual(ss.prefill_ops([ruled, rop]), {"rename": 1})
        self.assertEqual(rop, before)

    def test_reject_without_jev_reason_gets_the_default(self):
        none, blank = (self.person({"decision": "reject", "probability": 0.95, **r}) for r in ({}, {"reason": " "}))
        self.assertEqual(ss.prefill_ops([none, blank]), {"resolve_person": 2})
        for op in (none, blank):
            self.assertEqual(op["edited"], {"reason": "Jev: none of the candidates is this person"})

    def test_decided_untouched(self):
        op = self.rename(self.cand("mr:0101-x-a", "surname"), decision="reject")
        op["decision"] = "reject"
        p = self.person({"decision": "accept", "wikidata": "Q1", "probability": 1.0})
        p["decision"] = "reject"
        self.assertEqual(ss.prefill_ops([op, p]), {})
        self.assertEqual((op["decision"], p["decision"]), ("reject", "reject"))
        self.assertNotIn("prefilled", op)

    def test_the_command_refuses_a_change_set_inside_a_work_tree(self):
        here = Path(__file__).resolve()
        with self.assertRaises(SystemExit):
            ss.main(["prefill", str(here)])

    def test_the_command_prints_the_counts_and_writes_the_file(self):
        op = self.rename(self.cand("mr:0101-x-a", "surname"))
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "cs.json"
            path.write_text(json.dumps({"operations": [op]}), encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                ss.main(["prefill", str(path), "--threshold", "0.8"])
            self.assertIn("{'rename': 1}", out.getvalue())
            self.assertEqual(json.loads(path.read_text())["operations"][0]["decision"], "accept")

    def test_a_failed_write_leaves_the_old_file_and_no_temp(self):
        from unittest import mock
        op = self.rename(self.cand("mr:0101-x-a", "surname"))
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "cs.json"
            old = json.dumps({"operations": [op]})
            path.write_text(old, encoding="utf-8")
            with mock.patch("os.replace", side_effect=OSError("disk")):
                with self.assertRaises(OSError):
                    ss.main(["prefill", str(path), "--threshold", "0.8"])
            self.assertEqual(path.read_text(), old)
            self.assertEqual([p.name for p in Path(d).iterdir()], ["cs.json"])


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
