import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import wikidata as wd  # noqa: E402


def time(t, precision=11):
    return {"mainsnak": {"datavalue": {"value": {"time": t, "precision": precision}}}}


def item(qid, value):
    return {"mainsnak": {"datavalue": {"value": {"id": value}}}}


RAW = {
    "id": "Q380649",
    "labels": {"en": {"value": "Paul Miki"}, "it": {"value": "Paolo Miki"}},
    "aliases": {"la": [{"value": "Paulus Miki"}]},
    "descriptions": {"en": {"value": "Japanese Jesuit martyr"}},
    "claims": {"P31": [item("x", "Q5")], "P411": [item("x", "Q43115")],
               "P569": [time("+1564-00-00T00:00:00Z", 9)], "P570": [time("+1597-02-05T00:00:00Z")],
               "P841": [item("x", "Q2915")]},
}


class SummarizePersonTest(unittest.TestCase):
    def test_summary(self):
        s = wd.summarize_person(RAW)
        self.assertEqual(s["wikidata"], "Q380649")
        self.assertEqual(s["label"], "Paul Miki")
        self.assertTrue(s["human"])
        self.assertEqual(s["statuses"], ["Q43115"])
        self.assertEqual(s["born"], "1564")
        self.assertEqual(s["died"], "1597-02-05")
        self.assertEqual(s["feast"], ["Q2915"])
        self.assertEqual(sorted(s["names"]), ["Paolo Miki", "Paul Miki", "Paulus Miki"])

    def test_a_human_biblical_figure_is_human(self):
        # Anna the Prophetess (Q1774668) is typed "human biblical figure", not human.
        raw = {"id": "Q1774668", "labels": {"en": {"value": "Anna"}}, "claims": {"P31": [item("x", "Q20643955")]}}
        self.assertTrue(wd.summarize_person(raw)["human"])

    def test_a_human_whose_existence_is_disputed_is_human(self):
        # Saint Prisca (Q426200), the titular of the Aventine basilica, is typed so: legendary saints are.
        raw = {"id": "Q426200", "labels": {"en": {"value": "Saint Prisca"}}, "claims": {"P31": [item("x", "Q21070568")]}}
        self.assertTrue(wd.summarize_person(raw)["human"])

    def test_a_legendary_saint_is_human(self):
        # Saint Martina (Q272101) is typed only legendary saint (Q113371917), a subclass of Q21070568.
        raw = {"id": "Q272101", "labels": {"en": {"value": "Martina of Rome"}}, "claims": {"P31": [item("x", "Q113371917")]}}
        self.assertTrue(wd.summarize_person(raw)["human"])

    def test_places_current_only(self):
        ended = item("x", "Q1")
        ended["qualifiers"] = {"P582": [{}]}
        gone = item("x", "Q220")
        gone["rank"] = "deprecated"
        raw = {"id": "Q9", "claims": {"P20": [item("x", "Q490"), gone], "P119": [ended],
                                      "P19": [item("x", "Q2")],
                                      "P937": [item("x", "Q3"), item("x", "Q4")]}}
        s = wd.summarize_person(raw)
        self.assertEqual(s["death_place"], ["Q490"])
        self.assertEqual(s["burial_place"], [])
        self.assertEqual(s["birth_place"], ["Q2"])
        self.assertEqual(s["work_places"], ["Q3", "Q4"])


    def test_signals(self):
        old = item("x", "Q1")
        old["rank"] = "deprecated"
        ext = lambda v: {"mainsnak": {"datavalue": {"value": v}}}  # noqa: E731
        stale = ext("1")
        stale["rank"] = "deprecated"
        raw = {"id": "Q9", "claims": {"P841": [old], "P6126": [stale], "P8080": [ext("V/x.htm")],
                                      "P8366": [ext("123")]}}
        # A deprecated statement is no signal; a GCatholic ID lists bishops, saints or not.
        self.assertEqual(wd.summarize_person(raw)["signals"], ["P8080"])
        self.assertEqual(wd.summarize_person({"id": "Q9", "claims": {"P8366": [ext("123")]}})["signals"], [])


class PersonSearchTest(unittest.TestCase):
    def test_searches_each_language_and_summarizes(self):
        calls = []

        def fetch(url):
            calls.append(url)
            if "wbsearchentities" in url:
                return {"search": [{"id": "Q380649"}]}
            return {"entities": {"Q380649": RAW}}

        with tempfile.TemporaryDirectory() as d:
            client = wd.Wikidata(Path(d), fetch=fetch)
            found = client.person_candidates("Paulus Miki")
        self.assertEqual([c["wikidata"] for c in found], ["Q380649"])
        searched = [u for u in calls if "wbsearchentities" in u]
        self.assertEqual(len(searched), 3)
        self.assertTrue(any("language=la" in u for u in searched))

    def test_people_summarizes_by_qid_fifty_per_request(self):
        calls = []

        def fetch(url):
            calls.append(url)
            return {"entities": {"Q380649": RAW, "Q2": {"id": "Q2", "missing": ""}}}

        qids = ["Q380649", "Q2"] + [f"Q{n}" for n in range(100, 160)]
        with tempfile.TemporaryDirectory() as d:
            found = wd.Wikidata(Path(d), fetch=fetch).people(qids)
        self.assertEqual(list(found), ["Q380649"])
        self.assertEqual(found["Q380649"], wd.summarize_person(RAW))
        self.assertEqual(len(calls), 2)

import build_person_items as bp  # noqa: E402


def cand(qid, names, died="1597-02-05", statuses=("Q43115",), human=True):
    return {"wikidata": qid, "label": names[0], "description": "", "names": list(names), "human": human,
            "statuses": list(statuses), "born": None, "died": died, "feast": []}


PERSON = {"eulogy": "mr:0206-paulus-miki-et-socii", "name": "Paulus Miki", "day": "02-05",
          "typology": "dies_natalis", "subject": "Sancti Paulus Miki et socii", "where": "text",
          "companions": ["Ioannes de Goto Soan"]}


class SearchTermsTest(unittest.TestCase):
    def test_the_english_form_first(self):
        self.assertEqual(bp.search_terms("Ioannes Talbot")[:2], ["Ioannes Talbot", "John Talbot"])
        self.assertIn("Peter Higgins", bp.search_terms("Petrus Higgins"))

    def test_names_whose_vernacular_shares_their_stem_are_sought_in_it(self):
        self.assertIn("Richard Whiting", bp.search_terms("Richardus Whiting"))
        self.assertIn("Robert Johnson", bp.search_terms("Robertus Johnson"))

    def test_names_with_another_vernacular_stem(self):
        self.assertIn("Andrew Kim Tae Gon", bp.search_terms("Andreas Kim Tae Gon"))
        self.assertIn("Edward Powell", bp.search_terms("Eduardus Powell"))
        self.assertIn("Ralph Sherwin", bp.search_terms("Radulphus Sherwin"))

    def test_a_one_word_name_is_sought_as_printed(self):
        self.assertEqual(bp.search_terms("Agathonica")[0], "Agathonica")


FORMS = {"aegidius": {"en": [["Giles", 1]], "it": [["Egidio", 1]]},
         "ioanna": {"en": [["Jeanne", 4]], "it": [["Giovanna", 5], ["Colomba", 1]]},
         "ioannes": {"en": [["John", 70]], "it": [["Giovanni", 70]]}}


class NameFormsTest(unittest.TestCase):
    """data/name_forms.json: the forms the 2004 English and Italian subjects give a Latin first name."""

    def test_its_forms_are_searched_after_the_equivalents(self):
        with mock.patch.object(bp, "NAME_FORMS", FORMS):
            self.assertIn("Giles Ruiz", bp.search_terms("Aegidius Ruiz"))
            self.assertEqual(bp.search_terms("Ioannes Talbot")[:2], ["Ioannes Talbot", "John Talbot"])
        with mock.patch.object(bp, "NAME_FORMS", {"cuthbertus": {"en": [["Cuthbert", 1]], "it": [["Cutberto", 1]]}}):
            self.assertEqual(bp.search_terms("Cuthbertus Mayne"), ["Cuthbertus Mayne", "Cuthbert Mayne", "Cutberto Mayne"])

    def test_a_form_seen_twice_is_the_same_name_one_seen_once_is_not(self):
        with mock.patch.object(bp, "NAME_FORMS", FORMS):
            self.assertTrue(bp.name_matches("Ioanna Lopez", ["Giovanna Lopez"]))
            self.assertFalse(bp.name_matches("Ioanna Lopez", ["Colomba Lopez"]))

    def test_the_committed_table_is_current(self):
        import name_forms
        repo = Path(__file__).resolve().parent.parent
        persons = json.loads((repo / "data" / "persons.json").read_text(encoding="utf-8"))["editions"][name_forms.EDITION]
        subjects = {lang: json.loads((repo / "i18n" / f"{lang}.json").read_text(encoding="utf-8"))
                    for lang in name_forms.LANGUAGES}
        committed = json.loads((repo / "data" / "name_forms.json").read_text(encoding="utf-8"))["forms"]
        self.assertEqual(committed, name_forms.harvest(persons, subjects), "run scripts/name_forms.py")


class NameMatchTest(unittest.TestCase):
    def test_latin_and_vernacular_forms(self):
        self.assertTrue(bp.name_matches("Paulus Miki", ["Paul Miki"]))
        self.assertTrue(bp.name_matches("Basilius", ["Saint Basil"]))
        self.assertTrue(bp.name_matches("Ioannes de Brito", ["John de Brito"]))  # NAME_EQUIVALENTS
        self.assertFalse(bp.name_matches("Paulus Miki", ["Peter Miki"]))
        self.assertFalse(bp.name_matches("Basilius", ["Basil the Great"]))


class EvaluateTest(unittest.TestCase):
    def test_one_passing_candidate_is_auto(self):
        r = bp.evaluate(PERSON, [cand("Q1", ["Paul Miki"]), cand("Q2", ["Paul Miki"], human=False)])
        self.assertEqual(r["auto"]["wikidata"], "Q1")

    def test_a_death_on_another_day_blocks_auto(self):
        r = bp.evaluate(PERSON, [cand("Q1", ["Paul Miki"], died="1597-03-05")])
        self.assertIsNone(r["auto"])
        self.assertTrue(any("death" in f for f in r["failed"]))

    def test_two_passing_candidates_queue(self):
        r = bp.evaluate(PERSON, [cand("Q1", ["Paul Miki"]), cand("Q2", ["Paul Miki"])])
        self.assertIsNone(r["auto"])

    def test_the_death_rule_applies_only_to_dies_natalis(self):
        r = bp.evaluate(dict(PERSON, typology="translatio"), [cand("Q1", ["Paul Miki"], died="1597")])
        self.assertEqual(r["auto"]["wikidata"], "Q1")

    def test_no_status_fails(self):
        r = bp.evaluate(PERSON, [cand("Q1", ["Paul Miki"], statuses=())])
        self.assertIsNone(r["auto"])


class FakeClient:
    def __init__(self, by_name=None, by_qid=None, fail=(), places=None, kin=None):
        self.by_name, self.by_qid, self.fail = by_name or {}, by_qid or {}, set(fail)
        self.places, self.items_calls, self.people_calls = places or {}, [], []
        self.kin, self.relatives_calls = kin or {}, []

    def person_candidates(self, name, languages=("la", "it", "en")):
        if name in self.fail:
            raise bp.WikidataError("boom")
        return [dict(c) for c in self.by_name.get(name, [])]

    def person(self, qid):
        return self.by_qid.get(qid)

    def people(self, qids):
        self.people_calls.append(list(qids))
        if "people" in self.fail:
            raise bp.WikidataError("boom")
        return {q: self.by_qid[q] for q in qids if q in self.by_qid}

    def items(self, qids):
        self.items_calls.append(list(qids))
        if "items" in self.fail:
            raise bp.WikidataError("boom")
        return {q: self.places[q] for q in qids if q in self.places}

    def relatives(self, qid):
        self.relatives_calls.append(qid)
        return [dict(c) for c in self.kin.get(qid, [])]


def member(qid, names, died="1597-03-01", source="companion:P361"):
    return dict(cand(qid, names, died=died), source=source)


