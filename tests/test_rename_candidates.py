import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import rename_candidates as rc  # noqa: E402


class Forms(unittest.TestCase):
    def test_ensis(self):
        self.assertEqual(rc.adjective_slug("Condatiscénsis", False), "condatiscensis")

    def test_ensis_feminine_unchanged(self):
        self.assertEqual(rc.adjective_slug("Condatiscénsis", True), "condatiscensis")

    def test_feminine_anus(self):
        self.assertEqual(rc.adjective_slug("Ancyránus", True), "ancyrana")

    def test_masculine_ina(self):
        self.assertEqual(rc.adjective_slug("Alexandrína", False), "alexandrinus")

    def test_known_genitive(self):
        self.assertEqual(rc.genitive_slug({"nominative": "Treviri", "genitive": None}), ("trevirorum", True))

    def test_record_genitive_uncertain(self):
        self.assertEqual(rc.genitive_slug({"nominative": "Metae", "genitive": "Metarum"}), ("metarum", False))

    def test_no_genitive(self):
        self.assertEqual(rc.genitive_slug({"nominative": "X", "genitive": None}), (None, False))

    def test_genitive_key_missing(self):
        self.assertEqual(rc.genitive_slug({"nominative": "X"}), (None, False))

    def test_roles(self):
        self.assertIn("abbas", rc.CLERIC_ROLES)
        self.assertEqual(rc.WEAK_ROLES, {"martyr", "virgo", "confessor"})


def rec(name, roles=(), places=(), **kw):
    r = {"id": "", "name": name, "kind": "person", "surname": None, "feminine": False,
         "roles": [{"role": x, "printed": x, "occurrence": 0} for x in roles], "places": list(places),
         "cognomen": None, "relations": [], "death_year": None, "role_en": None, "role_it": None}
    r.update(kw)
    return r


def place(kind, grammar, nominative, en, it=None, adjective=None, genitive=None):
    return {"kind": kind, "printed": adjective or nominative, "occurrence": 0, "grammar": grammar,
            "nominative": nominative, "adjective": adjective, "genitive": genitive, "en": en, "it": it or en}


EUGENDUS = rec("Eugendus", ["abbas"], [place("monastery", "adjective-person", "Condatiscum", "Condat",
                                             adjective="condatiscensis")], role_en="abbot", role_it="abate")
BASILIUS = rec("Basilius", ["episcopus"], [place("see", "locative", "Caesarea", "Caesarea", "Cesarea",
                                                 genitive="Caesareae")], role_en="bishop", role_it="vescovo")
HILARIUS = rec("Hilarius", ["episcopus"], [place("see", "adjective-person", "Pictavium", "Poitiers",
                                                 adjective="Pictaviénsis")], role_en="bishop", role_it="vescovo")
AGRICIUS = rec("Agricius", ["episcopus"], [place("see", "locative", "Treviri", "Trier", "Treviri")],
               role_en="bishop", role_it="vescovo")
MONK = rec("Nilammo", ["eremita"], [place("death", "locative", "Gerae", "Gera", genitive="Gerarum")],
           role_en="hermit", role_it="eremita")
MARTYR = rec("Magnus", ["martyr"], role_en="martyr", role_it="martire")
LEGO = rec("Ioannes", ["presbyter"], [place("death", "locative", "Olomucium", "Olomouc", genitive="Olomucii")],
           surname="Sarkander", role_en="priest", role_it="sacerdote")
POPE = rec("Fabianus", ["papa", "martyr"], role_en="pope", role_it="papa")
ABRAHAM = rec("Abraham", ["patriarcha"], role_en="patriarch", role_it="patriarca")
BISHOP_NOWHERE = rec("Severus", ["episcopus"], role_en="bishop", role_it="vescovo")
ABBESS = rec("Glodesindis", ["abbatissa"], [place("monastery", "adjective-noun", "Metae", "Metz",
                                                  adjective="Metensis")], feminine=True)

