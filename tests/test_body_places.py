import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import body_places as bp  # noqa: E402

TEXTS = {"mr:0101-a": "Fictopoli, sancti Fictitii, qui in Fictonia natus et Romæ educatus est."}
TEXTS_IT = {"mr:0101-a": "A Fictopoli, san Fictizio, nato in Fictonia ed educato a Roma."}
LEADS = {"mr:0101-a": {"role": "death", "la": "Fictopoli", "source": "lead"}}
PERSONS = {"mr:0101-a": [{"name": "Fictitius", "where": "text"}]}


def prop(**kw):
    return {"eulogy": "mr:0101-a", "role": "birth", "la": "in Fictonia", "it": "in Fictonia",
            "confidence": "high", "reasoning": "natus"} | kw


def run_check(proposals, curated=None, review=None):
    curated = {} if curated is None else curated
    review = bp.new_changeset() if review is None else review
    n, failures = bp.check(proposals, curated, review, TEXTS, TEXTS_IT, LEADS, PERSONS)
    return n, failures, review


class CheckTest(unittest.TestCase):
    def test_valid_proposal_becomes_an_op(self):
        n, failures, review = run_check([prop()])
        self.assertEqual((n, failures), (1, []))
        op = review["operations"][0]
        self.assertEqual(op["op"], "add_place")
        self.assertEqual(op["id"], "mr:0101-a#birth#in Fictonia")
        self.assertEqual({k: op[k] for k in ("eulogy", "role", "la", "it", "confidence", "decision", "edited")},
                         {"eulogy": "mr:0101-a", "role": "birth", "la": "in Fictonia", "it": "in Fictonia",
                          "confidence": "high", "decision": None, "edited": None})

    def test_bad_proposals_are_reported_good_ones_kept(self):
        n, failures, review = run_check([prop(), prop(la="in Fictlandia"), prop(role="nativity", la="Romæ", it="a Roma"),
                                         prop(eulogy="mr:0909-x"), prop(confidence="sure", la="Romæ", it="a Roma")])
        self.assertEqual(n, 1)
        self.assertEqual(len(failures), 4)
        self.assertTrue(any("not verbatim" in f for f in failures))
        self.assertTrue(any("unknown role" in f for f in failures))
        self.assertTrue(any("not a current ID" in f for f in failures))
        self.assertTrue(any("confidence" in f for f in failures))

    def test_existing_ops_curated_and_rejected_are_not_requeued(self):
        review = bp.new_changeset()
        run_check([prop()], review=review)
        review["operations"][0]["decision"] = "accept"  # an existing op is left exactly as it is
        n, failures, _ = run_check([prop(), prop(role="education", la="Romæ", it="a Roma")],
                                   curated={"mr:0101-a": [{"role": "education", "la": "Romæ", "it": "a Roma"}]},
                                   review=review)
        self.assertEqual((n, failures), (0, []))
        self.assertEqual(review["operations"][0]["decision"], "accept")
        review2 = bp.new_changeset()
        review2["rejected"] = [bp.op_id(prop())]
        self.assertEqual(run_check([prop()], review=review2)[0], 0)

    def test_duplicate_proposals_in_one_batch(self):
        n, failures, _ = run_check([prop(), prop()])
        self.assertEqual(n, 1)

    def test_occurrence_1_and_n_1_are_the_same_item(self):
        self.assertEqual(bp.op_id(bp.item_of(prop(occurrence=1, occurrence_it=1)) | {"eulogy": "mr:0101-a"}),
                         bp.op_id(prop()))
        review = bp.new_changeset()
        review["rejected"] = [bp.op_id(prop())]
        self.assertEqual(run_check([prop(occurrence=1)], review=review)[0], 0)
        self.assertEqual(bp.op_id(prop(occurrence=1, n=1, person="Fictitius")), bp.op_id(prop(person="Fictitius")))

    def test_reasoning_must_not_quote_the_text(self):
        n, failures, _ = run_check([prop(reasoning="the text says qui in Fictonia natus et")])
        self.assertEqual(n, 0)
        self.assertTrue(any("reasoning quotes the text" in f for f in failures), failures)
        n, failures, _ = run_check([prop(reasoning="x" * 301)])
        self.assertTrue(any("reasoning is longer than 300" in f for f in failures), failures)
        self.assertEqual(run_check([prop(reasoning="birth cue right after the place in Fictonia")])[0], 1)

    def test_op_id_parts(self):
        self.assertEqual(bp.op_id(prop(occurrence=2, person="Fictitius", n=2)),
                         "mr:0101-a#birth#in Fictonia#2#Fictitius#2")


class ApplyTest(unittest.TestCase):
    def setUp(self):
        self.review = bp.new_changeset()
        run_check([prop(), prop(role="education", la="Romæ", it="a Roma", confidence="low")], review=self.review)
        self.curated = {"mr:0101-x": [{"role": "birth", "la": "Fictiae"}]}

    def export(self, **decisions):
        ops = []
        for o in self.review["operations"]:
            d = decisions.get(o["role"])
            ops.append(dict(o, decision=d[0], edited=d[1]) if d else dict(o))
        return {"schema": bp.SCHEMA, "operations": ops}

    def apply(self, exported):
        return bp.apply(exported, self.curated, self.review, TEXTS, TEXTS_IT, LEADS, PERSONS)

    def test_accept_edit_reject_and_undecided(self):
        n = self.apply(self.export(birth=("accept", None)))
        self.assertEqual(n, 1)
        self.assertEqual(self.curated["mr:0101-a"], [{"role": "birth", "la": "in Fictonia", "it": "in Fictonia"}])
        self.assertEqual([o["role"] for o in self.review["operations"]], ["education"])
        n = self.apply(self.export(education=("edit", {"role": "religious_life", "person": "Fictitius"})))
        self.assertEqual(self.curated["mr:0101-a"][1],
                         {"role": "religious_life", "la": "Romæ", "it": "a Roma", "person": "Fictitius"})
        self.assertEqual(self.review["operations"], [])

    def test_reject_is_remembered(self):
        self.apply(self.export(birth=("reject", None)))
        self.assertIn("mr:0101-a#birth#in Fictonia", self.review["rejected"])
        self.assertNotIn("mr:0101-a", self.curated)

    def test_one_invalid_decision_applies_nothing(self):
        before_c, before_r = repr(self.curated), repr(self.review)
        with self.assertRaisesRegex(ValueError, "not verbatim"):
            self.apply(self.export(birth=("accept", None), education=("edit", {"la": "Parisiis"})))
        self.assertEqual((repr(self.curated), repr(self.review)), (before_c, before_r))

    def test_unknown_decision_and_schema(self):
        with self.assertRaisesRegex(ValueError, "unknown decision"):
            self.apply(self.export(birth=("maybe", None)))
        with self.assertRaisesRegex(ValueError, "not a crmedr-changeset/v1"):
            self.apply({"schema": "x", "operations": []})


if __name__ == "__main__":
    unittest.main()
