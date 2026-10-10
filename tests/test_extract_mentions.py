import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import extract_mentions as em  # noqa: E402

GAZETTEER = {"Cæsaréæ in Cappadócia": "Q48338", "Londínii in Anglia": "Q84"}
BASIL_TEXT = "Cæsaréæ in Cappadócia, commemorátio sancti Basilíi, magístri."
BASIL_PLACE = {"role": "burial", "la": "Cæsaréæ in Cappadócia", "it": "A Cesarea in Cappadocia", "source": "lead"}


def mentions_of(text, places=(), persons=(), notes=(), lang="la", qids=None):
    return em.eulogy_mentions(text, list(notes), list(places), list(persons), lang=lang,
                              place_qid=GAZETTEER.get, person_qid=lambda n: (qids or {}).get(n))


class EulogyMentionsTest(unittest.TestCase):
    def test_a_place_and_a_person(self):
        ms, review, hows = mentions_of(BASIL_TEXT, [BASIL_PLACE], [{"name": "Basilius", "where": "text"}],
                                       qids={"Basilius": "Q19546"})
        s = BASIL_TEXT.index("Basilíi")
        self.assertEqual(ms, [
            {"kind": "place", "where": "text", "start": 0, "end": 21, "form": "Cæsaréæ in Cappadócia", "qid": "Q48338"},
            {"kind": "person", "where": "text", "start": s, "end": s + 7, "form": "Basilíi", "name": "Basilius",
             "qid": "Q19546"},
        ])
        self.assertEqual(review, [])
        self.assertEqual(hows, [("place", True, "as printed"), ("person", True, "stem")])

    def test_an_italian_back_reference(self):
        place = {"role": "death", "la": "Londínii in Anglia", "it": "A Londra in Inghilterra", "source": "lead",
                 "via": "mr:0101-x"}
        ms, _, hows = mentions_of("Sempre a Londra, beato Tommaso, sacerdote.", [place], lang="it")
        self.assertEqual(ms, [{"kind": "place", "where": "text", "start": 0, "end": 15, "form": "Sempre a Londra",
                               "qid": "Q84"}])
        self.assertEqual(hows, [("place", True, "back-reference")])

    def test_a_place_without_a_form_in_this_language_is_not_expected(self):
        place = {"role": "death", "la": "Romæ", "source": "lead"}
        self.assertEqual(mentions_of("A Roma, san Nemo.", [place], lang="it")[:2], ([], []))

    def test_a_footnote_person(self):
        notes = ["Quorum nómina: Nemárdus Fictin et Nemárdus Némau."]
        ms, _, _ = mentions_of("Nagasáki, sanctórum Nemárdi Fictin et sociórum.",
                               persons=[{"name": "Nemardus Nemau", "where": {"footnote": 1}}], notes=notes)
        self.assertEqual(ms[0]["where"], {"footnote": 1})
        self.assertEqual(notes[0][ms[0]["start"]:ms[0]["end"]], "Nemárdus Némau")

    def test_footnotes_count_from_one_in_printed_order_and_offsets_from_the_footnote(self):
        notes = ["Nemárdus Némau, presbýter.", "Inter quos: Nemárdus Némau et Fictínus Nemáki."]
        ms, _, _ = mentions_of("Nagasáki, sanctórum mártyrum.",
                               persons=[{"name": "Fictinus Nemaki", "where": {"footnote": 2}}], notes=notes)
        s = notes[1].index("Fictínus")
        self.assertEqual((ms[0]["where"], ms[0]["start"], ms[0]["end"]), ({"footnote": 2}, s, s + len("Fictínus Nemáki")))

    def test_longer_names_are_placed_first(self):
        text = "Romæ, beatórum Nemárdi a Fictúra Néma, presbýteri, et Némæ, vírginis."
        ms, review, _ = mentions_of(text, persons=[{"name": "Nema", "where": "text"},
                                                   {"name": "Nemardus a Fictura Nema", "where": "text"}])
        self.assertEqual([m["form"] for m in ms], ["Nemárdi a Fictúra Néma", "Némæ"])
        self.assertEqual(review, [])

    def test_of_two_names_as_long_a_decided_one_is_placed_first(self):
        text = "In Coréa, sancti Pauli Nem Nŭm-ka, mártyris."
        persons = [{"name": "Paulus Nem Num Ka", "where": "text"}, {"name": "Paulus Nem Nŭm-ka", "where": "text"}]
        ms, review, _ = mentions_of(text, persons=persons, qids={"Paulus Nem Nŭm-ka": "Q1"})
        self.assertEqual([(m["name"], m["qid"]) for m in ms], [("Paulus Nem Nŭm-ka", "Q1")])
        self.assertEqual([(r["op"], r["name"]) for r in review], [("add_mention", "Paulus Nem Num Ka")])

    def test_a_longer_undecided_name_still_comes_before_a_shorter_decided_one(self):
        text = "Romæ, beáti Nemárdi a Fictúra Néma, presbýteri."
        persons = [{"name": "Nema", "where": "text"}, {"name": "Nemardus a Fictura Nema", "where": "text"}]
        ms, review, _ = mentions_of(text, persons=persons, qids={"Nema": "Q2"})
        self.assertEqual([(m["name"], m["form"]) for m in ms], [("Nemardus a Fictura Nema", "Nemárdi a Fictúra Néma")])
        self.assertEqual([(r["op"], r["name"]) for r in review], [("add_mention", "Nema")])

    def test_a_person_inside_a_place_phrase_is_reviewed_and_the_place_kept(self):
        text = "In civitáte Sancti Ioánnis, commemorátio sanctórum mártyrum."
        ms, review, _ = mentions_of(text, [{"role": "cult", "la": "In civitáte Sancti Ioánnis", "source": "lead"}],
                                    [{"name": "Ioannes", "where": "text"}])
        self.assertEqual([m["kind"] for m in ms], ["place"])
        self.assertEqual([(r["op"], r["kind"], r["form"]) for r in review], [
            ("add_mention", "person", "Ioánnis"), ("remove_mention", "place", "In civitáte Sancti Ioánnis")])

    def test_two_persons_inside_one_place_phrase_remove_the_place_once(self):
        text = "In civitáte Sancti Ioánnis Páuli, commemorátio sanctórum."
        ms, review, _ = mentions_of(text, [{"role": "cult", "la": "In civitáte Sancti Ioánnis Páuli",
                                            "source": "lead"}],
                                    [{"name": "Ioannes", "where": "text"}, {"name": "Paulus", "where": "text"}])
        self.assertEqual([m["kind"] for m in ms], ["place"])
        removes = [r for r in review if r["op"] == "remove_mention"]
        self.assertEqual(len(removes), 1)
        self.assertIn("Ioannes", removes[0]["reasoning"])
        self.assertIn("Paulus", removes[0]["reasoning"])
        adds = sorted((r["start"], r["end"]) for r in review if r["op"] == "add_mention")
        self.assertEqual(len(adds), 2)
        self.assertLessEqual(adds[0][1], adds[1][0])

    def test_an_unfound_person_is_reviewed_with_its_best_partial_match(self):
        text = "Romæ, beáti Nemárdi a Fictúra, presbýteri."
        ms, review, _ = mentions_of(text, persons=[{"name": "Nemardus Baptista", "where": "text"}])
        self.assertEqual(ms, [])
        self.assertEqual((review[0]["op"], review[0]["kind"], review[0]["name"], review[0]["form"]),
                         ("add_mention", "person", "Nemardus Baptista", "Nemárdi"))

    def test_a_person_with_no_match_at_all_has_no_span(self):
        _, review, _ = mentions_of("Romæ, sancti Nemo.", persons=[{"name": "Felix", "where": "text"}])
        self.assertEqual((review[0]["start"], review[0]["end"], review[0]["form"]), (None, None, None))

    def test_a_further_match_is_proposed_as_the_same_person_and_nothing_is_removed(self):
        text = "Romæ, sanctórum Felícis presbýteri et Felícis diáconi."
        ms, review, _ = mentions_of(text, persons=[{"name": "Felix", "where": "text"}])
        second = text.index("Felícis", text.index("Felícis") + 1)
        self.assertEqual([(m["start"], m["name"]) for m in ms], [(text.index("Felícis"), "Felix")])
        self.assertEqual([(r["op"], r["kind"], r["start"], r["name"]) for r in review],
                         [("add_mention", "person", second, "Felix")])
        self.assertNotIn("n", review[0])

    def test_an_unfound_place_is_reviewed(self):
        ms, review, _ = mentions_of("Romæ, beáti Nemo.", [{"role": "death", "la": "Londínii in Anglia",
                                                           "source": "lead"}])
        self.assertEqual(ms, [])
        self.assertEqual((review[0]["op"], review[0]["kind"], review[0]["start"]), ("add_mention", "place", None))
        self.assertEqual(review[0]["qid"], "Q84")

    def test_where_key(self):
        self.assertEqual((em.where_key("text"), em.where_key({"footnote": 2})), ("text", "footnote:2"))