LABELS = {
    "la": {"mr:0101-eugendus": "Sanctus Eugendus", "mr:0101-basilius": "Sanctus Basilius",
           "mr:0614-basilius-magnus": "Sanctus Basilius Magnus", "mr:0101-magnus": "Sanctus Magnus"},
    "en": {"mr:0101-eugendus": "Saint Eugendus", "mr:0101-basilius": "Saint Basil",
           "mr:0614-basilius-magnus": "Saint Basil the Great", "mr:0101-magnus": "Saint Magnus",
           "mr:0114-hilarius": "Saint Hilary", "mr:0106-nilammo": "Saint Nilammon"},
    "it": {"mr:0101-eugendus": "Sant’Eugendo", "mr:0101-basilius": "San Basilio",
           "mr:0614-basilius-magnus": "San Basilio Magno", "mr:0101-magnus": "San Magno",
           "mr:0114-hilarius": "Sant’Ilàrio"},
}
CTX = rc.Context(taken={}, twins={"mr:0101-basilius": ["mr:0614-basilius-magnus"]}, ids=set(), labels=LABELS)


class Candidates(unittest.TestCase):
    def test_cleric_role_place_first(self):
        c = rc.candidates(EUGENDUS, "mr:0101-eugendus", "Sanctus Eugendus", CTX)
        self.assertEqual(c[0]["new_id"], "mr:0101-eugendus-abbas-condatiscensis")
        self.assertEqual(c[0]["category"], "role-place")
        self.assertEqual(c[0]["labels"]["la"], "Sanctus Eugendus abbas Condatiscensis")
        self.assertEqual(c[0]["labels"]["en"], "Saint Eugendus, abbot of Condat")
        self.assertEqual(c[0]["labels"]["it"], "Sant’Eugendo, abate di Condat")
        self.assertFalse(c[0]["weak"])

    def test_cleric_place_alone_second(self):
        c = rc.candidates(EUGENDUS, "mr:0101-eugendus", "Sanctus Eugendus", CTX)
        self.assertEqual([(x["new_id"], x["category"]) for x in c],
                         [("mr:0101-eugendus-abbas-condatiscensis", "role-place"),
                          ("mr:0101-eugendus-condatiscensis", "place-adjective")])
        self.assertEqual(c[1]["labels"]["en"], "Saint Eugendus of Condat")

    def test_twin_wins(self):
        c = rc.candidates(BASILIUS, "mr:0101-basilius", "Sanctus Basilius", CTX)
        self.assertEqual((c[0]["new_id"], c[0]["category"]), ("mr:0101-basilius-magnus", "twin"))
        self.assertEqual(c[0]["labels"], {"la": "Sanctus Basilius Magnus", "en": "Saint Basil the Great",
                                          "it": "San Basilio Magno"})

    def test_twin_disagreement_dropped(self):
        ids = [x["new_id"] for x in rc.candidates(BASILIUS, "mr:0101-basilius", "Sanctus Basilius", CTX)]
        self.assertEqual(ids, ["mr:0101-basilius-magnus"])
        self.assertIn(("mr:0101-basilius-episcopus-caesareae", "twin disagreement"),
                      rc.rejected(BASILIUS, "mr:0101-basilius", CTX))

    def test_twin_of_a_joint_eulogy_cut_at_et(self):
        joint = "mr:0102-basilius-magnus-et-gregorius-nazianzenus"
        labels = {lang: {**LABELS[lang], joint: "Saints Basil and Gregory"} for lang in LABELS}
        ctx = CTX._replace(twins={"mr:0101-basilius": [joint]}, labels=labels)
        c = rc.candidates(BASILIUS, "mr:0101-basilius", "Sanctus Basilius", ctx)
        self.assertEqual((c[0]["new_id"], c[0]["category"]), ("mr:0101-basilius-magnus", "twin"))
        # this ID's own subjects + the discriminator, never the joint subject
        self.assertEqual(c[0]["labels"], {"la": "Sanctus Basilius Magnus", "en": None, "it": None})

    def test_joint_twin_beside_its_own_twin_takes_the_vernacular(self):
        joint = "mr:0102-basilius-magnus-et-gregorius-nazianzenus"
        ctx = CTX._replace(twins={"mr:0101-basilius": [joint, "mr:0614-basilius-magnus"]})
        c = rc.candidates(BASILIUS, "mr:0101-basilius", "Sanctus Basilius", ctx)
        self.assertEqual(c[0]["labels"], {"la": "Sanctus Basilius Magnus", "en": "Saint Basil the Great",
                                          "it": "San Basilio Magno"})

    def test_twin_nothing_before_et_socii(self):
        ctx = CTX._replace(twins={"mr:0806-xystus-ii": ["mr:0807-xystus-ii-et-socii"]})
        r = rec("Xystus", ["papa"])
        self.assertEqual(rc.candidates(r, "mr:0806-xystus-ii", "Sanctus Xystus II", ctx), [])

    def test_deprecated_only_twin(self):
        ctx = CTX._replace(twins={"mr:0101-basilius": ["mr:0614-basilius-magnus"]}, ids={"mr:0101-basilius"})
        c = rc.candidates(BASILIUS, "mr:0101-basilius", "Sanctus Basilius", ctx)
        self.assertEqual((c[0]["new_id"], c[0]["category"]), ("mr:0101-basilius-magnus", "twin"))

    def test_twins_disagree_current_then_most_frequent(self):
        twins = ["mr:0201-basilius-caesariensis", "mr:0301-basilius-magnus", "mr:0401-basilius-magnus",
                 "mr:0501-basilius-ancyranus"]
        ctx = CTX._replace(twins={"mr:0101-basilius": twins},
                           ids={"mr:0101-basilius", "mr:0201-basilius-caesariensis", "mr:0501-basilius-ancyranus"})
        ids = [x["new_id"] for x in rc.candidates(BASILIUS, "mr:0101-basilius", "Sanctus Basilius", ctx)]
        # caesariensis and ancyranus are current (once each, in twin order); magnus is deprecated (twice)
        self.assertEqual(ids, ["mr:0101-basilius-caesariensis", "mr:0101-basilius-ancyranus",
                               "mr:0101-basilius-magnus"])
        ctx = ctx._replace(ids={"mr:0101-basilius", "mr:0201-basilius-caesariensis", "mr:0301-basilius-magnus"})
        ids = [x["new_id"] for x in rc.candidates(BASILIUS, "mr:0101-basilius", "Sanctus Basilius", ctx)]
        self.assertEqual(ids[:2], ["mr:0101-basilius-magnus", "mr:0101-basilius-caesariensis"])

    def test_episcopi_adjective(self):
        c = rc.candidates(HILARIUS, "mr:0114-hilarius", "Sanctus Hilarius", CTX)
        self.assertEqual(c[0]["new_id"], "mr:0114-hilarius-episcopus-pictaviensis")
        self.assertEqual(c[0]["labels"]["la"], "Sanctus Hilarius episcopus Pictaviensis")
        self.assertEqual(c[0]["labels"]["en"], "Saint Hilary, bishop of Poitiers")
        self.assertEqual(c[0]["labels"]["it"], "Sant’Ilario, vescovo di Poitiers")  # it_label drops stress

    def test_known_genitive_certain(self):
        c = rc.candidates(AGRICIUS, "mr:0113-agricius", "Sanctus Agricius", CTX)
        self.assertEqual(c[0]["new_id"], "mr:0113-agricius-episcopus-trevirorum")
        self.assertEqual(c[0]["labels"]["la"], "Sanctus Agricius episcopus Trevirorum")
        self.assertTrue(c[0]["certain"])
        self.assertIsNone(c[0]["labels"]["en"])  # no English subject to build on

    def test_non_cleric_place_alone(self):
        c = rc.candidates(MONK, "mr:0106-nilammo", "Sanctus Nilammo", CTX)
        self.assertEqual(c[0]["category"], "place-genitive")
        self.assertEqual(c[0]["new_id"], "mr:0106-nilammo-gerarum")
        self.assertFalse(c[0]["certain"])
        self.assertNotIn("role-place", [x["category"] for x in c])
        self.assertNotIn("role", [x["category"] for x in c])

    def test_weak_class_word(self):
        c = rc.candidates(MARTYR, "mr:0101-magnus", "Sanctus Magnus", CTX)
        self.assertEqual((c[0]["new_id"], c[0]["weak"]), ("mr:0101-magnus-martyr", True))
        self.assertEqual(c[0]["category"], "role")
        self.assertEqual(c[0]["labels"]["en"], "Saint Magnus, martyr")
        self.assertEqual(c[0]["labels"]["it"], "San Magno, martire")

    def test_class_word_not_beside_a_place(self):
        r = rec("Magnus", ["martyr"], [place("death", "locative", "Treviri", "Trier")])
        ids = [x["new_id"] for x in rc.candidates(r, "mr:0101-magnus", "Sanctus Magnus", CTX)]
        self.assertEqual(ids, ["mr:0101-magnus-trevirorum"])

    def test_cleric_without_place_weak_role(self):
        c = rc.candidates(BISHOP_NOWHERE, "mr:0101-severus", "Sanctus Severus", CTX)
        self.assertEqual([(x["new_id"], x["category"], x["weak"]) for x in c],
                         [("mr:0101-severus-episcopus", "role", True)])

    def test_surname_no_place(self):
        self.assertEqual([x["category"] for x in rc.candidates(LEGO, "mr:0101-x", "Beatus Ioannes", CTX)][0],
                         "surname")

    def test_surname_then_place(self):
        c = rc.candidates(LEGO, "mr:0317-ioannes", "Sanctus Ioannes", CTX)
        self.assertEqual([x["new_id"] for x in c][:2], ["mr:0317-ioannes-sarkander",
                                                       "mr:0317-ioannes-presbyter-olomucii"])
        self.assertEqual(c[0]["labels"]["la"], "Sanctus Ioannes Sarkander")

    def test_cognomen_epithet(self):
        r = rec("Petrus", ["episcopus"], cognomen={"value": "Chrysologus", "source": "text"})
        c = rc.candidates(r, "mr:0730-petrus", "Sanctus Petrus", CTX)
        self.assertEqual((c[0]["new_id"], c[0]["category"]), ("mr:0730-petrus-chrysologus", "epithet"))

    def test_epithet_labels_leave_english_and_italian_to_the_curator(self):
        r = rec("Basilius", cognomen={"value": "Magnus", "source": "text"})
        c = rc.candidates(r, "mr:0101-basilius", "Sanctus Basilius", CTX._replace(twins={}))
        self.assertEqual((c[0]["category"], c[0]["labels"]),
                         ("epithet", {"la": "Sanctus Basilius Magnus", "en": None, "it": None}))

    def test_papa(self):
        c = rc.candidates(POPE, "mr:0120-fabianus", "Sanctus Fabianus", CTX)
        self.assertEqual([(x["new_id"], x["category"]) for x in c], [("mr:0120-fabianus-papa", "papa")])

    def test_papa_with_ordinal(self):
        self.assertEqual(rc.candidates(POPE, "mr:0120-gregorius-ii", "Sanctus Gregorius II", CTX), [])

    def test_biblical_title(self):
        c = rc.candidates(ABRAHAM, "mr:1009-abraham", "Sanctus Abraham", CTX)
        self.assertEqual((c[0]["new_id"], c[0]["category"], c[0]["weak"]),
                         ("mr:1009-abraham-patriarcha", "biblical-title", False))

    def test_feminine_adjective_of_a_noun(self):
        c = rc.candidates(ABBESS, "mr:0725-glodesindis", "Sancta Glodesindis", CTX)
        self.assertEqual(c[0]["new_id"], "mr:0725-glodesindis-abbatissa-metensis")
        self.assertEqual(c[0]["labels"]["la"], "Sancta Glodesindis abbatissa Metensis")

    def test_taken_slug_dropped(self):
        ctx = CTX._replace(taken={"0101": {"eugendus-abbas-condatiscensis"}})
        ids = [x["new_id"] for x in rc.candidates(EUGENDUS, "mr:0101-eugendus", "Sanctus Eugendus", ctx)]
        self.assertNotIn("mr:0101-eugendus-abbas-condatiscensis", ids)
        self.assertEqual(ids, ["mr:0101-eugendus-condatiscensis"])
        self.assertIn(("mr:0101-eugendus-abbas-condatiscensis", "taken that day"),
                      rc.rejected(EUGENDUS, "mr:0101-eugendus", ctx))

    def test_never_numeric(self):
        for x in rc.candidates(EUGENDUS, "mr:0101-eugendus", "Sanctus Eugendus", CTX):
            self.assertFalse(any(t.isdigit() for t in x["new_id"].split("-")[1:]))

    def test_numeric_rejected(self):
        r = rec("Magnus", cognomen={"value": "2", "source": "text"})
        self.assertEqual(rc.candidates(r, "mr:0101-magnus", "Sanctus Magnus", CTX), [])
        self.assertEqual(rc.rejected(r, "mr:0101-magnus", CTX), [("mr:0101-magnus-2", "numeric token")])

    def test_no_genitive_rejected(self):
        r = rec("Magnus", places=[place("death", "locative", "Xa", "Xa")])
        self.assertEqual(rc.rejected(r, "mr:0101-magnus", CTX), [("mr:0101-magnus-xa", "no genitive for Xa")])
        self.assertEqual(rc.candidates(r, "mr:0101-magnus", "Sanctus Magnus", CTX), [])  # no role to fall back on

    def test_weak_fallback_after_drops(self):
        r = rec("Magnus", ["martyr"], [place("death", "locative", "Xa", "Xa")], role_en="martyr")
        c = rc.candidates(r, "mr:0101-magnus", "Sanctus Magnus", CTX)
        self.assertEqual([(x["new_id"], x["category"], x["weak"]) for x in c],
                         [("mr:0101-magnus-martyr", "role", True)])

    def test_cleric_fallback_when_role_place_taken(self):
        ctx = CTX._replace(taken={"0101": {"eugendus-abbas-condatiscensis", "eugendus-condatiscensis"}})
        c = rc.candidates(EUGENDUS, "mr:0101-eugendus", "Sanctus Eugendus", ctx)
        self.assertEqual([(x["new_id"], x["weak"]) for x in c], [("mr:0101-eugendus-abbas", True)])