class GroupRouteTest(unittest.TestCase):
    """The members of a matched companion's group (P361, P527): the group stands for the death day
    (the user's ruling, 2026-10-28: the 117 Vietnamese martyrs share 24 November, each died on his
    own day)."""
    KOZAKI = "mr:0206-paulus-miki-et-socii|Thomas Kozaki"

    def run_propose(self, kin, items=None):
        items = items if items is not None else {
            "mr:0206-paulus-miki-et-socii": {"Ioannes de Goto Soan": {"wikidata": "Q10", "status": "auto"}}}
        index = {self.KOZAKI: dict(PERSON, name="Thomas Kozaki", companions=["Ioannes de Goto Soan"])}
        client = FakeClient({"Thomas Kozaki": [], "Thomas": []}, kin={"Q10": kin})
        review = bp.new_changeset([])
        bp.propose(items, review, index, client)
        return items, review, client

    def test_a_group_member_of_the_full_name_is_matched_though_it_died_on_another_day(self):
        items, review, _ = self.run_propose([member("Q20", ["Thomas Kozaki"]), member("Q21", ["Petrus Sukejiro"])])
        self.assertEqual(items["mr:0206-paulus-miki-et-socii"]["Thomas Kozaki"], {"wikidata": "Q20", "status": "auto"})
        self.assertEqual(review["operations"], [])

    def test_kin_do_not_stand_for_the_death_day(self):
        items, review, _ = self.run_propose([member("Q22", ["Thomas Kozaki"], source="companion:P3373")])
        self.assertNotIn("Thomas Kozaki", items["mr:0206-paulus-miki-et-socii"])
        self.assertEqual([c["wikidata"] for c in review["operations"][0]["candidates"]], [])

    def test_a_member_whose_name_does_not_fit_is_left_out(self):
        items, review, _ = self.run_propose([member("Q21", ["Petrus Sukejiro"])])
        self.assertNotIn("Thomas Kozaki", items["mr:0206-paulus-miki-et-socii"])
        self.assertEqual(review["operations"][0]["candidates"], [])

    def test_a_member_of_another_given_name_is_a_candidate_not_a_match(self):
        # Kozaki fits by the surname (_fits_group_member), but "Paulus Kozaki" is not his name.
        items, review, _ = self.run_propose([member("Q23", ["Paul Kozaki"])])
        self.assertNotIn("Thomas Kozaki", items["mr:0206-paulus-miki-et-socii"])
        self.assertEqual([c["wikidata"] for c in review["operations"][0]["candidates"]], ["Q23"])

    def test_a_companion_matched_in_the_same_run_opens_the_group_route(self):
        # Paulus Miki is matched by the search; his group then finds Thomas Kozaki, in one run.
        index = {"mr:0206-paulus-miki-et-socii|Paulus Miki": dict(PERSON, companions=["Thomas Kozaki"]),
                 self.KOZAKI: dict(PERSON, name="Thomas Kozaki", companions=["Paulus Miki"])}
        client = FakeClient({"Paulus Miki": [cand("Q10", ["Paul Miki"])]}, kin={"Q10": [member("Q20", ["Thomas Kozaki"])]})
        items, review = {}, bp.new_changeset([])
        bp.propose(items, review, index, client)
        self.assertEqual(items["mr:0206-paulus-miki-et-socii"],
                         {"Paulus Miki": {"wikidata": "Q10", "status": "auto"},
                          "Thomas Kozaki": {"wikidata": "Q20", "status": "auto"}})
        self.assertEqual(review["operations"], [])

    def test_no_matched_companion_no_group_lookup(self):
        _, _, client = self.run_propose([member("Q20", ["Thomas Kozaki"])], items={})
        self.assertEqual(client.relatives_calls, [])


INDEX = {"mr:0206-paulus-miki-et-socii|Paulus Miki": PERSON,
         "mr:0206-paulus-miki-et-socii|Thomas Kozaki": dict(PERSON, name="Thomas Kozaki", where={"footnote": 1})}


class ProposeApplyTest(unittest.TestCase):
    def test_propose_writes_auto_queues_the_rest_and_keeps_decisions(self):
        items = {"mr:0206-paulus-miki-et-socii": {}}
        review = bp.new_changeset([])
        client = FakeClient({"Paulus Miki": [cand("Q1", ["Paul Miki"])], "Thomas Kozaki": []})
        not_processed = bp.propose(items, review, INDEX, client)
        self.assertEqual(not_processed, [])
        self.assertEqual(items["mr:0206-paulus-miki-et-socii"]["Paulus Miki"], {"wikidata": "Q1", "status": "auto"})
        self.assertEqual([op["id"] for op in review["operations"]], ["mr:0206-paulus-miki-et-socii|Thomas Kozaki"])
        op = review["operations"][0]
        self.assertEqual(op["op"], "resolve_person")
        self.assertEqual(op["where"], {"footnote": 1})
        # A rerun never changes a decision.
        items["mr:0206-paulus-miki-et-socii"]["Paulus Miki"] = {"wikidata": "Q9", "status": "reviewed"}
        bp.propose(items, review, INDEX, client)
        self.assertEqual(items["mr:0206-paulus-miki-et-socii"]["Paulus Miki"]["wikidata"], "Q9")

    def test_a_failed_lookup_is_not_processed(self):
        items, review = {}, bp.new_changeset([])
        out = bp.propose(items, review, INDEX, FakeClient(fail={"Paulus Miki", "Thomas Kozaki"}))
        self.assertEqual(len(out), 2)
        self.assertEqual(items, {})
        self.assertEqual(review["operations"], [])

    def test_apply_accept_edit_reject(self):
        items = {}
        review = bp.new_changeset([])
        # Thomas's only candidate has no saint status, so both persons queue.
        bp.propose(items, review, INDEX, FakeClient({"Paulus Miki": [],
                                                     "Thomas Kozaki": [cand("Q7", ["Thomas Kozaki"], statuses=())]}))
        exported = json.loads(json.dumps(review))
        for op in exported["operations"]:
            if op["name"] == "Paulus Miki":
                op["decision"], op["edited"] = "edit", {"wikidata": "Q380649"}
            else:
                op["decision"], op["edited"] = "reject", {"reason": "No item"}
        client = FakeClient(by_qid={"Q380649": cand("Q380649", ["Paul Miki"])})
        self.assertEqual(bp.apply_decisions(items, review, exported, INDEX, client), 2)
        e = items["mr:0206-paulus-miki-et-socii"]
        self.assertEqual(e["Paulus Miki"], {"wikidata": "Q380649", "status": "reviewed"})
        self.assertEqual(e["Thomas Kozaki"], {"wikidata": None, "status": "unresolved", "note": "No item"})
        self.assertEqual(review["operations"], [])

    def test_apply_refuses_an_edit_that_is_not_a_saint(self):
        items, review = {}, bp.new_changeset([])
        bp.propose(items, review, INDEX, FakeClient({"Paulus Miki": [], "Thomas Kozaki": []}))
        exported = json.loads(json.dumps(review))
        exported["operations"][0]["decision"] = "edit"
        exported["operations"][0]["edited"] = {"wikidata": "Q42"}
        with self.assertRaises(ValueError):
            bp.apply_decisions(items, review, exported, INDEX,
                               FakeClient(by_qid={"Q42": cand("Q42", ["Douglas Adams"], statuses=())}))

    def test_reject_needs_a_reason(self):
        items, review = {}, bp.new_changeset([])
        bp.propose(items, review, INDEX, FakeClient({"Paulus Miki": [], "Thomas Kozaki": []}))
        exported = json.loads(json.dumps(review))
        exported["operations"][0]["decision"] = "reject"
        exported["operations"][0]["edited"] = {"reason": " "}
        with self.assertRaises(ValueError):
            bp.apply_decisions(items, review, exported, INDEX, FakeClient())


class ValidateTest(unittest.TestCase):
    def test_validate(self):
        good = {"mr:0206-paulus-miki-et-socii": {"Paulus Miki": {"wikidata": "Q1", "status": "auto"}}}
        self.assertEqual(bp.validate(good, INDEX), [])
        self.assertTrue(bp.validate({"mr:0206-paulus-miki-et-socii": {"Nemo": {"wikidata": "Q1", "status": "auto"}}}, INDEX))
        self.assertTrue(bp.validate({"mr:0206-paulus-miki-et-socii": {"Paulus Miki": {"wikidata": None, "status": "unresolved"}}}, INDEX))
        self.assertTrue(bp.validate({"mr:0206-paulus-miki-et-socii": {"Paulus Miki": {"wikidata": "x", "status": "auto"}}}, INDEX))

    def test_every_person_has_a_status_or_a_queued_review(self):
        good = {"mr:0206-paulus-miki-et-socii": {"Paulus Miki": {"wikidata": "Q1", "status": "auto"}}}
        self.assertEqual(bp.unaccounted(good, INDEX, [{"id": "mr:0206-paulus-miki-et-socii|Thomas Kozaki"}]), [])
        self.assertEqual(bp.unaccounted(good, INDEX, []),
                         ["mr:0206-paulus-miki-et-socii|Thomas Kozaki: neither a status nor a queued review"])
        # A person whose lookup failed this run is reported as not processed instead.
        self.assertEqual(bp.unaccounted(good, INDEX, [], skipped=["mr:0206-paulus-miki-et-socii|Thomas Kozaki"]), [])


class NameMatchReviewTest(unittest.TestCase):
    """Final review: a 4-letter prefix matched different names."""

    def test_different_names_sharing_a_prefix_do_not_match(self):
        for latin, other in [("Ia", "Iacobus"), ("Leo", "Leontius"), ("Iulia", "Iulianus"), ("Victor", "Victoria"),
                             ("Felix", "Felicitas"), ("Paulus", "Paulinus"), ("Marcus", "Marcellinus"),
                             ("Petrus", "Petronilla"), ("Innocentius IV", "Innocent Iustus")]:
            self.assertFalse(bp.name_matches(latin, [other]), (latin, other))

    def test_latin_and_vernacular_forms_of_one_name_still_match(self):
        for latin, other in [("Paulus Miki", "Paul Miki"), ("Basilius", "Saint Basil"), ("Ioannes de Brito", "John de Brito"),
                             ("Petrus", "Saint Peter"), ("Leo", "Leo"), ("Innocentius IV", "Innocent IV"),
                             ("Caecilia", "Cecilia"), ("Augustinus", "Augustine")]:
            self.assertTrue(bp.name_matches(latin, [other]), (latin, other))

    def test_english_ius_as_y_and_antonius(self):
        for latin, other in [("Hilarius", "Hilary of Poitiers"), ("Gregorius", "Saint Gregory"), ("Antonius", "Anthony"),
                             ("Antonius", "Antoine"), ("Gregorius Nyssenus", "Gregory Nyssenus")]:
            self.assertTrue(bp.name_matches(latin, [other.replace(" of Poitiers", "")]), (latin, other))
        for latin, other in [("Marius", "Mary"), ("Lucius", "Lucy"), ("Hilarius", "Hilda")]:
            self.assertFalse(bp.name_matches(latin, [other]), (latin, other))


class LagBreakerTest(unittest.TestCase):
    def test_propose_stops_early_after_consecutive_failures_and_leaves_the_rest_unprocessed(self):
        index = {f"mr:0101-x|N{i}": dict(PERSON, name=f"N{i}") for i in range(20)}
        client = FakeClient(fail={f"N{i}" for i in range(20)})
        calls = []
        orig = client.person_candidates
        client.person_candidates = lambda name, languages=(): calls.append(name) or orig(name, languages)
        items, review = {}, bp.new_changeset([])
        out = bp.propose(items, review, index, client)
        self.assertEqual(len(out), 20)                  # every person reported as not processed
        self.assertEqual(len(calls), bp.MAX_CONSECUTIVE_FAILURES)  # but only the first few asked
        self.assertEqual(items, {})


class SanctityTitlesTest(unittest.TestCase):
    """The round trip found saints Wikidata records by an Eastern or ancient title (Telemachus: Reverend Martyr)."""

    def test_saints_by_title_pass_the_status_rule(self):
        for title in ["Q4377390", "Q2993173", "Q1349880", "Q18344276", "Q3332786", "Q2032316"]:
            r = bp.evaluate(dict(PERSON, typology="translatio"), [cand("Q1", ["Paul Miki"], statuses=(title,))])
            self.assertIsNotNone(r["auto"], title)

    def test_venerable_and_servant_of_god_do_not(self):
        for title in ["Q12774503", "Q51619", "Q869974"]:
            r = bp.evaluate(dict(PERSON, typology="translatio"), [cand("Q1", ["Paul Miki"], statuses=(title,))])
            self.assertIsNone(r["auto"], title)


