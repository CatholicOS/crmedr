import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import mentioned_persons as mp  # noqa: E402

A, B = "mr:0101-a", "mr:0102-b"
LA = {A: "Romæ sancti Fictitii, quem Ambrósius, epíscopus Mediolanénsis, baptizávit.",
      B: "Fictopoli sancti Alii."}
IT = {A: "A Roma san Fictizio, battezzato da Ambrogio, vescovo di Milano.", B: "A Fictopoli sant'Alio."}
NOTES = {A: ["Vide Ambrósium."]}
SOURCES = {"la": (LA, NOTES), "it": (IT, {})}
PERSONS = {A: [{"name": "Fictitius", "where": "text"}], B: [{"name": "Alius", "where": "text", "role": "mentioned"}]}


def mark(src, phrase, **kw):
    s = src.index(phrase)
    return {"kind": "person", "where": "text", "start": s, "end": s + len(phrase), "name": "Fictitius", **kw}


MENTIONS = {"la": {A: [mark(LA[A], "Fictitii")]}, "it": {A: [mark(IT[A], "Fictizio")]}}


def prop(**kw):
    return {"name": "Ambrosius", "where": "text", "la": ["Ambrósius, epíscopus Mediolanénsis"],
            "it": ["Ambrogio, vescovo di Milano"], "who": "Bishop of Milan", "kind": "saint"} | kw


def run(proposals, mentions=MENTIONS):
    return mp.check_proposals(proposals, SOURCES, PERSONS, mentions)


class CheckTest(unittest.TestCase):
    def test_a_good_proposal_passes(self):
        self.assertEqual(run({A: [prop()]}), [])

    def test_a_footnote_phrase(self):
        self.assertEqual(run({A: [prop(where={"footnote": 1}, la=["Ambrósium"], it=[])]}), [])

    def test_phrase_not_found(self):
        out = run({A: [prop(la=["Augustínus"])]})
        self.assertEqual(len(out), 1)
        self.assertIn("Augustínus", out[0])

    def test_phrase_not_found_in_its_where(self):
        self.assertTrue(run({A: [prop(where={"footnote": 1})]}))

    def test_whole_words_only(self):
        self.assertTrue(run({A: [prop(la=["Ambrós"], it=[])]}))

    def test_missing_footnote(self):
        self.assertTrue(run({A: [prop(where={"footnote": 3})]}))

    def test_phrase_overlapping_a_commemorated_mark(self):
        out = run({A: [prop(la=["sancti Fictitii"], it=[])]})
        self.assertEqual(len(out), 1)
        self.assertIn("overlaps", out[0])

    def test_italian_overlap(self):
        out = run({A: [prop(la=["Ambrósius"], it=["san Fictizio"])]})
        self.assertEqual(len(out), 1)
        self.assertIn("(it)", out[0])

    def test_a_place_mark_inside_the_span_is_allowed(self):
        mentions = {"la": {A: [{"kind": "place", "where": "text", "start": LA[A].index("Mediolanénsis"),
                                "end": LA[A].index("Mediolanénsis") + 13, "qid": "Q490"}]}, "it": {}}
        self.assertEqual(run({A: [prop()]}, mentions), [])

    def test_a_mentioned_mark_does_not_block(self):
        mentions = {"la": {A: [mark(LA[A], "Ambrósius", role="mentioned")]}, "it": {}}
        self.assertEqual(run({A: [prop()]}, mentions), [])

    def test_excluded_names(self):
        for name in ("Christus", "Iesus", "Dominus", "Deus", "Spiritus Sanctus", "Trinitas", "Maria Virgo"):
            out = run({A: [prop(name=name)]})
            self.assertTrue(any("excluded" in o for o in out), name)

    def test_maria_is_excluded_only_for_the_virgin(self):
        self.assertTrue(any("excluded" in o for o in run({A: [prop(name="Maria", who="the Virgin Mary")]})))
        self.assertFalse(any("excluded" in o for o in run({A: [prop(name="Maria", who="Mary of Egypt")]})))

    def test_already_a_person_of_the_eulogy(self):
        out = run({A: [prop(name="Fictítius")]})
        self.assertTrue(any("already a person" in o for o in out))
        self.assertFalse(any("already a person" in o for o in run({A: [prop(name="Fictitius", n=2)]})))

    def test_two_eulogies_are_checked_independently(self):
        out = run({A: [prop()], B: [prop(la=["Ambrósius"], it=[])]})
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0].startswith(B))

    def test_shape_errors(self):
        out = run({A: [prop(kind="angel", who="")]})
        self.assertEqual(len(out), 2)
        self.assertTrue(run({A: [{k: v for k, v in prop().items() if k != "it"}]}))


class BriefTest(unittest.TestCase):
    REGISTRY = {"entries": [{"id": A, "month": 1}, {"id": "mr:0101-old", "month": 1, "deprecated": True},
                            {"id": B, "month": 2}]}

    def test_brief_of_a_month(self):
        persons = {"la": {A: PERSONS[A]}, "it": {}}
        out = mp.build_brief(1, self.REGISTRY, SOURCES, persons, MENTIONS | {"it": MENTIONS["it"]})
        self.assertEqual([e["id"] for e in out], [A])
        e = out[0]
        self.assertEqual((e["la"], e["la_footnotes"], e["it"]), (LA[A], NOTES[A], IT[A]))
        self.assertEqual(e["persons"], [{"name": "Fictitius", "n": 1, "role": "commemorated"}])
        s = LA[A].index("Fictitii")
        self.assertEqual(e["marks"]["la"], [["person", "text", s, s + 8, "Fictitii"]])

    def test_brief_refuses_a_git_work_tree(self):
        with tempfile.TemporaryDirectory() as d:
            subprocess.run(["git", "init", "-q", d], check=True)
            r = subprocess.run([sys.executable, str(Path(mp.__file__)), "brief", "1", d, str(Path(d) / "b.json")],
                               capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("git work tree", r.stderr)
            self.assertFalse((Path(d) / "b.json").exists())


if __name__ == "__main__":
    unittest.main()