class RepeatedNamesTest(unittest.TestCase):
    NOTE = "Quorum nómina: Felix, Emeritus; álius Felix, Rogatus; Felix."

    def test_persons_of_one_name_take_its_matches_in_order(self):
        persons = [{"name": "Felix", "where": {"footnote": 1}}, {"name": "Felix", "n": 2, "where": {"footnote": 1}},
                   {"name": "Felix", "n": 3, "where": {"footnote": 1}}]
        ms, review, _ = mentions_of("Romæ.", persons=persons, notes=[self.NOTE], qids={"Felix#2": "Q2"})
        starts = [i for i in range(len(self.NOTE)) if self.NOTE.startswith("Felix", i)]
        self.assertEqual([(m["start"], m.get("n"), m["qid"]) for m in ms],
                         [(starts[0], None, None), (starts[1], 2, "Q2"), (starts[2], 3, None)])
        self.assertEqual(list(ms[1]), ["kind", "where", "start", "end", "form", "name", "n", "qid"])
        self.assertEqual(review, [])

    def test_a_decided_second_person_does_not_take_the_first_match(self):
        persons = [{"name": "Felix", "where": {"footnote": 1}}, {"name": "Felix", "n": 2, "where": {"footnote": 1}}]
        ms, _, _ = mentions_of("Romæ.", persons=persons, notes=[self.NOTE], qids={"Felix#2": "Q2"})
        self.assertEqual([m.get("n") for m in sorted(ms, key=lambda m: m["start"])], [None, 2])

    def test_a_match_after_the_last_person_of_a_name_is_proposed_as_that_person(self):
        persons = [{"name": "Felix", "where": {"footnote": 1}}, {"name": "Felix", "n": 2, "where": {"footnote": 1}}]
        ms, review, _ = mentions_of("Romæ.", persons=persons, notes=[self.NOTE])
        third = self.NOTE.rindex("Felix")
        self.assertEqual(len(ms), 2)
        self.assertEqual([(r["op"], r["start"], r["name"], r["n"]) for r in review],
                         [("add_mention", third, "Felix", 2)])
        self.assertIn("matched again", review[0]["reasoning"])

    def test_a_footnote_person_of_the_name_does_not_hide_a_further_match_in_the_text(self):
        # Felix (the subject, in the text) and another Felix in a footnote: the text's last person of the
        # name is Felix 1, so the text's second "Felícis" is proposed as him.
        text = "Romæ, sanctórum Felícis et Felícis."
        persons = [{"name": "Felix", "where": "text"}, {"name": "Felix", "n": 2, "where": {"footnote": 1}}]
        ms, review, _ = mentions_of(text, persons=persons, notes=["Quorum nómina: álius Felix, Victor."])
        self.assertEqual([(m["where"], m.get("n")) for m in ms], [("text", None), ({"footnote": 1}, 2)])
        self.assertEqual([(r["op"], r["where"], r["start"], r["name"], r.get("n")) for r in review],
                         [("add_mention", "text", text.rindex("Felícis"), "Felix", None)])

    def test_a_further_match_found_at_another_step_is_proposed_too(self):
        # The first match is verbatim, the second only by stem: still a further match of the name.
        text = "Romæ, sanctus Felix, mártyr; ídem Felícis memória."
        ms, review, _ = mentions_of(text, persons=[{"name": "Felix", "where": "text"}])
        self.assertEqual([m["form"] for m in ms], ["Felix"])
        self.assertEqual([(r["op"], r["form"]) for r in review], [("add_mention", "Felícis")])

    def test_spellings_of_one_name_are_one_name(self):
        # Two martyrs whose names differ only in their accents: name_key folds them together, so
        # extract_persons numbers the second, and each keeps its own words.
        note = "Quorum nómina: Iosephus Tuấn, Petrus, Iosephus Tuân."
        persons = [{"name": "Iosephus Tuấn", "where": {"footnote": 1}},
                   {"name": "Iosephus Tuân", "n": 2, "where": {"footnote": 1}}]
        # Spellings of one name may differ in length ("Æmilia", "Aemilia"): still placed in n order.
        aemiliae = [{"name": "Æmilia", "where": {"footnote": 1}}, {"name": "Aemilia", "n": 2, "where": {"footnote": 1}}]
        ms = mentions_of("Romæ.", persons=aemiliae, notes=["Quorum nómina: Æmilia, Petrus, Æmilia."])[0]
        self.assertEqual([m.get("n") for m in ms], [None, 2])
        for qids in ({}, {"Iosephus Tuân#2": "Q2"}):
            ms, review, _ = mentions_of("Romæ.", persons=persons, notes=[note], qids=qids)
            self.assertEqual([(m["form"], m.get("n")) for m in ms], [("Iosephus Tuấn", None), ("Iosephus Tuân", 2)])
            self.assertEqual(review, [])