class UserPolicyTest(unittest.TestCase):
    """The user's rulings after the first full run (2026-10-09)."""

    def test_a_death_date_known_to_the_month_counts_when_the_month_matches(self):
        self.assertIsNotNone(bp.evaluate(PERSON, [cand("Q1", ["Paul Miki"], died="1597-02")])["auto"])

    def test_a_year_only_death_date_does_not_count(self):
        # A eulogy has no year: a year can be checked against nothing (the user's ruling after the
        # sample: Zacharias matched the biblical prophet, Papias Papias of Hierapolis).
        self.assertIsNone(bp.evaluate(PERSON, [cand("Q1", ["Paul Miki"], died="1597")])["auto"])

    def test_a_coarse_date_that_contradicts_or_no_date_does_not(self):
        self.assertIsNone(bp.evaluate(PERSON, [cand("Q1", ["Paul Miki"], died="1597-03")])["auto"])
        self.assertIsNone(bp.evaluate(PERSON, [cand("Q1", ["Paul Miki"], died=None)])["auto"])
        self.assertIsNone(bp.evaluate(PERSON, [cand("Q1", ["Paul Miki"], died="1597-02-06")])["auto"])

    def test_the_report_lists_automatic_matches_without_a_date_check(self):
        index = {"mr:0107-valentinus|Valentinus": dict(PERSON, eulogy="mr:0107-valentinus", name="Valentinus",
                                                       typology="commemoratio"),
                 "mr:0206-paulus-miki-et-socii|Paulus Miki": PERSON}
        items = {"mr:0107-valentinus": {"Valentinus": {"wikidata": "Q1", "status": "auto"}},
                 "mr:0206-paulus-miki-et-socii": {"Paulus Miki": {"wikidata": "Q2", "status": "auto"}}}
        report = bp.render_report(items, index, [])
        self.assertIn("mr:0107-valentinus|Valentinus: Q1", report)
        self.assertNotIn("Paulus Miki: Q2", report)

    def test_a_forced_person_is_queued_even_when_one_candidate_passes(self):
        items, review = {}, bp.new_changeset([])
        index = {"mr:0206-paulus-miki-et-socii|Paulus Miki": PERSON}
        bp.propose(items, review, index, FakeClient({"Paulus Miki": [cand("Q1", ["Paul Miki"])]}),
                   force_review={"mr:0206-paulus-miki-et-socii|Paulus Miki": "a namesake"})
        self.assertEqual(items, {})
        self.assertIn("forced review: a namesake", review["operations"][0]["failed"])


class EditNeedsAQidTest(unittest.TestCase):
    def test_an_edit_without_a_qid_is_an_error_not_the_suggestion(self):
        items, review = {}, bp.new_changeset([])
        bp.propose(items, review, INDEX, FakeClient({"Paulus Miki": [cand("Q7", ["Paul Miki"], statuses=())],
                                                     "Thomas Kozaki": []}))
        exported = json.loads(json.dumps(review))
        op = next(o for o in exported["operations"] if o["name"] == "Paulus Miki")
        op["suggested"] = {"wikidata": "Q380649"}
        op["decision"], op["edited"] = "edit", {}
        with self.assertRaisesRegex(ValueError, "no item chosen"):
            bp.apply_decisions(items, review, exported, INDEX,
                               FakeClient(by_qid={"Q380649": cand("Q380649", ["Paul Miki"])}))


class SharedItemTest(unittest.TestCase):
    """The user's ruling after the #79 review: an item matched in several eulogies through a one-word
    name is usually a famous namesake, so none of those matches is automatic."""

    def _index(self):
        und = dict(PERSON, typology="commemoratio")
        return {"mr:0802-eusebius|Eusebius": dict(und, eulogy="mr:0802-eusebius", name="Eusebius"),
                "mr:0926-eusebius|Eusebius": dict(und, eulogy="mr:0926-eusebius", name="Eusebius"),
                "mr:0101-x|Eusebius Fictus": dict(und, eulogy="mr:0101-x", name="Eusebius Fictus"),
                "mr:0103-y|Gordius": dict(und, eulogy="mr:0103-y", name="Gordius")}

    def test_a_one_word_name_whose_item_is_matched_elsewhere_is_queued(self):
        items, review = {}, bp.new_changeset([])
        client = FakeClient({"Eusebius": [cand("Q1", ["Eusebius"])], "Eusebius Fictus": [cand("Q1", ["Eusebius Fictus"])],
                             "Gordius": [cand("Q2", ["Gordius"])]})
        bp.propose(items, review, self._index(), client)
        queued = {op["id"]: op for op in review["operations"]}
        self.assertIn("mr:0802-eusebius|Eusebius", queued)
        self.assertIn("mr:0926-eusebius|Eusebius", queued)
        self.assertIn("matched in another eulogy", queued["mr:0802-eusebius|Eusebius"]["failed"][-1])
        self.assertEqual(items["mr:0101-x"]["Eusebius Fictus"]["wikidata"], "Q1")  # a full name stays automatic
        self.assertEqual(items["mr:0103-y"]["Gordius"]["wikidata"], "Q2")          # matched once: automatic

    def test_an_existing_automatic_match_counts_too(self):
        items = {"mr:0802-eusebius": {"Eusebius": {"wikidata": "Q1", "status": "auto"}}}
        review = bp.new_changeset([])
        index = {k: v for k, v in self._index().items() if k == "mr:0926-eusebius|Eusebius"}
        index["mr:0802-eusebius|Eusebius"] = self._index()["mr:0802-eusebius|Eusebius"]
        bp.propose(items, review, index, FakeClient({"Eusebius": [cand("Q1", ["Eusebius"])]}))
        queued = {op["id"] for op in review["operations"]}
        self.assertIn("mr:0926-eusebius|Eusebius", queued)
        # The existing automatic match is withdrawn too (#79 review): none of them is automatic.
        self.assertIn("mr:0802-eusebius|Eusebius", queued)
        self.assertNotIn("mr:0802-eusebius", items)

    def test_a_full_name_match_elsewhere_queues_the_one_word_match(self):
        und = dict(PERSON, typology="commemoratio")
        index = {"mr:0526-augustinus|Augustinus": dict(und, eulogy="mr:0526-augustinus", name="Augustinus"),
                 "mr:0828-augustinus|Aurelius Augustinus": dict(und, eulogy="mr:0828-augustinus", name="Aurelius Augustinus")}
        items, review = {}, bp.new_changeset([])
        bp.propose(items, review, index, FakeClient({"Augustinus": [cand("Q8018", ["Augustinus"])],
                                                     "Aurelius Augustinus": [cand("Q8018", ["Aurelius Augustinus"])]}))
        self.assertEqual([op["id"] for op in review["operations"]], ["mr:0526-augustinus|Augustinus"])
        self.assertEqual(items["mr:0828-augustinus"]["Aurelius Augustinus"]["wikidata"], "Q8018")

    def test_a_curators_decision_is_never_withdrawn(self):
        items = {"mr:0802-eusebius": {"Eusebius": {"wikidata": "Q1", "status": "reviewed"}}}
        review = bp.new_changeset([])
        index = {"mr:0802-eusebius|Eusebius": self._index()["mr:0802-eusebius|Eusebius"],
                 "mr:0926-eusebius|Eusebius": self._index()["mr:0926-eusebius|Eusebius"]}
        bp.propose(items, review, index, FakeClient({"Eusebius": [cand("Q1", ["Eusebius"])]}))
        self.assertEqual(items["mr:0802-eusebius"]["Eusebius"]["status"], "reviewed")


class OneWordListNameTest(unittest.TestCase):
    """A one-word name in a footnote list (an obscure companion) is automatic only when the item's
    death date is the eulogy's very day: Cornelius of the martyrs of Lyons matched Pope Cornelius
    (died in June, the month of 2 June), Kizito of the Uganda martyrs is right (died 3 June)."""

    LISTED = dict(PERSON, eulogy="mr:0602-pothinus-et-socii", name="Cornelius", day="06-02", where={"footnote": 1})

    def test_a_month_only_death_date_is_not_enough(self):
        r = bp.evaluate(self.LISTED, [cand("Q54798", ["Cornelius"], died="0253-06")])
        self.assertIsNone(r["auto"])
        self.assertIn("one-word name in a footnote list", r["failed"][-1])

    def test_no_death_date_is_not_enough_even_without_a_death_rule(self):
        r = bp.evaluate(dict(self.LISTED, typology="commemoratio"), [cand("Q1", ["Cornelius"], died=None)])
        self.assertIsNone(r["auto"])

    def test_the_very_day_is_enough(self):
        kizito = dict(self.LISTED, eulogy="mr:0603-carolus-lwanga-et-socii", name="Kizito", day="06-03")
        self.assertEqual(bp.evaluate(kizito, [cand("Q3463928", ["Kizito"], died="1886-06-03")])["auto"]["wikidata"],
                         "Q3463928")

    def test_a_one_word_name_in_the_text_keeps_the_month_rule(self):
        text = dict(self.LISTED, where="text")
        self.assertEqual(bp.evaluate(text, [cand("Q54798", ["Cornelius"], died="0253-06")])["auto"]["wikidata"], "Q54798")

    def test_propose_withdraws_an_existing_automatic_match_that_fails_it(self):
        items = {"mr:0602-pothinus-et-socii": {"Cornelius": {"wikidata": "Q54798", "status": "auto"}}}
        review = bp.new_changeset([])
        index = {"mr:0602-pothinus-et-socii|Cornelius": self.LISTED}
        bp.propose(items, review, index, FakeClient({"Cornelius": [cand("Q54798", ["Cornelius"], died="0253-06")]}))
        self.assertNotIn("mr:0602-pothinus-et-socii", items)
        self.assertEqual([op["id"] for op in review["operations"]], ["mr:0602-pothinus-et-socii|Cornelius"])

    def test_propose_keeps_a_match_whose_item_the_search_did_not_return(self):
        # Its date is unchecked: an incomplete search is no reason to withdraw it.
        items = {"mr:0602-pothinus-et-socii": {"Cornelius": {"wikidata": "Q54798", "status": "auto"}}}
        review = bp.new_changeset([])
        index = {"mr:0602-pothinus-et-socii|Cornelius": self.LISTED}
        bp.propose(items, review, index, FakeClient({"Cornelius": [cand("Q1", ["Cornelius"], died="0300-01-01")]}))
        self.assertEqual(items["mr:0602-pothinus-et-socii"]["Cornelius"], {"wikidata": "Q54798", "status": "auto"})
        self.assertEqual(review["operations"], [])

    def test_a_curators_decision_is_never_withdrawn(self):
        items = {"mr:0602-pothinus-et-socii": {"Cornelius": {"wikidata": "Q54798", "status": "reviewed"}}}
        review = bp.new_changeset([])
        bp.propose(items, review, {"mr:0602-pothinus-et-socii|Cornelius": self.LISTED},
                   FakeClient({"Cornelius": [cand("Q54798", ["Cornelius"], died="0253-06")]}))
        self.assertEqual(items["mr:0602-pothinus-et-socii"]["Cornelius"]["status"], "reviewed")


class OneWordCompanionTest(unittest.TestCase):
    """A one-word companion of the text that the subject does not name, in a eulogy with no death-day
    rule, is automatic only when the item died on the eulogy's very day: Lucas with Silvanus
    (6 February) matched Luke the Evangelist, Moyses with Bassianus (14 February) Moses."""

    LUCAS = dict(PERSON, eulogy="mr:0206-silvanus", name="Lucas", day="02-06", typology="commemoratio",
                 subject="Sanctus Silvanus")

    def test_a_namesake_without_the_very_day_is_queued(self):
        r = bp.evaluate(self.LUCAS, [cand("Q128538", ["Lucas"], died=None)])
        self.assertIsNone(r["auto"])
        self.assertIn("one-word companion", r["failed"][-1])

    def test_the_very_day_is_enough(self):
        self.assertEqual(bp.evaluate(self.LUCAS, [cand("Q1", ["Lucas"], died="0312-02-06")])["auto"]["wikidata"], "Q1")

    def test_a_saint_the_subject_names_is_not_a_companion(self):
        silvanus = dict(self.LUCAS, name="Silvanus")
        self.assertEqual(bp.evaluate(silvanus, [cand("Q1", ["Silvanus"], died=None)])["auto"]["wikidata"], "Q1")

    def test_propose_withdraws_an_existing_automatic_match_that_fails_it(self):
        items = {"mr:0206-silvanus": {"Lucas": {"wikidata": "Q128538", "status": "auto"}}}
        review = bp.new_changeset([])
        bp.propose(items, review, {"mr:0206-silvanus|Lucas": self.LUCAS},
                   FakeClient({"Lucas": [cand("Q128538", ["Lucas"], died=None)]}))
        self.assertNotIn("mr:0206-silvanus", items)
        self.assertEqual([op["id"] for op in review["operations"]], ["mr:0206-silvanus|Lucas"])


