"""End to end: identity records -> review cards -> Jev's suggestions -> the curator takes them -> apply."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_person_items as bp  # noqa: E402
import rename_candidates as rc  # noqa: E402
import suggest_subjects as ss  # noqa: E402
from test_subject_jev import EUGENDUS, LA, POP  # noqa: E402
from test_suggest_subjects import StubClient  # noqa: E402

RECORD = dict(EUGENDUS, cognomen=None, relations=[], death_year=None, role_en="abbot", role_it="abate")
LABELS = {"la": {"mr:0101-eugendus": "Sanctus Eugendus"}, "en": {"mr:0101-eugendus": "Saint Eugendus"},
          "it": {"mr:0101-eugendus": "Sant’Eugendo"}}
DATA = {"la": {"mr:0101-eugendus": LA}, "en": {}, "it": {}, "labels": {"en": LABELS["en"], "it": LABELS["it"]},
        "items": {}}


def take(op):
    """The curator takes Jev's suggestion as their decision, as the review tool would write it."""
    jev = op["jev"]
    op["decision"] = jev["decision"]
    if jev["decision"] == "edit":
        op["edited"] = {"new_id": jev["new_id"]} if op["op"] == "rename" else {"wikidata": jev["wikidata"]}


class PipelineTest(unittest.TestCase):
    def test_a_rename_card(self):
        ctx = rc.Context(taken={}, twins={}, ids={"mr:0101-eugendus"}, labels=LABELS)
        old = {"mr:0101-eugendus": {"new_id": "mr:0101-eugendus-condatisci", "class": "place-form,low",
                                    "subject_la": "Sanctus Eugendus Condatisci"}}
        changeset = rc.build_changeset([RECORD], ctx, LABELS["la"], old)
        op = changeset["operations"][0]
        self.assertEqual([c["new_id"] for c in op["candidates"]],
                         ["mr:0101-eugendus-abbas-condatiscensis", "mr:0101-eugendus-condatiscensis",
                          "mr:0101-eugendus-condatisci"])
        counts = ss.suggest_ops(changeset["operations"], DATA, ss.index_records([RECORD]),
                                StubClient(picks={"pick": "c1"}), 0.9)
        self.assertEqual(counts["suggested"], 1)
        take(op)
        self.assertEqual(ss.curator_outcome(op), "mr:0101-eugendus-condatiscensis")
        self.assertEqual(op["edited"], {"new_id": "mr:0101-eugendus-condatiscensis"})

    def test_a_person_card(self):
        person = {"eulogy": "mr:0101-eugendus", "name": "Eugendus", "where": "text", "day": "01-01",
                  "typology": "dies_natalis", "subject": "Sanctus Eugendus", "companions": []}
        key = "mr:0101-eugendus|Eugendus"
        candidates = copy.deepcopy(POP["candidates"])
        review = bp.new_changeset([bp.make_op(key, person, {"failed": [], "candidates": candidates}, None)])
        counts = ss.suggest_ops(review["operations"], DATA, ss.index_records([RECORD]),
                                StubClient(picks={"item": "q1"}), 0.9)
        self.assertEqual(counts["suggested"], 1)
        exported = copy.deepcopy(review)
        take(exported["operations"][0])
        items = {}
        self.assertEqual(bp.apply_decisions(items, review, exported, {key: person}, None), 1)
        self.assertEqual(items, {"mr:0101-eugendus": {"Eugendus": {"wikidata": "Q2", "status": "reviewed"}}})
        self.assertEqual(review["operations"], [])


if __name__ == "__main__":
    unittest.main()
