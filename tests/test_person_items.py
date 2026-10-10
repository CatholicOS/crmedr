import json
import sys
import tempfile
import unittest
from pathlib import Path

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

import build_person_items as bp  # noqa: E402


def cand(qid, names, died="1597-02-05", statuses=("Q43115",), human=True):
    return {"wikidata": qid, "label": names[0], "description": "", "names": list(names), "human": human,
            "statuses": list(statuses), "born": None, "died": died, "feast": []}


PERSON = {"eulogy": "mr:0206-paulus-miki-et-socii", "name": "Paulus Miki", "day": "02-05",
          "typology": "dies_natalis", "subject": "Sancti Paulus Miki et socii", "where": "text",
          "companions": ["Ioannes de Goto Soan"]}


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
    def __init__(self, by_name=None, by_qid=None, fail=()):
        self.by_name, self.by_qid, self.fail = by_name or {}, by_qid or {}, set(fail)

    def person_candidates(self, name, languages=("la", "it", "en")):
        if name in self.fail:
            raise bp.WikidataError("boom")
        return [dict(c) for c in self.by_name.get(name, [])]

    def person(self, qid):
        return self.by_qid.get(qid)


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