class RepeatedNamesTest(unittest.TestCase):
    """Two persons of one name in one eulogy (2026-10-10 spec)."""

    DOC = {"editions": {"martyrologium_romanum_2004": {"mr:0212-x": [
        {"name": "Felix", "where": {"footnote": 1}}, {"name": "Felix", "n": 2, "where": {"footnote": 1}},
        {"name": "Secunda", "where": {"footnote": 1}}, {"name": "Secunda", "n": 2, "where": {"footnote": 1}}]}}}
    ENTRIES = [{"id": "mr:0212-x", "month": 2, "day": 12}]

    def index(self):
        return bp.person_index(self.DOC, self.ENTRIES, {"mr:0212-x": "dies_natalis"}, {"mr:0212-x": "Sancti X"})

    def test_the_index_keys_a_second_person_by_name_and_n(self):
        index = self.index()
        self.assertEqual(sorted(index), ["mr:0212-x|Felix", "mr:0212-x|Felix#2", "mr:0212-x|Secunda",
                                         "mr:0212-x|Secunda#2"])
        self.assertEqual(index["mr:0212-x|Felix#2"]["n"], 2)
        self.assertNotIn("n", index["mr:0212-x|Felix"])
        self.assertEqual(index["mr:0212-x|Felix#2"]["companions"], ["Secunda"])

    def test_propose_decides_and_queues_each_person_under_its_key(self):
        items, review = {}, bp.new_changeset([])
        client = FakeClient({"Felix": [cand("Q1", ["Felix"], died="0304-02-12")], "Secunda": []})
        bp.propose(items, review, self.index(), client)
        # Both Felixes matched the same item: neither is automatic.
        queued = {op["id"]: op for op in review["operations"]}
        self.assertIn("mr:0212-x|Felix#2", queued)
        self.assertIn("mr:0212-x|Felix", queued)
        self.assertEqual(queued["mr:0212-x|Felix#2"]["n"], 2)
        self.assertEqual(list(queued["mr:0212-x|Felix#2"])[5:8], ["subject", "name", "n"])
        self.assertIn("another person of this eulogy", queued["mr:0212-x|Felix#2"]["failed"][-1])
        self.assertNotIn("mr:0212-x", items)

    def test_an_item_already_decided_for_another_person_of_the_eulogy_is_not_automatic(self):
        items = {"mr:0212-x": {"Felix": {"wikidata": "Q1", "status": "reviewed"}}}
        review = bp.new_changeset([])
        bp.propose(items, review, self.index(), FakeClient({"Felix": [cand("Q1", ["Felix"], died="0304-02-12")],
                                                            "Secunda": []}))
        self.assertIn("mr:0212-x|Felix#2", {op["id"] for op in review["operations"]})
        self.assertEqual(items["mr:0212-x"], {"Felix": {"wikidata": "Q1", "status": "reviewed"}})

    def test_apply_writes_a_second_person_under_its_key(self):
        items, review = {}, bp.new_changeset([])
        bp.propose(items, review, self.index(), FakeClient({"Felix": [], "Secunda": []}))
        exported = json.loads(json.dumps(review))
        for op in exported["operations"]:
            if op["id"] == "mr:0212-x|Felix#2":
                op["decision"], op["edited"] = "edit", {"wikidata": "Q2"}
        bp.apply_decisions(items, review, exported, self.index(), FakeClient(by_qid={"Q2": cand("Q2", ["Felix"])}))
        self.assertEqual(items, {"mr:0212-x": {"Felix#2": {"wikidata": "Q2", "status": "reviewed"}}})

    def test_apply_refuses_one_item_for_two_persons_of_a_eulogy(self):
        client = FakeClient(by_qid={"Q2": cand("Q2", ["Felix"])})
        # Within one change-set:
        items, review = {}, bp.new_changeset([])
        bp.propose(items, review, self.index(), FakeClient({"Felix": [], "Secunda": []}))
        exported = json.loads(json.dumps(review))
        for op in exported["operations"]:
            if op["name"] == "Felix":
                op["decision"], op["edited"] = "edit", {"wikidata": "Q2"}
        with self.assertRaises(ValueError) as e:
            bp.apply_decisions(items, review, exported, self.index(), client)
        self.assertIn("Q2", str(e.exception))
        self.assertEqual(items, {})
        # Against a decision already in the file:
        items = {"mr:0212-x": {"Felix": {"wikidata": "Q2", "status": "reviewed"}}}
        exported["operations"] = [op for op in exported["operations"] if op["id"] == "mr:0212-x|Felix#2"]
        with self.assertRaises(ValueError):
            bp.apply_decisions(items, review, exported, self.index(), client)
        self.assertEqual(items, {"mr:0212-x": {"Felix": {"wikidata": "Q2", "status": "reviewed"}}})

    def test_check_accepts_a_second_person_and_reports_a_shared_item(self):
        index = self.index()
        self.assertEqual(bp.validate({"mr:0212-x": {"Felix#2": {"wikidata": "Q2", "status": "auto"}}}, index), [])
        self.assertTrue(bp.validate({"mr:0212-x": {"Felix#3": {"wikidata": "Q3", "status": "auto"}}}, index))
        errors = bp.validate({"mr:0212-x": {"Felix": {"wikidata": "Q2", "status": "auto"},
                                            "Felix#2": {"wikidata": "Q2", "status": "reviewed"}}}, index)
        self.assertTrue(any("Q2" in e for e in errors))

    def test_the_report_reads_a_second_persons_own_decision(self):
        index = bp.person_index(self.DOC, self.ENTRIES, {"mr:0212-x": "commemoratio"}, {"mr:0212-x": "Sancti X"})
        items = {"mr:0212-x": {"Felix": {"wikidata": "Q1", "status": "reviewed"},
                               "Felix#2": {"wikidata": "Q2", "status": "auto"}}}
        report = bp.render_report(items, index, [])
        self.assertIn("mr:0212-x|Felix#2: Q2", report)
        self.assertNotIn("mr:0212-x|Felix: Q1", report)  # reviewed: not an automatic match

    def test_propose_drops_a_queued_op_whose_person_is_gone(self):
        items, review = {}, bp.new_changeset([])
        bp.propose(items, review, self.index(), FakeClient({"Felix": [], "Secunda": []}))
        self.assertIn("mr:0212-x|Secunda#2", {op["id"] for op in review["operations"]})
        # The list is corrected: there is one Secunda after all.
        index = {k: v for k, v in self.index().items() if k != "mr:0212-x|Secunda#2"}
        bp.propose(items, review, index, FakeClient({"Felix": [], "Secunda": []}))
        self.assertNotIn("mr:0212-x|Secunda#2", {op["id"] for op in review["operations"]})
        self.assertEqual(bp.validate(items, index, review["operations"]), [])


class VariantsTest(unittest.TestCase):
    DOC = {"editions": {"martyrologium_romanum_2004": {"mr:0724-kinga": [
        {"name": "Kinga", "also": ["Cunegundis"], "where": "text"}]}}}
    ENTRIES = [{"id": "mr:0724-kinga", "month": 7, "day": 24}]

    def index(self):
        return bp.person_index(self.DOC, self.ENTRIES, {"mr:0724-kinga": "dies_natalis"}, {"mr:0724-kinga": "Sancta Kinga"})

    def test_the_index_and_the_op_carry_also(self):
        person = self.index()["mr:0724-kinga|Kinga"]
        self.assertEqual(person["also"], ["Cunegundis"])
        op = bp.make_op("mr:0724-kinga|Kinga", person, {"failed": [], "candidates": []}, None)
        self.assertEqual(list(op)[5:8], ["subject", "name", "also"])

    def test_the_search_tries_each_name_and_a_variant_satisfies_the_name_rule(self):
        searched = []

        class Client(FakeClient):
            def person_candidates(self, name, languages=("la", "it", "en")):
                searched.append(name)
                return [cand("Q1", ["Cunegundis"], died="1292-07-24")] if name == "Cunegundis" else []

        person = self.index()["mr:0724-kinga|Kinga"]
        cands = bp.gather(person, Client())
        self.assertIn("Cunegundis", searched)
        self.assertEqual(bp.evaluate(person, cands)["auto"]["wikidata"], "Q1")

    def test_a_queued_op_takes_the_persons_details_even_when_the_lookup_fails(self):
        index = self.index()
        review = bp.new_changeset([])
        bp.propose({}, review, {k: dict(v, also=[]) for k, v in index.items()}, FakeClient({"Kinga": []}))
        before = review["operations"][0]
        bp.propose({}, review, index, FakeClient(fail={"Kinga", "Cunegundis"}))
        op = review["operations"][0]
        self.assertEqual(op["also"], ["Cunegundis"])
        self.assertEqual((op["candidates"], op["failed"]), (before["candidates"], before["failed"]))