ED = "martyrologium_romanum_2004"
PLACES = {"mr:0101-basilius": [BASIL_PLACE], "mr:0102-nemo": [{"role": "death", "la": "Romæ", "source": "lead"}]}
PERSONS = {"mr:0101-basilius": [{"name": "Basilius", "where": "text"}]}
ITEMS = {"mr:0101-basilius": {"Basilius": {"wikidata": "Q19546", "status": "auto"}}}
GAZ = {"Cæsaréæ in Cappadócia": {"wikidata": "Q48338", "status": "auto"}}


class BuildEditionTest(unittest.TestCase):
    def build(self, curated=None):
        return em.build_edition("la", {"mr:0101-basilius": BASIL_TEXT}, {}, PLACES, PERSONS, GAZ, ITEMS,
                                curated or {})

    def test_marks_counts_and_skips_eulogies_without_a_text(self):
        out, review, counts = self.build()
        self.assertEqual([m["form"] for m in out["mr:0101-basilius"]], ["Cæsaréæ in Cappadócia", "Basilíi"])
        self.assertEqual([m["qid"] for m in out["mr:0101-basilius"]], ["Q48338", "Q19546"])
        self.assertNotIn("mr:0102-nemo", out)
        self.assertEqual(counts["no_text"], ["mr:0102-nemo"])
        self.assertEqual(counts["expected"][("place", True)], 2)
        self.assertEqual(counts["found"][("person", True, "stem")], 1)

    def test_a_curated_eulogy_replaces_the_extraction_and_takes_its_qids(self):
        s = BASIL_TEXT.index("Basilíi")
        curated = {"mr:0101-basilius": [{"kind": "person", "where": "text", "start": s, "end": s + 7,
                                         "check": em.check("Basilíi"), "name": "Basilius", "qid": "Q1"}]}
        out, _, counts = self.build(curated)
        self.assertEqual(out["mr:0101-basilius"], [{"kind": "person", "where": "text", "start": s, "end": s + 7,
                                                    "form": "Basilíi", "name": "Basilius", "qid": "Q19546"}])
        self.assertEqual(counts["found"][("person", True, "curated")], 1)

    def test_a_curated_second_person_takes_the_qid_decided_for_its_key(self):
        text = "Romæ, sanctórum Felícis et Felícis."
        s = text.rindex("Felícis")
        curated = {"mr:0101-felix": [{"kind": "person", "where": "text", "start": s, "end": s + 7,
                                      "check": em.check("Felícis"), "name": "Felix", "n": 2, "qid": None}]}
        out, _, _ = em.build_edition("la", {"mr:0101-felix": text}, {}, {}, {}, {},
                                     {"mr:0101-felix": {"Felix": {"wikidata": "Q1", "status": "auto"},
                                                        "Felix#2": {"wikidata": "Q2", "status": "auto"}}},
                                     curated)
        self.assertEqual([(m["n"], m["qid"]) for m in out["mr:0101-felix"]], [(2, "Q2")])

    def test_a_curated_span_whose_check_fails_is_an_error(self):
        s = BASIL_TEXT.index("Basilíi")
        curated = {"mr:0101-basilius": [{"kind": "person", "where": "text", "start": s, "end": s + 7,
                                         "check": em.check("Basilii"), "name": "Basilius", "qid": None}]}
        out, _, _ = self.build(curated)
        errors = em.validate({ED: out}, lambda e, m, w: BASIL_TEXT)
        self.assertEqual(len(errors), 1)
        self.assertIn("mr:0101-basilius", errors[0])
        self.assertIn("does not pass its check", errors[0])


