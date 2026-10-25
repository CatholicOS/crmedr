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
    return {"schema": "crmedr-changeset/v1", "operations": list(ops)}


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


LABELS = {"la": "Sanctus A Nova", "en": "Saint A the New", "it": "Sant’A Nuova"}


def relabel(mrid="mr:0101-a", decision="accept", edited=None, labels=LABELS):
    current = {"la": "Sanctus A", "en": None, "it": None}
    return {"op": "relabel", "id": mrid, "uid": "labels:" + mrid, "current": current, "labels": labels,
            "candidates": [{"labels": labels, "from_id": "mr:0101-a-x"}, {"labels": current, "from_id": None}],
            "decision": decision, "edited": edited}


class RelabelsTest(unittest.TestCase):
    def test_relabel_overrides(self):
        self.assertEqual(ar.renames(cs(op(), relabel())), [R("mr:0101-a", "mr:0101-a-x", **LABELS)])
        edited = {"labels": {"la": "Sanctus A Edita", "en": "Saint A", "it": ""}}
        self.assertEqual(ar.relabels(cs(relabel(decision="edit", edited=edited))),
                         {"mr:0101-a": {"la": "Sanctus A Edita", "en": "Saint A", "it": None}})
        # the relabel wins over the rename's edited subject too
        e = {"new_id": "mr:0101-a-y", "subject_la": "Sanctus A abbas"}
        self.assertEqual(ar.renames(cs(relabel(), op(decision="edit", edited=e))),
                         [R("mr:0101-a", "mr:0101-a-y", **LABELS)])

    def test_reject_keeps_current(self):
        self.assertEqual(ar.relabels(cs(relabel(decision="reject"))), {"mr:0101-a": R("", "").labels})
        self.assertEqual(ar.renames(cs(op(), relabel(decision="reject"))), [R("mr:0101-a", "mr:0101-a-x")])

    def test_undecided_relabel_keeps_rename_labels(self):
        self.assertEqual(ar.relabels(cs(relabel(decision=None))), {})
        self.assertEqual(ar.renames(cs(op(), relabel(decision=None))),
                         [R("mr:0101-a", "mr:0101-a-x", la="Sanctus A X", en="Saint A X")])

    def test_relabel_only(self):
        self.assertEqual(ar.relabel_only(cs(op(decision="reject"), relabel(), relabel("mr:0101-b", "reject"),
                                            op("mr:0101-c", "mr:0101-c-x"), relabel("mr:0101-c"))),
                         [R("mr:0101-a", "mr:0101-a", **LABELS)])


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

    def test_deprecated_old_id(self):
        self.assertEqual(ar.check([R("mr:0101-c", "mr:0101-c-x")], self.IDS, {"mr:0101-c"}),
                         ["mr:0101-c → mr:0101-c-x: deprecated IDs are not renamed"])

    def test_no_registry_skips_registry_checks(self):
        self.assertEqual(ar.check([R("mr:0101-zz", "mr:0101-taken")]), [])
        self.assertEqual(ar.check([R("mr:0101-zz", "mr:0102-zz")]), ["mr:0101-zz → mr:0102-zz: the day changes"])

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

    def test_per_eulogy_gazetteer_key(self):
        text = '{"ecclésiam Sancti Petri@mr:0101-basilius": {}, "x@mr:0101-basilius-magnus": {}}'
        self.assertEqual(ar.rekey_text(text, self.M),
                         ('{"ecclésiam Sancti Petri@mr:0101-basilius-x": {}, "x@mr:0101-basilius-magnus": {}}', 1))

    def test_longer_and_prose_untouched(self):
        text = '["mr:0101-basilius-magnus", "see mr:0101-basilius in", "xmr:0101-basilius"]'
        self.assertEqual(ar.rekey_text(text, self.M), (text, 0))

    def test_prose_standalone_ids(self):
        text = '{"mr:0101-basilius": "(mr:0101-basilius) mr:0101-basilius-magnus x:mr:0101-basilius mr:0101-basilius."}'
        self.assertEqual(ar.rekey_text(text, self.M, prose=True),
                         ('{"mr:0101-basilius-x": "(mr:0101-basilius-x) mr:0101-basilius-magnus '
                          'x:mr:0101-basilius mr:0101-basilius-x."}', 3))

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