class ExpandTest(unittest.TestCase):
    class Client(FakeClient):
        def __init__(self, **kw):
            super().__init__(**kw)
            self.kin, self.day, self.titles, self.calls = {}, [], [], []
            self.place, self.place_calls = [], []
            self.name_place, self.name_place_calls = [], []
            self.rare, self.rare_calls = [], []
            self.feast, self.feast_calls = [], []
            self.surname, self.surname_calls = {}, []

        def saints_by_feast_day(self, month, day, given, matches=None):
            self.feast_calls.append((month, day, given))
            return [dict(c, source="feast") for c in self.feast]

        def saints_by_name(self, name):
            self.rare_calls.append(name)
            return [dict(c, source="name") for c in self.rare]

        def saints_by_surname(self, surname):
            self.surname_calls.append(surname)
            return [dict(c, source="surname") for c in self.surname.get(surname, [])]

        def relatives(self, qid):
            if qid in self.fail:
                raise bp.WikidataError("boom")
            return [dict(c) for c in self.kin.get(qid, [])]

        def saints_by_death_day(self, month, day, given, year=None, matches=None):
            self.calls.append((month, day, given, year))
            self.matches = matches
            return [dict(c, source="sparql") for c in self.day]

        def saints_by_place(self, qids, given, matches=None):
            self.place_calls.append((list(qids), given))
            return [dict(c, source="place") for c in self.place]

        def saints_by_name_and_place(self, name, labels):
            self.name_place_calls.append((name, list(labels)))
            return [dict(c, source="place") for c in self.name_place]

        def title_candidates(self, text):
            return [dict(c, source="title") for c in self.titles]

    def op(self, **kw):
        base = {"op": "resolve_person", "id": "mr:0101-ioannes-et-renatus-lego|Ioannes",
                "eulogy": "mr:0101-ioannes-et-renatus-lego", "day": "01-01", "typology": "dies_natalis",
                "subject": "Ioannes et Renatus Lego", "name": "Ioannes", "companions": ["Renatus Lego"],
                "failed": [], "candidates": [dict(cand("Q9", ["John"]), evidence=["human"])],
                "decision": None, "edited": None}
        return dict(base, **kw)

    def run_expand(self, op, client, items=None, record=None, places=None):
        review = bp.new_changeset([op])
        items = {"mr:0101-ioannes-et-renatus-lego": {"Renatus Lego": {"wikidata": "Q2652595", "status": "reviewed"}}
                 } if items is None else items
        records = {op["eulogy"]: [record or {"id": op["eulogy"], "name": op["name"], "kind": "person",
                                             "death_year": 1642}]}
        return bp.expand(review, items, records, client, places), review["operations"][0]

    def test_sibling_found(self):
        client = self.Client(by_qid={"Q2652595": cand("Q2652595", ["Renatus Lego"])})
        client.kin = {"Q2652595": [dict(cand("Q52161488", ["Ioannes Lego"]), source="companion:P3373")]}
        left, op = self.run_expand(self.op(), client)
        self.assertEqual(left, [])
        self.assertIn(("Q52161488", "companion:P3373"), {(c["wikidata"], c["source"]) for c in op["candidates"]})
        self.assertEqual(next(c for c in op["candidates"] if c["wikidata"] == "Q9")["source"], "search")
        self.assertIn("status", next(c for c in op["candidates"] if c["wikidata"] == "Q52161488")["evidence"])

    def test_group_members_must_fit_the_name_kin_need_not(self):
        client = self.Client(by_qid={"Q2652595": cand("Q2652595", ["Renatus Lego"])})
        client.kin = {"Q2652595": [dict(cand("Q52161488", ["Jean Légo"]), source="companion:P361"),
                                   dict(cand("Q118445257", ["Marie-Anne Vaillot"]), source="companion:P361"),
                                   dict(cand("Q7", ["Pierre Lego"]), source="companion:P3373")]}
        _, op = self.run_expand(self.op(candidates=[]), client)
        self.assertEqual({c["wikidata"] for c in op["candidates"]}, {"Q52161488", "Q7"})

    def test_expand_drops_earlier_group_members_that_do_not_fit(self):
        client = self.Client(by_qid={"Q2652595": cand("Q2652595", ["Renatus Lego"])})
        member = lambda q, n: dict(cand(q, [n]), source="companion:P361", evidence=["human"])
        op = self.op(candidates=[member("Q1", "Odile Baumgarten"), dict(cand("Q9", ["John"]), evidence=["human"]),
                                 member("Q2", "Marie-Anne Vaillot"), member("Q3", "Jean Légo"),
                                 member("Q4", "Natalis Pinot")],
                     decision="edit", edited={"wikidata": "Q4"})
        _, got = self.run_expand(op, client)
        # the first stays (an accept means candidates[0]), and so does the decided pick
        self.assertEqual([c["wikidata"] for c in got["candidates"]], ["Q1", "Q9", "Q3", "Q4"])

    def test_expand_drops_an_open_cards_first_group_member_that_does_not_fit(self):
        # Andreas Duliou, in the footnote of Turpin du Cormier and companions, was offered only
        # Turpin du Cormier's item: on an open card the first candidate has no accept to keep.
        client = self.Client(by_qid={"Q2652595": cand("Q2652595", ["Renatus Lego"])})
        member = lambda q, n: dict(cand(q, [n]), source="companion:P361", evidence=["human"])
        op = self.op(candidates=[member("Q1", "Odile Baumgarten"), member("Q3", "Jean Légo")])
        _, got = self.run_expand(op, client)
        self.assertEqual([c["wikidata"] for c in got["candidates"]], ["Q3"])

    def test_a_suggestion_naming_a_dropped_group_member_is_cleared(self):
        # An accept applies the suggestion first: it must not name a candidate that was dropped.
        client = self.Client(by_qid={"Q2652595": cand("Q2652595", ["Renatus Lego"])})
        member = lambda q, n: dict(cand(q, [n]), source="companion:P361", evidence=["human"])
        op = self.op(candidates=[member("Q1", "Odile Baumgarten"), member("Q3", "Jean Légo")],
                     suggested={"wikidata": "Q1"}, reasoning="r", confidence="high")
        _, got = self.run_expand(op, client)
        self.assertEqual([c["wikidata"] for c in got["candidates"]], ["Q3"])
        self.assertFalse({"suggested", "reasoning", "confidence"} & set(got))

    def test_a_second_given_name_is_not_a_surname(self):
        # Maria Anna Vaillot does not fit Anna Francisca de Villeneuve, a martyr of the same group.
        client = self.Client(by_qid={"Q2652595": cand("Q2652595", ["Renatus Lego"])})
        client.kin = {"Q2652595": [dict(cand("Q141886840", ["Anna Francisca de Villeneuve"]), source="companion:P361"),
                                   dict(cand("Q118445257", ["Marie-Anne Vaillot"]), source="companion:P361")]}
        op = self.op(name="Maria Anna Vaillot", companions=["Renatus Lego", "Anna Francisca de Villeneuve"], candidates=[])
        _, got = self.run_expand(op, client, record={"id": op["eulogy"], "name": op["name"], "kind": "person"})
        self.assertEqual([c["wikidata"] for c in got["candidates"]], ["Q118445257"])

    def test_a_group_member_sharing_an_earlier_surname_fits(self):
        # Migoret-Lamberdiere on Wikidata, Migoret Lambardière in the 2004 list: the last word differs.
        client = self.Client(by_qid={"Q2652595": cand("Q2652595", ["Renatus Lego"])})
        client.kin = {"Q2652595": [dict(cand("Q29635385", ["Francois Migoret-Lamberdiere"]), source="companion:P361")]}
        op = self.op(name="Franciscus Migoret Lambardière", candidates=[])
        _, got = self.run_expand(op, client, record={"id": op["eulogy"], "name": op["name"], "kind": "person"})
        self.assertEqual([c["wikidata"] for c in got["candidates"]], ["Q29635385"])

    def test_a_group_member_sharing_the_surname_fits(self):
        # Aloysius is Louis: the given names differ in the loaded labels, the surname does not.
        client = self.Client(by_qid={"Q2652595": cand("Q2652595", ["Renatus Lego"])})
        client.kin = {"Q2652595": [dict(cand("Q536708", ["Louis Lego"]), source="companion:P361"),
                                   dict(cand("Q4075367", ["Bai Xiaoman"]), source="companion:P361")]}
        op = self.op(name="Aloysius Lego", candidates=[])
        _, got = self.run_expand(op, client, record={"id": op["eulogy"], "name": "Aloysius Lego", "kind": "person"})
        self.assertEqual([c["wikidata"] for c in got["candidates"]], ["Q536708"])

    def test_first_name_forms_must_fit_a_longer_name(self):
        # "Mary Verona" finds every Mary of Verona: only the person's own names are trusted as matched.
        class Client(self.Client):
            def saints_by_name_and_place(self, name, labels):
                self.name_place_calls.append((name, list(labels)))
                if name == "Maria Dominica Lego":
                    return [dict(cand("Q1", ["Mariae Dominicae"]), source="place")]
                if len(name.split()) == 1:  # a first-name form alone: every Mary of the place
                    return [dict(cand("Q2", ["Vincenza Maria Poloni"]), source="place")]
                return []
        client = Client()
        places = {"mr:0101-ioannes-et-renatus-lego": [{"role": "death", "la": "Veronae", "qid": "Q2028", "label": "Verona"}]}
        op = self.op(name="Maria Dominica Lego", companions=[], candidates=[])
        _, got = self.run_expand(op, client, record={"id": op["eulogy"], "name": "Maria Dominica Lego", "kind": "person"},
                                 places=places)
        self.assertEqual([c["wikidata"] for c in got["candidates"]], ["Q1"])

    def test_unresolved_companion_adds_nothing(self):
        client = self.Client(by_qid={"Q2652595": cand("Q2652595", ["Renatus Lego"])})
        client.kin = {"Q2652595": [dict(cand("Q52161488", ["Ioannes Lego"]), source="companion:P3373")]}
        items = {"mr:0101-ioannes-et-renatus-lego": {"Renatus Lego": {"wikidata": None, "status": "unresolved",
                                                                      "note": "x"}}}
        _, op = self.run_expand(self.op(), client, items)
        self.assertEqual([c["wikidata"] for c in op["candidates"]], ["Q9"])

    def test_non_human_companion_adds_nothing(self):
        client = self.Client(by_qid={"Q2652595": cand("Q2652595", ["Lego"], human=False)})
        client.kin = {"Q2652595": [dict(cand("Q52161488", ["Ioannes Lego"]), source="companion:P3373")]}
        _, op = self.run_expand(self.op(), client)
        self.assertEqual([c["wikidata"] for c in op["candidates"]], ["Q9"])

    def test_place_route(self):
        client = self.Client()
        client.day = [cand("Q5", ["Ioannes Lego"], died="1642-01-01")]
        client.place = [cand("Q6", ["Ioannes Lego"], died="1650-03-03")]
        places = {"mr:0101-ioannes-et-renatus-lego": [
            {"role": "death", "la": "Lutetiae", "qid": "Q90", "label": "Paris"},
            {"role": "burial", "la": "Romae", "qid": "Q91", "label": "Rome"},
            {"role": "birth", "la": "Nanneti", "qid": "Q92", "label": "Nantes"},
            {"role": "death", "la": "?", "qid": None, "label": None}]}
        _, op = self.run_expand(self.op(companions=[], candidates=[]), client, places=places)
        self.assertEqual(client.place_calls[0][0], ["Q90", "Q91"])
        self.assertEqual([c["wikidata"] for c in op["candidates"]][-2:].count("Q6"), 1)
        self.assertEqual({(c["wikidata"], c["source"]) for c in op["candidates"]},
                         {("Q5", "sparql"), ("Q6", "place")})
        self.assertIn("human", next(c for c in op["candidates"] if c["wikidata"] == "Q6")["evidence"])

    def test_name_and_place_route(self):
        # The search matched the name with the place in every language: no name check after it.
        client = self.Client()
        client.name_place = [cand("Q7", ["Kyros of Constantinople"])]
        places = {"mr:0101-ioannes-et-renatus-lego": [
            {"role": "death", "la": "Lutetiae", "qid": "Q90", "label": "Paris"},
            {"role": "cult", "la": "Nanneti", "qid": "Q92", "label": "Nantes"},
            {"role": "mention", "la": "Romae", "qid": "Q220", "label": "Rome"},
            {"role": "burial", "la": "?", "qid": None, "label": None}]}
        _, op = self.run_expand(self.op(companions=[], candidates=[]), client, places=places)
        self.assertEqual(client.name_place_calls[0], ("Ioannes", ["Paris", "Nantes"]))
        self.assertEqual([(c["wikidata"], c["source"]) for c in op["candidates"]], [("Q7", "place")])

    @mock.patch.object(bp, "NAME_FORMS", {})  # the Latin endings' forms alone
    def test_name_and_place_route_searches_the_vernacular_forms(self):
        self.assertEqual(bp.fulltext_names({"name": "Rogerius", "also": []}),
                         ["Rogerius", "Roger", "Rogere", "Rogerio"])
        self.assertEqual(bp.fulltext_names({"name": "Aemiliana", "also": []}),
                         ["Aemiliana", "Aemilian", "Aemiliane", "Emilian", "Emiliana", "Emiliane"])
        names = bp.fulltext_names({"name": "Paulus Miki", "also": ["Paulus"]})
        self.assertEqual(names[:5], ["Paulus Miki", "Paul Miki", "Paulus", "Paul", "Paule"])
        self.assertEqual(len(names), len(set(names)))

    def test_name_and_place_route_searches_the_full_name_and_its_other_names(self):
        client = self.Client()
        places = {"mr:0101-ioannes-et-renatus-lego": [{"role": "death", "la": "Lutetiae", "qid": "Q90", "label": "Paris"}]}
        op = self.op(name="Ioannes Lego", also=["Ioannes Baptista Lego", "Ioannes Lego"], companions=[], candidates=[])
        self.run_expand(op, client, record={"id": op["eulogy"], "name": "Ioannes Lego", "kind": "person"}, places=places)
        called = [n for n, _ in client.name_place_calls]
        self.assertEqual(called[0], "Ioannes Lego")
        self.assertIn("Ioannes Baptista Lego", called)
        self.assertEqual(len(called), len(set(called)))

    def test_name_and_place_route_does_not_repeat_a_place_candidate(self):
        client = self.Client()
        client.place = [cand("Q6", ["Ioannes"])]
        client.name_place = [cand("Q6", ["Ioannes"])]
        places = {"mr:0101-ioannes-et-renatus-lego": [{"role": "death", "la": "Romae", "qid": "Q91", "label": "Rome"}]}
        _, op = self.run_expand(self.op(companions=[], candidates=[]), client, places=places)
        self.assertEqual([c["wikidata"] for c in op["candidates"]], ["Q6"])

    def test_name_and_place_route_searches_the_eulogy_vernacular_names(self):
        # Gudila is Gudula on Wikidata, as in the English eulogy: its spellings are her own names.
        client = self.Client()
        gudula = cand("Q267660", ["Gudula"])

        def name_place(name, labels):
            client.name_place_calls.append((name, list(labels)))
            return [dict(gudula, source="place")] if name == "Gudula" else []

        client.saints_by_name_and_place = name_place
        places = {"mr:0101-ioannes-et-renatus-lego": [{"role": "death", "la": "Morsellae", "qid": "Q836859", "label": "Moorsel"}]}
        op = self.op(name="Gudila", companions=[], candidates=[])
        bp.expand(bp.new_changeset([op]), {}, {op["eulogy"]: [{"id": op["eulogy"], "name": "Gudila", "kind": "person"}]},
                  client, places, vernacular={op["eulogy"]: ["Gudula", "Gudila"]})
        called = [n for n, _ in client.name_place_calls]
        self.assertEqual(called[:2], ["Gudila", "Gudula"])
        self.assertEqual(len(called), len(set(called)))
        self.assertIn("Q267660", [c["wikidata"] for c in op["candidates"]])

    def test_vernacular_names_are_not_a_companion_s(self):
        # "Saint Gudula" names the eulogy's subject, not each of the persons it lists.
        client = self.Client()
        places = {"mr:0101-ioannes-et-renatus-lego": [{"role": "death", "la": "Lutetiae", "qid": "Q90", "label": "Paris"}]}
        op = self.op(candidates=[])
        bp.expand(bp.new_changeset([op]), {}, {op["eulogy"]: [{"id": op["eulogy"], "name": "Ioannes", "kind": "person"}]},
                  client, places, vernacular={op["eulogy"]: ["Gudula"]})
        self.assertNotIn("Gudula", [n for n, _ in client.name_place_calls])

    def test_subject_name_drops_the_title(self):
        self.assertEqual(bp.subject_name("Saint Gudula"), "Gudula")
        self.assertEqual(bp.subject_name("Santa Gudila"), "Gudila")
        self.assertEqual(bp.subject_name("Sant’Angela da Foligno"), "Angela da Foligno")
        self.assertEqual(bp.subject_name("Blessed Maria Domenica Mantovani"), "Maria Domenica Mantovani")
        self.assertEqual(bp.subject_name("Beato Ludovico"), "Ludovico")
        self.assertIsNone(bp.subject_name("Saints Paul Miki and companions"))
        self.assertIsNone(bp.subject_name("Santi Lucio e Pietro"))
        self.assertIsNone(bp.subject_name(""))

    def test_rare_name_route_when_no_saint_was_found(self):
        # Nathalan has no place on Wikidata: a name only a few saints bear is searched alone.
        client = self.Client()
        client.rare = [cand("Q2448164", ["Nathalan"])]
        op = self.op(name="Nathalanus", companions=[], candidates=[dict(cand("Q1", ["Nathalanus"], statuses=()), evidence=["human"])])
        _, got = self.run_expand(op, client, record={"id": op["eulogy"], "name": "Nathalanus", "kind": "person"})
        self.assertIn("Nathalan", client.rare_calls)
        self.assertIn(("Q2448164", "name"), [(c["wikidata"], c["source"]) for c in got["candidates"]])

    def test_no_rare_name_route_once_a_saint_was_found(self):
        client = self.Client()
        client.rare = [cand("Q2448164", ["Nathalan"])]
        _, got = self.run_expand(self.op(companions=[]), client)  # Q9 is a saint
        self.assertEqual(client.rare_calls, [])
        self.assertNotIn("Q2448164", [c["wikidata"] for c in got["candidates"]])

    def test_surname_route_when_no_saint_was_found(self):
        # Eduardus Stransham is Edward Stransham on Wikidata: the first names differ, the surname not.
        client = self.Client()
        client.surname = {"Stransham": [cand("Q59625", ["Edward Stransham"])]}
        op = self.op(name="Eduardus Stransham", companions=[], candidates=[])
        _, got = self.run_expand(op, client, record={"id": op["eulogy"], "name": op["name"], "kind": "person"})
        self.assertIn("Stransham", client.surname_calls)
        sources = [(c["wikidata"], c["source"]) for c in got["candidates"]]
        self.assertIn(("Q59625", "surname"), sources)

    def test_surname_route_searches_the_whole_surname_too(self):
        client = self.Client()
        client.surname = {"Vilar David": [cand("Q6161375", ["Vicente Vilar David"])]}
        op = self.op(name="Vincentius Vilar David", companions=[], candidates=[])
        _, got = self.run_expand(op, client, record={"id": op["eulogy"], "name": op["name"], "kind": "person"})
        self.assertEqual(client.surname_calls, ["David", "Vilar David"])
        self.assertIn("Q6161375", [c["wikidata"] for c in got["candidates"]])

    def test_surnames_are_the_names_last_words(self):
        # A compound surname stays searchable after two given names.
        self.assertEqual(bp._surnames({"name": "Vincentius Maria Vilar David"}),
                         ["David", "Vilar David", "Maria Vilar David"])
        self.assertEqual(bp._surnames({"name": "Paulus Le Van Loc"}), ["Van Loc", "Le Van Loc"])
        self.assertEqual(bp._surnames({"name": "Tarsicia"}), [])

    def test_no_surname_route_for_a_single_name_or_once_a_saint_was_found(self):
        client = self.Client()
        self.run_expand(self.op(name="Tarsicia", companions=[], candidates=[]), client,
                        record={"id": "mr:0101-ioannes-et-renatus-lego", "name": "Tarsicia", "kind": "person"})
        self.run_expand(self.op(name="Renatus Lego", companions=[]), client)  # Q9 is a saint
        self.assertEqual(client.surname_calls, [])

    def test_surname_is_a_saint_route(self):
        self.assertIn("surname", bp.SAINT_ROUTES)

    def test_feast_day_route(self):
        # John of Réôme's death is dated to the year only; his feast (P841) is the eulogy's day.
        client = self.Client()
        client.feast = [cand("Q107863881", ["Iohannes", "John of Reome"]), cand("Q8", ["Petrus"])]
        op = self.op(companions=[], typology="translatio")
        _, got = self.run_expand(op, client)
        month, day, given = client.feast_calls[0]
        self.assertEqual((month, day), (1, 1))
        self.assertIn("Ioannes", given)
        sources = [(c["wikidata"], c["source"]) for c in got["candidates"]]
        self.assertIn(("Q107863881", "feast"), sources)
        self.assertNotIn("Q8", [q for q, _ in sources])

    def test_no_place_route_without_places(self):
        client = self.Client()
        client.place = [cand("Q6", ["Ioannes"])]
        self.run_expand(self.op(companions=[]), client)
        self.assertEqual(client.place_calls, [])
        self.assertEqual(client.name_place_calls, [])

    def test_death_day_uses_name_equivalents_and_year(self):
        client = self.Client()
        client.day = [cand("Q5", ["John Lego", "John"], died="1642-01-01")]
        _, op = self.run_expand(self.op(companions=[]), client)
        month, day, given, year = client.calls[0]
        self.assertEqual((month, day, year), (1, 1, 1642))
        self.assertIn("Ioannes", given)
        self.assertIn("john", given)
        self.assertIn(("Q5", "sparql"), {(c["wikidata"], c["source"]) for c in op["candidates"]})

    def test_death_day_passes_the_stem_and_keeps_only_name_matches(self):
        client = self.Client()
        client.day = [cand("Q5", ["Eugende"], died="0510-01-01"), cand("Q6", ["Eugenio"], died="0510-01-01")]
        op = self.op(name="Eugendus", companions=[], candidates=[])
        _, got = self.run_expand(op, client, record={"id": op["eulogy"], "name": "Eugendus", "kind": "person"})
        self.assertIn("eugend", client.calls[0][2])
        self.assertEqual([c["wikidata"] for c in got["candidates"]], ["Q5"])  # Eugenio shares only a prefix
        self.assertTrue(client.matches(["Eugendo"]))
        self.assertFalse(client.matches(["Eugenio"]))

    def test_death_day_filter_compares_first_words(self):
        client = self.Client()
        client.day = [cand("Q5", ["Jean Légo"], died="1642-01-01"), cand("Q6", ["Pierre Martin"], died="1642-01-01")]
        _, got = self.run_expand(self.op(companions=[], candidates=[]), client)
        self.assertEqual([c["wikidata"] for c in got["candidates"]], ["Q5"])
        self.assertTrue(client.matches(["Jean Légo"]))
        self.assertFalse(client.matches(["Pierre Martin"]))
        self.assertTrue(client.matches(["Saint Eugende"]) is False)

    def test_eugendus_matches_saint_forms(self):
        client = self.Client()
        client.day = [cand("Q5", ["Saint Eugende"], died="0510-01-01")]
        op = self.op(name="Eugendus", companions=[], candidates=[])
        _, got = self.run_expand(op, client, record={"id": op["eulogy"], "name": "Eugendus", "kind": "person"})
        self.assertEqual([c["wikidata"] for c in got["candidates"]], ["Q5"])
        self.assertTrue(client.matches(["Eugendo"]))

    def test_multi_word_name_needs_its_other_words(self):
        fits = bp._name_fits
        self.assertTrue(fits("Renatus Lego", "René Lego"))
        self.assertFalse(fits("Renatus Lego", "René Dupont"))
        # Name particles are left out on both sides.
        self.assertTrue(fits("Ioanna Maria de Maille", "Jeanne Marie Maille"))
        self.assertTrue(fits("Gaspar de Bono", "Gaspar Bono"))
        self.assertTrue(fits("Gaspar Bono", "Gaspar de Bono"))

    def test_a_latin_title_is_not_a_name_word(self):
        fits = bp._name_fits
        self.assertTrue(fits("Anna Prophetissa", "Anna"))
        self.assertTrue(fits("Paulus Apostolus", "Paul"))
        self.assertFalse(fits("Anna Prophetissa", "Maria"))

    def companion_op(self, evidence):
        return self.op(id="mr:0101-ioannes-et-renatus-lego|Renatus Lego", name="Renatus Lego", companions=[],
                       candidates=[dict(cand("Q2652595", ["Renatus Lego"]), evidence=evidence)])

    def run_undecided(self, evidence):
        client = self.Client(by_qid={"Q2652595": cand("Q2652595", ["Renatus Lego"])})
        client.kin = {"Q2652595": [dict(cand("Q52161488", ["Ioannes Lego"]), source="companion:P3373")]}
        ops = [self.op(), self.companion_op(evidence)]
        review = bp.new_changeset(ops)
        records = {ops[0]["eulogy"]: [{"id": ops[0]["eulogy"], "name": "Ioannes", "kind": "person"},
                                      {"id": ops[0]["eulogy"], "name": "Renatus Lego", "kind": "person"}]}
        bp.expand(review, {}, records, client)
        return review["operations"][0]

    def test_undecided_companion_with_strong_match_is_used(self):
        op = self.run_undecided(["human", "status", "death"])
        self.assertIn(("Q52161488", "companion:P3373"), {(c["wikidata"], c["source"]) for c in op["candidates"]})

    def test_undecided_companion_with_weak_match_is_not_used(self):
        op = self.run_undecided(["human", "name"])
        self.assertEqual([c["wikidata"] for c in op["candidates"]], ["Q9"])

    def test_existing_qid_is_not_duplicated(self):
        client = self.Client()
        client.day = [cand("Q9", ["John"])]
        _, op = self.run_expand(self.op(companions=[]), client)
        self.assertEqual([(c["wikidata"], c["source"]) for c in op["candidates"]], [("Q9", "search")])

    def test_celebration_gets_titles(self):
        client = self.Client()
        client.titles = [cand("Q208542", ["Theotokos"], human=False, statuses=())]
        op = self.op(id="mr:0101-maria-dei-genetrix|Maria", eulogy="mr:0101-maria-dei-genetrix", name="Maria",
                     typology="festum", companions=[], candidates=[])
        _, got = self.run_expand(op, client, record={"id": op["eulogy"], "name": "Maria", "kind": "celebration"})
        self.assertEqual([(c["wikidata"], c["source"]) for c in got["candidates"]], [("Q208542", "title")])

    def test_curated_title_is_added_when_search_misses_it(self):
        client = self.Client(by_qid={"Q208542": cand("Q208542", ["Theotokos"], human=False)})
        op = self.op(id="mr:0101-maria-dei-genetrix|Maria", eulogy="mr:0101-maria-dei-genetrix", name="Maria",
                     companions=[], candidates=[])
        _, got = self.run_expand(op, client, record={"id": op["eulogy"], "name": "Maria", "kind": "celebration"})
        self.assertEqual([(c["wikidata"], c["source"]) for c in got["candidates"]], [("Q208542", "curated")])

    def test_a_curated_title_displaces_the_last_search_candidate_at_the_cap(self):
        client = self.Client(by_qid={"Q208542": cand("Q208542", ["Theotokos"], human=False)})
        searched = [dict(cand(f"Q{100 + i}", ["Maria"]), source="search", evidence=[]) for i in range(bp.MAX_EXPANDED)]
        op = self.op(id="mr:0101-maria-dei-genetrix|Maria", eulogy="mr:0101-maria-dei-genetrix", name="Maria",
                     companions=[], candidates=searched)
        _, got = self.run_expand(op, client, record={"id": op["eulogy"], "name": "Maria", "kind": "celebration"})
        qids = [c["wikidata"] for c in got["candidates"]]
        self.assertEqual(len(qids), bp.MAX_EXPANDED)
        self.assertEqual(qids[0], "Q100")
        self.assertIn("Q208542", qids)

    def test_cap_keeps_existing_candidates(self):
        client = self.Client()
        client.day = [cand(f"Q{100 + i}", ["John"]) for i in range(20)]
        _, op = self.run_expand(self.op(companions=[]), client)
        self.assertEqual(len(op["candidates"]), bp.MAX_EXPANDED)
        self.assertIn("Q9", {c["wikidata"] for c in op["candidates"]})

    def test_a_saint_route_displaces_the_last_search_candidates_at_the_cap(self):
        # Emeritus of Abitinae: found by his feast behind 15 namesakes from the search.
        client = self.Client()
        client.feast = [cand("Q500", ["Ioannes"])]
        searched = [dict(cand(f"Q{100 + i}", ["John"]), source="search", evidence=[]) for i in range(14)]
        op = self.op(companions=[], candidates=self.op()["candidates"] + searched,
                     decision="reject", edited={"wikidata": "Q113"})
        _, got = self.run_expand(op, client)
        qids = [c["wikidata"] for c in got["candidates"]]
        self.assertEqual(len(qids), bp.MAX_EXPANDED)
        self.assertEqual(qids[0], "Q9")  # an accept without a suggestion means candidates[0]
        self.assertIn("Q500", qids)
        self.assertIn("Q113", qids)  # the decided pick stays
        self.assertNotIn("Q112", qids)  # the last search candidate but the pick makes room

    def test_a_kin_candidate_does_not_displace_at_the_cap(self):
        client = self.Client(by_qid={"Q2652595": cand("Q2652595", ["Renatus Lego"])})
        client.kin = {"Q2652595": [dict(cand("Q600", ["Ioannes Lego"]), source="companion:P3373")]}
        searched = [dict(cand(f"Q{100 + i}", ["John"]), source="search", evidence=[]) for i in range(14)]
        _, got = self.run_expand(self.op(candidates=self.op()["candidates"] + searched), client)
        self.assertNotIn("Q600", [c["wikidata"] for c in got["candidates"]])

    def test_paul_is_a_curated_title(self):
        self.assertEqual(bp.CURATED_TITLES["mr:0125-conversio-pauli-apostoli"], "Q9200")

    def test_our_lady_of_lourdes_is_a_curated_title(self):
        self.assertEqual(bp.CURATED_TITLES["mr:0211-maria-de-lourdes"], "Q21532387")

    def test_decision_untouched_and_failure_continues(self):
        client = self.Client(by_qid={"Q2652595": cand("Q2652595", ["Renatus Lego"])}, fail={"Q2652595"})
        op = self.op(decision="edit", edited={"wikidata": "Q1"})
        left, got = self.run_expand(op, client)
        self.assertEqual([k for k, _ in left], [op["id"]])
        self.assertEqual((got["decision"], got["edited"]), ("edit", {"wikidata": "Q1"}))
        client = self.Client()
        _, got = self.run_expand(self.op(decision="accept", edited=None), client)
        self.assertEqual((got["decision"], got["edited"]), ("accept", None))

    def test_existing_order_is_kept_so_accept_still_means_the_first(self):
        client = self.Client()
        client.day = [cand("Q5", ["John"], died="1642-01-01")]  # human, status, name, death: more evidence
        op = self.op(companions=[], decision="accept")
        op["candidates"][0]["evidence"] = []
        _, got = self.run_expand(op, client)
        self.assertEqual([c["wikidata"] for c in got["candidates"]], ["Q9", "Q5"])

    def test_failed_lookup_still_marks_existing_candidates_as_search(self):
        client = self.Client(by_qid={"Q2652595": cand("Q2652595", ["Renatus Lego"])}, fail={"Q2652595"})
        _, got = self.run_expand(self.op(), client)
        self.assertEqual(got["candidates"][0]["source"], "search")


    def test_consecutive_failures_stop_the_lookups(self):
        client = self.Client(by_qid={"Q2652595": cand("Q2652595", ["Renatus Lego"])}, fail={"Q2652595"})
        ops = [self.op(id=f"mr:0101-ioannes-et-renatus-lego|Ioannes#{i}") for i in range(bp.MAX_CONSECUTIVE_FAILURES + 2)]
        review = bp.new_changeset(ops)
        items = {"mr:0101-ioannes-et-renatus-lego": {"Renatus Lego": {"wikidata": "Q2652595", "status": "reviewed"}}}
        records = {"mr:0101-ioannes-et-renatus-lego": [{"id": "mr:0101-ioannes-et-renatus-lego", "name": "Ioannes",
                                                         "kind": "person"}]}
        left = bp.expand(review, items, records, client)
        self.assertEqual(len(left), len(ops))
        self.assertEqual([e for _, e in left[bp.MAX_CONSECUTIVE_FAILURES:]], ["skipped: Wikidata unavailable"] * 2)


    def test_a_title_item_the_search_also_returns_keeps_its_provenance(self):
        title = dict(cand("Q208542", ["Theotokos"], human=False, statuses=()), evidence=[], source="curated")
        old = self.op(candidates=[title])
        person = {k: old[k] for k in ("eulogy", "day", "typology", "subject", "name", "companions")}
        person["where"] = "text"
        found = dict(cand("Q208542", ["Theotokos"], human=False, statuses=()), evidence=[])
        op = bp.make_op(old["id"], person, {"failed": [], "candidates": [found]}, old)
        self.assertEqual([(c["wikidata"], c.get("source")) for c in op["candidates"]], [("Q208542", "curated")])

    def test_expand_marks_a_searched_title_item_as_title(self):
        client = self.Client()
        client.titles = [cand("Q208542", ["Theotokos"], human=False, statuses=())]
        op = self.op(eulogy="mr:0101-maria-dei-genetrix", id="mr:0101-maria-dei-genetrix|Maria", name="Maria",
                     companions=[], typology="celebratio",
                     candidates=[dict(cand("Q208542", ["Theotokos"], human=False, statuses=()), evidence=[])])
        _, got = self.run_expand(op, client, items={}, record={"id": op["eulogy"], "name": "Maria", "kind": "celebration"})
        self.assertEqual([(c["wikidata"], c["source"]) for c in got["candidates"]], [("Q208542", "title")])

    def test_propose_keeps_the_expanded_candidates(self):
        old = self.op(candidates=[dict(cand("Q9", ["John"]), evidence=["human"], source="search"),
                                  dict(cand("Q52161488", ["Jean Légo"]), evidence=[], source="companion:P3373")])
        person = {k: old[k] for k in ("eulogy", "day", "typology", "subject", "name", "companions")}
        person["where"] = "text"
        op = bp.make_op(old["id"], person, {"failed": [], "candidates": [dict(cand("Q9", ["John"]), evidence=["human"])]}, old)
        self.assertEqual([c["wikidata"] for c in op["candidates"]], ["Q9", "Q52161488"])
        self.assertEqual(op["candidates"][1]["source"], "companion:P3373")
        self.assertIn("status", op["candidates"][1]["evidence"])  # recomputed