def person(start, end, form, name="Nemo"):
    return {"kind": "person", "where": "text", "start": start, "end": end, "form": form, "name": name, "qid": None}


class ValidateTest(unittest.TestCase):
    def errors(self, mentions, text="Romæ, sancti Nemínis."):
        return em.validate({"ed": {"mr:x": mentions}}, lambda e, m, w: text)

    def test_a_valid_mention(self):
        self.assertEqual(self.errors([person(13, 20, "Nemínis")]), [])

    def test_a_span_that_is_not_its_words_is_an_error(self):
        self.assertIn("does not pass its check", self.errors([person(0, 4, "Nemo")])[0])

    def test_overlaps_are_errors(self):
        self.assertIn("overlaps", self.errors([person(13, 20, "Nemínis"), person(13, 17, "Nemí")])[0])

    def test_a_person_needs_a_name_and_a_place_has_none(self):
        nameless = dict(person(13, 20, "Nemínis"), name=None)
        self.assertIn("a person needs a name", self.errors([nameless])[0])

    def test_a_missing_footnote_is_an_error(self):
        m = dict(person(0, 4, "Nemo"), where={"footnote": 3})
        errors = em.validate({"ed": {"mr:x": [m]}}, lambda e, mrid, w: None)
        self.assertIn("has no text", errors[0])


class CheckTest(unittest.TestCase):
    def test_check_is_sha256_of_the_utf8_printed_words(self):
        self.assertEqual(em.check("Cæsaréæ"), hashlib.sha256("Cæsaréæ".encode("utf-8")).hexdigest()[:8])
        self.assertNotEqual(em.check("Cæsaréæ"), em.check("Caesareae"))
        self.assertRegex(em.check("Basilíi"), r"^[0-9a-f]{8}$")

    def test_a_span_over_a_surrogate_pair(self):
        text = "\U0001D510 Nemo"
        doc = json.loads(em.render_json({"ed": {"mr:x": [dict(person(0, 1, "\U0001D510"), name="X")]}},
                                        lambda e, m, w: text, None))
        m = doc["editions"]["ed"]["mr:x"][0]
        self.assertEqual((m["start"], m["end"]), (0, 2))
        self.assertEqual(m["check"], hashlib.sha256("\U0001D510".encode("utf-8")).hexdigest()[:8])
        self.assertEqual(em.from_file(m, text)["form"], "\U0001D510")


