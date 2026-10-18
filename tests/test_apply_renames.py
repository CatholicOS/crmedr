import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import apply_renames as ar  # noqa: E402

CANDS = [
    {"new_id": "mr:0101-a-x", "category": "c", "labels": {"la": "Sanctus A X", "en": "Saint A X", "it": None}},
    {"new_id": "mr:0101-a-y", "category": "c", "labels": {"la": "Sanctus A Y", "en": None, "it": "Sant’A Y"}},
]


def op(old="mr:0101-a", new="mr:0101-a-x", decision="accept", edited=None, cands=CANDS):
    return {"op": "rename", "id": old, "new_id": new, "uid": "subject:" + old, "candidates": cands,
            "subject_la": "Sanctus A", "decision": decision, "edited": edited}


def cs(*ops):
    return {"schema": "crmedr-changeset/v1", "ops": list(ops)}


def R(old, new, **labels):
    return ar.Rename(old, new, {"la": None, "en": None, "it": None} | labels)


class RenamesTest(unittest.TestCase):
    def test_accept_takes_candidate_labels(self):
        self.assertEqual(ar.renames(cs(op())),
                         [R("mr:0101-a", "mr:0101-a-x", la="Sanctus A X", en="Saint A X")])

    def test_reject_null_and_other_ops_skipped(self):
        other = {"op": "add_place", "decision": "accept"}
        self.assertEqual(ar.renames(cs(op(decision="reject"), op(decision=None), other)), [])

    def test_edit_new_id_among_candidates_with_subject(self):
        e = {"new_id": "mr:0101-a-y", "subject_la": "Sanctus A abbas"}
        self.assertEqual(ar.renames(cs(op(decision="edit", edited=e))),
                         [R("mr:0101-a", "mr:0101-a-y", la="Sanctus A abbas", it="Sant’A Y")])

    def test_edit_empty_subject_keeps_candidate_la(self):
        e = {"new_id": "mr:0101-a-y", "subject_la": ""}
        self.assertEqual(ar.renames(cs(op(decision="edit", edited=e)))[0].labels["la"], "Sanctus A Y")

    def test_edit_only_subject_keeps_op_new_id(self):
        e = {"subject_la": "Sanctus A abbas"}
        self.assertEqual(ar.renames(cs(op(decision="edit", edited=e))),
                         [R("mr:0101-a", "mr:0101-a-x", la="Sanctus A abbas", en="Saint A X")])

    def test_edit_id_not_a_candidate_has_no_labels(self):
        e = {"new_id": "mr:0101-a-z"}
        self.assertEqual(ar.renames(cs(op(decision="edit", edited=e))), [R("mr:0101-a", "mr:0101-a-z")])
        e = {"new_id": "mr:0101-a-z", "subject_la": "Sanctus Z"}
        self.assertEqual(ar.renames(cs(op(decision="edit", edited=e))),
                         [R("mr:0101-a", "mr:0101-a-z", la="Sanctus Z")])

    def test_file_order(self):
        rs = ar.renames(cs(op("mr:0102-b", "mr:0102-b-x", cands=[]), op()))
        self.assertEqual([r.old for r in rs], ["mr:0102-b", "mr:0101-a"])


class CheckTest(unittest.TestCase):
    IDS = {"mr:0101-a", "mr:0101-b", "mr:0101-taken", "mr:0101-c"}

    def errs(self, *rs):
        return ar.check(list(rs), self.IDS)

    def test_pass(self):
        self.assertEqual(self.errs(R("mr:0101-a", "mr:0101-a-x")), [])

    def test_day_changes(self):
        self.assertEqual(self.errs(R("mr:0101-a", "mr:0102-a-x")), ["mr:0101-a → mr:0102-a-x: the day changes"])

    def test_numeric_token(self):
        self.assertEqual(self.errs(R("mr:0101-a", "mr:0101-a-2")), ["mr:0101-a → mr:0101-a-2: a numeric token"])

    def test_already_exists(self):
        self.assertEqual(self.errs(R("mr:0101-a", "mr:0101-taken")),
                         ["mr:0101-a → mr:0101-taken: mr:0101-taken already exists"])

    def test_no_such_id(self):
        self.assertEqual(self.errs(R("mr:0101-zz", "mr:0101-zz-x")), ["mr:0101-zz → mr:0101-zz-x: no such ID"])

    def test_two_give_same(self):
        self.assertEqual(self.errs(R("mr:0101-a", "mr:0101-y"), R("mr:0101-b", "mr:0101-y")),
                         ["mr:0101-b → mr:0101-y: two renames give mr:0101-y"])

    def test_new_is_other_old(self):
        self.assertEqual(self.errs(R("mr:0101-a", "mr:0101-b"), R("mr:0101-b", "mr:0101-b-x")),
                         ["mr:0101-a → mr:0101-b: mr:0101-b already exists",
                          "mr:0101-a → mr:0101-b: mr:0101-b is renamed too"])

    def test_not_mr_form(self):
        self.assertEqual(self.errs(R("mr:0101-a", "mr:0101-A_x")), ["mr:0101-a → mr:0101-A_x: not mr:MMDD-slug"])
        self.assertEqual(self.errs(R("mr:0101-a", "mr:0101-")), ["mr:0101-a → mr:0101-: not mr:MMDD-slug"])


