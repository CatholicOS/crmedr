import contextlib
import io
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
    def test_cleric_takes_the_place_alone(self):
        c = rc.candidates(EUGENDUS, "mr:0101-eugendus", "Sanctus Eugendus", CTX)
        self.assertEqual([(x["new_id"], x["category"]) for x in c],
                         [("mr:0101-eugendus-condatiscensis", "place-adjective")])
        self.assertEqual(c[0]["labels"], {"la": "Sanctus Eugendus Condatiscensis", "en": "Saint Eugendus of Condat",
                                          "it": "Sant’Eugendo di Condat"})
        self.assertFalse(c[0]["weak"])

    def test_twin_wins(self):
        c = rc.candidates(BASILIUS, "mr:0101-basilius", "Sanctus Basilius", CTX)
        self.assertEqual((c[0]["new_id"], c[0]["category"]), ("mr:0101-basilius-magnus", "twin"))
        self.assertEqual(c[0]["labels"], {"la": "Sanctus Basilius Magnus", "en": "Saint Basil the Great",
                                          "it": "San Basilio Magno"})

    def test_twin_disagreement_dropped(self):
        ids = [x["new_id"] for x in rc.candidates(BASILIUS, "mr:0101-basilius", "Sanctus Basilius", CTX)]
        self.assertEqual(ids, ["mr:0101-basilius-magnus"])
        self.assertIn(("mr:0101-basilius-caesareae", "twin disagreement"),
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
        self.assertEqual(c[0]["new_id"], "mr:0114-hilarius-pictaviensis")
        self.assertEqual(c[0]["labels"]["la"], "Sanctus Hilarius Pictaviensis")
        self.assertEqual(c[0]["labels"]["en"], "Saint Hilary of Poitiers")
        self.assertEqual(c[0]["labels"]["it"], "Sant’Ilario di Poitiers")  # it_label drops stress

    def test_known_genitive_certain(self):
        c = rc.candidates(AGRICIUS, "mr:0113-agricius", "Sanctus Agricius", CTX)
        self.assertEqual(c[0]["new_id"], "mr:0113-agricius-trevirorum")
        self.assertEqual(c[0]["labels"]["la"], "Sanctus Agricius Trevirorum")
        self.assertTrue(c[0]["certain"])
        self.assertIsNone(c[0]["labels"]["en"])  # no English subject to build on

    def test_non_cleric_place_alone(self):
        c = rc.candidates(MONK, "mr:0106-nilammo", "Sanctus Nilammo", CTX)
        self.assertEqual(c[0]["category"], "place-genitive")
        self.assertEqual(c[0]["new_id"], "mr:0106-nilammo-gerarum")
        self.assertFalse(c[0]["certain"])
        self.assertNotIn("role", [x["category"] for x in c])

    def test_locative_has_the_genitive_form(self):
        r = rec("Hugolinus", ["eremita"], [dict(place("death", "locative", "Gualdum Captaneorum", "Gualdo Cattaneo"),
                                                printed="Gualdi Captaneórum")])
        c = rc.candidates(r, "mr:0101-hugolinus", "Beatus Hugolinus", CTX)
        self.assertEqual([(x["new_id"], x["category"], x["certain"]) for x in c],
                         [("mr:0101-hugolinus-gualdi-captaneorum", "place-genitive", False)])

    def test_locative_in_ae_keeps_ae(self):
        r = rec("Silvester", ["abbas"], [dict(place("monastery", "locative", "Troyna", "Troina"), printed="Troýnæ")])
        ids = [x["new_id"] for x in rc.candidates(r, "mr:0102-silvester", "Sanctus Silvester", CTX)]
        self.assertEqual(ids, ["mr:0102-silvester-troynae"])

    def test_third_declension_locative_falls_back_to_the_role(self):
        r = rec("Caesaria", ["abbatissa"], [dict(place("monastery", "locative", "Arelate", "Arles"),
                                                 printed="Areláte")], feminine=True)
        c = rc.candidates(r, "mr:0112-caesaria", "Sancta Caesaria", CTX)
        self.assertEqual([(x["new_id"], x["weak"]) for x in c], [("mr:0112-caesaria-abbatissa", True)])

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
        self.assertEqual([x["new_id"] for x in c][:2], ["mr:0317-ioannes-sarkander", "mr:0317-ioannes-olomucii"])
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
        self.assertEqual(c[0]["new_id"], "mr:0725-glodesindis-metensis")
        self.assertEqual(c[0]["labels"]["la"], "Sancta Glodesindis Metensis")

    def test_taken_slug_dropped(self):
        ctx = CTX._replace(taken={"0101": {"eugendus-condatiscensis"}})
        self.assertNotIn("mr:0101-eugendus-condatiscensis",
                         [x["new_id"] for x in rc.candidates(EUGENDUS, "mr:0101-eugendus", "Sanctus Eugendus", ctx)])
        self.assertIn(("mr:0101-eugendus-condatiscensis", "taken that day"),
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

    def test_cleric_fallback_when_the_place_is_taken(self):
        ctx = CTX._replace(taken={"0101": {"eugendus-condatiscensis"}})
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
                        "same_eulogy": ["mr:0614-basilius-magnus"]},
                       {"id": "mr:0201-aa-bononiae", "month": 2, "day": 1},
                       {"id": "mr:0202-b-bononiae", "month": 2, "day": 2}]
            bononia = [{"role": "death", "la": "Bonóniæ"}]
            (root / "data" / "places.json").write_text(json.dumps(
                {"places": {"mr:0201-aa-bononiae": bononia, "mr:0202-b-bononiae": bononia}}))
            (root / "data" / "gazetteer.json").write_text(json.dumps(
                {"places": {"Bonóniæ": {"wikidata": "Q1891", "label": "Bologna"}}}))
            persons = {"mr:0101-basilius": {"Basilius": {"wikidata": "Q1", "status": "auto"}},
                       "mr:0614-basilius-magnus": {"Basilius": {"wikidata": "Q1", "status": "reviewed"}},
                       "mr:0509-gregorius": {"Gregorius": {"wikidata": "Q2", "status": "unresolved"}}}
            (root / "data" / "martyrology_ids.json").write_text(json.dumps({"entries": entries}))
            (root / "data" / "person_items.json").write_text(json.dumps({"persons": persons}))
            for lang in ("la", "en", "it"):
                (root / "i18n" / f"{lang}.json").write_text(json.dumps({"mr:0101-basilius": lang}))
            ctx = rc.load_context(root)
            self.assertEqual((ctx.persons, ctx.hint_labels), ({}, None))  # no data/persons.json
            (root / "data" / "persons.json").write_text(json.dumps(
                {"editions": {"martyrologium_romanum_2004": {"mr:0101-basilius": [{"name": "Basilius"}]}}}))
            with_persons = rc.load_context(root)
        self.assertEqual(with_persons.persons, {"mr:0101-basilius": [{"name": "Basilius"}]})
        self.assertEqual(with_persons.items["mr:0101-basilius"], {"Basilius": {"wikidata": "Q1", "status": "auto"}})
        self.assertEqual(ctx.taken["0101"], {"basilius", "basilius-old"})
        self.assertNotIn("mr:0101-basilius-old", ctx.ids)
        self.assertEqual(ctx.twins["mr:0101-basilius"], ["mr:0614-basilius-magnus"])
        self.assertEqual(ctx.twins["mr:0614-basilius-magnus"],
                         ["mr:0101-basilius", "mr:0102-basilius-magnus-et-gregorius",
                          "mr:0614-basilius-caesariensis"])  # a deprecated twin counts
        self.assertEqual(ctx.twins["mr:0509-gregorius"], ["mr:0102-basilius-magnus-et-gregorius"])
        self.assertEqual(ctx.labels["it"], {"mr:0101-basilius": "it"})
        self.assertEqual(ctx.genitives, {"Q1891": "bononiae"})
        self.assertEqual(ctx.places["mr:0201-aa-bononiae"][0]["qid"], "Q1891")


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
                         ("mr:0101-eugendus-condatiscensis", "place-adjective", "subject:mr:0101-eugendus", None))
        self.assertEqual(op["confidence"], "medium")
        drafts = [c for c in op["candidates"] if c["basis"] == "bare-name draft"]
        self.assertEqual([c["new_id"] for c in drafts], ["mr:0101-eugendus-condatisci"])
        self.assertIn("also: mr:0101-eugendus-condatisci (place-genitive)", op["reasoning"])

    def test_relabel_after_rename(self):
        old = {"mr:0101-eugendus": {"new_id": "mr:0101-eugendus-condatisci", "class": "place-genitive",
                                    "subject_la": "Sanctus Eugendus Condatisci"}}
        ops = self.build([dict(EUGENDUS, id="mr:0101-eugendus"), dict(MARTYR, id="mr:0101-magnus")], old)["operations"]
        self.assertEqual([(o["op"], o["id"]) for o in ops],
                         [("rename", "mr:0101-eugendus"), ("relabel", "mr:0101-eugendus"),
                          ("rename", "mr:0101-magnus"), ("relabel", "mr:0101-magnus")])
        relabel = ops[1]
        current = {"la": "Sanctus Eugendus", "en": "Saint Eugendus", "it": "Sant’Eugendo"}
        first = {"la": "Sanctus Eugendus Condatiscensis", "en": "Saint Eugendus of Condat",
                 "it": "Sant’Eugendo di Condat"}
        self.assertEqual(relabel, {
            "op": "relabel", "id": "mr:0101-eugendus", "uid": "labels:mr:0101-eugendus", "current": current,
            "labels": first,
            "candidates": [{"labels": first, "from_id": "mr:0101-eugendus-condatiscensis"},
                           {"labels": {"la": "Sanctus Eugendus Condatisci", "en": "Saint Eugendus",
                                       "it": "Sant’Eugendo"},  # a None language filled from current
                            "from_id": "mr:0101-eugendus-condatisci"},
                           {"labels": current, "from_id": None}],
            "decision": None, "edited": None})

    def test_relabel_candidates_deduped_current_last(self):
        current = {"la": "Sanctus A", "en": "Saint A", "it": None}
        ctx = CTX._replace(labels={"la": {"mr:0101-a": "Sanctus A"}, "en": {"mr:0101-a": "Saint A"}, "it": {}})
        x = {"la": "Sanctus A X", "en": None, "it": None}
        cands = [{"new_id": "mr:0101-a-x", "labels": x}, {"new_id": "mr:0101-a-y", "labels": dict(x, en="Saint A")},
                 {"new_id": "mr:0101-a-z", "labels": dict(current)}]
        op = rc.relabel_op("mr:0101-a", cands, ctx)
        self.assertEqual(op["candidates"], [{"labels": dict(x, en="Saint A"), "from_id": "mr:0101-a-x"},
                                            {"labels": current, "from_id": None}])
        self.assertIsNone(rc.relabel_op("mr:0101-a", cands[2:], ctx))  # nothing but the current labels

    def test_relabel_candidate_equal_to_current_once_filled_not_offered(self):
        ctx = CTX._replace(labels={"la": {"mr:0101-a": "Sanctus A"}, "en": {"mr:0101-a": "Saint A"},
                                   "it": {"mr:0101-a": "Sant’A"}})
        same = {"new_id": "mr:0101-a-y", "labels": {"la": "Sanctus A", "en": None, "it": None}}
        self.assertIsNone(rc.relabel_op("mr:0101-a", [same, dict(same, labels=None)], ctx))
        x = {"new_id": "mr:0101-a-x", "labels": {"la": "Sanctus A X", "en": None, "it": "Sant’A X"}}
        op = rc.relabel_op("mr:0101-a", [same, x], ctx)
        self.assertEqual([c["from_id"] for c in op["candidates"]], ["mr:0101-a-x", None])
        self.assertEqual(op["labels"], {"la": "Sanctus A X", "en": "Saint A", "it": "Sant’A X"})

    HINT_CTX = CTX._replace(
        persons={"mr:0101-eugendus": [{"name": "Eugendus", "where": "text"}],
                 "mr:0101-magnus": [{"name": "Magnus", "where": "text"}, {"name": "Felix", "where": "text"}]},
        items={"mr:0101-eugendus": {"Eugendus": {"wikidata": "Q389249", "status": "auto"}},
               "mr:0101-magnus": {"Magnus": {"wikidata": "Q5", "status": "auto"}}},
        hint_labels={"Q389249": {"en": "Eugendus", "it": None}, "Q5": {"en": "Magnus", "it": "Magno"}})

    def test_relabel_hint_for_a_single_decided_person(self):
        ops = self.build([dict(EUGENDUS, id="mr:0101-eugendus"), dict(MARTYR, id="mr:0101-magnus")],
                         ctx=self.HINT_CTX)["operations"]
        relabels = {o["id"]: o for o in ops if o["op"] == "relabel"}
        self.assertEqual(relabels["mr:0101-eugendus"]["hint"],
                         {"wikidata": "Q389249", "labels": {"en": "Eugendus", "it": None}})
        self.assertNotIn("hint", relabels["mr:0101-magnus"])  # two persons
        self.assertEqual(rc.hint_qids(self.HINT_CTX, ["mr:0101-eugendus", "mr:0101-magnus"]), ["Q389249"])

    def test_no_relabel_hint_for_an_undecided_person_or_without_labels(self):
        for status in ("unresolved", "jev", "reviewed"):
            items = {"mr:0101-eugendus": {"Eugendus": {"wikidata": "Q389249", "status": status}}}
            ctx = self.HINT_CTX._replace(items=items)
            relabel = self.build([dict(EUGENDUS, id="mr:0101-eugendus")], ctx=ctx)["operations"][1]
            self.assertEqual("hint" in relabel, status != "unresolved", status)
        no_qid = {"mr:0101-eugendus": {"Eugendus": {"status": "reviewed"}}}
        for ctx in (self.HINT_CTX._replace(items=no_qid), self.HINT_CTX._replace(items={}),
                    self.HINT_CTX._replace(hint_labels=None), self.HINT_CTX._replace(hint_labels={})):
            relabel = self.build([dict(EUGENDUS, id="mr:0101-eugendus")], ctx=ctx)["operations"][1]
            self.assertNotIn("hint", relabel)

    def test_fetch_hint_labels_one_call_and_a_failure_leaves_every_hint_out(self):
        import wikidata

        class Client:
            def __init__(self, error=None):
                self.calls, self.error = [], error

            def labels(self, qids, languages=("en", "it")):
                self.calls.append(list(qids))
                if self.error:
                    raise self.error
                return {q: {"en": q.lower(), "it": None} for q in qids}

        client = Client()
        ids = ["mr:0101-eugendus", "mr:0101-magnus"]
        self.assertEqual(rc.fetch_hint_labels(self.HINT_CTX, ids, client), {"Q389249": {"en": "q389249", "it": None}})
        self.assertEqual(client.calls, [["Q389249"]])
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertIsNone(rc.fetch_hint_labels(self.HINT_CTX, ids, Client(wikidata.WikidataError("HTTP 503"))))
        self.assertEqual(len(err.getvalue().strip().splitlines()), 1)
        self.assertIn("HTTP 503", err.getvalue())

    def test_non_bare_no_op(self):
        self.assertEqual(self.build([dict(BASILIUS, id="mr:0614-basilius-magnus")])["operations"], [])

    def test_record_matching_the_name(self):
        recs = [dict(MARTYR, id="mr:0101-eugendus"), dict(EUGENDUS, id="mr:0101-eugendus")]
        self.assertEqual(self.build(recs)["operations"][0]["class"], "place-adjective")

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
        self.assertEqual(len(self.build([dict(BISHOP_NOWHERE, id="mr:0101-severus", roles=[])],
                                        {"mr:0101-severus": dict(old["mr:0101-severus"], subject_la=None)})
                             ["operations"]), 1)  # no label differs from the current (none): no relabel

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