class RecordMatchTest(unittest.TestCase):
    """expand takes a person's own record (name and n), else only the kind of the eulogy's only record."""
    Client = ExpandTest.Client

    def op(self, name, n=None):
        mrid = "mr:0101-ioannes-et-renatus-lego"
        return {"op": "resolve_person", "id": f"{mrid}|{name}" + (f"#{n}" if n else ""), "eulogy": mrid,
                "day": "01-01", "typology": "dies_natalis", "subject": "Ioannes et Renatus Lego", "name": name,
                **({"n": n} if n else {}), "companions": [], "failed": [], "candidates": [],
                "decision": None, "edited": None}

    def years(self, op, records):
        client = self.Client()
        bp.expand(bp.new_changeset([op]), {}, {op["eulogy"]: records}, client)
        return [year for _, _, _, year in client.calls]

    def test_another_persons_record_lends_no_death_year(self):
        renatus = {"id": "mr:0101-ioannes-et-renatus-lego", "name": "Renatus Lego", "kind": "person",
                   "death_year": 1642}
        self.assertEqual(self.years(self.op("Ioannes"), [renatus]), [None])  # its kind only
        self.assertEqual(self.years(self.op("Renatus Lego"), [renatus]), [1642])

    def test_a_repeated_name_takes_the_record_with_its_n(self):
        first = {"id": "mr:0101-ioannes-et-renatus-lego", "name": "Ioannes", "kind": "person", "death_year": 300}
        second = dict(first, n=2, death_year=304)
        self.assertEqual(self.years(self.op("Ioannes", 2), [first, second]), [304])
        self.assertEqual(self.years(self.op("Ioannes"), [second, first]), [300])

    def test_no_record_of_its_own_among_several(self):
        a = {"id": "mr:0101-ioannes-et-renatus-lego", "name": "A", "kind": "person"}
        self.assertEqual(self.years(self.op("Ioannes"), [a, dict(a, name="B")]), [])


