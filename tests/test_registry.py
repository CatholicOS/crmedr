import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import extract_registry as r  # noqa: E402  (must import without openpyxl)

ENTRY = {"id": "mr:0101-fictitius", "month": 1, "day": 1, "entry": 1,
         "asterisk": False, "country": "IT", "note": "n"}


class RegistryTypologyTest(unittest.TestCase):
    def test_add_typology_inserts_after_country(self):
        out = r.add_typology([dict(ENTRY)], {"mr:0101-fictitius": "depositio"})
        self.assertEqual(list(out[0]), ["id", "month", "day", "entry", "asterisk", "country", "typology", "note"])
        self.assertEqual(out[0]["typology"], "depositio")

    def test_add_typology_is_idempotent_and_skips_untagged(self):
        once = r.add_typology([dict(ENTRY)], {"mr:0101-fictitius": "depositio"})
        twice = r.add_typology(once, {"mr:0101-fictitius": "depositio"})
        self.assertEqual(once, twice)
        self.assertEqual(list(twice[0]).count("typology"), 1)
        self.assertNotIn("typology", r.add_typology([dict(ENTRY)], {})[0])

    def test_load_typology_missing_file(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(r.load_typology(Path(d), {"mr:0101-fictitius"}), {})

    def test_load_typology_stale_file_fails(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "data").mkdir()
            (Path(d) / "data" / "typology.json").write_text(
                json.dumps({"typology": {"mr:0101-other": "depositio"}}), encoding="utf-8")
            with self.assertRaisesRegex(AssertionError, r"(?s)move data/typology\.json aside.*"
                                        r"extract_registry\.py.*extract_typology\.py.*extract_registry\.py"):
                r.load_typology(Path(d), {"mr:0101-fictitius"})

    def test_markdown_has_typology_column(self):
        with tempfile.TemporaryDirectory() as d:
            r.write_markdown(r.add_typology([dict(ENTRY)], {"mr:0101-fictitius": "depositio"}), Path(d))
            md = (Path(d) / "registry" / "01-january.md").read_text(encoding="utf-8")
        self.assertIn("| Day | Entry | ID | * | Country | Typology | Editions | Notes |", md)
        self.assertIn("| 1 | 1 | `mr:0101-fictitius` |  | IT | depositio |  | n |", md)
        self.assertIn("`Typology`", md)


PLACES = {"mr:0101-fictitius": [{"role": "death", "la": "Fictopoli", "source": "lead"}]}


class RegistryPlacesTest(unittest.TestCase):
    def test_add_places_after_typology(self):
        e = r.add_typology([dict(ENTRY)], {"mr:0101-fictitius": "depositio"})
        out = r.add_places(e, PLACES)
        self.assertEqual(list(out[0]), ["id", "month", "day", "entry", "asterisk", "country",
                                        "typology", "places", "note"])

    def test_add_places_without_typology_goes_after_country(self):
        out = r.add_places([dict(ENTRY)], PLACES)
        self.assertEqual(list(out[0])[5:7], ["country", "places"])

    def test_add_places_is_idempotent_and_skips_placeless(self):
        once = r.add_places([dict(ENTRY)], PLACES)
        self.assertEqual(r.add_places(once, PLACES), once)
        self.assertNotIn("places", r.add_places([dict(ENTRY)], {})[0])

    def test_add_places_drops_a_stale_key(self):
        once = r.add_places([dict(ENTRY)], PLACES)
        self.assertNotIn("places", r.add_places(once, {})[0])

    def test_place_roles_must_match_typology(self):
        r.check_place_roles(PLACES, {"mr:0101-fictitius": "dies_natalis"})
        with self.assertRaisesRegex(AssertionError, "extract_places"):
            r.check_place_roles(PLACES, {"mr:0101-fictitius": "depositio"})
        curated = {"mr:0101-fictitius": [{"role": "birth", "la": "Fictia", "source": "curated"}]}
        r.check_place_roles(curated, {"mr:0101-fictitius": "depositio"})   # curated roles are free

    def test_recovery_mentions_both_files(self):
        self.assertRegex(r.RECOVERY, r"(?s)typology\.json.*places\.json.*extract_registry.*"
                                     r"extract_typology.*extract_places.*extract_registry")

    def test_load_places(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(r.load_places(Path(d), {"mr:0101-fictitius"}), {})
            (Path(d) / "data").mkdir()
            (Path(d) / "data" / "places.json").write_text(json.dumps({"places": PLACES}), encoding="utf-8")
            self.assertEqual(r.load_places(Path(d), {"mr:0101-fictitius", "mr:0102-x"}), PLACES)
            with self.assertRaisesRegex(AssertionError, "move data/places.json aside"):
                r.load_places(Path(d), {"mr:0102-x"})



class IdCorrectionsAppliedTest(unittest.TestCase):
    """No workbook ID that ID_CORRECTIONS replaces may survive in the data."""

    def test_no_corrected_source_id_remains(self):
        root = Path(__file__).resolve().parent.parent
        files = ["data/martyrology_ids.json", "data/typology.json", "data/places.json",
                 "i18n/la.json", "i18n/it.json", "i18n/en.json"]
        text = "\n".join((root / f).read_text(encoding="utf-8") for f in files)
        leftovers = sorted(old for old in r.ID_CORRECTIONS if f'"{old}"' in text)
        self.assertEqual(leftovers, [])

    def test_registry_markdown_ids_are_canonical(self):
        """The month tables are checked too: every ID they show is in the registry."""
        root = Path(__file__).resolve().parent.parent
        canonical = {e["id"] for e in json.load(open(root / "data" / "martyrology_ids.json",
                                                      encoding="utf-8"))["entries"]}
        shown = set()
        for path in sorted((root / "registry").glob("*.md")):
            shown.update(re.findall(r"`(mr:[^`]+)`", path.read_text(encoding="utf-8")))
        self.assertTrue(shown)
        self.assertEqual(sorted(shown - canonical), [])

    def test_stephanus_fanus_is_corrected(self):
        self.assertEqual(r.ID_CORRECTIONS.get("mr:1130-stephanus-fanus"), "mr:1130-cuthbertus-mayne")

class MultiSubjectSlugs40Test(unittest.TestCase):
    """#40: a slug naming two or more subjects goes with a plural Latin subject."""

    # "et" inside a religious name, a feast title or two titles of one subject, not a
    # second subject.
    NOT_MULTI = {"mr:0724-modestinus-a-iesu-et-maria-mazzarello",
                 "mr:1118-dedicatio-basilicarum-petri-et-pauli-apostolorum",
                 "mr:1229-david-rex-et-propheta"}

    def test_corrections_present(self):
        self.assertEqual(r.ID_CORRECTIONS.get("mr:1115-guria"), "mr:1115-guria-et-samona")
        self.assertEqual(r.ID_CORRECTIONS.get("mr:0821-iosephus"), "mr:0821-iosephus-dang-dinh-vien")
        self.assertEqual(r.ID_CORRECTIONS.get("mr:0320-sabas"), "mr:0320-viginti-monachi-palaestinae")

    def test_multi_subject_ids_have_plural_latin_subjects(self):
        root = Path(__file__).resolve().parent.parent
        la = json.load(open(root / "i18n" / "la.json", encoding="utf-8"))
        entries = json.load(open(root / "data" / "martyrology_ids.json", encoding="utf-8"))["entries"]
        singular = sorted(e["id"] for e in entries
                          if not e.get("deprecated") and "-et-" in e["id"]
                          and e["id"] not in self.NOT_MULTI
                          and la[e["id"]].split()[0] not in ("Sancti", "Sanctae", "Beati", "Beatae"))
        self.assertEqual(singular, [])


class CurrentIdFixes52Test(unittest.TestCase):
    """#52: current slugs that misnamed the eulogy, and prophets keeping -propheta."""

    def test_corrections_present(self):
        self.assertEqual(r.ID_CORRECTIONS.get("mr:0905-v"), "mr:0905-quintus")
        self.assertEqual(r.ID_CORRECTIONS.get("mr:0809-laurentius"), "mr:0809-romanus")
        self.assertEqual(r.ID_CORRECTIONS.get("mr:1017-osea"), "mr:1017-osee-propheta")

    def test_prophets_say_so_in_slug_and_subject(self):
        root = Path(__file__).resolve().parent.parent
        la = json.load(open(root / "i18n" / "la.json", encoding="utf-8"))
        entries = {e["id"]: e for e in json.load(open(root / "data" / "martyrology_ids.json", encoding="utf-8"))["entries"]}
        for cid in ("mr:0615-amos-propheta", "mr:1218-malachias-propheta", "mr:1229-david-rex-et-propheta",
                    "mr:0203-simeon-et-anna-prophetissa"):
            self.assertIn(cid, entries)
            self.assertRegex(la[cid], r"Prophet(a|issa)$")
        # the 1914 deprecated twin of St Romanus merged into the renamed current ID
        self.assertFalse(entries["mr:0809-romanus"].get("deprecated"))


class Apostles56Test(unittest.TestCase):
    """#56: apostles keep -apostolus / -apostoli; feast phrases drop the honorific."""

    def test_apostles_and_feasts(self):
        root = Path(__file__).resolve().parent.parent
        la = json.load(open(root / "i18n" / "la.json", encoding="utf-8"))
        ids = {e["id"] for e in json.load(open(root / "data" / "martyrology_ids.json", encoding="utf-8"))["entries"]}
        for cid in ("mr:0514-matthias-apostolus", "mr:1028-simon-et-iudas-apostoli",
                    "mr:0629-petrus-et-paulus-apostoli", "mr:0125-conversio-pauli-apostoli",
                    "mr:0222-cathedra-petri-apostoli"):
            self.assertIn(cid, ids)
            self.assertRegex(la[cid], r"Apostol(us|i)$")
        self.assertEqual(r.ID_CORRECTIONS.get("mr:0629-petrus-et-paulus-simon"), "mr:0629-petrus-et-paulus-apostoli")
        # #59: the evangelists who were not apostles
        for cid in ("mr:0425-marcus-evangelista", "mr:1018-lucas-evangelista"):
            self.assertIn(cid, ids)
            self.assertRegex(la[cid], r"Evangelista$")
        en = json.load(open(root / "i18n" / "en.json", encoding="utf-8"))
        self.assertEqual(en["mr:1018-lucas-evangelista"], "Saint Luke the Evangelist")


class RegistryIntegrityTest(unittest.TestCase):
    """Every ID once, the header counts right, and the i18n key sets equal to the registry."""

    def test_unique_ids_counts_and_i18n(self):
        root = Path(__file__).resolve().parent.parent
        reg = json.load(open(root / "data" / "martyrology_ids.json", encoding="utf-8"))
        ids = [e["id"] for e in reg["entries"]]
        self.assertEqual(len(ids), len(set(ids)))
        dep = [e["id"] for e in json.load(open(root / "data" / "deprecated_ids.json", encoding="utf-8"))]
        self.assertEqual(len(dep), len(set(dep)))
        self.assertEqual(reg["entry_count"], len(ids))
        self.assertEqual(reg["current_count"], sum(1 for e in reg["entries"] if not e.get("deprecated")))
        self.assertEqual(reg["deprecated_count"], len(dep))
        for lang in ("la", "it", "en"):
            keys = json.load(open(root / "i18n" / f"{lang}.json", encoding="utf-8"))
            self.assertEqual(set(keys), set(ids), lang)


class PlaceLeadCorrections25Test(unittest.TestCase):
    """#25: Leonard's deprecated ID became current; three deprecated IDs were coined."""

    def test_registry(self):
        root = Path(__file__).resolve().parent.parent
        entries = {e["id"]: e for e in json.load(open(root / "data" / "martyrology_ids.json"))["entries"]}
        self.assertFalse(entries["mr:1126-leonardus-a-portu-mauritio"].get("deprecated"))
        for mr_id in ("mr:0320-photina-et-socii", "mr:0823-philippus-benizi", "mr:0324-pigmenius"):
            self.assertTrue(entries[mr_id]["deprecated"], mr_id)
        self.assertEqual(r.ID_CORRECTIONS["mr:1126-bonaventura"], "mr:1126-leonardus-a-portu-mauritio")


class DeprecatedSameEulogy45Test(unittest.TestCase):
    """#45: a deprecated ID that is the same eulogy as a current ID is removed."""

    # Kept deprecated: a separate eulogy, and same-day homonyms (see the report).
    # #51 re-minted two garbled slugs: mr:0513-maria, mr:0917-franciscus.
    KEPT = {"mr:0827-rufus-et-carpophorus", "mr:0124-timotheus",
            "mr:0513-dedicatio-sanctae-mariae-ad-martyres", "mr:0629-maria",
            "mr:0917-impressio-stigmatum-francisci"}

    def test_registry(self):
        root = Path(__file__).resolve().parent.parent
        entries = {e["id"]: e for e in json.load(open(root / "data" / "martyrology_ids.json"))["entries"]}
        # The removal mapping is the report's #45 table.
        report = (root / "docs" / "canonicalization-report.md").read_text(encoding="utf-8")
        table = report.split("| Removed deprecated ID | Current ID |", 1)[1].split("\n\n", 1)[0]
        mapping = re.findall(r"^\| (mr:\S+) \| (mr:\S+) \|$", table, re.M)
        self.assertEqual(len(mapping), 21)
        for gone, current in mapping:
            self.assertNotIn(gone, entries)
            self.assertFalse(entries[current].get("deprecated"), current)
        for mr_id in self.KEPT:
            self.assertTrue(entries[mr_id]["deprecated"], mr_id)


class February20Test(unittest.TestCase):
    """#47: the Eleutherii of February 20."""

    def test_registry(self):
        root = Path(__file__).resolve().parent.parent
        entries = {e["id"]: e for e in json.load(open(root / "data" / "martyrology_ids.json"))["entries"]}
        self.assertEqual(r.ID_CORRECTIONS["mr:0220-eleutherius"], "mr:0220-eleutherius-tornaci")
        self.assertFalse(entries["mr:0220-eleutherius-tornaci"].get("deprecated"))
        for gone in ("mr:0220-eleutherius", "mr:0220-eleutherius-pe"):
            self.assertNotIn(gone, entries)
        for dep in ("mr:0220-eleutherius-constantinopoli", "mr:0220-eleutherius-et-socii"):
            self.assertTrue(entries[dep]["deprecated"], dep)
        self.assertIn("mr:0218-sadoth-et-socii", entries["mr:0220-eleutherius-et-socii"]["note"])


class DeprecatedSameEulogy49Test(unittest.TestCase):
    """#49: 42 more deprecated IDs that are the same eulogy as a current ID are removed."""

    def test_registry(self):
        root = Path(__file__).resolve().parent.parent
        entries = {e["id"]: e for e in json.load(open(root / "data" / "martyrology_ids.json"))["entries"]}
        report = (root / "docs" / "canonicalization-report.md").read_text(encoding="utf-8")
        section = report.split("**More deprecated IDs merged into current IDs", 1)[1]
        table = section.split("| Removed deprecated ID | Current ID |", 1)[1].split("\n\n", 1)[0]
        mapping = re.findall(r"^\| (mr:\S+) \| (mr:\S+) \|$", table, re.M)
        self.assertEqual(len(mapping), 42)
        for gone, current in mapping:
            self.assertNotIn(gone, entries)
            self.assertFalse(entries[current].get("deprecated"), current)


class CrossDayEulogies49Test(unittest.TestCase):
    """#49: a eulogy printed on another day has its own ID there, linked by same_eulogy."""

    def test_link_deprecated_twins(self):
        cur = [{"id": "mr:0601-x", "month": 6, "day": 1, "entry": 1, "asterisk": False}]
        dep = [{"id": "mr:1220-x", "month": 12, "day": 20, "entry": 6, "deprecated": True,
                "same_eulogy": ["mr:0601-x"]}]
        r.link_deprecated_twins(cur, dep)
        r.link_deprecated_twins(cur, dep)
        self.assertEqual(cur[0]["same_eulogy"], ["mr:1220-x"])
        self.assertEqual(r.validate_editions(cur + dep), [])
        dep[0]["same_eulogy"] = ["mr:1220-y"]
        self.assertTrue(any("unknown" in e for e in r.validate_editions(cur + dep)))

    def test_registry(self):
        root = Path(__file__).resolve().parent.parent
        entries = json.load(open(root / "data" / "martyrology_ids.json"))["entries"]
        by_id = {e["id"]: e for e in entries}
        self.assertEqual(r.validate_editions(entries), [])
        self.assertEqual(by_id["mr:1220-ammon-et-socii"]["same_eulogy"], ["mr:0601-ammon-et-socii"])
        self.assertIn("mr:1220-ammon-et-socii", by_id["mr:0601-ammon-et-socii"]["same_eulogy"])
        self.assertNotIn("same_eulogy", by_id["mr:1209-valeria"])  # another saint, no 2004 eulogy


class PerEditionPlacementsTest(unittest.TestCase):
    """Per-edition differences from the main (Latin print) placement."""

    def test_overrides_record_cei_differences(self):
        self.assertEqual(
            r.edition_overrides("mr:0104-gregorius", entry=3, asterisk=False, cei_entry=2, cei_asterisk=False),
            {r.EDITION_IT: {"entry": 2}})
        self.assertEqual(
            r.edition_overrides("mr:0104-ferreolus", entry=4, asterisk=True, cei_entry=3, cei_asterisk=False),
            {r.EDITION_IT: {"entry": 3, "asterisk": False}})
        self.assertEqual(
            r.edition_overrides("mr:0101-fictitius", entry=1, asterisk=False, cei_entry=1, cei_asterisk=False), {})

    def test_cei_only_eulogies_are_absent_from_latin_and_english(self):
        self.assertEqual(
            r.edition_overrides("mr:0712-proclus-et-hilarion", entry=1, asterisk=False, cei_entry=1, cei_asterisk=False),
            {r.EDITION_LA: {"absent": True}, r.EDITION_EN: {"absent": True}})

    def test_tables(self):
        self.assertEqual(r.LATIN_RENUMBERING["mr:0104-gregorius"], 3)
        self.assertEqual(r.LATIN_RENUMBERING["mr:0104-elisabeth-anna-seton"], 11)
        self.assertEqual(r.LATIN_RENUMBERING["mr:0610-eduardus-poppe"], 10)
        self.assertEqual(r.LATIN_RENUMBERING["mr:0825-genesius"], 3)
        self.assertEqual(r.LATIN_RENUMBERING["mr:0825-aloysius-urbano-lanaspa"], 13)
        self.assertEqual(r.LATIN_RENUMBERING["mr:1210-gundisalvus-vines-masip"], 9)
        self.assertEqual(r.CEI_ONLY, {"mr:0712-proclus-et-hilarion", "mr:0825-eusebius-et-socii",
                                      "mr:0709-maria-a-iesu-crucifixo-petkovic", "mr:1210-marcus-antonius-durando"})
        self.assertEqual(r.SAME_EULOGY, {"mr:0610-marcus-antonius-durando": "mr:1210-marcus-antonius-durando"})
        self.assertNotIn("mr:1210-marcus-antonius-durando", r.ID_CORRECTIONS)
        self.assertNotIn("mr:0610-marcus-antonius-durando", r.PLACEMENT_OVERRIDES)
        print_only = {e["id"]: e for e in r.PRINT_ONLY_ENTRIES}
        self.assertEqual(print_only["mr:0104-abrunculus"]["entry"], 2)
        self.assertEqual(print_only["mr:0104-abrunculus"]["editions"], {r.EDITION_IT: {"absent": True}})
        self.assertEqual(print_only["mr:0104-emmanuel-gonzalez-garcia"]["entry"], 12)
        self.assertEqual(print_only["mr:0104-emmanuel-gonzalez-garcia"]["editions"], {r.EDITION_IT: {"entry": 11}})
        self.assertEqual(print_only["mr:0610-marcus-antonius-durando"]["entry"], 9)
        self.assertEqual(print_only["mr:0610-marcus-antonius-durando"]["editions"], {r.EDITION_IT: {"absent": True}})

    def test_link_same_eulogy_is_symmetric_and_idempotent(self):
        entries = [{"id": "mr:0610-x", "month": 6, "day": 10}, {"id": "mr:1210-x", "month": 12, "day": 10}]
        r.link_same_eulogy(entries, {"mr:0610-x": "mr:1210-x"})
        r.link_same_eulogy(entries, {"mr:0610-x": "mr:1210-x"})
        self.assertEqual(entries[0]["same_eulogy"], ["mr:1210-x"])
        self.assertEqual(entries[1]["same_eulogy"], ["mr:0610-x"])

    def _day(self):
        return [
            {"id": "mr:0825-a", "month": 8, "day": 25, "entry": 1, "asterisk": False, "unnumbered": True},
            {"id": "mr:0825-b", "month": 8, "day": 25, "entry": 2, "asterisk": False, "unnumbered": True},
            {"id": "mr:0825-c", "month": 8, "day": 25, "entry": 3, "asterisk": False,
             "editions": {r.EDITION_LA: {"absent": True}, r.EDITION_EN: {"absent": True}}},
            {"id": "mr:0825-d", "month": 8, "day": 25, "entry": 3, "asterisk": False,
             "editions": {r.EDITION_IT: {"entry": 4}}},
        ]

    def test_valid_day_with_unnumbered_memorias(self):
        self.assertEqual(r.validate_editions(self._day()), [])

    def test_numbering_clash_within_an_edition(self):
        day = self._day()
        del day[3]["editions"]  # the CEI would print both c and d as 3
        errors = r.validate_editions(day)
        self.assertTrue(any("8/25" in e and r.EDITION_IT in e for e in errors), errors)

    def test_bad_overrides(self):
        day = self._day()
        day[3]["editions"] = {"martyrologium_romanum_1749": {"entry": 4}}
        self.assertTrue(any("unknown edition" in e for e in r.validate_editions(day)))
        day[3]["editions"] = {r.EDITION_IT: {"day": 26}}
        self.assertTrue(any("unknown override key" in e for e in r.validate_editions(day)))
        day[3]["editions"] = {r.EDITION_IT: {"entry": 3}}
        self.assertTrue(any("repeats the main value" in e for e in r.validate_editions(day)))

    def test_same_eulogy_must_link_back_on_another_day(self):
        one = [{"id": "mr:0610-x", "month": 6, "day": 10, "entry": 1, "asterisk": False, "same_eulogy": ["mr:1210-x"]},
               {"id": "mr:1210-x", "month": 12, "day": 10, "entry": 1, "asterisk": False}]
        self.assertTrue(any("link back" in e for e in r.validate_editions(one)))
        missing = [{"id": "mr:0610-x", "month": 6, "day": 10, "entry": 1, "asterisk": False, "same_eulogy": ["mr:1210-y"]}]
        self.assertTrue(any("unknown" in e for e in r.validate_editions(missing)))

    def test_same_day_same_eulogy_only_with_a_deprecated_id(self):
        """#51: a historical eulogy whose subject the 2004 edition changed keeps its own ID and is
        linked to the current one on the same day (Circumcisio Domini / Maria Dei Genetrix)."""
        cur = {"id": "mr:0101-maria-dei-genetrix", "month": 1, "day": 1, "entry": 1, "asterisk": False,
               "same_eulogy": ["mr:0101-circumcisio-domini"]}
        dep = {"id": "mr:0101-circumcisio-domini", "month": 1, "day": 1, "entry": 1, "deprecated": True,
               "attested_in": "martyrologium_romanum_1749", "same_eulogy": ["mr:0101-maria-dei-genetrix"]}
        self.assertEqual(r.validate_editions([cur, dep]), [])
        two = [{"id": "mr:0101-a", "month": 1, "day": 1, "entry": 1, "asterisk": False, "same_eulogy": ["mr:0101-b"]},
               {"id": "mr:0101-b", "month": 1, "day": 1, "entry": 2, "asterisk": False, "same_eulogy": ["mr:0101-a"]}]
        self.assertTrue(any("same day" in e for e in r.validate_editions(two)))


class PerEditionPlacementsDataTest(unittest.TestCase):
    """The regenerated registry holds the 2004 editions' own placements."""

    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parent.parent
        cls.e = {e["id"]: e for e in json.load(open(root / "data" / "martyrology_ids.json"))["entries"]}

    def test_january_4(self):
        self.assertEqual((self.e["mr:0104-abrunculus"]["entry"], self.e["mr:0104-abrunculus"]["editions"]),
                         (2, {r.EDITION_IT: {"absent": True}}))
        self.assertEqual((self.e["mr:0104-gregorius"]["entry"], self.e["mr:0104-gregorius"]["editions"]),
                         (3, {r.EDITION_IT: {"entry": 2}}))
        self.assertEqual(self.e["mr:0104-emmanuel-gonzalez-garcia"]["entry"], 12)

    def test_durando_has_one_id_per_day(self):
        june, dec = self.e["mr:0610-marcus-antonius-durando"], self.e["mr:1210-marcus-antonius-durando"]
        self.assertEqual((june["entry"], june["same_eulogy"]), (9, ["mr:1210-marcus-antonius-durando"]))
        self.assertEqual((dec["entry"], dec["same_eulogy"]), (9, ["mr:0610-marcus-antonius-durando"]))
        self.assertEqual(dec["editions"], {r.EDITION_LA: {"absent": True}, r.EDITION_EN: {"absent": True}})
        self.assertEqual(self.e["mr:1210-gundisalvus-vines-masip"]["editions"], {r.EDITION_IT: {"entry": 10}})

    def test_august_25(self):
        self.assertEqual(self.e["mr:0825-genesius"]["entry"], 3)
        self.assertEqual(self.e["mr:0825-eusebius-et-socii"]["editions"],
                         {r.EDITION_LA: {"absent": True}, r.EDITION_EN: {"absent": True}})

    def test_asterisk_discrepancies_are_cei_overrides(self):
        self.assertEqual(self.e["mr:0104-ferreolus"]["editions"], {r.EDITION_IT: {"entry": 3, "asterisk": False}})
        with_asterisk_override = [i for i, x in self.e.items() if "asterisk" in x.get("editions", {}).get(r.EDITION_IT, {})]
        # One CEI asterisk override per verified discrepancy (29 per the report).
        self.assertEqual(sorted(with_asterisk_override), sorted(r.ASTERISK_OVERRIDES))

    def test_valid(self):
        self.assertEqual(r.validate_editions(list(self.e.values())), [])


if __name__ == "__main__":
    unittest.main()
