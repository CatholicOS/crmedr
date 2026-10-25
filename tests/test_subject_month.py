import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import subject_month as sm  # noqa: E402


def doc(*ops, generated_at="t"):
    return {"schema": "crmedr-changeset/v1", "generated_by": "g", "generated_at": generated_at,
            "base": "b", "operations": list(ops)}


def rename(mrid, **kw):
    return {"op": "rename", "uid": f"subject:{mrid}", "id": mrid, **kw}


class MergeTest(unittest.TestCase):
    def test_decided_and_prefilled_kept(self):
        a = rename("m1", decision="accept", note="old")
        b = rename("m2", prefilled="rule", decision=None)
        c = {"op": "resolve_person", "id": "m3|Ann", "decision": "reject"}
        old = doc(a, b, c)
        new = doc(rename("m1", note="new"), rename("m2", note="new"),
                  {"op": "resolve_person", "id": "m3|Ann", "note": "new"}, generated_at="t2")
        out, notes = sm.merge(old, new)
        self.assertEqual(out["generated_at"], "t2")
        self.assertEqual([json.dumps(o) for o in out["operations"]],
                         [json.dumps(o) for o in (a, b, c)])
        self.assertEqual(notes, [])

    def test_undecided_rebuilt(self):
        old = doc(rename("m1"), rename("m2", decision=None))
        new = doc(rename("m1", note="new"), rename("m2", note="new"))
        out, _ = sm.merge(old, new)
        self.assertEqual(out["operations"], new["operations"])

    def test_uid_distinguishes_same_id(self):
        old = doc(rename("m1", decision="accept"), {"op": "relabel", "uid": "labels:m1", "id": "m1"})
        new = doc(rename("m1"), {"op": "relabel", "uid": "labels:m1", "id": "m1", "n": 2})
        out, _ = sm.merge(old, new)
        self.assertEqual(out["operations"][0]["decision"], "accept")
        self.assertEqual(out["operations"][1]["n"], 2)

    def test_new_ops_appended(self):
        old = doc(rename("m2"), rename("m1"))
        new = doc(rename("m3"), rename("m1"), rename("m4"), rename("m2"))
        out, _ = sm.merge(old, new)
        self.assertEqual([o["id"] for o in out["operations"]], ["m2", "m1", "m3", "m4"])

    def test_missing_ids(self):
        old = doc(rename("m1"), rename("m2", decision="edit"), rename("m3", prefilled="jev"),
                  rename("m4"))
        with self.assertRaises(ValueError) as cm:
            sm.merge(old, doc(rename("m4")))
        self.assertIn("subject:m2", str(cm.exception))
        self.assertIn("subject:m3", str(cm.exception))
        out, notes = sm.merge(doc(rename("m1"), rename("m2")), doc(rename("m1")))
        self.assertEqual([o["id"] for o in out["operations"]], ["m1"])
        self.assertEqual(len(notes), 1)
        self.assertIn("subject:m2", notes[0])


CURRENT = {"la": "Sanctus Felix", "en": "Saint Felix", "it": "San Felice"}
ROMA = {"la": "Sanctus Felix Romanus", "en": "Saint Felix of Rome", "it": "San Felice di Roma"}
NOLA = {"la": "Sanctus Felix Nolanus", "en": "Saint Felix of Nola", "it": "San Felice di Nola"}


def named(decision, edited=None, **kw):
    return rename("m1", new_id="felix-romanus", decision=decision, edited=edited, candidates=[
        {"new_id": "felix-romanus", "labels": ROMA}, {"new_id": "felix-nolanus", "labels": NOLA},
        {"new_id": "felix-presbyter", "labels": None}], **kw)


def relabel(labels=ROMA, *others):
    return {"op": "relabel", "uid": "labels:m1", "id": "m1", "current": CURRENT, "labels": labels,
            "candidates": [{"labels": labels, "from_id": "x"}] + [{"labels": o, "from_id": "y"} for o in others]
            + [{"labels": CURRENT, "from_id": None}], "decision": None, "edited": None}


class RelabelFollowsRenameTest(unittest.TestCase):
    def merged(self, rename_op, rebuilt_relabel):
        out, notes = sm.merge(doc(rename_op, relabel()), doc(rename("m1"), rebuilt_relabel))
        return out["operations"][1], notes

    def test_accept_puts_the_accepted_labels_first(self):
        op, notes = self.merged(named("accept"), relabel(NOLA, ROMA))
        self.assertEqual(op["labels"], ROMA)
        self.assertEqual([c["labels"] for c in op["candidates"]], [ROMA, NOLA, CURRENT])
        self.assertEqual(op["candidates"][0]["from_id"], "felix-romanus")
        self.assertEqual(notes, [])

    def test_edit_and_prefilled(self):
        op, _ = self.merged(named("edit", {"new_id": "felix-nolanus"}), relabel(ROMA))
        self.assertEqual(op["labels"], NOLA)
        self.assertEqual([c["labels"] for c in op["candidates"]], [NOLA, ROMA, CURRENT])
        op, _ = self.merged(named("edit", {"new_id": "felix-nolanus"}, prefilled="rule"), relabel(ROMA))
        self.assertEqual(op["labels"], NOLA)

    def test_reject_proposes_the_current_labels(self):
        op, _ = self.merged(named("reject"), relabel(ROMA, NOLA))
        self.assertEqual(op["labels"], CURRENT)
        self.assertEqual([c["labels"] for c in op["candidates"]], [ROMA, NOLA, CURRENT])

    def test_a_chosen_candidate_without_labels_leaves_the_relabel(self):
        rebuilt = relabel(NOLA)
        op, notes = self.merged(named("edit", {"new_id": "felix-presbyter"}), rebuilt)
        self.assertEqual(op, relabel(NOLA))
        self.assertEqual(len(notes), 1)
        self.assertIn("labels:m1", notes[0])

    def test_undecided_rename_or_decided_relabel_unchanged(self):
        out, _ = sm.merge(doc(named(None), relabel()), doc(named(None), relabel(NOLA)))
        self.assertEqual(out["operations"][1]["labels"], NOLA)
        kept = dict(relabel(NOLA), decision="accept")
        out, _ = sm.merge(doc(named("accept"), kept), doc(rename("m1"), relabel(ROMA)))
        self.assertEqual(out["operations"][1], kept)


class CliTest(unittest.TestCase):
    def test_cli_writes_and_refuses_repository(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "o.json").write_text(json.dumps(doc(rename("m1", decision="accept"))))
            (d / "r.json").write_text(json.dumps(doc(rename("m1"), rename("m2"))))
            with contextlib.redirect_stdout(io.StringIO()) as buf:
                sm.main(["merge", str(d / "o.json"), str(d / "r.json"), str(d / "out.json")])
            out = json.loads((d / "out.json").read_text())
            self.assertEqual([o["id"] for o in out["operations"]], ["m1", "m2"])
            self.assertIn("kept 1", buf.getvalue())
            repo = Path(__file__).resolve().parent.parent
            with self.assertRaises(SystemExit):
                sm.main(["merge", str(d / "o.json"), str(d / "r.json"), str(repo / "x.json")])
            self.assertFalse((repo / "x.json").exists())


if __name__ == "__main__":
    unittest.main()
