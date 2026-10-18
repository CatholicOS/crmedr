import contextlib
import io
import json
import subprocess
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


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


class Fake:
    def __init__(self, code=0):
        self.code, self.calls = code, []

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        return subprocess.CompletedProcess(cmd, self.code)


class SubcommandsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "crmedr"
        self.texts = Path(tmp.name) / "texts"
        r = self.root
        entries = [{"id": "mr:0101-a"}, {"id": "mr:0101-b"}, {"id": "mr:0101-old", "deprecated": True}]
        dump(r / "data" / "martyrology_ids.json", {"entries": entries})
        for lang in ("la", "en", "it"):
            dump(r / "i18n" / f"{lang}.json", {e["id"]: f"{lang} {e['id']}" for e in entries})
        dump(r / "data" / "typology.json", {"typology": {"mr:0101-a": "x", "mr:0101-b": "y"}})
        (r / "scripts").mkdir()
        (r / "scripts" / "extract_registry.py").write_text('ENTRY_NOTES = {\n    "mr:0101-a": "n",\n}\n')
        git = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]
        subprocess.run(["git", "init", "-q"], cwd=r, check=True)
        subprocess.run(["git", "add", "."], cwd=r, check=True)
        subprocess.run(git + ["commit", "-qm", "init"], cwd=r, check=True)
        self.wip = r / "data" / "wip.json"
        dump(self.wip, {"mr:0101-a": 1})
        for ed in ar.EDITIONS:
            dump(self.texts / "data" / "editions" / ed / "01.json", {"mr:0101-a": "t", "z": ["mr:0101-b"]})
        dump(self.texts / "data" / "editions" / ar.EDITIONS[0] / "footnotes.json", {"mr:0101-a": ["f"]})
        cands = [{"new_id": "mr:0101-a-x", "labels": {"la": "Sanctus A X", "en": None, "it": "Sant'A X"}},
                 {"new_id": "mr:0101-b-y", "labels": {"la": "Sanctus B Y", "en": "Saint B Y", "it": None}}]
        self.cs = cs(op("mr:0101-a", "mr:0101-a-x", cands=cands),
                     op("mr:0101-b", "mr:0101-b-z", "edit", {"new_id": "mr:0101-b-y"}, cands=cands))

    def snapshot(self):
        return {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file() and ".git" not in p.parts}

    def test_crmedr_applies_accept_and_edit(self):
        fake = Fake()
        rep = ar.apply_crmedr(self.cs, self.root, False, run=fake)
        self.assertTrue(rep.ok, rep.errors)
        self.assertEqual(len(rep.applied), 2)
        self.assertEqual(json.loads((self.root / "i18n" / "en.json").read_text())["mr:0101-b-y"], "Saint B Y")
        self.assertEqual(json.loads((self.root / "i18n" / "en.json").read_text())["mr:0101-a-x"], "en mr:0101-a")
        self.assertEqual(json.loads((self.root / "i18n" / "it.json").read_text())["mr:0101-a-x"], "Sant'A X")
        self.assertEqual(json.loads((self.root / "i18n" / "la.json").read_text())["mr:0101-b-y"], "Sanctus B Y")
        self.assertIn('"mr:0101-a-x": "n"', (self.root / "scripts" / "extract_registry.py").read_text())
        self.assertEqual(json.loads(self.wip.read_text()), {"mr:0101-a": 1})
        self.assertEqual(rep.files[str(self.root / "data" / "typology.json")], 2)
        self.assertEqual([c[1] for c in fake.calls], ["scripts/extract_registry.py", "-m"])

    def test_failing_check_writes_nothing(self):
        before = self.snapshot()
        bad = cs(op("mr:0101-a", "mr:0101-a-x"), op("mr:0101-b", "mr:0102-b-x"))
        rep = ar.apply_crmedr(bad, self.root, False, run=Fake())
        self.assertFalse(rep.ok)
        self.assertEqual(self.snapshot(), before)

    def test_dry_run_writes_nothing(self):
        before = self.snapshot()
        fake = Fake()
        rep = ar.apply_crmedr(self.cs, self.root, True, run=fake)
        self.assertTrue(rep.ok, rep.errors)
        self.assertGreater(sum(rep.files.values()), 0)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(fake.calls, [])

    def test_second_run_is_already_applied(self):
        ids = self.root / "data" / "martyrology_ids.json"
        ar.apply_crmedr(self.cs, self.root, False, run=Fake())
        # the stub extract_registry does not rebuild the registry, so do it here
        ids.write_text(ids.read_text().replace("mr:0101-a\"", "mr:0101-a-x\"").replace("mr:0101-b\"", "mr:0101-b-y\""))
        before = self.snapshot()
        rep = ar.apply_crmedr(self.cs, self.root, False, run=Fake())
        self.assertTrue(rep.ok)
        self.assertEqual((len(rep.applied), len(rep.skipped)), (0, 2))
        self.assertEqual(self.snapshot(), before)

    def test_failed_run_makes_report_fail(self):
        rep = ar.apply_crmedr(self.cs, self.root, False, run=Fake(1))
        self.assertFalse(rep.ok)
        self.assertIn("failed", rep.errors[0])

    def test_non_string_label_value_is_an_error(self):
        dump(self.root / "i18n" / "it.json", {"mr:0101-a": None, "mr:0101-b": "x", "mr:0101-old": "x"})
        before = self.snapshot()
        rep = ar.apply_crmedr(self.cs, self.root, False, run=Fake())
        self.assertFalse(rep.ok)
        self.assertEqual(self.snapshot(), before)

    def test_texts_rekeys_three_editions(self):
        rep = ar.apply_texts(self.cs, self.texts, self.root, False)
        self.assertTrue(rep.ok, rep.errors)
        self.assertEqual(len(rep.files), 4)
        for ed in ar.EDITIONS:
            d = json.loads((self.texts / "data" / "editions" / ed / "01.json").read_text())
            self.assertEqual(d, {"mr:0101-a-x": "t", "z": ["mr:0101-b-y"]})

    def test_texts_dry_and_failed_check_write_nothing(self):
        f = self.texts / "data" / "editions" / ar.EDITIONS[0] / "01.json"
        before = f.read_bytes()
        self.assertTrue(ar.apply_texts(self.cs, self.texts, self.root, True).ok)
        self.assertFalse(ar.apply_texts(cs(op("mr:0101-zz", "mr:0101-zz-x")), self.texts, self.root, False).ok)
        self.assertEqual(f.read_bytes(), before)

    def test_main_exits_1_on_check_errors(self):
        decided = self.root.parent / "decided.json"
        decided.write_text(json.dumps(cs(op("mr:0101-zz", "mr:0101-zz-x"))), encoding="utf-8")
        with self.assertRaises(SystemExit) as cm, contextlib.redirect_stdout(io.StringIO()):
            ar.main(["crmedr", str(decided), str(self.root)])
        self.assertEqual(cm.exception.code, 1)

    def test_render_lists_renames_and_next_steps(self):
        out = ar.render(ar.apply_crmedr(self.cs, self.root, False, run=Fake()), self.root)
        self.assertIn("mr:0101-a → mr:0101-a-x", out)
        self.assertIn("test_registry_keys.py", out)


if __name__ == "__main__":
    unittest.main()