class TitleApplyTest(unittest.TestCase):
    INDEX = {"mr:0101-maria-dei-genetrix|Maria": {"eulogy": "mr:0101-maria-dei-genetrix", "name": "Maria",
                                                  "day": "01-01", "typology": "festum", "where": "text",
                                                  "subject": "Sollemnitas sanctae Dei Genetricis Mariae",
                                                  "companions": []}}

    def apply(self, source, decision="accept", edited=None):
        title = dict(cand("Q208542", ["Theotokos"], human=False, statuses=()), source=source)
        op = {"op": "resolve_person", "id": "mr:0101-maria-dei-genetrix|Maria",
              "eulogy": "mr:0101-maria-dei-genetrix", "name": "Maria", "failed": [], "candidates": [title],
              "decision": decision, "edited": edited}
        items, review = {}, bp.new_changeset([dict(op, decision=None)])
        bp.apply_decisions(items, review, bp.new_changeset([op]), self.INDEX, FakeClient())
        return items, review

    def test_a_celebration_card_applies_its_title_item(self):
        items, review = self.apply("curated")
        self.assertEqual(items, {"mr:0101-maria-dei-genetrix": {"Maria": {"wikidata": "Q208542",
                                                                          "status": "reviewed"}}})
        self.assertEqual(review["operations"], [])
        self.assertEqual(bp.validate(items, self.INDEX), [])
        items, _ = self.apply("title", "edit", {"wikidata": "Q208542"})
        self.assertEqual(items["mr:0101-maria-dei-genetrix"]["Maria"]["wikidata"], "Q208542")

    def test_a_non_human_from_the_search_is_still_refused(self):
        with self.assertRaisesRegex(ValueError, "not a human with a saint"):
            self.apply("search")


    def test_verify_suggestions_accepts_a_title_item(self):
        title = dict(cand("Q208542", ["Theotokos"], human=False, statuses=()), source="curated")
        op = {"id": "mr:0101-maria-dei-genetrix|Maria", "candidates": [title], "confidence": "high",
              "suggested": {"wikidata": "Q208542"}}
        self.assertEqual(bp.verify_suggestions(bp.new_changeset([op]), FakeClient()), [])
        op = dict(op, candidates=[dict(title, source="search")])
        self.assertTrue(bp.verify_suggestions(bp.new_changeset([op]), FakeClient()))


class ExportTest(unittest.TestCase):
    def test_one_months_ops(self):
        review = bp.new_changeset([{"id": "mr:0101-a|A", "eulogy": "mr:0101-a"},
                                   {"id": "mr:0201-b|B", "eulogy": "mr:0201-b"},
                                   {"id": "mr:0131-c|C", "eulogy": "mr:0131-c"}])
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as away:
            (Path(root) / "data").mkdir()
            (Path(root) / "data" / "person_items_review.json").write_text(json.dumps(review))
            out = Path(away) / "01.json"
            with contextlib.redirect_stdout(io.StringIO()):
                bp.main(["export", "01", str(out), root])
            doc = json.loads(out.read_text())
        self.assertEqual(doc["schema"], bp.SCHEMA)
        self.assertEqual([op["id"] for op in doc["operations"]], ["mr:0101-a|A", "mr:0131-c|C"])

    def test_refused_inside_a_work_tree_and_a_bad_month(self):
        here = Path(__file__).resolve()
        with self.assertRaisesRegex(SystemExit, "outside any git work tree"):
            bp.main(["export", "01", str(here.parent / "out.json")])
        with self.assertRaises(SystemExit):
            bp.main(["export", "13", "/nowhere/out.json"])
        self.assertFalse((here.parent / "out.json").exists())


