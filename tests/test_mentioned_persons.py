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

    def test_a_proposal_overlapping_a_mentioned_mark(self):
        # Final review 5: a mentioned person's mark is not skipped, but a proposal over it is a problem.
        mentions = {"la": {A: [mark(LA[A], "Ambrósius", name="Alius", role="mentioned")]}, "it": {}}
        out = run({A: [prop()]}, mentions)
        self.assertEqual(len(out), 1)
        self.assertIn("overlaps the mark of the mentioned person Alius", out[0])

    def test_a_namesake_phrase_skips_the_commemorated_mark(self):
        # Final review 1: the Italian "Zenone" of Zeno#2 is its next printing, not the commemorated Zeno's.
        z = "mr:1226-z"
        sources = {"la": ({z: "Sancti Zenónis, quem Zeno álius baptizávit."}, {}),
                   "it": ({z: "San Zenone, battezzato da Zenone."}, {})}
        la, it = sources["la"][0][z], sources["it"][0][z]
        mentions = {"la": {z: [mark(la, "Zenónis", name="Zeno")]}, "it": {z: [mark(it, "Zenone", name="Zeno")]}}
        p = prop(name="Zeno", n=2, la=["Zeno álius"], it=["Zenone"], who="another Zeno")
        persons = {z: [{"name": "Zeno", "where": "text"}]}
        self.assertEqual(mp.check_proposals({z: [p]}, sources, persons, mentions), [])
        it_only = {"la": ({z: la}, {}), "it": ({z: "San Zenone."}, {})}
        out = mp.check_proposals({z: [p]}, it_only, persons, {"la": {}, "it": {z: [mark("San Zenone.", "Zenone",
                                                                                         name="Zeno")]}})
        self.assertEqual(len(out), 1)
        self.assertIn("overlaps the mark of Zeno", out[0])

    def test_a_footnote_phrase_object_of_a_text_person(self):
        # Final review 2: a phrase object names its own where.
        fn = {"phrase": "Ambrósium", "where": {"footnote": 1}}
        self.assertEqual(run({A: [prop(la=["Ambrósius, epíscopus Mediolanénsis", fn])]}), [])
        out = run({A: [prop(la=["Ambrósius, epíscopus Mediolanénsis", dict(fn, where="text")])]})
        self.assertEqual(len(out), 1)
        self.assertIn("'Ambrósium' is not printed in the text", out[0])

    def test_proposals_overlapping_each_other_or_repeated(self):
        # Final review 5.
        out = run({A: [prop(), prop(name="Augustinus", la=["epíscopus Mediolanénsis"], it=[])]})
        self.assertEqual(len(out), 1)
        self.assertIn("Augustinus", out[0])
        self.assertIn("overlaps the phrase of Ambrosius", out[0])
        out = run({A: [prop(), prop(la=["Ambrósius"], it=[])]})
        self.assertTrue(any("proposed twice" in o for o in out), out)

    def test_malformed_where_or_phrase_is_a_problem(self):
        # Final review 5: listed, no traceback.
        for kw in ({"where": "body"}, {"where": {"footnote": "1"}}, {"la": [3]},
                   {"it": [{"phrase": "Ambrogio", "where": {"footnote": 0}}]}, {"la": [{"where": "text"}]}):
            out = run({A: [prop(**kw)]})
            self.assertEqual(len(out), 1, (kw, out))
            self.assertIn("malformed", out[0])

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


def decision(**kw):
    return {"wikidata": "Q1", "decided": "jev", "status": "reviewed", "proposal": prop()} | kw


KEY = f"{A}|Ambrosius"