class GenitiveMapTest(unittest.TestCase):
    BONONIA = {"role": "death", "la": "Bonóniæ", "qid": "Q1891", "label": "Bologna"}

    def test_mined_from_ids(self):
        entries = [{"id": "mr:0101-aa-bononiae"}, {"id": "mr:0202-b-bononiae"}]
        places = {"mr:0101-aa-bononiae": [self.BONONIA], "mr:0202-b-bononiae": [self.BONONIA]}
        self.assertEqual(rc.mine_genitives(entries, places), {"Q1891": rc.Counter({"bononiae": 2})})

    def test_window_after_the_first_words(self):
        entries = [{"id": "mr:0101-aa-bononiae"}]
        places = {"mr:0101-aa-bononiae": [dict(self.BONONIA, la="In urbe Bonóniæ")]}
        self.assertEqual(rc.mine_genitives(entries, places), {"Q1891": rc.Counter({"bononiae": 1})})

    def test_longest_window_first_capitalized_only(self):
        entries = [{"id": "mr:0101-aa-gualdi-captaneorum"}, {"id": "mr:0102-bb-urbe-cappadocia"}]
        places = {"mr:0101-aa-gualdi-captaneorum": [{"role": "death", "la": "Gualdi Captaneórum", "qid": "Q2"}],
                  "mr:0102-bb-urbe-cappadocia": [{"role": "death", "la": "urbe Cappadócia", "qid": "Q3"}]}
        self.assertEqual(rc.mine_genitives(entries, places),
                         {"Q2": rc.Counter({"gualdi-captaneorum": 1}), "Q3": rc.Counter({"cappadocia": 1})})

    def test_deprecated_and_unmatched_ignored_once_per_id(self):
        entries = [{"id": "mr:0101-aa-bononiae", "deprecated": True}, {"id": "mr:0102-b-martyr"},
                   {"id": "mr:0103-c-bononiae"}]
        places = {"mr:0101-aa-bononiae": [self.BONONIA], "mr:0102-b-martyr": [self.BONONIA],
                  "mr:0103-c-bononiae": [self.BONONIA, dict(self.BONONIA, role="burial")]}
        self.assertEqual(rc.mine_genitives(entries, places), {"Q1891": rc.Counter({"bononiae": 1})})

    def test_after_a_preposition_not_a_genitive(self):
        entries = [{"id": "mr:0224-constantius-de-fabriano"}]
        places = {"mr:0224-constantius-de-fabriano": [{"role": "death", "la": "Fabriáno", "qid": "Q13145"}]}
        self.assertEqual(rc.mine_genitives(entries, places), {})

    def test_one_id_is_not_certain(self):
        self.assertEqual(rc.certain_genitives({"Q1891": rc.Counter({"bononiae": 1})}), ({}, {}))

    def test_two_genitives_conflict(self):
        mined = {"Q220": rc.Counter({"romae": 2, "urbis": 1}), "Q1891": rc.Counter({"bononiae": 2})}
        self.assertEqual(rc.certain_genitives(mined), ({"Q1891": "bononiae"}, {"Q220": ["romae", "urbis"]}))

    def test_certain_from_map(self):
        p = {"qid": "Q1891", "nominative": "Bononia", "genitive": "Bononiae", "printed": "Bonóniæ"}
        self.assertEqual(rc.genitive_slug(p, {"Q1891": "bononiae"}), ("bononiae", True))
        self.assertEqual(rc.genitive_slug(p), ("bononiae", False))

    def test_override_wins(self):
        p = {"qid": "Q3936", "nominative": "Treviri", "genitive": None}
        self.assertEqual(rc.genitive_slug(p, {"Q3936": "trevirensium"}), ("trevirorum", True))

    def test_link_places(self):
        record = rec("Petronius", ["episcopus"], [place("see", "locative", "Bononia", "Bologna",
                                                        genitive="Bononiae")])
        record["places"][0]["printed"] = "Bonóniæ"
        linked = rc.link_places(record, [{"role": "death", "la": "Romæ", "qid": "Q220"},
                                         dict(self.BONONIA, la="In urbe Bonóniæ")])
        self.assertEqual(linked["places"][0]["qid"], "Q1891")
        self.assertNotIn("qid", record["places"][0])  # a copy

    def test_build_takes_the_certain_genitive(self):
        record = rec("Petronius", ["episcopus"], [place("see", "locative", "Bononia", "Bologna",
                                                        genitive="Bononiae")])
        record["places"][0]["printed"] = "Bonóniæ"
        ctx = CTX._replace(genitives={"Q1891": "bononiae"}, places={"mr:0104-petronius": [self.BONONIA]})
        c = rc.candidates(record, "mr:0104-petronius", "Sanctus Petronius", ctx)
        self.assertEqual((c[0]["new_id"], c[0]["certain"]), ("mr:0104-petronius-bononiae", True))
        self.assertFalse(rc.candidates(record, "mr:0104-petronius", "Sanctus Petronius", CTX)[0]["certain"])

    def test_one_id_genitive_offered_uncertain(self):
        mined = {"Q1891": rc.Counter({"bononiae": 1})}
        p = {"qid": "Q1891", "nominative": "Bononia", "genitive": None, "printed": "Bononia", "grammar": "nominative"}
        self.assertEqual(rc.genitive_slug(p, {}, mined), ("bononiae", False))
        self.assertEqual(rc.genitive_slug(dict(p, genitive="Bononiensium"), {}, mined), ("bononiensium", False))
        # two mined genitives: none is the slug's; the locative stays the last fallback
        two = {"Q1891": rc.Counter({"bononiae": 2, "felsinae": 1})}
        self.assertEqual(rc.genitive_slug(p, {}, two), (None, False))

    def test_conflict_offers_each_uncertain(self):
        record = rec("Petronius", ["episcopus"], [place("see", "locative", "Bononia", "Bologna",
                                                        genitive="Bononiae")])
        record["places"][0]["printed"] = "Bonóniæ"
        ctx = CTX._replace(places={"mr:0104-petronius": [self.BONONIA]},
                           mined={"Q1891": rc.Counter({"bononiae": 2, "felsinae": 1})})
        c = rc.candidates(record, "mr:0104-petronius", "Sanctus Petronius", ctx)
        self.assertEqual([(x["new_id"], x["category"], x["certain"]) for x in c],
                         [("mr:0104-petronius-bononiae", "place-genitive", False),
                          ("mr:0104-petronius-felsinae", "place-genitive", False)])
        self.assertEqual(c[1]["labels"]["la"], "Sanctus Petronius Felsinae")
        self.assertEqual(c[1]["basis"], "see Bonóniæ (locative); mined genitive felsinae (1 ID)")

    def test_link_falls_back_to_the_opening_place(self):
        opening = [{"role": "burial", "la": "Ravénnæ", "qid": "Q13364"},
                   {"role": "death", "la": "In Æmília", "qid": "Q1263"}]
        for kind, qid in (("see", "Q1263"), ("death", "Q1263"), ("burial", None)):
            record = rec("Petronius", [], [place(kind, "locative", "Bononia", "Bologna")])
            self.assertEqual(rc.link_places(record, opening)["places"][0].get("qid"), qid, kind)

    def test_report_conflicts_first(self):
        mined = {"Q220": {"romae": ["mr:0101-aa-romae", "mr:0102-b-romae"], "urbis": ["mr:0103-c-urbis"]},
                 "Q1891": {"bononiae": ["mr:0104-d-bononiae", "mr:0105-ee-bononiae"]},
                 "Q2": {"gerae": ["mr:0106-f-gerae"]}}
        text = rc.genitives_report(mined, {"Q220": "Rome", "Q1891": "Bologna"})
        self.assertLess(text.index("Q220"), text.index("Q1891"))
        self.assertLess(text.index("Q1891"), text.index("Q2 "))
        self.assertIn("`romae` (2: mr:0101-aa-romae, mr:0102-b-romae)", text)

    def test_report_command(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "data").mkdir()
            (root / "docs").mkdir()
            ids = ["mr:0201-aa-bononiae", "mr:0202-b-bononiae"]
            (root / "data" / "martyrology_ids.json").write_text(json.dumps({"entries": [{"id": i} for i in ids]}))
            (root / "data" / "places.json").write_text(json.dumps(
                {"places": {i: [{"role": "death", "la": "Bonóniæ"}] for i in ids}}))
            (root / "data" / "gazetteer.json").write_text(json.dumps(
                {"places": {"Bonóniæ": {"wikidata": "Q1891", "label": "Bologna"}}}))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(rc.main(["report", str(root)]), 0)
            text = (root / "docs" / "rename-genitives-report.md").read_text(encoding="utf-8")
        self.assertIn("- Q1891 Bologna: `bononiae` (2: mr:0201-aa-bononiae, mr:0202-b-bononiae)", text)


if __name__ == "__main__":
    unittest.main()