def commit(repo):
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(git + ["commit", "-qm", "init"], cwd=repo, check=True)


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
        (r / "scripts" / "rules.py").write_text('OVERRIDES = {"mr:0101-b": "x"}  # mr:0101-b\n')
        (r / "scripts" / "apply_renames.py").write_text('EXAMPLE = "mr:0101-a"\n')
        (r / "tests").mkdir()
        (r / "tests" / "test_x.py").write_text('IDS = [\n    "mr:0101-b",\n]\n')
        commit(r)
        self.wip = r / "data" / "wip.json"
        dump(self.wip, {"mr:0101-a": 1})
        t = self.texts
        for ed in ar.EDITIONS:
            dump(t / "data" / "editions" / ed / "01.json", {"mr:0101-a": "t", "z": ["mr:0101-b"], "mr:0101-b": "u"})
        dump(t / "data" / "editions" / ar.EDITIONS[0] / "footnotes.json", {"mr:0101-a": ["f"]})
        (t / "tests").mkdir(parents=True)
        (t / "tests" / "test_registry_keys.py").write_text('EN_UNTRANSLATED = {\n    "mr:0101-a",\n}\n')
        (t / "README.md").write_text("Example: mr:0101-b.\n")
        commit(t)
        self.texts_wip = t / "data" / "editions" / ar.EDITIONS[0] / "02.json"
        dump(self.texts_wip, {"mr:0101-a": "wip"})
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
        # the subject left as it was, its prose ID re-keyed
        self.assertEqual(json.loads((self.root / "i18n" / "en.json").read_text())["mr:0101-a-x"], "en mr:0101-a-x")
        self.assertEqual(json.loads((self.root / "i18n" / "it.json").read_text())["mr:0101-a-x"], "Sant'A X")
        self.assertEqual(json.loads((self.root / "i18n" / "la.json").read_text())["mr:0101-b-y"], "Sanctus B Y")
        self.assertIn('"mr:0101-a-x": "n"', (self.root / "scripts" / "extract_registry.py").read_text())
        self.assertEqual(json.loads(self.wip.read_text()), {"mr:0101-a": 1})
        self.assertEqual(rep.files[str(self.root / "data" / "typology.json")], 2)
        self.assertEqual([c[1] for c in fake.calls], ["scripts/extract_registry.py", "-m"])

    def test_relabel_without_rename(self):
        doc = cs(op("mr:0101-a", "mr:0101-a-x", decision=None), relabel("mr:0101-a"),
                 op("mr:0101-b", "mr:0101-b-z", "edit", {"new_id": "mr:0101-b-y"},
                    cands=self.cs["operations"][1]["candidates"]),
                 relabel("mr:0101-b", labels={"la": "Sanctus B Novus", "en": None, "it": "San B"}))
        fake = Fake()
        rep = ar.apply_crmedr(doc, self.root, False, run=fake)
        self.assertTrue(rep.ok, rep.errors)
        self.assertEqual(([r.old for r in rep.applied], [r.old for r in rep.relabeled]), (["mr:0101-b"], ["mr:0101-a"]))
        read = lambda lang: json.loads((self.root / "i18n" / f"{lang}.json").read_text())  # noqa: E731
        self.assertEqual([read(lang)["mr:0101-a"] for lang in ("la", "en", "it")],
                         ["Sanctus A Nova", "Saint A the New", "Sant’A Nuova"])  # under the current ID
        self.assertEqual([read(lang)["mr:0101-b-y"] for lang in ("la", "en", "it")],
                         ["Sanctus B Novus", "en mr:0101-b-y", "San B"])  # the relabel's, not the candidate's
        self.assertIn("relabeled: mr:0101-a", ar.render(rep, self.root))
        # a relabel alone still rebuilds and tests
        fake = Fake()
        rep = ar.apply_crmedr(cs(relabel("mr:0101-a", labels={"la": "Sanctus A", "en": None, "it": None})),
                              self.root, False, run=fake)
        self.assertTrue(rep.ok, rep.errors)
        self.assertEqual(read("la")["mr:0101-a"], "Sanctus A")
        self.assertEqual([c[1] for c in fake.calls], ["scripts/extract_registry.py", "-m"])

    def test_relabel_of_an_unknown_or_deprecated_id_is_an_error(self):
        before = self.snapshot()
        rep = ar.apply_crmedr(cs(relabel("mr:0101-zz"), relabel("mr:0101-old")), self.root, False, run=Fake())
        self.assertEqual(rep.errors, ["mr:0101-zz: relabel of no such ID",
                                      "mr:0101-old: deprecated IDs are not relabeled"])
        self.assertEqual(self.snapshot(), before)

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
        self.assertEqual(len(rep.files), 5)
        for ed in ar.EDITIONS:
            d = json.loads((self.texts / "data" / "editions" / ed / "01.json").read_text())
            self.assertEqual(d, {"mr:0101-a-x": "t", "z": ["mr:0101-b-y"], "mr:0101-b-y": "u"})
        self.assertIn('"mr:0101-a-x",', (self.texts / "tests" / "test_registry_keys.py").read_text())
        self.assertEqual(json.loads(self.texts_wip.read_text()), {"mr:0101-a": "wip"})  # untracked
        self.assertEqual(rep.leftovers, ("README.md:1",))

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

    def test_regenerators_run_in_order_with_texts_path(self):
        fake = Fake()
        rep = ar.apply_crmedr(self.cs, self.root, False, run=fake, regenerate="/the/texts")
        self.assertTrue(rep.ok, rep.errors)
        self.assertEqual([c[1] for c in fake.calls],
                         ["scripts/extract_registry.py", "scripts/extract_typology.py", "scripts/extract_places.py",
                          "scripts/registry_places.py", "scripts/extract_persons.py", "scripts/extract_mentions.py", "-m"])
        for c in fake.calls[1:3] + fake.calls[4:6]:
            self.assertEqual(c[2], "/the/texts")
        self.assertIn("--review", fake.calls[5])
        self.assertFalse(Path(fake.calls[5][-1]).is_relative_to(self.root))

    def test_regenerated_typology_that_differs_fails(self):
        typology = self.root / "data" / "typology.json"

        class Changing(Fake):
            def __call__(self, cmd, **kw):
                if cmd[1] == "scripts/extract_typology.py":
                    typology.write_text("{}\n")
                return super().__call__(cmd, **kw)

        fake = Changing()
        rep = ar.apply_crmedr(self.cs, self.root, False, run=fake, regenerate="/the/texts")
        self.assertFalse(rep.ok)
        self.assertIn("data/typology.json changed after regeneration", rep.errors[0])
        self.assertNotIn("scripts/extract_persons.py", [c[1] for c in fake.calls])

    def test_regeneration_compares_with_the_rekeyed_file(self):
        fake = Fake()  # leaves the re-keyed typology as it is: no difference
        rep = ar.apply_crmedr(self.cs, self.root, False, run=fake, regenerate="/the/texts")
        self.assertEqual(rep.errors, [])

    def test_texts_edition_folder_without_files_is_an_error(self):
        for f in (self.texts / "data" / "editions" / ar.EDITIONS[2]).glob("*.json"):
            f.unlink()
        before = (self.texts / "data" / "editions" / ar.EDITIONS[0] / "01.json").read_bytes()
        rep = ar.apply_texts(self.cs, self.texts, self.root, False)
        self.assertFalse(rep.ok)
        self.assertIn(ar.EDITIONS[2], rep.errors[0])
        self.assertEqual((self.texts / "data" / "editions" / ar.EDITIONS[0] / "01.json").read_bytes(), before)

    def test_main_missing_arguments_print_usage(self):
        for argv in (["crmedr"], ["texts", "x.json"], ["crmedr", "--dry-run"], ["crmedr", "--regenerate"]):
            with self.assertRaises(SystemExit) as cm:
                ar.main(argv)
            self.assertEqual(cm.exception.code, ar.__doc__)

    def test_texts_judges_by_its_own_keys_not_the_registry(self):
        # crmedr already applied: the registry names the new IDs, the texts still the old ones
        ids = self.root / "data" / "martyrology_ids.json"
        ids.write_text(ids.read_text().replace('mr:0101-a"', 'mr:0101-a-x"').replace('mr:0101-b"', 'mr:0101-b-y"'))
        rep = ar.apply_texts(self.cs, self.texts, self.root / "nowhere", False)
        self.assertTrue(rep.ok, rep.errors)
        self.assertEqual((len(rep.applied), len(rep.skipped)), (2, 0))
        again = ar.apply_texts(self.cs, self.texts, self.root, False)
        self.assertTrue(again.ok, again.errors)
        self.assertEqual((len(again.applied), len(again.skipped), again.files), (0, 2, {}))

    def test_texts_neither_id_a_key_or_both_are_errors(self):
        f = self.texts / "data" / "editions" / ar.EDITIONS[0] / "01.json"
        before = f.read_bytes()
        rep = ar.apply_texts(cs(op("mr:0101-zz", "mr:0101-zz-x"), op("mr:0101-a", "mr:0101-b")),
                             self.texts, self.root, False)
        self.assertEqual(rep.errors, ["mr:0101-zz → mr:0101-zz-x: neither ID is a key of the 2004 editions",
                                      "mr:0101-a → mr:0101-b: mr:0101-b is already a key of the 2004 editions"])
        self.assertEqual(f.read_bytes(), before)

    def test_texts_checks_still_run(self):
        rep = ar.apply_texts(cs(op("mr:0101-a", "mr:0102-a-x", cands=[])), self.texts, self.root, False)
        self.assertEqual(rep.errors, ["mr:0101-a → mr:0102-a-x: the day changes"])

    def test_crmedr_rekeys_scripts_quoted_only_not_itself_nor_tests(self):
        rep = ar.apply_crmedr(self.cs, self.root, False, run=Fake())
        self.assertTrue(rep.ok, rep.errors)
        s = self.root / "scripts"
        self.assertEqual((s / "rules.py").read_text(), 'OVERRIDES = {"mr:0101-b-y": "x"}  # mr:0101-b\n')
        self.assertEqual((s / "apply_renames.py").read_text(), 'EXAMPLE = "mr:0101-a"\n')
        self.assertEqual((self.root / "tests" / "test_x.py").read_text(), 'IDS = [\n    "mr:0101-b",\n]\n')

    def test_a_script_that_would_not_compile_writes_nothing(self):
        (self.root / "scripts" / "rules.py").write_text('X = "mr:0101-b" +\n')  # already broken
        before = self.snapshot()
        rep = ar.apply_crmedr(self.cs, self.root, False, run=Fake())
        self.assertFalse(rep.ok)
        self.assertIn("rules.py", rep.errors[0])
        self.assertEqual(self.snapshot(), before)

    def test_crmedr_rekeys_prose_ids_in_data_i18n_and_extract_registry(self):
        ids = self.root / "data" / "martyrology_ids.json"
        doc = json.loads(ids.read_text())
        doc["entries"][2]["note"] = "Same eulogy as (mr:0101-a); not mr:0101-a-magnus nor x:mr:0101-a."
        dump(ids, doc)
        reg = self.root / "scripts" / "extract_registry.py"
        reg.write_text('ENTRY_NOTES = {\n    "mr:0101-a": "see mr:0101-b.",\n}\n')
        rep = ar.apply_crmedr(self.cs, self.root, False, run=Fake())
        self.assertTrue(rep.ok, rep.errors)
        self.assertEqual(json.loads(ids.read_text())["entries"][2]["note"],
                         "Same eulogy as (mr:0101-a-x); not mr:0101-a-magnus nor x:mr:0101-a.")
        self.assertEqual(reg.read_text(), 'ENTRY_NOTES = {\n    "mr:0101-a-x": "see mr:0101-b-y.",\n}\n')

    def test_scan_lists_tracked_files_not_rekeyed(self):
        rep = ar.apply_crmedr(self.cs, self.root, True, run=Fake())
        self.assertTrue(rep.ok, rep.errors)
        # scripts/rules.py is re-keyed for quoted IDs only: its comment naming the old ID is listed.
        self.assertEqual(rep.leftovers, ("scripts/apply_renames.py:1", "scripts/rules.py:1", "tests/test_x.py:2"))
        out = ar.render(rep, self.root)
        self.assertIn("still naming an old ID", out)
        self.assertIn("  tests/test_x.py:2", out)

    def person_review(self, *ids):
        dump(self.root / "data" / "person_items_review.json",
             cs(*[{"op": "resolve_person", "id": i, "eulogy": i.split("|")[0]} for i in ids]))

    def with_person(self, decision="accept", eulogy="mr:0101-a"):
        return cs(*self.cs["operations"],
                  {"op": "resolve_person", "id": f"{eulogy}|A", "eulogy": eulogy, "decision": decision})

    def test_an_unreadable_person_review_is_an_error_not_a_traceback(self):
        (self.root / "data" / "person_items_review.json").write_text("{not json", encoding="utf-8")
        rep = ar.apply_crmedr(self.with_person(), self.root, True, run=Fake())
        self.assertFalse(rep.ok)
        self.assertIn("person_items_review.json: not a readable crmedr-changeset", rep.errors[0])

    def test_queued_person_decision_on_renamed_eulogy_refuses(self):
        self.person_review("mr:0101-a|A")
        before = self.snapshot()
        for dry in (True, False):
            rep = ar.apply_crmedr(self.with_person(), self.root, dry, run=Fake())
            self.assertFalse(rep.ok)
            self.assertIn("mr:0101-a|A", rep.errors[0])
            self.assertIn("run `python3 scripts/build_person_items.py apply <decided.json>` first", rep.errors[0])
        self.assertEqual(self.snapshot(), before)

    def test_person_decision_applied_undecided_or_not_renamed_passes(self):
        self.person_review("mr:0101-a|A", "mr:0101-c|A")
        for decided in (self.with_person(None), self.with_person(eulogy="mr:0101-c")):
            self.assertTrue(ar.apply_crmedr(decided, self.root, True, run=Fake()).ok)
        self.person_review()  # applied: no longer queued
        self.assertTrue(ar.apply_crmedr(self.with_person(), self.root, True, run=Fake()).ok)

    def test_not_a_changeset_is_an_error(self):
        bad = [{"schema": "crmedr-changeset/v1", "ops": self.cs["operations"]},
               {"schema": "other", "operations": self.cs["operations"]}, []]
        for doc in bad:
            self.assertFalse(ar.apply_crmedr(doc, self.root, True, run=Fake()).ok)
            self.assertFalse(ar.apply_texts(doc, self.texts, self.root, True).ok)
        self.assertEqual(ar.apply_crmedr(bad[0], self.root, True).errors,
                         ["the change-set has no operations list"])
        self.assertEqual(ar.apply_crmedr(bad[1], self.root, True).errors, ["not a crmedr-changeset/v1 document"])

    def test_deprecated_old_id_is_an_error(self):
        rep = ar.apply_crmedr(cs(op("mr:0101-old", "mr:0101-old-x", cands=[])), self.root, True, run=Fake())
        self.assertEqual(rep.errors, ["mr:0101-old → mr:0101-old-x: deprecated IDs are not renamed"])

    def test_texts_outside_a_git_work_tree_is_an_error(self):
        rep = ar.apply_texts(self.cs, self.root.parent / "nowhere", self.root, True)
        self.assertFalse(rep.ok)
        self.assertIn("not a git work tree", rep.errors[0])

    def test_render_lists_renames_and_next_steps(self):
        out = ar.render(ar.apply_crmedr(self.cs, self.root, False, run=Fake()), self.root)
        self.assertIn("mr:0101-a → mr:0101-a-x", out)
        self.assertIn("test_registry_keys.py", out)
        self.assertIn("docs/*-report.md", out)
        self.assertIn("npm run snapshot-registry", out)
        self.assertIn("CRMEDR_REF", out)
        self.assertIn("build_person_items.py apply, texts, crmedr", out)
        out = ar.render(ar.apply_texts(self.cs, self.texts, self.root, True))
        self.assertIn("apply_renames.py crmedr", out)


if __name__ == "__main__":
    unittest.main()