class LoadContext(unittest.TestCase):
    def test_load(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "data").mkdir()
            (root / "i18n").mkdir()
            entries = [{"id": "mr:0101-basilius", "month": 1, "day": 1},
                       {"id": "mr:0102-basilius-magnus-et-gregorius", "month": 1, "day": 2,
                        "same_eulogy": ["mr:0614-basilius-magnus", "mr:0509-gregorius"]},
                       {"id": "mr:0614-basilius-magnus", "month": 6, "day": 14},
                       {"id": "mr:0509-gregorius", "month": 5, "day": 9},
                       {"id": "mr:0101-basilius-old", "month": 1, "day": 1, "deprecated": True},
                       {"id": "mr:0614-basilius-caesariensis", "month": 6, "day": 14, "deprecated": True,
                        "same_eulogy": ["mr:0614-basilius-magnus"]}]
            persons = {"mr:0101-basilius": {"Basilius": {"wikidata": "Q1", "status": "auto"}},
                       "mr:0614-basilius-magnus": {"Basilius": {"wikidata": "Q1", "status": "reviewed"}},
                       "mr:0509-gregorius": {"Gregorius": {"wikidata": "Q2", "status": "unresolved"}}}
            (root / "data" / "martyrology_ids.json").write_text(json.dumps({"entries": entries}))
            (root / "data" / "person_items.json").write_text(json.dumps({"persons": persons}))
            for lang in ("la", "en", "it"):
                (root / "i18n" / f"{lang}.json").write_text(json.dumps({"mr:0101-basilius": lang}))
            ctx = rc.load_context(root)
        self.assertEqual(ctx.taken["0101"], {"basilius", "basilius-old"})
        self.assertNotIn("mr:0101-basilius-old", ctx.ids)
        self.assertEqual(ctx.twins["mr:0101-basilius"], ["mr:0614-basilius-magnus"])
        self.assertEqual(ctx.twins["mr:0614-basilius-magnus"],
                         ["mr:0101-basilius", "mr:0102-basilius-magnus-et-gregorius",
                          "mr:0614-basilius-caesariensis"])  # a deprecated twin counts
        self.assertEqual(ctx.twins["mr:0509-gregorius"], ["mr:0102-basilius-magnus-et-gregorius"])
        self.assertEqual(ctx.labels["it"], {"mr:0101-basilius": "it"})