class ApplyTest(unittest.TestCase):
    def setUp(self):
        self.mentioned = {"$comment": "c", B: [{"name": "Alius", "where": "text", "la": ["x"], "it": []}]}
        self.items = {B: {"Alius": {"wikidata": "Q9", "status": "reviewed", "decided": "research"}}}
        self.curated = {A: [{"role": "mention", "la": "Mediolanénsis", "it": "Milano"},
                            {"role": "birth", "la": "Romæ", "it": "Roma"}]}

    def apply(self, decisions, marks=None):
        return mp.apply_decisions(decisions, self.mentioned, self.items, self.curated, (LA, NOTES), marks or {})

    def test_apply_writes_mentioned_and_items(self):
        removed, problems = self.apply({KEY: decision(note="n")})
        self.assertEqual(problems, [])
        self.assertEqual(self.mentioned[A], [{"name": "Ambrosius", "where": "text",
                                              "la": ["Ambrósius, epíscopus Mediolanénsis"],
                                              "it": ["Ambrogio, vescovo di Milano"]}])
        self.assertEqual(self.items[A]["Ambrosius"], {"wikidata": "Q1", "status": "reviewed", "decided": "jev",
                                                       "note": "n"})

    def test_unresolved_and_numbered(self):
        d = decision(wikidata=None, decided=None, status="unresolved", note="not found", proposal=prop(n=2))
        self.assertEqual(self.apply({f"{A}|Ambrosius#2": d})[1], [])
        self.assertEqual(self.items[A]["Ambrosius#2"], {"wikidata": None, "status": "unresolved", "note": "not found"})
        self.assertEqual(self.mentioned[A][0]["n"], 2)

    def test_place_inside_the_name_is_removed(self):
        removed, _ = self.apply({KEY: decision()})
        self.assertEqual(len(removed), 1)
        self.assertIn("Mediolanénsis", removed[0])
        self.assertEqual([it["la"] for it in self.curated[A]], ["Romæ"])

    def test_apply_skips_doubts(self):
        removed, problems = self.apply({KEY: decision(wikidata=None, decided=None, status="doubt")})
        self.assertEqual((removed, problems), ([], []))
        self.assertNotIn(A, self.mentioned)
        self.assertNotIn(A, self.items)
        self.assertEqual(len(self.curated[A]), 2)

    def test_apply_refuses_a_conflicting_qid(self):
        self.items[A] = {"Ambrosius": {"wikidata": "Q2", "status": "reviewed", "decided": "jev"}}
        before = json.dumps([self.mentioned, self.items, self.curated])
        removed, problems = self.apply({KEY: decision()})
        self.assertEqual(len(problems), 1)
        self.assertIn("Q2", problems[0])
        self.assertEqual(json.dumps([self.mentioned, self.items, self.curated]), before)

    def test_the_same_decision_twice_is_a_no_op(self):
        self.apply({KEY: decision()})
        before = json.dumps([self.mentioned, self.items])
        self.assertEqual(self.apply({KEY: decision()}), ([], []))
        self.assertEqual(json.dumps([self.mentioned, self.items]), before)

    def test_a_key_disagreeing_with_its_proposal(self):
        _, problems = self.apply({f"{A}|Augustinus": decision()})
        self.assertEqual(len(problems), 1)
        _, problems = self.apply({f"{A}|Ambrosius#2": decision()})
        self.assertEqual(len(problems), 1)
        self.assertNotIn(A, self.items)

    def test_invalid_decisions(self):
        for kw in ({"decided": "guess"}, {"wikidata": "x"}, {"status": "auto"},
                   {"status": "unresolved", "wikidata": None, "decided": None}):
            self.assertTrue(self.apply({KEY: decision(**kw)})[1], kw)

    def test_a_place_elsewhere_in_the_text_is_kept(self):
        text = "Mediolanénsis. Ambrósius, epíscopus Mediolanénsis."
        curated = {A: [{"role": "mention", "la": "Mediolanénsis", "it": "Milano", "occurrence": 1}]}
        removed, _ = mp.apply_decisions({KEY: decision()}, {}, {}, curated, ({A: text}, {}), {})
        self.assertEqual((removed, len(curated[A])), ([], 1))

    def test_a_namesake_phrase_removes_the_place_of_its_own_printing(self):
        # Final review 1: the phrase skips the commemorated Zeno's mark, so the place inside its next printing goes.
        z = "mr:1226-z"
        text = "Zeno Veronénsis, cum Zeno Veronénsis álius"
        curated = {z: [{"role": "mention", "la": "Veronénsis", "occurrence": 1},
                       {"role": "mention", "la": "Veronénsis", "occurrence": 2}]}
        d = decision(proposal=prop(name="Zeno", n=2, la=["Zeno Veronénsis"], it=[]))
        removed, problems = mp.apply_decisions({f"{z}|Zeno#2": d}, {}, {}, curated, ({z: text}, {}),
                                               {z: [mark(text, "Zeno", name="Zeno")]})
        self.assertEqual(problems, [])
        self.assertEqual(len(removed), 1)
        self.assertEqual([it["occurrence"] for it in curated[z]], [1])

    def test_a_footnote_phrase_removes_no_text_place(self):
        # Final review 2: only the text phrases remove a body place.
        notes = {A: ["Vide Mediolanénsis."]}
        p = prop(la=["Ambrósius", {"phrase": "Mediolanénsis", "where": {"footnote": 1}}], it=[])
        removed, problems = mp.apply_decisions({KEY: decision(proposal=p)}, self.mentioned, self.items,
                                               self.curated, (LA, notes), {})
        self.assertEqual((removed, problems), ([], []))
        self.assertEqual(len(self.curated[A]), 2)
        self.assertEqual(self.mentioned[A][0]["la"], p["la"])

    def test_a_rerun_after_a_partial_apply_writes_the_missing_item(self):
        # Final review 4: persons_mentioned.json written, person_items.json not.
        self.mentioned[A] = [mp.mentioned_of(prop())]
        removed, problems = self.apply({KEY: decision()})
        self.assertEqual(problems, [])
        self.assertEqual(self.items[A]["Ambrosius"], {"wikidata": "Q1", "status": "reviewed", "decided": "jev"})
        self.assertEqual(len(self.mentioned[A]), 1)

    def test_apply_cli_reminds_to_rebuild_the_places(self):
        # Final review 3 (and 4: atomic writes, no temp file left).
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as t:
            root, texts = Path(d), Path(t)
            (root / "data").mkdir()
            folder = texts / "data" / "editions" / mp.EDITIONS["la"]
            folder.mkdir(parents=True)
            for month in range(1, 13):
                (folder / f"{month:02d}.json").write_text(json.dumps(LA if month == 1 else {}), encoding="utf-8")
            (folder / "footnotes.json").write_text(json.dumps({A: [{"text": NOTES[A][0]}]}), encoding="utf-8")
            for name, doc in (("persons_mentioned.json", {}), ("person_items.json", {"persons": {}}),
                              ("places_curated.json", self.curated), ("mentions.json", {"editions": {}})):
                (root / "data" / name).write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            (root / "dec.json").write_text(json.dumps({KEY: decision()}), encoding="utf-8")
            r = subprocess.run([sys.executable, str(Path(mp.__file__)), "apply", str(root / "dec.json"), t, d],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("run python3 scripts/extract_places.py", r.stdout)
            self.assertEqual(json.loads((root / "data" / "person_items.json").read_text())["persons"][A]["Ambrosius"]
                             ["decided"], "jev")
            self.assertEqual(len(json.loads((root / "data" / "places_curated.json").read_text())[A]), 1)
            self.assertEqual(sorted(p.name for p in (root / "data").iterdir()),
                             ["mentions.json", "person_items.json", "persons_mentioned.json", "places_curated.json"])

    def test_render_matches_build_person_items(self):
        self.apply({KEY: decision()})
        import build_person_items as bpi
        self.assertEqual(json.loads(bpi.render_json(self.items))["persons"][A]["Ambrosius"]["decided"], "jev")
        out = json.loads(mp.render_mentioned(self.mentioned))
        self.assertEqual(list(out), ["$comment", A, B])


class CardsTest(unittest.TestCase):
    def test_cards_hold_only_doubts(self):
        doubt = decision(wikidata=None, decided=None, status="doubt", note="two bishops fit",
                         candidates=["Q5", {"wikidata": "Q6", "label": "X"}])
        cs = mp.build_cards({KEY: decision(), f"{A}|Ambrosius#2": doubt | {"proposal": prop(n=2)}})
        self.assertEqual(cs["schema"], "crmedr-changeset/v1")
        self.assertEqual(len(cs["operations"]), 1)
        op = cs["operations"][0]
        self.assertEqual((op["op"], op["id"], op["eulogy"], op["name"], op["n"], op["reasoning"]),
                         ("resolve_person", f"{A}|Ambrosius#2", A, "Ambrosius", 2, "two bishops fit"))
        self.assertEqual(op["candidates"], [{"wikidata": "Q5"}, {"wikidata": "Q6", "label": "X"}])
        self.assertEqual((op["decision"], op["edited"]), (None, None))
        # Final review 9: the phrases travel with the card, so a decided doubt can be applied.
        self.assertEqual((op["la"], op["it"], op["who"]), (prop()["la"], prop()["it"], "Bishop of Milan"))

    def test_cards_cli_refuses_a_git_work_tree(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / "dec.json").write_text(json.dumps({KEY: decision(status="doubt")}))
            r = subprocess.run([sys.executable, str(Path(mp.__file__)), "cards", str(root / "dec.json"),
                                str(root / "out.json"), str(root)], capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)
            self.assertFalse((root / "out.json").exists())

    def test_cards_cli_writes_outside(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as o:
            (Path(d) / "dec.json").write_text(json.dumps({KEY: decision(status="doubt")}))
            r = subprocess.run([sys.executable, str(Path(mp.__file__)), "cards", str(Path(d) / "dec.json"),
                                str(Path(o) / "out.json"), d], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(len(json.loads((Path(o) / "out.json").read_text())["operations"]), 1)



class DecisionsTest(unittest.TestCase):
    """Final review 8: proposals, Jev's choices and the research joined into a decisions file."""
    PROPOSALS = {A: [prop() | {"candidates": [{"wikidata": "Q1"}]}, prop(n=2), prop(name="Augustinus")]}
    JEV = {A: {"Ambrosius": {"choice": "Q1", "p": 0.95, "accepted": True},
               "Ambrosius#2": {"choice": "Q2", "p": 0.5, "accepted": False}}}
    RESEARCH = {f"{A}|Ambrosius#2": {"wikidata": "Q7", "decided": "research", "status": "reviewed", "note": "n"},
                f"{A}|Augustinus": {"wikidata": None, "decided": None, "status": "doubt", "note": "two fit",
                                    "candidates": ["Q8", "Q9"]}}

    def test_join(self):
        out, problems = mp.build_decisions(self.PROPOSALS, self.JEV, self.RESEARCH)
        self.assertEqual(problems, [])
        self.assertEqual(out[KEY], {"wikidata": "Q1", "decided": "jev", "status": "reviewed", "proposal": prop()})
        self.assertEqual(out[f"{A}|Ambrosius#2"], self.RESEARCH[f"{A}|Ambrosius#2"] | {"proposal": prop(n=2)})
        self.assertEqual(out[f"{A}|Augustinus"]["candidates"], ["Q8", "Q9"])
        self.assertEqual(mp.decision_problems(out), [])

    def test_research_overrides_jev(self):
        research = {KEY: {"wikidata": None, "decided": None, "status": "unresolved", "note": "not him"}}
        out, problems = mp.build_decisions({A: [prop()]}, self.JEV, research)
        self.assertEqual((problems, out[KEY]["status"]), ([], "unresolved"))

    def test_problems(self):
        _, problems = mp.build_decisions(self.PROPOSALS, self.JEV, {})
        self.assertEqual(problems, [f"{A}|Ambrosius#2: neither an accepted Jev choice nor a research entry",
                                    f"{A}|Augustinus: neither an accepted Jev choice nor a research entry"])
        _, problems = mp.build_decisions({A: [prop()]}, {}, {KEY: {"wikidata": None, "decided": None,
                                                                   "status": "unresolved", "note": ""}})
        self.assertEqual(len(problems), 1)
        self.assertIn("note", problems[0])
        _, problems = mp.build_decisions({A: [prop()]}, self.JEV, {f"{B}|Alius": {"status": "doubt"}})
        self.assertEqual(problems, [f"{B}|Alius: a research entry for no proposed person"])

    def test_cli(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as o:
            paths = {n: Path(d) / f"{n}.json" for n in ("proposals", "jev", "research")}
            for n, doc in (("proposals", self.PROPOSALS), ("jev", self.JEV), ("research", self.RESEARCH)):
                paths[n].write_text(json.dumps(doc), encoding="utf-8")
            script = str(Path(mp.__file__))
            r = subprocess.run([sys.executable, script, "decisions", str(paths["proposals"]), str(paths["jev"]),
                                str(paths["research"]), str(Path(o) / "dec.json")], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(len(json.loads((Path(o) / "dec.json").read_text())), 3)
            r = subprocess.run([sys.executable, script, "decisions", str(paths["proposals"]), str(paths["jev"]),
                                str(Path(o) / "dec2.json")], capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("neither an accepted Jev choice", r.stderr)
            self.assertFalse((Path(o) / "dec2.json").exists())
        with tempfile.TemporaryDirectory() as d:
            subprocess.run(["git", "init", "-q", d], check=True)
            (Path(d) / "p.json").write_text(json.dumps({A: [prop()]}), encoding="utf-8")
            (Path(d) / "j.json").write_text(json.dumps(self.JEV), encoding="utf-8")
            r = subprocess.run([sys.executable, script, "decisions", str(Path(d) / "p.json"), str(Path(d) / "j.json"),
                                str(Path(d) / "dec.json")], capture_output=True, text=True, cwd=d)
            self.assertNotEqual(r.returncode, 0)
            self.assertFalse((Path(d) / "dec.json").exists())


if __name__ == "__main__":
    unittest.main()