class RenderTest(unittest.TestCase):
    def test_offsets_are_utf16_the_words_are_a_check_and_the_texts_commit_is_recorded(self):
        text = "\U0001D510 Nemo"
        doc = json.loads(em.render_json({"ed": {"mr:x": [person(2, 6, "Nemo")]}}, lambda e, m, w: text, "abc123"))
        self.assertEqual(list(doc), ["$comment", "texts", "editions"])
        self.assertEqual(doc["texts"], {"commit": "abc123"})
        m = doc["editions"]["ed"]["mr:x"][0]
        self.assertEqual((m["start"], m["end"], m["check"]), (3, 7, em.check("Nemo")))
        self.assertEqual(list(m), ["kind", "where", "start", "end", "check", "name", "qid"])

    def test_a_second_person_keeps_n_in_the_file(self):
        text = "Romæ, sanctórum Felícis et Felícis."
        s = text.rindex("Felícis")
        m = {"kind": "person", "where": "text", "start": s, "end": s + 7, "form": "Felícis", "name": "Felix", "n": 2,
             "qid": None}
        self.assertEqual(list(em.to_file(m, text)), ["kind", "where", "start", "end", "check", "name", "n", "qid"])
        self.assertEqual(em.from_file(em.to_file(m, text), text), m)

    def test_report(self):
        _, _, counts = em.build_edition("la", {"mr:0101-basilius": BASIL_TEXT}, {}, PLACES, PERSONS, GAZ, ITEMS, {})
        report = em.render_report({"martyrologium_romanum_2004": counts})
        self.assertIn("| Persons in the text | 1 | 1 | 100.0% | stem 1 |", report)
        self.assertIn("`mr:0102-nemo`", report)
        self.assertNotIn("Basilíi", report)

    def test_texts_commit_outside_git_is_none(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(em.texts_commit(Path(d)))

    def test_the_curated_file_carries_the_one_comment(self):
        curated = json.loads((Path(__file__).resolve().parent.parent / "data" / "mentions_curated.json")
                             .read_text(encoding="utf-8"))
        self.assertEqual(curated["$comment"], em.CURATED_COMMENT)


class FootnoteTest(unittest.TestCase):
    NOTES = {"mr:0101-basilius": ["Prima nota.", "Nemínis in nota."]}

    def test_source_text_numbers_footnotes_from_one(self):
        src = (self.texts(), self.NOTES)
        self.assertEqual(em.source_text(src, "mr:0101-basilius", {"footnote": 1}), "Prima nota.")
        self.assertEqual(em.source_text(src, "mr:0101-basilius", {"footnote": 2}), "Nemínis in nota.")
        self.assertIsNone(em.source_text(src, "mr:0101-basilius", {"footnote": 0}))
        self.assertIsNone(em.source_text(src, "mr:0101-basilius", {"footnote": 3}))
        self.assertIsNone(em.source_text(src, "mr:0102-nemo", {"footnote": 1}))
        self.assertEqual(em.source_text(src, "mr:0101-basilius", "text"), BASIL_TEXT)

    def texts(self):
        return {"mr:0101-basilius": BASIL_TEXT}

    def test_a_footnote_mention_is_relative_to_its_footnote(self):
        ms, _, hows = em.eulogy_mentions(BASIL_TEXT, self.NOTES["mr:0101-basilius"], [],
                                         [{"name": "Nemo", "where": {"footnote": 2}}], lang="la",
                                         place_qid=GAZETTEER.get, person_qid=lambda n: None)
        self.assertEqual((ms[0]["where"], ms[0]["start"], ms[0]["form"]), ({"footnote": 2}, 0, "Nemínis"))
        self.assertEqual(hows, [("person", False, "stem")])

    def test_a_curated_footnote_mention_passes_through_build_and_render(self):
        curated = {"mr:0101-basilius": [{"kind": "person", "where": {"footnote": 2}, "start": 0, "end": 7,
                                         "check": em.check("Nemínis"), "name": "Nemo", "qid": None}]}
        out, _, counts = em.build_edition("la", self.texts(), self.NOTES, {}, {}, GAZ, {}, curated)
        self.assertEqual(out["mr:0101-basilius"][0]["form"], "Nemínis")
        self.assertEqual(counts["found"][("person", False, "curated")], 1)
        source = lambda e, m, w: em.source_text((self.texts(), self.NOTES), m, w)
        self.assertEqual(em.validate({ED: out}, source), [])
        doc = json.loads(em.render_json({ED: out}, source, None))
        m = doc["editions"][ED]["mr:0101-basilius"][0]
        self.assertEqual((m["where"], m["start"], m["end"], m["check"]),
                         ({"footnote": 2}, 0, 7, em.check("Nemínis")))


FICTURA = "Romæ, beáti Nemárdi a Fictúra, presbýteri."


class ReviewOpsTest(unittest.TestCase):
    def test_an_add_with_a_span(self):
        s = FICTURA.index("Nemárdi")
        review = {"mr:x": [{"op": "add_mention", "kind": "person", "where": "text", "start": s, "end": s + 7,
                            "form": "Nemárdi", "name": "Nemardus Baptista", "reasoning": "Nemardus Baptista was not found"}]}
        op = em.review_ops(ED, review, lambda e, m, w: FICTURA)[0]
        self.assertEqual(list(op), ["op", "id", "edition", "eulogy", "where", "start", "end", "form", "kind", "name",
                                    "context", "context_start", "reasoning", "decision", "edited"])
        self.assertEqual(op["id"], f"{ED}|mr:x|text|{s}")
        self.assertEqual(op["context"][op["start"] - op["context_start"]:][:7], "Nemárdi")
        self.assertEqual((op["decision"], op["edited"]), (None, None))

    def test_an_add_without_a_span_quotes_the_whole_text_and_ends_its_id_with_the_name(self):
        notes = "Quorum nómina: Paulus et Ioánnes."
        review = {"mr:x": [{"op": "add_mention", "kind": "person", "where": {"footnote": 2}, "start": None,
                            "end": None, "form": None, "name": "Felix", "reasoning": "Felix was not found"}]}
        op = em.review_ops(ED, review, lambda e, m, w: notes)[0]
        self.assertEqual(op["id"], f"{ED}|mr:x|footnote:2|Felix")
        self.assertEqual((op["start"], op["end"], op["form"], op["context"], op["context_start"]),
                         (None, None, None, notes, 0))

    def test_a_spanless_place_add_ends_its_id_with_its_qid(self):
        review = {"mr:x": [{"op": "add_mention", "kind": "place", "where": "text", "start": None, "end": None,
                            "form": None, "qid": "Q48338", "reasoning": "the place was not found"}]}
        op = em.review_ops(ED, review, lambda e, m, w: FICTURA)[0]
        self.assertEqual(op["id"], f"{ED}|mr:x|text|Q48338")
        self.assertNotIn("name", op)

    def test_a_spanless_place_add_without_a_qid_ends_its_id_with_place(self):
        review = {"mr:x": [{"op": "add_mention", "kind": "place", "where": "text", "start": None, "end": None,
                            "form": None, "qid": None, "reasoning": "the place was not found"}]}
        op = em.review_ops(ED, review, lambda e, m, w: FICTURA)[0]
        self.assertEqual(op["id"], f"{ED}|mr:x|text|place")

    def test_two_ops_at_one_offset_get_distinct_ids(self):
        review = {"mr:x": [
            {"op": "remove_mention", "kind": "place", "where": "text", "start": 0, "end": 4, "form": "Romæ",
             "reasoning": "x"},
            {"op": "add_mention", "kind": "person", "where": "text", "start": 0, "end": 4, "form": "Romæ",
             "name": "Roma", "reasoning": "y"}]}
        ids = [op["id"] for op in em.review_ops(ED, review, lambda e, m, w: FICTURA)]
        self.assertEqual(len(set(ids)), 2)
        self.assertEqual(ids[0], f"{ED}|mr:x|text|0")
        self.assertEqual(ids[1], f"{ED}|mr:x|text|0|add_mention")

    def test_an_add_for_a_second_person_carries_n_and_a_spanless_one_ends_its_id_with_the_key(self):
        notes = "Quorum nómina: Paulus et Ioánnes."
        review = {"mr:x": [{"op": "add_mention", "kind": "person", "where": {"footnote": 1}, "start": None,
                            "end": None, "form": None, "name": "Felix", "n": 2, "reasoning": "Felix was not found"}]}
        op = em.review_ops(ED, review, lambda e, m, w: notes)[0]
        self.assertEqual(op["id"], f"{ED}|mr:x|footnote:1|Felix#2")
        self.assertEqual((op["name"], op["n"]), ("Felix", 2))
        self.assertEqual(list(op)[9:11], ["name", "n"])

    def test_a_remove_has_a_kind_and_no_edited(self):
        review = {"mr:x": [{"op": "remove_mention", "kind": "place", "where": "text", "start": 0, "end": 4,
                            "form": "Romæ", "reasoning": "x"}]}
        op = em.review_ops(ED, review, lambda e, m, w: FICTURA)[0]
        self.assertEqual(op["kind"], "place")
        self.assertNotIn("edited", op)
        self.assertNotIn("name", op)

    def test_the_context_is_words_around_the_span(self):
        text = "Alpha beta gamma delta " * 6 + "Nemo" + " epsilon zeta eta theta" * 6
        s = text.index("Nemo")
        ctx, at = em.context(text, s, s + 4)
        self.assertTrue(0 < at < s and s + 4 < at + len(ctx) < len(text))
        self.assertEqual(text[at:at + len(ctx)], ctx)
        self.assertEqual(text[at - 1], " ")


def write(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")


ALLOWED_STRINGS = {"kind", "qid", "name", "check", "where"}


def no_printed_words(doc):
    """Every string value of a mentions file that is not an id, QID, name, kind,
    check or where ("text"): the policy test. `form` must never appear."""
    found = []

    def walk(node, key=None):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "form":
                    found.append(("form", v))
                elif k not in ("$comment", "commit"):
                    walk(v, k)
        elif isinstance(node, list):
            for v in node:
                walk(v, key)
        elif isinstance(node, str) and key not in ALLOWED_STRINGS:
            found.append((key, node))

    walk(doc)
    return found


IT_TEXT = "A Cesarea in Cappadocia, san Basilio, vescovo."
IT_ED = "martyrologium_romanum_2004_it_IT"


def fixture(root, files=None):
    """A crmedr root and a texts checkout with one Latin and one Italian eulogy.
    `files` maps an edition to its {eulogy: text}, to replace those of the default."""
    repo, texts = root / "crmedr", root / "texts"
    write(repo / "data" / "places.json", {"places": PLACES})
    write(repo / "data" / "persons.json", {"editions": {ED: PERSONS}})
    write(repo / "data" / "gazetteer.json", {"places": GAZ})
    write(repo / "data" / "person_items.json", {"persons": ITEMS})
    (repo / "docs").mkdir(parents=True)
    files = files or {ED: {"mr:0101-basilius": BASIL_TEXT}, IT_ED: {"mr:0101-basilius": IT_TEXT}}
    for edition, by_id in files.items():
        for month in range(1, 13):
            write(texts / "data" / "editions" / edition / f"{month:02d}.json", by_id if month == 1 else {})
    return repo, texts


def run_main(argv):
    """em.main without its progress line in the test output."""
    with contextlib.redirect_stdout(io.StringIO()):
        em.main(argv)


class MainTest(unittest.TestCase):
    def test_writes_mentions_report_and_review(self):
        with tempfile.TemporaryDirectory() as d:
            repo, texts = fixture(Path(d))
            review = Path(d) / "private" / "mentions-review.json"
            review.parent.mkdir()
            run_main([str(texts), str(repo), "--review", str(review)])
            doc = json.loads((repo / "data" / "mentions.json").read_text(encoding="utf-8"))
            self.assertEqual(doc["texts"], {"commit": None})
            self.assertEqual([m["check"] for m in doc["editions"][ED]["mr:0101-basilius"]],
                             [em.check("Cæsaréæ in Cappadócia"), em.check("Basilíi")])
            self.assertEqual([m["check"] for m in doc["editions"][IT_ED]["mr:0101-basilius"]],
                             [em.check("A Cesarea in Cappadocia")])
            self.assertTrue((repo / "docs" / "mentions-report.md").exists())
            changeset = json.loads(review.read_text(encoding="utf-8"))
            self.assertEqual((changeset["schema"], changeset["operations"]), ("crmedr-changeset/v1", []))

    def test_mentions_json_holds_no_printed_words(self):
        with tempfile.TemporaryDirectory() as d:
            repo, texts = fixture(Path(d))
            run_main([str(texts), str(repo), "--review", str(Path(d) / "mentions-review.json")])
            doc = json.loads((repo / "data" / "mentions.json").read_text(encoding="utf-8"))
            self.assertEqual(no_printed_words(doc), [])
            self.assertEqual(doc["editions"][ED]["mr:0101-basilius"][1]["check"], em.check("Basilíi"))

    def test_the_review_path_is_required(self):
        with tempfile.TemporaryDirectory() as d:
            repo, texts = fixture(Path(d))
            with self.assertRaises(SystemExit):
                run_main([str(texts), str(repo)])
            self.assertFalse((repo / "data" / "mentions.json").exists())

    def test_a_review_path_inside_the_repository_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            repo, texts = fixture(Path(d))
            with self.assertRaises(SystemExit) as cm:
                run_main([str(texts), str(repo), "--review", str(repo / "data" / "mentions-review.json")])
            self.assertIn("outside the repository", str(cm.exception.code))

    def test_an_exported_change_set_inside_the_repository_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            repo, texts = fixture(Path(d))
            exported = repo / "data" / "mentions-review-exported.json"
            write(exported, {"operations": []})
            with self.assertRaises(SystemExit) as cm:
                run_main(["apply", str(exported), str(texts), str(repo), "--review", str(Path(d) / "r.json")])
            self.assertIn("outside the repository", str(cm.exception.code))
            self.assertFalse((repo / "data" / "mentions.json").exists())

    def test_a_text_filed_under_a_twin_is_recorded_under_the_twin(self):
        with tempfile.TemporaryDirectory() as d:
            # The persons and places belong to mr:0101-basilius; the editions file the text under its twin.
            files = {ED: {"mr:0614-basilius": BASIL_TEXT}, IT_ED: {"mr:0614-basilius": IT_TEXT}}
            repo, texts = fixture(Path(d), files)
            write(repo / "data" / "martyrology_ids.json", {"entries": [
                {"id": "mr:0101-basilius", "same_eulogy": ["mr:0614-basilius"]},
                {"id": "mr:0614-basilius", "deprecated": True}]})
            run_main([str(texts), str(repo), "--review", str(Path(d) / "mentions-review.json")])
            doc = json.loads((repo / "data" / "mentions.json").read_text(encoding="utf-8"))
            for edition in (ED, IT_ED):
                self.assertEqual(list(doc["editions"][edition]), ["mr:0614-basilius"])
            ms = doc["editions"][ED]["mr:0614-basilius"]
            self.assertEqual([m["check"] for m in ms], [em.check("Cæsaréæ in Cappadócia"), em.check("Basilíi")])
            s = BASIL_TEXT.index("Basilíi")  # offsets into the twin's text
            self.assertEqual((ms[1]["start"], ms[1]["end"], ms[1]["name"], ms[1]["qid"]), (s, s + 7, "Basilius", "Q19546"))
            report = (repo / "docs" / "mentions-report.md").read_text(encoding="utf-8")
            self.assertIn("`mr:0101-basilius` (as `mr:0614-basilius`)", report)
            self.assertNotIn("no text of their own in this edition: `mr:0101", report)

    def test_a_twin_with_mentions_of_its_own_is_left_alone(self):
        entries = [{"id": "mr:0101-a", "same_eulogy": ["mr:0614-b"]}]
        places, persons, twins = em.file_under_twins(entries, {"mr:0614-b": "x"}, {"mr:0101-a": [1], "mr:0614-b": [2]}, {})
        self.assertEqual((twins, places), ({}, {"mr:0101-a": [1], "mr:0614-b": [2]}))

    def test_a_text_filed_under_a_twin_reports_a_review_op_under_the_twin(self):
        with tempfile.TemporaryDirectory() as d:
            files = {ED: {"mr:0614-basilius": "Alia verba nulla."}, IT_ED: {}}
            repo, texts = fixture(Path(d), files)
            write(repo / "data" / "martyrology_ids.json", {"entries": [
                {"id": "mr:0101-basilius", "same_eulogy": ["mr:0614-basilius"]}]})
            review = Path(d) / "mentions-review.json"
            run_main([str(texts), str(repo), "--review", str(review)])
            ops = json.loads(review.read_text(encoding="utf-8"))["operations"]
            self.assertTrue(ops)
            self.assertEqual({op["eulogy"] for op in ops}, {"mr:0614-basilius"})
            self.assertTrue(all(op["id"].startswith(f"{ED}|mr:0614-basilius|") for op in ops))


def stored(kind, start, end, words, name=None, qid=None):
    """A mention as the data files hold it (UTF-16 offsets, check)."""
    m = {"kind": kind, "where": "text", "start": start, "end": end, "check": em.check(words)}
    if kind == "person":
        m["name"] = name
    m["qid"] = qid
    return m


class ApplyDecisionsTest(unittest.TestCase):
    MENTIONS = {ED: {"mr:x": [stored("place", 0, 4, "Romæ", qid="Q220"), stored("person", 13, 20, "Nemínis", "Nemo")]}}

    def op(self, op, decision="accept", **kw):
        return {"op": op, "edition": ED, "eulogy": "mr:x", "where": "text", "decision": decision, **kw}

    def test_accept_remove_edit_add_and_ignore_the_rest(self):
        exported = {"operations": [
            self.op("remove_mention", kind="person", start=13, end=20, form="Nemínis"),
            self.op("add_mention", "edit", kind="person", name="Nemo", start=None, end=None, form=None,
                    edited={"start": 13, "end": 17, "form": "Nemí"}),
            self.op("remove_mention", "reject", kind="place", start=0, end=4, form="Romæ"),
            {"op": "resolve_person", "decision": "accept"},
        ]}
        curated = {}
        applied, errors = em.apply_decisions(curated, self.MENTIONS, exported)
        self.assertEqual((applied, errors), (2, []))
        self.assertEqual([(m["start"], m.get("name")) for m in curated[ED]["mr:x"]], [(0, None), (13, "Nemo")])
        # The added mention waits for apply to check it against the texts.
        self.assertEqual((curated[ED]["mr:x"][1]["form"], "check" in curated[ED]["mr:x"][1]), ("Nemí", False))
        self.assertEqual(len(self.MENTIONS[ED]["mr:x"]), 2)  # the input is not changed

    def test_an_added_second_person_keeps_n(self):
        exported = {"operations": [self.op("add_mention", kind="person", name="Nemo", n=2, start=13, end=20,
                                           form="Nemínis")]}
        mentions = {ED: {"mr:x": [stored("place", 0, 4, "Romæ", qid="Q220")]}}
        curated = {}
        em.apply_decisions(curated, mentions, exported)
        added = curated[ED]["mr:x"][1]
        self.assertEqual((added["name"], added["n"]), ("Nemo", 2))

    def test_set_span_with_an_edit(self):
        exported = {"operations": [self.op("set_span", "edit", kind="place", **{"from": {"start": 0, "end": 4},
                                            "to": {"start": 0, "end": 3, "form": "Rom"}},
                                            edited={"start": 0, "end": 5, "form": "Romæ,"})]}
        curated = {}
        em.apply_decisions(curated, self.MENTIONS, exported)
        moved = curated[ED]["mr:x"][0]
        self.assertEqual((moved["start"], moved["end"], moved["form"], "check" in moved), (0, 5, "Romæ,", False))

    def test_an_added_mention_needs_a_span(self):
        exported = {"operations": [self.op("add_mention", kind="person", name="Felix", start=None, end=None,
                                           form=None)]}
        applied, errors = em.apply_decisions({}, self.MENTIONS, exported)
        self.assertEqual(applied, 0)
        self.assertIn("needs a span", errors[0])

    def test_an_operation_on_a_mention_that_is_not_there_is_an_error(self):
        exported = {"operations": [self.op("remove_mention", kind="place", start=1, end=4, form="omæ")]}
        applied, errors = em.apply_decisions({}, self.MENTIONS, exported)
        self.assertEqual(applied, 0)
        self.assertIn("no such mention", errors[0])

    def test_a_curated_eulogy_is_edited_where_it_stands(self):
        curated = {ED: {"mr:x": [stored("place", 0, 4, "Romæ")]}}
        em.apply_decisions(curated, self.MENTIONS, {"operations": [
            self.op("remove_mention", kind="place", start=0, end=4, form="Romæ")]})
        self.assertEqual(curated[ED]["mr:x"], [])


class ApplyCommandTest(unittest.TestCase):
    def applied(self, d, operations, files=None):
        """Extract, then apply `operations` through main; the repo and the curated file's content."""
        repo, texts = fixture(Path(d), files)
        review = Path(d) / "mentions-review.json"
        run_main([str(texts), str(repo), "--review", str(review)])
        exported = Path(d) / "exported.json"
        write(exported, {"operations": operations})
        run_main(["apply", str(exported), str(texts), str(repo), "--review", str(review)])
        curated = json.loads((repo / "data" / "mentions_curated.json").read_text(encoding="utf-8"))
        return repo, curated

    def test_apply_writes_the_curated_file_and_extracts_again(self):
        with tempfile.TemporaryDirectory() as d:
            s = BASIL_TEXT.index("Basilíi")
            repo, curated = self.applied(d, [{"op": "remove_mention", "edition": ED, "eulogy": "mr:0101-basilius",
                                              "where": "text", "kind": "person", "start": s, "end": s + 7,
                                              "form": "Basilíi", "decision": "accept"}])
            self.assertEqual(curated["$comment"], em.CURATED_COMMENT)
            self.assertEqual([m["kind"] for m in curated["editions"][ED]["mr:0101-basilius"]], ["place"])
            self.assertEqual(no_printed_words(curated), [])
            doc = json.loads((repo / "data" / "mentions.json").read_text(encoding="utf-8"))
            self.assertEqual([m["kind"] for m in doc["editions"][ED]["mr:0101-basilius"]], ["place"])

    def test_apply_computes_the_check_from_the_texts(self):
        with tempfile.TemporaryDirectory() as d:
            s = BASIL_TEXT.index("Basilíi")
            _, curated = self.applied(d, [{"op": "set_span", "edition": ED, "eulogy": "mr:0101-basilius",
                                           "where": "text", "kind": "person", "from": {"start": s, "end": s + 7},
                                           "to": {"start": s, "end": s + 8, "form": "Basilíi,"},
                                           "decision": "accept"}])
            moved = curated["editions"][ED]["mr:0101-basilius"][1]
            self.assertEqual(list(moved), ["kind", "where", "start", "end", "check", "name", "qid"])
            self.assertEqual((moved["end"], moved["check"]), (s + 8, em.check("Basilíi,")))
            self.assertEqual(no_printed_words(curated), [])

    def test_a_decision_on_a_twin_filed_eulogy_checks_its_span_in_the_twin_text(self):
        with tempfile.TemporaryDirectory() as d:
            files = {ED: {"mr:0614-basilius": BASIL_TEXT}, IT_ED: {"mr:0614-basilius": IT_TEXT}}
            ids = Path(d) / "crmedr" / "data" / "martyrology_ids.json"
            write(ids, {"entries": [{"id": "mr:0101-basilius", "same_eulogy": ["mr:0614-basilius"]},
                                    {"id": "mr:0614-basilius", "deprecated": True}]})
            s = BASIL_TEXT.index("Basilíi")
            _, curated = self.applied(d, [{"op": "set_span", "edition": ED, "eulogy": "mr:0614-basilius",
                                           "where": "text", "kind": "person", "from": {"start": s, "end": s + 7},
                                           "to": {"start": s, "end": s + 8, "form": "Basilíi,"},
                                           "decision": "accept"}], files)
            self.assertEqual(curated["editions"][ED]["mr:0614-basilius"][1]["check"], em.check("Basilíi,"))

    def test_an_apply_that_breaks_a_span_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            repo, texts = fixture(Path(d))
            exported = Path(d) / "exported.json"
            write(exported, {"operations": [{"op": "add_mention", "edition": ED, "eulogy": "mr:0101-basilius",
                                             "where": "text", "kind": "person", "name": "Nemo", "start": 0,
                                             "end": 4, "form": "Nemo", "decision": "accept"}]})
            with self.assertRaises(SystemExit):
                run_main(["apply", str(exported), str(texts), str(repo), "--review", str(Path(d) / "r.json")])
            self.assertFalse((repo / "data" / "mentions_curated.json").exists())


if __name__ == "__main__":
    unittest.main()
