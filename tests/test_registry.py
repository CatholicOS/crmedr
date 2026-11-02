import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import extract_registry as r  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_INPUTS = ["data/martyrology_ids.json", "data/typology.json", "data/places.json",
                   "data/gazetteer.json", "data/countries_curated.json", "data/deprecated_ids.json",
                   "data/dates.json"]


def registry_ids():
    return {e["id"] for e in json.load(open(ROOT / "data" / "martyrology_ids.json", encoding="utf-8"))["entries"]}


def copy_registry(dst):
    """The registry and the inputs of its rebuild, copied under dst."""
    for f in REGISTRY_INPUTS:
        (dst / f).parent.mkdir(parents=True, exist_ok=True)
        (dst / f).write_bytes((ROOT / f).read_bytes())
    (dst / "registry").mkdir()
    for md in (ROOT / "registry").glob("*.md"):
        (dst / "registry" / md.name).write_bytes(md.read_bytes())

ENTRY = {"id": "mr:0101-fictitius", "month": 1, "day": 1, "entry": 1,
         "asterisk": False, "country": "IT", "note": "n"}


class RegistryDatesTest(unittest.TestCase):
    DATE = {"year": 304, "basis": "death", "source": "wikidata"}

    def test_add_dates_inserts_after_places(self):
        e = r.with_key(dict(ENTRY), "places", [{"role": "death", "la": "Romæ", "source": "lead"}])
        out = r.add_dates([e], {"mr:0101-fictitius": self.DATE})
        self.assertEqual(list(out[0]), ["id", "month", "day", "entry", "asterisk", "country", "places",
                                        "date", "note"])
        self.assertEqual(out[0]["date"], self.DATE)

    def test_add_dates_removes_stale(self):
        e = r.with_key(dict(ENTRY), "date", self.DATE)
        self.assertNotIn("date", r.add_dates([e], {})[0])

    def test_dates_with_unknown_id_fail(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "data").mkdir()
            (Path(d) / "data" / "dates.json").write_text(
                json.dumps({"dates": {"mr:0101-other": self.DATE}}), encoding="utf-8")
            with self.assertRaises(AssertionError):
                r.load_dates(Path(d), {"mr:0101-fictitius"})

    def test_load_dates_missing_file(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(r.load_dates(Path(d), {"mr:0101-fictitius"}), {})


class RegistryItemsTest(unittest.TestCase):
    ITEMS = {"mr:0101-fictitius": {"wikidata": "Q1", "kind": "group", "status": "reviewed"},
             "mr:0101-alter": {"wikidata": None, "status": "unresolved", "note": "n"}}

    def test_item_copied_after_date(self):
        e = r.with_key(dict(ENTRY), "date", {"year": 304})
        other = dict(ENTRY, id="mr:0101-alter")
        out = r.add_items([e, other], self.ITEMS)
        self.assertEqual(out[0]["item"], {"wikidata": "Q1", "kind": "group"})
        keys = list(out[0])
        self.assertEqual(keys[keys.index("date") + 1], "item")
        self.assertNotIn("item", out[1])

    def test_an_auto_suggestion_is_not_copied(self):
        auto = {"mr:0101-fictitius": {"wikidata": "Q1", "kind": "group", "status": "auto"}}
        self.assertNotIn("item", r.add_items([dict(ENTRY)], auto)[0])

    def test_items_for_unknown_ids_fail(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "data").mkdir()
            (Path(d) / "data" / "eulogy_items.json").write_text(
                json.dumps({"items": {"mr:0101-other": self.ITEMS["mr:0101-fictitius"]}}), encoding="utf-8")
            with self.assertRaisesRegex(AssertionError, "build_eulogy_items"):
                r.load_items(Path(d), {"mr:0101-fictitius"})


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



class RenamesAppliedTest(unittest.TestCase):
    """Renamed IDs (once applied on extraction from the workbook, now made in the registry
    itself, #127): the old ID is gone from the data, the new one is current."""

    RENAMED = {
        "mr:1130-stephanus-fanus": "mr:1130-cuthbertus-mayne",
        "mr:1115-guria": "mr:1115-guria-et-samona",                         # #40
        "mr:0821-iosephus": "mr:0821-iosephus-dang-dinh-vien",
        "mr:0320-sabas": "mr:0320-viginti-monachi-palaestinae",
        "mr:0905-v": "mr:0905-quintus-capuae",                                     # #52
        "mr:0809-laurentius": "mr:0809-romanus-romae",
        "mr:1017-osea": "mr:1017-osee-propheta",
        "mr:0629-petrus-et-paulus-simon": "mr:0629-petrus-et-paulus-apostoli",  # #56
        "mr:1126-bonaventura": "mr:1126-leonardus-a-portu-mauritio",        # #25
        "mr:0220-eleutherius": "mr:0220-eleutherius-tornaci",               # #47
        "mr:0709-melania-et-maria-anna-magdalena-de-guilhermier":
            "mr:0709-melania-et-maria-anna-margarita-ab-angelis",           # #77
        "mr:0317-alexandria": "mr:0317-plurimi-martyres-alexandriae",       # #109
        "mr:0623-nicomedia": "mr:0623-plurimi-martyres-nicomediae",
    }

    def test_old_ids_are_gone_and_new_ones_current(self):
        files = ["data/martyrology_ids.json", "data/typology.json", "data/places.json",
                 "i18n/la.json", "i18n/it.json", "i18n/en.json"]
        text = "\n".join((ROOT / f).read_text(encoding="utf-8") for f in files)
        self.assertEqual(sorted(old for old in self.RENAMED if f'"{old}"' in text), [])
        entries = {e["id"]: e for e in json.load(open(ROOT / "data" / "martyrology_ids.json"))["entries"]}
        for new in self.RENAMED.values():
            self.assertFalse(entries[new].get("deprecated"), new)

    def test_registry_markdown_ids_are_canonical(self):
        """The month tables are checked too: every ID they show is in the registry."""
        shown = set()
        for path in sorted((ROOT / "registry").glob("*.md")):
            shown.update(re.findall(r"`(mr:[^`]+)`", path.read_text(encoding="utf-8")))
        self.assertTrue(shown)
        self.assertEqual(sorted(shown - registry_ids()), [])


class RegistrySourceTest(unittest.TestCase):
    """#127: the committed registry is the source; no workbook."""

    def test_committed_files_are_what_the_build_writes(self):
        self.assertEqual(r.main(["--check", str(ROOT)]), 0)

    def test_no_workbook(self):
        source = (ROOT / "scripts" / "extract_registry.py").read_text(encoding="utf-8")
        self.assertNotIn("openpyxl", source)
        for name in ("ID_CORRECTIONS", "LATIN_RENUMBERING", "PRINT_ONLY_ENTRIES", "CEI_ONLY",
                     "ASTERISK_OVERRIDES", "UNNUMBERED_LEADS", "PLACEMENT_OVERRIDES", "extract"):
            self.assertFalse(hasattr(r, name), name)

    def test_a_registry_change_is_rebuilt_and_check_sees_it(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            copy_registry(d)
            path = d / "data" / "martyrology_ids.json"
            reg = json.loads(path.read_text(encoding="utf-8"))
            e = next(x for x in reg["entries"] if x["id"] == "mr:0104-gregorius-lingonensis")
            e["editions"][r.EDITION_IT]["asterisk"] = True  # the CEI now asterisks it
            path.write_text(json.dumps(reg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self.assertEqual(r.main(["--check", str(d)]), 1)
            self.assertEqual(r.main([str(d)]), 0)
            self.assertEqual(r.main(["--check", str(d)]), 0)
            rebuilt = {x["id"]: x for x in json.loads(path.read_text(encoding="utf-8"))["entries"]}
        notes = rebuilt["mr:0104-gregorius-lingonensis"]["edition_notes"]
        self.assertIn("Printed here without an asterisk (entry 3.)", notes[r.EDITION_LA])
        self.assertIn("Asterisked here", notes[r.EDITION_IT])

    def test_load_current(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "data").mkdir()
            entries = [dict(ENTRY, typology="depositio", same_eulogy=["mr:1201-dep", "mr:0601-cur"]),
                       {"id": "mr:0601-cur", "month": 6, "day": 1, "entry": 1, "asterisk": False,
                        "same_eulogy": ["mr:0101-fictitius"]},
                       {"id": "mr:1201-dep", "month": 12, "day": 1, "entry": 1, "deprecated": True}]
            (d / "data" / "martyrology_ids.json").write_text(json.dumps({"entries": entries}), encoding="utf-8")
            (d / "data" / "deprecated_ids.json").write_text(json.dumps(entries[2:]), encoding="utf-8")
            out = r.load_current(d)
            self.assertEqual([e["id"] for e in out], ["mr:0101-fictitius", "mr:0601-cur"])
            self.assertEqual(out[0], {"id": "mr:0101-fictitius", "month": 1, "day": 1, "entry": 1,
                                      "asterisk": False, "country": "IT", "same_eulogy": ["mr:0601-cur"]})
            entries[1]["same_eulogy"] = ["mr:0101-fictitius", "mr:0202-typo"]
            (d / "data" / "martyrology_ids.json").write_text(json.dumps({"entries": entries}), encoding="utf-8")
            with self.assertRaisesRegex(AssertionError, r"same_eulogy names unknown IDs \['mr:0202-typo'\]"):
                r.load_current(d)
            entries[1]["same_eulogy"] = ["mr:0101-fictitius"]
            entries[0]["remark"] = "x"
            (d / "data" / "martyrology_ids.json").write_text(json.dumps({"entries": entries}), encoding="utf-8")
            with self.assertRaisesRegex(AssertionError, "unknown registry keys"):
                r.load_current(d)

    def test_check_sees_a_surplus_month_table(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            copy_registry(d)
            (d / "registry" / "13-extra.md").write_text("x\n", encoding="utf-8")
            (d / "registry" / "notes.txt").write_text("x\n", encoding="utf-8")
            self.assertEqual(r.main(["--check", str(d)]), 1)
            self.assertEqual(r.main([str(d)]), 0)  # the rebuild removes it
            self.assertFalse((d / "registry" / "13-extra.md").exists())
            self.assertTrue((d / "registry" / "notes.txt").exists())
            self.assertEqual(r.main(["--check", str(d)]), 0)

    def test_typology_and_places_without_a_country(self):
        e = {"id": "mr:0101-fictitius", "month": 1, "day": 1, "entry": 1, "asterisk": False,
             "note": "n"}
        out = r.add_places(r.add_typology([e], {e["id"]: "depositio"}), {e["id"]: [{"la": "Romae"}]})
        self.assertEqual(list(out[0]), ["id", "month", "day", "entry", "asterisk", "typology",
                                        "places", "note"])
        self.assertEqual(out[0]["places"], [{"la": "Romae"}])

    def test_notes_for_unknown_ids_fail(self):
        with self.assertRaisesRegex(AssertionError, "not current"):
            r.add_notes([{"id": "mr:0101-fictitius", "month": 1, "day": 1, "entry": 1, "asterisk": False}])


class MultiSubjectSlugs40Test(unittest.TestCase):
    """#40: a slug naming two or more subjects goes with a plural Latin subject."""

    # "et" inside a religious name, a feast title or two titles of one subject, not a
    # second subject.
    NOT_MULTI = {"mr:0724-dominicus-mazzarello",
                 "mr:1118-dedicatio-basilicarum-petri-et-pauli-apostolorum",
                 "mr:1229-david-rex-et-propheta", "mr:0826-melchisedech-rex-et-sacerdos",
                 "mr:0921-matthaeus-apostolus-et-evangelista", "mr:1227-ioannes-apostolus-et-evangelista"}

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

    def test_prophets_say_so_in_slug_and_subject(self):
        root = Path(__file__).resolve().parent.parent
        la = json.load(open(root / "i18n" / "la.json", encoding="utf-8"))
        entries = {e["id"]: e for e in json.load(open(root / "data" / "martyrology_ids.json", encoding="utf-8"))["entries"]}
        for cid in ("mr:0615-amos-propheta", "mr:1218-malachias-propheta", "mr:1229-david-rex-et-propheta",
                    "mr:0203-simeon-et-anna-prophetissa"):
            self.assertIn(cid, entries)
            self.assertRegex(la[cid], r"Prophet(a|issa)$")
        # the 1914 deprecated twin of St Romanus merged into the renamed current ID
        self.assertFalse(entries["mr:0809-romanus-romae"].get("deprecated"))


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
        # Same-day namesakes take a place or an epithet, never a number (rule 9, #59).
        self.assertEqual([i for i in ids if any(t.isdigit() for t in i.split("-", 1)[1].split("-"))], [])


class PlaceLeadCorrections25Test(unittest.TestCase):
    """#25: Leonard's deprecated ID became current; three deprecated IDs were coined."""

    def test_registry(self):
        root = Path(__file__).resolve().parent.parent
        entries = {e["id"]: e for e in json.load(open(root / "data" / "martyrology_ids.json"))["entries"]}
        self.assertFalse(entries["mr:1126-leonardus-a-portu-mauritio"].get("deprecated"))
        for mr_id in ("mr:0320-photina-et-socii", "mr:0823-philippus-benizi", "mr:0324-pigmenius"):
            self.assertTrue(entries[mr_id]["deprecated"], mr_id)


class DeprecatedSameEulogy45Test(unittest.TestCase):
    """#45: a deprecated ID that is the same eulogy as a current ID is removed."""

    # Kept deprecated: a separate eulogy, and same-day homonyms (see the report).
    # #51 re-minted two garbled slugs: mr:0513-maria, mr:0917-franciscus.
    KEPT = {"mr:0827-rufus-et-carpophorus", "mr:0124-timotheus-ephesi",
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
            if gone != current:  # a later rename may give the eulogy the removed ID (mr:0220-eucherius-aurelianensis)
                self.assertNotIn(gone, entries)
            self.assertFalse(entries[current].get("deprecated"), current)
        for mr_id in self.KEPT:
            self.assertTrue(entries[mr_id]["deprecated"], mr_id)


class February20Test(unittest.TestCase):
    """#47: the Eleutherii of February 20."""

    def test_registry(self):
        root = Path(__file__).resolve().parent.parent
        entries = {e["id"]: e for e in json.load(open(root / "data" / "martyrology_ids.json"))["entries"]}
        self.assertFalse(entries["mr:0220-eleutherius-tornaci"].get("deprecated"))
        for gone in ("mr:0220-eleutherius", "mr:0220-eleutherius-pe"):
            self.assertNotIn(gone, entries)
        for dep in ("mr:0220-eleutherius-constantinopoli", "mr:0220-eleutherius-et-socii"):
            self.assertTrue(entries[dep]["deprecated"], dep)
        self.assertIn("mr:0218-sadoth-et-socii", entries["mr:0220-eleutherius-et-socii"]["note"])


class OrangeUrsulinesJuly9Test(unittest.TestCase):
    """#77: Sister Melania (Maria Anna Magdalena de Guilhermier) is one martyr; the
    second is Maria Anna Margarita ab Angelis de Rocher."""

    def test_registry(self):
        root = Path(__file__).resolve().parent.parent
        old, new = ("mr:0709-melania-et-maria-anna-magdalena-de-guilhermier",
                    "mr:0709-melania-et-maria-anna-margarita-ab-angelis")
        entries = {e["id"]: e for e in json.load(open(root / "data" / "martyrology_ids.json"))["entries"]}
        self.assertNotIn(old, entries)
        self.assertEqual(set(entries[new]["edition_notes"]), {r.EDITION_LA, r.EDITION_IT, r.EDITION_EN})
        la = json.load(open(root / "i18n" / "la.json"))
        self.assertEqual(la[new], "Beatae Melania et Maria Anna Margarita ab Angelis")


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
            if gone != current:  # a later rename may give the eulogy the removed ID (mr:0114-datius-mediolani)
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
        self.assertEqual((self.e["mr:0104-abrunculus-lingonensis"]["entry"], self.e["mr:0104-abrunculus-lingonensis"]["editions"]),
                         (2, {r.EDITION_IT: {"absent": True}}))
        self.assertEqual((self.e["mr:0104-gregorius-lingonensis"]["entry"], self.e["mr:0104-gregorius-lingonensis"]["editions"]),
                         (3, {r.EDITION_IT: {"entry": 2}}))
        self.assertEqual(self.e["mr:0104-emmanuel-gonzalez-garcia"]["entry"], 12)

    def test_durando_has_one_id_per_day(self):
        june, dec = self.e["mr:0610-marcus-antonius-durando"], self.e["mr:1210-marcus-antonius-durando"]
        self.assertEqual((june["entry"], june["same_eulogy"]), (9, ["mr:1210-marcus-antonius-durando"]))
        self.assertEqual((dec["entry"], dec["same_eulogy"]), (9, ["mr:0610-marcus-antonius-durando"]))
        self.assertEqual(dec["editions"], {r.EDITION_LA: {"absent": True}, r.EDITION_EN: {"absent": True}})
        self.assertEqual(self.e["mr:1210-gundisalvus-vines-masip"]["editions"], {r.EDITION_IT: {"entry": 10}})

    def test_latin_numbering_where_the_cei_differs(self):
        for mr_id, entry, cei in (("mr:0104-gregorius-lingonensis", 3, 2), ("mr:0104-elisabeth-anna-seton", 11, 10),
                                  ("mr:0610-eduardus-poppe", 10, 9), ("mr:0825-genesius-arelatis", 3, 4),
                                  ("mr:0825-aloysius-urbano-lanaspa", 13, 14),
                                  ("mr:1210-gundisalvus-vines-masip", 9, 10)):
            self.assertEqual((self.e[mr_id]["entry"], self.e[mr_id]["editions"][r.EDITION_IT]["entry"]),
                             (entry, cei), mr_id)

    def test_cei_only_and_latin_only(self):
        absent = {r.EDITION_LA: {"absent": True}, r.EDITION_EN: {"absent": True}}
        cei_only = sorted(i for i, x in self.e.items() if x.get("editions", {}).get(r.EDITION_LA) == {"absent": True})
        self.assertEqual(cei_only, ["mr:0709-maria-a-iesu-crucifixo", "mr:0712-proclus-et-hilarion",
                                    "mr:0825-eusebius-et-socii", "mr:1210-marcus-antonius-durando"])
        for mr_id in cei_only:
            self.assertEqual(self.e[mr_id]["editions"], absent, mr_id)
        latin_only = sorted(i for i, x in self.e.items() if x.get("editions", {}).get(r.EDITION_IT) == {"absent": True})
        self.assertEqual(latin_only, ["mr:0104-abrunculus-lingonensis", "mr:0610-marcus-antonius-durando"])
        self.assertEqual(self.e["mr:0104-emmanuel-gonzalez-garcia"]["editions"], {r.EDITION_IT: {"entry": 11}})

    def test_august_25(self):
        self.assertEqual(self.e["mr:0825-genesius-arelatis"]["entry"], 3)
        self.assertEqual(self.e["mr:0825-eusebius-et-socii"]["editions"],
                         {r.EDITION_LA: {"absent": True}, r.EDITION_EN: {"absent": True}})

    def test_asterisk_discrepancies_are_cei_overrides(self):
        self.assertEqual(self.e["mr:0104-ferreolus-ucetiae"]["editions"], {r.EDITION_IT: {"entry": 3, "asterisk": False}})
        with_asterisk_override = [i for i, x in self.e.items() if "asterisk" in x.get("editions", {}).get(r.EDITION_IT, {})]
        # One CEI asterisk override per verified discrepancy (29 per the report), each with a note
        # on both editions.
        self.assertEqual(len(with_asterisk_override), 29)
        for mr_id in with_asterisk_override:
            self.assertEqual(r.asterisk_notes(self.e[mr_id]).keys(), {r.EDITION_LA, r.EDITION_IT}, mr_id)

    def test_valid(self):
        self.assertEqual(r.validate_editions(list(self.e.values())), [])



class RegistryCountryTest(unittest.TestCase):
    def test_no_country_corrections(self):
        self.assertFalse(hasattr(r, "COUNTRY_CORRECTIONS"))

    def test_header_texts_describe_the_opening_place(self):
        with tempfile.TemporaryDirectory() as d:
            r.write_json([dict(ENTRY)], [], Path(d))
            r.write_markdown([dict(ENTRY)], Path(d))
            comment = json.loads((Path(d) / "data" / "martyrology_ids.json").read_text(encoding="utf-8"))["$comment"]
            md = (Path(d) / "registry" / "01-january.md").read_text(encoding="utf-8")
        self.assertIn("opening place", comment)
        self.assertIn("modern country of the place the elogium opens with", md)

if __name__ == "__main__":
    unittest.main()


class EditionNotes51Test(unittest.TestCase):
    """#51: a source error of one edition is a note on that edition only (`edition_notes`)."""

    def test_validation(self):
        base = {"id": "mr:0101-x", "month": 1, "day": 1, "entry": 1}
        ok = dict(base, edition_notes={r.EDITION_1914: "Translation error."})
        self.assertEqual(r.validate_editions([ok]), [])
        bad_ed = dict(base, edition_notes={"martyrologium_romanum_1900": "x"})
        self.assertTrue(any("edition_notes" in e for e in r.validate_editions([bad_ed])))
        empty = dict(base, edition_notes={r.EDITION_1749: ""})
        self.assertTrue(any("edition_notes" in e for e in r.validate_editions([empty])))

    def test_registry(self):
        root = Path(__file__).resolve().parent.parent
        entries = {e["id"]: e for e in json.load(open(root / "data" / "martyrology_ids.json"))["entries"]}
        angela = entries["mr:0127-angela-merici"]
        self.assertIn("Brescia", angela["edition_notes"][r.EDITION_1914])
        self.assertNotIn("Brescia", angela.get("note", ""))
        self.assertIn(r.EDITION_1749, entries["mr:0821-privatus-gabalorum"]["edition_notes"])
        self.assertIn("Peter the Younger", entries["mr:0410-beda-gavelli"]["edition_notes"][r.EDITION_EN])
        self.assertNotIn("mr:0410-beda-gavelli", r.ENTRY_NOTES)
        self.assertIn(r.EDITION_IT, entries["mr:0712-proclus-et-hilarion"]["edition_notes"])
        # current IDs keep theirs in EDITION_NOTES (or the asterisk notes), so a rebuild keeps them
        for mr_id, e in entries.items():
            if not e.get("deprecated"):
                self.assertEqual(e.get("edition_notes", {}), r.edition_notes(e), mr_id)

    def test_newgate_mistranslated_newport(self):
        # The London Carthusians starved in Newgate (Neoportus); the CEI Italian has "Newport".
        root = Path(__file__).resolve().parent.parent
        entries = {e["id"]: e for e in json.load(open(root / "data" / "martyrology_ids.json"))["entries"]}
        for mr_id in ("mr:0609-robertus-salt", "mr:0920-thomas-johnson"):
            self.assertIn("Newgate", entries[mr_id]["edition_notes"][r.EDITION_IT], mr_id)
        self.assertIn("nonus", entries["mr:0920-thomas-johnson"]["edition_notes"][r.EDITION_EN])

    def test_markdown_names_the_edition(self):
        md = (Path(__file__).resolve().parent.parent / "registry" / "01-january.md").read_text(encoding="utf-8")
        row = next(line for line in md.splitlines() if "mr:0127-angela-merici" in line)
        self.assertIn("1914 English: ", row)
