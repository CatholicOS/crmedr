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


import urllib.parse  # noqa: E402

from wikidata import Wikidata  # noqa: E402
import mentions_jev as mj  # noqa: E402

C = "mr:1207-ambrosius"
ITEMS = {C: {"Ambrósius": {"wikidata": "Q1", "status": "auto"}},
         "mr:0404-ambrosius-x": {"Ambrosius": {"wikidata": "Q3", "status": "proposed"}}}
CAND_PERSONS = {C: [{"name": "Ambrósius", "where": "text"}],
                "mr:0404-ambrosius-x": [{"name": "Ambrosius", "where": "text"}],
                "mr:0405-y": [{"name": "Ambrosius", "where": "text", "role": "mentioned"}]}
COMMEMORATED = {"Q1": [C], "Q3": ["mr:0404-ambrosius-x"]}


def entity(qid, label, born=None):
    claims = {"P569": [{"mainsnak": {"datavalue": {"value": {"time": born, "precision": 9}}}}]} if born else {}
    return {"id": qid, "labels": {"en": {"value": label}}, "descriptions": {"en": {"value": f"about {label}"}},
            "claims": claims}


ENTITIES = {"Q1": entity("Q1", "Ambrose", "+0340-00-00T00:00:00Z"), "Q2": entity("Q2", "Ambrosius (name)"),
            "Q3": entity("Q3", "Another Ambrose")}


class FakeFetch:
    def __init__(self):
        self.searches = []

    def __call__(self, url):
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
        if q["action"] == "wbsearchentities":
            self.searches.append((q["search"], q["language"], q["limit"]))
            return {"search": [{"id": "Q2"}, {"id": "Q1"}]}
        return {"entities": {i: ENTITIES[i] for i in q["ids"].split("|")}}


class CandidatesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.fetch = FakeFetch()
        self.client = Wikidata(Path(self.tmp.name), fetch=self.fetch)

    def test_commemorated_route_comes_first(self):
        out = mp.build_candidates({A: [prop()]}, self.client, CAND_PERSONS, ITEMS, COMMEMORATED)
        cands = out[A][0]["candidates"]
        self.assertEqual([(c["wikidata"], c["route"]) for c in cands], [("Q1", "commemorated"), ("Q2", "search")])
        self.assertEqual(cands[0], {"wikidata": "Q1", "label": "Ambrose", "description": "about Ambrose",
                                    "born": 340, "died": None, "route": "commemorated", "eulogies": [C]})
        self.assertNotIn("eulogies", cands[1])
        self.assertEqual(self.fetch.searches, [("Ambrosius", lang, "7") for lang in ("la", "en", "it")])
        self.assertEqual(out[A][0]["who"], "Bishop of Milan")

    def test_candidates_refuse_a_git_work_tree(self):
        with tempfile.TemporaryDirectory() as d:
            subprocess.run(["git", "init", "-q", d], check=True)
            (Path(d) / "p.json").write_text("{}", encoding="utf-8")
            r = subprocess.run([sys.executable, str(Path(mp.__file__)), "candidates", str(Path(d) / "p.json"),
                                str(Path(d) / "c.json")], capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("git work tree", r.stderr)
            self.assertNotIn("Usage", r.stderr)


def answer(choice, p):
    return (200, json.dumps({"model": mj.MODEL, "answers": {"item": {
        "type": "choice", "choice": choice, "probabilities": {choice: p}, "confidence": 0.8}}}).encode())


class FakePost:
    def __init__(self, *responses):
        self.responses, self.bodies = list(responses), []

    def __call__(self, url, data, key):
        self.bodies.append(json.loads(data))
        return self.responses.pop(0)


CANDIDATES = {A: [prop() | {"candidates": [
    {"wikidata": "Q1", "label": "Ambrose", "description": "bishop of Milan", "born": 340, "died": 397,
     "route": "commemorated", "eulogies": [C]},
    {"wikidata": "Q2", "label": "Ambrosius", "description": "given name", "born": None, "died": None,
     "route": "search"}]}]}


class JevTest(unittest.TestCase):
    def client(self, *responses):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.post = FakePost(*responses)
        return mj.TypeSafe("k", Path(self.tmp.name), post=self.post, sleep=lambda s: None)

    def test_jev_request_lists_none(self):
        out, problems = mp.run_jev(CANDIDATES, SOURCES["la"], self.client(answer("Q1", 0.95)))
        self.assertEqual(problems, [])
        self.assertEqual(out, {A: {"Ambrosius": {"choice": "Q1", "p": 0.95, "accepted": True}}})
        body = self.post.bodies[0]
        self.assertEqual(body["model"], mj.MODEL)
        q = body["questions"]["item"]
        self.assertEqual(q["type"], "choice")
        self.assertEqual(list(q["criteria"]), ["Q1", "Q2", "none"])
        state = body["state"]
        self.assertEqual(state["latin_sentence"], LA[A].strip())
        self.assertEqual(state["italian_phrase"], "Ambrogio, vescovo di Milano")
        self.assertEqual(state["who"], "Bishop of Milan")
        self.assertEqual(state["candidates"]["Q1"]["commemorated_in"], [{"eulogy": C, "day": "December 7"}])
        self.assertEqual(state["candidates"]["Q1"]["born"], 340)
        self.assertNotIn("commemorated_in", state["candidates"]["Q2"])

    def test_accepts_only_at_or_above_090(self):
        for p, accepted in ((0.89, False), (0.90, True)):
            out, _ = mp.run_jev(CANDIDATES, SOURCES["la"], self.client(answer("Q1", p)))
            self.assertEqual(out[A]["Ambrosius"], {"choice": "Q1", "p": p, "accepted": accepted})
        out, _ = mp.run_jev(CANDIDATES, SOURCES["la"], self.client(answer("none", 0.99)))
        self.assertEqual(out[A]["Ambrosius"], {"choice": "none", "p": 0.99, "accepted": False})

    def test_an_answer_naming_no_option_is_a_problem(self):
        out, problems = mp.run_jev(CANDIDATES, SOURCES["la"], self.client(answer("Q9", 0.99)))
        self.assertEqual(out, {})
        self.assertEqual(len(problems), 1)

    def test_no_candidates_asks_nothing(self):
        cands = {A: [prop(n=2) | {"candidates": []}]}
        out, problems = mp.run_jev(cands, SOURCES["la"], self.client())
        self.assertEqual(out, {A: {"Ambrosius#2": {"choice": "none", "p": None, "accepted": False}}})
        self.assertEqual(self.post.bodies, [])

    def test_the_sentence_of_a_footnote_phrase(self):
        cands = {A: [prop(where={"footnote": 1}, la=["Ambrósium"], it=[])
                     | {"candidates": CANDIDATES[A][0]["candidates"]}]}
        mp.run_jev(cands, SOURCES["la"], self.client(answer("Q1", 0.95)))
        state = self.post.bodies[0]["state"]
        self.assertEqual((state["latin_sentence"], state["italian_phrase"]), ("Vide Ambrósium.", None))


if __name__ == "__main__":
    unittest.main()