class MainPlacesFailureTest(unittest.TestCase):
    def test_a_failed_place_annotation_exits_non_zero_after_writing_and_loads_places_once(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / "data").mkdir()
            (Path(root) / "docs").mkdir()
            (Path(root) / "data" / "martyrology_ids.json").write_text(json.dumps({"entries": {}}))
            load = mock.Mock(return_value={})
            with mock.patch.object(bp.eulogy_places, "load", load), \
                    mock.patch.object(bp, "person_index", return_value={}), \
                    mock.patch.object(bp, "annotate_places", side_effect=wd.WikidataError("down")), \
                    contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(SystemExit, "places were not annotated"):
                    bp.main(["verify-suggestions", root])
            self.assertEqual(load.call_count, 1)
            self.assertTrue((Path(root) / "docs" / "person-items-report.md").exists())
            self.assertIn("places: down", (Path(root) / "docs" / "person-items-report.md").read_text())

    def count_loads(self, argv):
        from unittest import mock
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / "data").mkdir()
            (Path(root) / "docs").mkdir()
            (Path(root) / "data" / "martyrology_ids.json").write_text(json.dumps({"entries": {}}))
            (Path(root) / "in.json").write_text("[]")
            load = mock.Mock(return_value={})
            with mock.patch.object(bp.eulogy_places, "load", load), \
                    mock.patch.object(bp, "person_index", return_value={}), \
                    mock.patch.object(bp, "annotate_places"), \
                    mock.patch.object(bp, "expand", return_value=[]), \
                    mock.patch.object(bp, "apply_decisions", return_value=0), \
                    contextlib.redirect_stdout(io.StringIO()):
                bp.main([argv[0]] + [a.replace("ROOT", root) for a in argv[1:]])
        return load.call_count

    def test_expand_loads_places_once(self):
        self.assertEqual(self.count_loads(["expand", "ROOT/in.json", "ROOT"]), 1)

    def test_apply_and_check_do_not_load_places(self):
        self.assertEqual(self.count_loads(["apply", "ROOT/in.json", "ROOT"]), 0)
        self.assertEqual(self.count_loads(["check", "ROOT"]), 0)


def place(qid, label, admin=()):
    return {"wikidata": qid, "label": label, "admin_qids": list(admin)}


# Bologna; a hermitage in Bologna; a hamlet in the hermitage (two steps from Bologna); Rome.
PLACES = {"Q490": place("Q490", "Bologna"), "Q900": place("Q900", "Eremo", ["Q490"]),
          "Q901": place("Q901", "Borgo", ["Q900"]), "Q220": place("Q220", "Roma")}


def admin(places=PLACES):
    return {q: p["admin_qids"] for q, p in places.items()}


def placed(qid, names, statuses=("Q43115",), **props):
    return dict(cand(qid, names, statuses=statuses), **{k: props.get(k, []) for k in
                                     ("birth_place", "death_place", "burial_place", "work_places", "signals")})


class SaintSignalsTest(unittest.TestCase):
    def test_a_saint_signal_counts_as_status(self):
        op = dict(PERSON, also=[])
        c = dict(cand("Q1", ["Paul Miki"], statuses=()), signals=["P8080"])
        self.assertIn("status", bp.evidence(op, c))
        self.assertTrue(bp._appliable(c))
        self.assertNotIn("status", bp.evidence(op, dict(c, signals=[])))
        self.assertFalse(bp._appliable(dict(c, signals=[])))
        self.assertFalse(bp._appliable(dict(c, human=False)))

    def test_annotate_fetches_the_signals_of_an_older_candidate(self):
        old = dict(placed("Q1", ["Paul Miki"], statuses=()))
        old.pop("signals")
        result = bp.evaluate(PERSON, [old])
        op = bp.make_op("mr:0206-paulus-miki-et-socii|Paulus Miki", PERSON, result, None)
        op["candidates"][0].pop("signals", None)
        client = FakeClient(by_qid={"Q1": dict(placed("Q1", ["Paul Miki"], statuses=()), signals=["P6126"])},
                            places=PLACES)
        bp.annotate_places([op], {PERSON["eulogy"]: []}, client)
        c = op["candidates"][0]
        self.assertEqual(client.people_calls, [["Q1"]])
        self.assertEqual(c["signals"], ["P6126"])
        self.assertEqual(c["evidence"][:2], ["human", "status"])


class PlaceAgreementTest(unittest.TestCase):
    BOLOGNA = {"role": "death", "la": "Bononiae", "qid": "Q490", "label": "Bologna"}

    def test_same_item(self):
        c = placed("Q1", ["Paul Miki"], death_place=["Q490"])
        self.assertEqual(bp.place_agreement([self.BOLOGNA], c, admin()),
                         [{"role": "death", "qid": "Q490", "label": "Bologna", "via": "P20"}])

    def test_the_first_property_of_the_role_that_agrees(self):
        c = placed("Q1", ["Paul Miki"], death_place=["Q220"], burial_place=["Q490"])
        self.assertEqual(bp.place_agreement([self.BOLOGNA], c, admin())[0]["via"], "P119")
        burial = dict(self.BOLOGNA, role="burial")
        c = placed("Q1", ["Paul Miki"], death_place=["Q490"], burial_place=["Q490"])
        self.assertEqual(bp.place_agreement([burial], c, admin())[0]["via"], "P119")

    def test_one_step_either_way(self):
        # The candidate died in a hermitage inside the eulogy's town.
        c = placed("Q1", ["Paul Miki"], death_place=["Q900"])
        self.assertEqual(len(bp.place_agreement([self.BOLOGNA], c, admin())), 1)
        # The eulogy's place is a hermitage inside the candidate's town.
        eremo = dict(self.BOLOGNA, qid="Q900", label="Eremo")
        c = placed("Q1", ["Paul Miki"], death_place=["Q490"])
        self.assertEqual(bp.place_agreement([eremo], c, admin()),
                         [{"role": "death", "qid": "Q900", "label": "Eremo", "via": "P20"}])
        # Two steps apart is not agreement.
        c = placed("Q1", ["Paul Miki"], death_place=["Q901"])
        self.assertEqual(bp.place_agreement([self.BOLOGNA], c, admin()), [])

    def test_role_outside_table(self):
        c = placed("Q1", ["Paul Miki"], death_place=["Q490"])
        self.assertEqual(bp.place_agreement([dict(self.BOLOGNA, role="mention")], c, admin()), [])
        # Birth reads P19 only.
        self.assertEqual(bp.place_agreement([dict(self.BOLOGNA, role="birth")], c, admin()), [])

    def _op(self, candidates, person=PERSON):
        result = bp.evaluate(person, candidates)
        return result, bp.make_op("mr:0206-paulus-miki-et-socii|Paulus Miki", person, result, None)

    def test_annotate_shows_places_and_labels(self):
        _, op = self._op([placed("Q1", ["Paul Miki"], death_place=["Q490"], work_places=["Q220", "Q999"])])
        by_eulogy = {PERSON["eulogy"]: [self.BOLOGNA, {"role": "mention", "la": "Romae", "qid": "Q220",
                                                        "label": None}]}
        client = FakeClient(places=PLACES)
        bp.annotate_places([op], by_eulogy, client)
        self.assertEqual(op["places"], [{"role": "death", "label": "Bologna", "qid": "Q490"},
                                        {"role": "mention", "label": "Roma", "qid": "Q220"}])
        c = op["candidates"][0]
        self.assertEqual(c["places"], [{"role": "death", "qid": "Q490", "label": "Bologna", "via": "P20"}])
        self.assertEqual(c["evidence"][-1], "place")
        # A label falls back to the QID when Wikidata has no item.
        self.assertEqual(c["place_labels"], {"death_place": ["Bologna"], "work_places": ["Roma", "Q999"]})
        self.assertEqual(len(client.items_calls), 1)
        self.assertEqual(set(client.items_calls[0]), {"Q490", "Q220", "Q999"})

    def test_no_agreement_no_place(self):
        _, op = self._op([placed("Q1", ["Paul Miki"], death_place=["Q220"])])
        bp.annotate_places([op], {PERSON["eulogy"]: [self.BOLOGNA]}, FakeClient(places=PLACES))
        c = op["candidates"][0]
        self.assertEqual(c["places"], [])
        self.assertNotIn("place", c["evidence"])
        # A eulogy with no places: empty lists.
        _, op = self._op([placed("Q1", ["Paul Miki"], death_place=["Q220"])])
        bp.annotate_places([op], {}, FakeClient(places=PLACES))
        self.assertEqual((op["places"], op["candidates"][0]["places"]), ([], []))

    def test_order_and_auto_unchanged(self):
        a = placed("Q1", ["Paul Miki"], death_place=["Q220"])
        b = placed("Q2", ["Paul Miki"], death_place=["Q490"], statuses=())
        result, op = self._op([b, a])
        self.assertEqual(result["auto"]["wikidata"], "Q1")
        self.assertEqual([c["wikidata"] for c in op["candidates"]], ["Q1", "Q2"])
        bp.annotate_places([op], {PERSON["eulogy"]: [self.BOLOGNA]}, FakeClient(places=PLACES))
        self.assertEqual([c["wikidata"] for c in op["candidates"]], ["Q1", "Q2"])
        self.assertEqual(op["candidates"][1]["evidence"][-1], "place")
        self.assertEqual(result["auto"]["wikidata"], "Q1")
        self.assertNotIn("place", result["auto"]["evidence"])
        # A non-auto op stays non-auto: agreement on every rule's failure fixes nothing.
        result, op = self._op([placed("Q3", ["Paul Miki"], death_place=["Q490"], statuses=())])
        bp.annotate_places([op], {PERSON["eulogy"]: [self.BOLOGNA]}, FakeClient(places=PLACES))
        self.assertIsNone(result["auto"])
        self.assertEqual(op["failed"], result["failed"])
        self.assertNotIn("status", op["candidates"][0]["evidence"])

    def test_annotate_twice_and_after_recompute(self):
        _, op = self._op([placed("Q1", ["Paul Miki"], death_place=["Q490"])])
        by_eulogy, client = {PERSON["eulogy"]: [self.BOLOGNA]}, FakeClient(places=PLACES)
        bp.annotate_places([op], by_eulogy, client)
        once = json.loads(json.dumps(op))
        bp.annotate_places([op], by_eulogy, client)
        self.assertEqual(op, once)
        c = op["candidates"][0]
        c["evidence"] = bp.evidence(op, c)
        self.assertNotIn("place", c["evidence"])
        bp.annotate_places([op], by_eulogy, client)
        self.assertEqual(op, once)

    def test_decided_and_prefilled_ops_untouched(self):
        by_eulogy, client = {PERSON["eulogy"]: [self.BOLOGNA]}, FakeClient(places=PLACES)
        _, decided = self._op([placed("Q1", ["Paul Miki"], death_place=["Q490"])])
        decided["decision"] = "accept"
        _, prefilled = self._op([placed("Q1", ["Paul Miki"], death_place=["Q490"])])
        prefilled["prefilled"] = "jev"
        before = json.loads(json.dumps([decided, prefilled]))
        bp.annotate_places([decided, prefilled], by_eulogy, client)
        self.assertEqual([decided, prefilled], before)
        self.assertEqual(client.items_calls, [])

    def test_a_failed_lookup_leaves_the_ops_unannotated(self):
        _, op = self._op([placed("Q1", ["Paul Miki"], death_place=["Q490"])])
        before = json.loads(json.dumps(op))
        with self.assertRaises(bp.WikidataError):
            bp.annotate_places([op], {PERSON["eulogy"]: [self.BOLOGNA]}, FakeClient(places=PLACES, fail={"items"}))
        self.assertEqual(op, before)

    def test_a_carried_over_candidate_gets_its_places(self):
        # A candidate kept from an old op has no place keys: they are fetched, once, and copied on.
        old = cand("Q1", ["Paul Miki"])
        _, op = self._op([old, placed("Q2", ["Paul Miki"], death_place=["Q220"])])
        client = FakeClient(by_qid={"Q1": dict(placed("Q1", ["Paul Miki"], death_place=["Q900"]),
                                               label="Other")}, places=PLACES)
        bp.annotate_places([op], {PERSON["eulogy"]: [self.BOLOGNA]}, client)
        self.assertEqual(client.people_calls, [["Q1"]])
        c = next(c for c in op["candidates"] if c["wikidata"] == "Q1")
        self.assertEqual((c["death_place"], c["work_places"], c["label"]), (["Q900"], [], "Paul Miki"))
        self.assertEqual(c["places"], [{"role": "death", "qid": "Q490", "label": "Bologna", "via": "P20"}])
        self.assertIn("Q900", client.items_calls[0])
        # Nothing to fetch: no call.
        client = FakeClient(places=PLACES)
        bp.annotate_places([op], {PERSON["eulogy"]: [self.BOLOGNA]}, client)
        self.assertEqual(client.people_calls, [])

    def test_a_failed_people_lookup_leaves_the_ops_unannotated(self):
        _, op = self._op([cand("Q1", ["Paul Miki"])])
        before = json.loads(json.dumps(op))
        client = FakeClient(places=PLACES, fail={"people"})
        with self.assertRaises(bp.WikidataError):
            bp.annotate_places([op], {PERSON["eulogy"]: [self.BOLOGNA]}, client)
        self.assertEqual((op, client.items_calls), (before, []))
