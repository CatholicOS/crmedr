import contextlib
import io
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

        def relatives(self, qid):
            if qid in self.fail:
                raise bp.WikidataError("boom")
            return [dict(c) for c in self.kin.get(qid, [])]

        def saints_by_death_day(self, month, day, given, year=None):
            self.calls.append((month, day, given, year))
            return [dict(c, source="sparql") for c in self.day]

        def title_candidates(self, text):
            return [dict(c, source="title") for c in self.titles]

    def op(self, **kw):
        base = {"op": "resolve_person", "id": "mr:0101-ioannes-et-renatus-lego|Ioannes",
                "eulogy": "mr:0101-ioannes-et-renatus-lego", "day": "01-01", "typology": "dies_natalis",
                "subject": "Ioannes et Renatus Lego", "name": "Ioannes", "companions": ["Renatus Lego"],
                "failed": [], "candidates": [dict(cand("Q9", ["John"]), evidence=["human"])],
                "decision": None, "edited": None}
        return dict(base, **kw)

    def run_expand(self, op, client, items=None, record=None):
        review = bp.new_changeset([op])
        items = {"mr:0101-ioannes-et-renatus-lego": {"Renatus Lego": {"wikidata": "Q2652595", "status": "reviewed"}}
                 } if items is None else items
        records = {op["eulogy"]: [record or {"id": op["eulogy"], "name": op["name"], "kind": "person",
                                             "death_year": 1642}]}
        return bp.expand(review, items, records, client), review["operations"][0]

    def test_sibling_found(self):
        client = self.Client(by_qid={"Q2652595": cand("Q2652595", ["Renatus Lego"])})
        client.kin = {"Q2652595": [dict(cand("Q52161488", ["Ioannes Lego"]), source="companion:P3373")]}
        left, op = self.run_expand(self.op(), client)
        self.assertEqual(left, [])
        self.assertIn(("Q52161488", "companion:P3373"), {(c["wikidata"], c["source"]) for c in op["candidates"]})
        self.assertEqual(next(c for c in op["candidates"] if c["wikidata"] == "Q9")["source"], "search")
        self.assertIn("status", next(c for c in op["candidates"] if c["wikidata"] == "Q52161488")["evidence"])

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

    def test_death_day_uses_name_equivalents_and_year(self):
        client = self.Client()
        client.day = [cand("Q5", ["John Lego"], died="1642-01-01")]
        _, op = self.run_expand(self.op(companions=[]), client)
        month, day, given, year = client.calls[0]
        self.assertEqual((month, day, year), (1, 1, 1642))
        self.assertIn("Ioannes", given)
        self.assertIn("john", given)
        self.assertIn(("Q5", "sparql"), {(c["wikidata"], c["source"]) for c in op["candidates"]})

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

    def test_cap_keeps_existing_candidates(self):
        client = self.Client()
        client.day = [cand(f"Q{100 + i}", ["John"]) for i in range(20)]
        _, op = self.run_expand(self.op(companions=[]), client)
        self.assertEqual(len(op["candidates"]), bp.MAX_EXPANDED)
        self.assertIn("Q9", {c["wikidata"] for c in op["candidates"]})

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
