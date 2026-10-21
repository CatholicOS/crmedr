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
import suggest_places as sp  # noqa: E402
from test_gazetteer_jev import OP, answers  # noqa: E402

TEXTS = {"la": {"mr:0101-a": "Londini, apud Tybúrni, passus est sanctus Thomas."},
         "en": {"mr:0101-a": "In London, at Tyburn, Saint Thomas suffered."}}


def op_with_candidates():
    return dict(copy.deepcopy(OP), occurrences=["mr:0101-a"], decision=None, edited=None)


class StubClient:
    """Returns `response` for every request; `key` and `cached` are what require_key reads."""

    def __init__(self, response, key="k", cached=True, error=None):
        self.response, self.key, self._cached, self.error, self.bodies = response, key, cached, error, []

    def cached(self, body):
        return self._cached

    def ask(self, body):
        self.bodies.append(body)
        if self.error:
            raise self.error
        return {"model": "jev-test", "answers": self.response}


class SuggestTest(unittest.TestCase):
    def test_suggest_writes_jev_whatever_the_probability(self):
        ops = [op_with_candidates()]
        counts = sp.suggest_ops(ops, TEXTS, StubClient(answers("c0", "place", 0.41)))
        self.assertEqual(counts["suggested"], 1)
        self.assertEqual(ops[0]["jev"]["probability"], 0.41)

    def test_decided_card_keeps_its_decision(self):
        op = dict(op_with_candidates(), decision="reject", edited={"reason": "x"})
        sp.suggest_ops([op], TEXTS, StubClient(answers("c0", "place", 0.99)))
        self.assertEqual((op["decision"], op["edited"]), ("reject", {"reason": "x"}))

    def test_suggested_is_never_touched(self):
        op = dict(op_with_candidates(), suggested={"wikidata": "Q2", "country": "GB"})
        sp.suggest_ops([op], TEXTS, StubClient(answers("c0", "place", 0.9)))
        self.assertEqual(op["suggested"], {"wikidata": "Q2", "country": "GB"})

    def test_no_key_stops_before_writing(self):
        with self.assertRaises(mj.TypeSafeError):
            sp.require_key([op_with_candidates()], TEXTS, StubClient(None, key=None, cached=False))

    def test_no_key_is_fine_when_everything_is_cached(self):
        sp.require_key([op_with_candidates()], TEXTS, StubClient(None, key=None, cached=True))

    def test_no_latin_text_skips_and_removes_jev(self):
        op = dict(op_with_candidates(), occurrences=["mr:9999-x"], jev={"kind": "place"})
        counts = sp.suggest_ops([op], TEXTS, StubClient(None))
        self.assertEqual(counts["skipped"], 1)
        self.assertNotIn("jev", op)

    def test_request_uses_the_first_occurrence_with_a_latin_text(self):
        op = dict(op_with_candidates(), occurrences=["mr:9999-x", "mr:0101-a"])
        body = sp.request_for(op, TEXTS)
        self.assertIn("Tybúrni", body["state"]["latin_clause"])
        self.assertIn("Tyburn", body["state"]["english_clause"])

    def test_error_is_counted_reported_and_removes_jev(self):
        op = dict(op_with_candidates(), jev={"kind": "place"})
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            counts = sp.suggest_ops([op], TEXTS, StubClient(None, error=mj.TypeSafeError("boom")))
        self.assertEqual(counts["errors"], 1)
        self.assertNotIn("jev", op)
        self.assertIn("boom", err.getvalue())

    def test_unreadable_answer_is_an_error(self):
        op = op_with_candidates()
        with contextlib.redirect_stderr(io.StringIO()):
            counts = sp.suggest_ops([op], TEXTS, StubClient({}))
        self.assertEqual((counts["errors"], counts["suggested"]), (1, 0))

    def test_refused_key_is_raised(self):
        with self.assertRaises(mj.KeyRefused):
            sp.suggest_ops([op_with_candidates()], TEXTS, StubClient(None, error=mj.KeyRefused("no")))

    def test_ops_of_other_kinds_are_left_alone(self):
        op = {"op": "add_place", "id": "x"}
        counts = sp.suggest_ops([op], TEXTS, StubClient(None))
        self.assertEqual(counts["skipped"], 1)
        self.assertEqual(op, {"op": "add_place", "id": "x"})