class Changeset(unittest.TestCase):
    def build(self, records, old=None, ctx=CTX):
        return rc.build_changeset(records, ctx, LABELS["la"], old)

    def test_eugendus_with_old_draft(self):
        old = {"mr:0101-eugendus": {"id": "mr:0101-eugendus", "new_id": "mr:0101-eugendus-condatisci",
                                    "class": "place-genitive", "subject_la": "Sanctus Eugendus Condatisci"}}
        cs = self.build([dict(EUGENDUS, id="mr:0101-eugendus")], old)
        self.assertEqual(cs["schema"], "crmedr-changeset/v1")
        self.assertEqual(cs["base"], {"edition": "martyrologium_romanum_2004", "registry": "data/martyrology_ids.json"})
        op = cs["operations"][0]
        self.assertEqual((op["new_id"], op["class"], op["uid"], op["decision"]),
                         ("mr:0101-eugendus-abbas-condatiscensis", "role-place", "subject:mr:0101-eugendus", None))
        self.assertEqual(op["confidence"], "medium")
        drafts = [c for c in op["candidates"] if c["basis"] == "bare-name draft"]
        self.assertEqual([c["new_id"] for c in drafts], ["mr:0101-eugendus-condatisci"])
        self.assertIn("also: mr:0101-eugendus-condatisci (place-genitive)", op["reasoning"])

    def test_non_bare_no_op(self):
        self.assertEqual(self.build([dict(BASILIUS, id="mr:0614-basilius-magnus")])["operations"], [])

    def test_record_matching_the_name(self):
        recs = [dict(MARTYR, id="mr:0101-eugendus"), dict(EUGENDUS, id="mr:0101-eugendus")]
        self.assertEqual(self.build(recs)["operations"][0]["class"], "role-place")

    def test_weak_is_low(self):
        op = self.build([dict(MARTYR, id="mr:0101-magnus")])["operations"][0]
        self.assertEqual(op["confidence"], "low")

    def test_uncertain_genitive_is_low(self):
        op = self.build([dict(MONK, id="mr:0106-nilammo")])["operations"][0]
        self.assertEqual(op["confidence"], "low")

    def test_certain_single_is_high(self):
        op = self.build([dict(AGRICIUS, id="mr:0201-agricius", roles=[])])["operations"][0]
        self.assertEqual(op["confidence"], "high")

    def test_draft_only(self):
        old = {"mr:0101-severus": {"new_id": "mr:0101-severus-x", "class": "bogus", "subject_la": "S"}}
        op = self.build([dict(BISHOP_NOWHERE, id="mr:0101-severus", roles=[])], old)["operations"][0]
        self.assertEqual((op["new_id"], op["class"], op["confidence"]), ("mr:0101-severus-x", "place-genitive", "low"))

    def test_draft_categories(self):
        self.assertEqual(rc.draft_category("epithet,low,weak-epithet", "mr:0101-x-magnus"), "epithet")
        self.assertEqual(rc.draft_category("place-form", "mr:0101-x-pictaviensis"), "place-adjective")
        self.assertEqual(rc.draft_category("align-existing", "mr:0101-x-ancyrana"), "place-adjective")
        self.assertEqual(rc.draft_category("place-form", "mr:0101-x-pictavorum"), "place-genitive")
        self.assertEqual(rc.draft_category("low", "mr:0101-x-metarum"), "place-genitive")
        self.assertEqual(rc.draft_category("twin,low", "mr:0101-x-magnus"), "twin")
        self.assertEqual(rc.draft_category("surname,non-latin", "mr:0101-x-miki"), "surname")
        self.assertEqual(rc.draft_category("low", "mr:0101-x-papa"), "papa")
        self.assertEqual(rc.draft_category("low", "mr:0101-x-episcopus"), "role")
        self.assertEqual(rc.draft_category(None, "mr:0101-x-alexandrinus"), "place-adjective")

    def test_a_draft_keeps_its_class(self):
        old = {"mr:0101-severus": {"new_id": "mr:0101-severus-metarum", "class": "low", "subject_la": "S"}}
        op = self.build([dict(BISHOP_NOWHERE, id="mr:0101-severus", roles=[])], old)["operations"][0]
        self.assertEqual((op["candidates"][0]["category"], op["candidates"][0]["draft_class"]),
                         ("place-genitive", "low"))

    def test_none_skipped(self):
        import contextlib
        import io
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            cs = self.build([dict(BISHOP_NOWHERE, id="mr:0101-severus", roles=[])])
        self.assertEqual(cs["operations"], [])
        self.assertIn("mr:0101-severus", err.getvalue())

    def test_cli_old_without_a_value(self):
        with self.assertRaises(SystemExit) as e:
            rc.main(["build", "in.json", "out.json", "--old"])
        self.assertIn("usage: rename_candidates.py build", str(e.exception))

    def test_cli_refuses_repository(self):
        with self.assertRaises(SystemExit) as e:
            rc.main(["build", "in.json", str(Path(__file__).resolve().parent / "out.json")])
        self.assertIn("outside the repository", str(e.exception))


if __name__ == "__main__":
    unittest.main()