class SplitAppliedTest(unittest.TestCase):
    def test_split(self):
        done, todo = R("mr:0101-old", "mr:0101-new"), R("mr:0101-a", "mr:0101-a-x")
        ids = {"mr:0101-new", "mr:0101-a"}
        self.assertEqual(ar.split_applied([done, todo], ids), ([todo], [done]))

    def test_old_and_new_both_absent_stays_to_apply(self):
        r = R("mr:0101-old", "mr:0101-new")
        self.assertEqual(ar.split_applied([r], set()), ([r], []))


class RekeyTextTest(unittest.TestCase):
    M = {"mr:0101-basilius": "mr:0101-basilius-x"}

    def test_keys_values_and_pipe(self):
        text = '{"mr:0101-basilius": ["mr:0101-basilius", "mr:0101-basilius|Basilius"]}'
        self.assertEqual(ar.rekey_text(text, self.M),
                         ('{"mr:0101-basilius-x": ["mr:0101-basilius-x", "mr:0101-basilius-x|Basilius"]}', 3))

    def test_longer_and_prose_untouched(self):
        text = '["mr:0101-basilius-magnus", "see mr:0101-basilius in", "xmr:0101-basilius"]'
        self.assertEqual(ar.rekey_text(text, self.M), (text, 0))

    def test_empty_mapping(self):
        self.assertEqual(ar.rekey_text("abc", {}), ("abc", 0))


class FilesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    M = {"mr:0101-b": "mr:0101-b-x"}

    def test_json_format_kept_byte_for_byte(self):
        src = '{\n "mr:0101-b": [\n  1, 2, ["mr:0101-b"]\n ],\n "t":"mr:0101-b|Name" ,\n "u":[ ]\n}\n'
        p = self.dir / "f.json"
        p.write_text(src, encoding="utf-8")
        self.assertEqual(ar.rekey_file(p, self.M, "json", False), 3)
        self.assertEqual(p.read_text(encoding="utf-8"), src.replace("mr:0101-b", "mr:0101-b-x"))

    def test_dry_writes_nothing(self):
        src = '{"mr:0101-b": 1}'
        p = self.dir / "f.json"
        p.write_text(src, encoding="utf-8")
        self.assertEqual(ar.rekey_file(p, self.M, "json", True), 1)
        self.assertEqual(p.read_text(encoding="utf-8"), src)

    def test_python_notes_still_compile(self):
        p = self.dir / "n.py"
        p.write_text('NOTES = {\n    "mr:0101-b": "a note",\n}\n', encoding="utf-8")
        self.assertEqual(ar.rekey_file(p, self.M, "python", False), 1)
        self.assertIn('"mr:0101-b-x": "a note"', p.read_text(encoding="utf-8"))

    def test_failed_check_writes_nothing(self):
        src = '{"a": "mr:0101-b"'  # already invalid JSON
        p = self.dir / "bad.json"
        p.write_text(src, encoding="utf-8")
        with self.assertRaises(ValueError):
            ar.rekey_file(p, self.M, "json", False)
        self.assertEqual(p.read_text(encoding="utf-8"), src)

    def test_set_labels_curly_apostrophe(self):
        p = self.dir / "it.json"
        p.write_text(json.dumps({"mr:0101-b": "Old", "mr:0101-c": "Keep \"q\""}, indent=2, ensure_ascii=False) + "\n",
                     encoding="utf-8")
        self.assertEqual(ar.set_labels(p, {"mr:0101-b": "Sant’Eugendo, abate di Condat"}, False), 1)
        self.assertEqual(p.read_text(encoding="utf-8"),
                         '{\n  "mr:0101-b": "Sant’Eugendo, abate di Condat",\n  "mr:0101-c": "Keep \\"q\\""\n}\n')

    def test_set_labels_missing_id_is_error_and_dry(self):
        p = self.dir / "it.json"
        src = '{\n  "mr:0101-b": "Old"\n}\n'
        p.write_text(src, encoding="utf-8")
        with self.assertRaises(ValueError):
            ar.set_labels(p, {"mr:0101-zz": "X"}, False)
        self.assertEqual(ar.set_labels(p, {"mr:0101-b": "New"}, True), 1)
        self.assertEqual(p.read_text(encoding="utf-8"), src)


if __name__ == "__main__":
    unittest.main()