def round1_op(cands, suggested=None):
    op = dict(op_with_candidates(), id="P", la="Tybúrni",
              candidates=[dict(OP["candidates"][0], wikidata=q) for q in cands])
    if suggested:
        op["suggested"] = {"wikidata": suggested}
    return op


class EvaluateTest(unittest.TestCase):
    def test_calibration_set_positive_and_negative(self):
        pairs = sp.calibration_set([round1_op(cands=["Q1", "Q2"], suggested="Q1")], {"P": {"wikidata": "Q1", "status": "reviewed"}})
        self.assertEqual([(len(op["candidates"]), exp) for op, exp in pairs], [(2, "Q1"), (1, None)])
        self.assertTrue(all("suggested" not in op for op, _ in pairs))

    def test_calibration_set_skips_settled_outside_candidates(self):
        self.assertEqual(sp.calibration_set([round1_op(cands=["Q2"])], {"P": {"wikidata": "Q1", "status": "reviewed"}}), [])

    def test_calibration_set_skips_unsettled_and_has_no_negative_for_one_candidate(self):
        self.assertEqual(sp.calibration_set([round1_op(cands=["Q1"])], {"P": {"wikidata": "Q1", "status": "pending"}}), [])
        pairs = sp.calibration_set([round1_op(cands=["Q1"])], {"P": {"wikidata": "Q1", "status": "auto"}})
        self.assertEqual([exp for _, exp in pairs], ["Q1"])

    def test_report_counts_agreement_per_threshold(self):
        rows = [{"id": "a", "expected": "Q1", "picked": "Q1", "probability": 0.95, "negative": False},
                {"id": "b", "expected": None, "picked": "Q3", "probability": 0.92, "negative": True}]
        out = sp.report(rows, [0.9])
        self.assertIn("0.9  positives 1/1 agree (100.0%)  negatives 0/1 agree (0.0%)", out)
        self.assertIn("disagreements at 0.9:", out)
        self.assertIn("  b [negative]: expected none, picked Q3 p=0.92", out)

    def test_report_with_no_rows_at_a_threshold(self):
        self.assertIn("0.99  positives 0/0 agree (0.0%)  negatives 0/0 agree (0.0%)", sp.report([], [0.99]))

    def test_evaluate_ops_rows_and_errors(self):
        pairs = sp.calibration_set([round1_op(cands=["Q1", "Q2"])], {"P": {"wikidata": "Q1", "status": "reviewed"}})
        rows = sp.evaluate_ops(pairs, TEXTS, StubClient(answers("c0", "place", 0.9)))
        self.assertEqual([(r["id"], r["expected"], r["picked"], r["negative"]) for r in rows],
                         [("P", "Q1", "Q1", False), ("P", None, "Q2", True)])
        failing = StubClient(None, error=mj.TypeSafeError("boom"))
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(sp.evaluate_ops(pairs, TEXTS, failing), [])

    def test_evaluate_ops_stops_without_a_key(self):
        pairs = sp.calibration_set([round1_op(cands=["Q1", "Q2"])], {"P": {"wikidata": "Q1", "status": "reviewed"}})
        with self.assertRaises(mj.TypeSafeError):
            sp.evaluate_ops(pairs, TEXTS, StubClient(None, key=None, cached=False))


class MainTest(unittest.TestCase):
    def test_writes_the_file_in_the_queue_format(self):
        with tempfile.TemporaryDirectory() as d:
            doc = {"operations": [op_with_candidates()]}
            path = Path(d) / "q.json"
            path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            sp.write_changeset(path, doc)
            self.assertEqual(path.read_text(encoding="utf-8"), json.dumps(doc, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    unittest.main()
