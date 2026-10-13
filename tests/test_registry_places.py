import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import registry_places as rp  # noqa: E402

GAZ = {
    "Fictópoli": {"wikidata": "Q1", "label": "Fictopolis", "country": "FR", "status": "auto"},
    "Altrópoli": {"wikidata": "Q2", "label": "Altropolis", "country": "DE", "status": "reviewed",
                  "text_says": [{"country": "AT", "it": "A Altropoli, nell’odierna Austria"}]},
    "Hierosólymæ": {"wikidata": "Q1218", "label": "Jerusalem", "country": "PS", "status": "reviewed"},
    "Nullópoli": {"wikidata": None, "status": "unresolved", "note": "n"},
}


def entry(mr_id, country, *places, **extra):
    e = {"id": mr_id, "month": 1, "day": 1, "entry": 1, "asterisk": False, "country": country}
    if places:
        e["places"] = [dict(p) for p in places]
    return e | extra


def lead(la, it=None, role="death"):
    p = {"role": role, "la": la, "source": "lead"}
    return p | ({"it": it} if it else {})


class ApplyTest(unittest.TestCase):
    def test_resolved_lead_sets_country_and_fields(self):
        out = rp.apply([entry("mr:0101-a", "IT", lead("Fictópoli", "A Fictopoli"))], GAZ, {})
        self.assertEqual(out[0]["country"], "FR")
        self.assertEqual(out[0]["places"][0], {"role": "death", "la": "Fictópoli", "it": "A Fictopoli",
                                               "source": "lead", "wikidata": "Q1", "label": "Fictopolis",
                                               "country": "FR"})

    def test_text_says_filtered_by_it(self):
        out = rp.apply([entry("mr:0101-a", "DE", lead("Altrópoli", "A Altropoli, nell’odierna Austria")),
                        entry("mr:0102-b", "DE", lead("Altrópoli", "Ad Altropoli"))], GAZ, {})
        self.assertEqual(out[0]["places"][0]["text_says"], [{"country": "AT", "it": "A Altropoli, nell’odierna Austria"}])
        self.assertNotIn("text_says", out[1]["places"][0])

    def test_queued_lead_falls_back_to_curated_and_gets_no_fields(self):
        out = rp.apply([entry("mr:0101-a", "IT", lead("Ignótia", "A Ignozia"))], GAZ, {"mr:0101-a": "ES"})
        self.assertEqual(out[0]["country"], "ES")
        self.assertEqual(out[0]["places"][0], lead("Ignótia", "A Ignozia"))

    def test_unresolved_place_gets_no_fields(self):
        out = rp.apply([entry("mr:0101-a", "IT", lead("Nullópoli"))], GAZ, {"mr:0101-a": "IT"})
        self.assertEqual(out[0]["places"][0], lead("Nullópoli"))

    def test_no_lead_uses_curated_value_note_and_null(self):
        curated_place = {"role": "cult", "la": "Fictópoli", "source": "curated"}
        out = rp.apply([entry("mr:0101-a", "IT", curated_place), entry("mr:0102-b", None),
                        entry("mr:0103-c", "IT")],
                       GAZ, {"mr:0101-a": "IT", "mr:0102-b": None, "mr:0103-c": {"country": "DE", "note": "died at Köln"}})
        self.assertEqual([e["country"] for e in out], ["IT", None, "DE"])
        self.assertEqual(out[0]["places"][0]["wikidata"], "Q1")  # curated (body) places get fields too

    def test_holy_land_convention_on_both_paths(self):
        gaz = GAZ | {"Lyddæ": {"wikidata": "Q207540", "label": "Lod", "country": "IL", "status": "reviewed"}}
        out = rp.apply([entry("mr:0101-a", "IL", lead("Lyddæ")), entry("mr:0102-b", "IL")], gaz, {"mr:0102-b": "IL"})
        self.assertEqual([e["country"] for e in out], ["PS", "PS"])
        self.assertEqual(out[0]["places"][0]["country"], "PS")

    def test_deprecated_untouched(self):
        dep = entry("mr:0101-z", "IL", deprecated=True, attested_in="x")
        out = rp.apply([dep], GAZ, {})
        self.assertEqual(out, [dep])

    def test_idempotent(self):
        entries = [entry("mr:0101-a", "IT", lead("Altrópoli", "A Altropoli, nell’odierna Austria"))]
        once = rp.apply(entries, GAZ, {})
        self.assertEqual(rp.apply(once, GAZ, {}), once)

    def test_key_order_of_place_items(self):
        out = rp.apply([entry("mr:0101-a", "IT", lead("Altrópoli", "A Altropoli, nell’odierna Austria"))], GAZ, {})
        self.assertEqual(list(out[0]["places"][0]),
                         ["role", "la", "source", "it", "wikidata", "label", "country", "text_says"])

    def test_input_not_mutated(self):
        entries = [entry("mr:0101-a", "IT", lead("Fictópoli"))]
        rp.apply(entries, GAZ, {})
        self.assertEqual(entries[0]["country"], "IT")
        self.assertNotIn("wikidata", entries[0]["places"][0])


class ValidateTest(unittest.TestCase):
    def errors(self, entries, curated):
        return "\n".join(rp.validate(entries, GAZ, curated))

    def test_resolved_lead_in_curated_file(self):
        self.assertRegex(self.errors([entry("mr:0101-a", "FR", lead("Fictópoli"))], {"mr:0101-a": "FR"}),
                         r"mr:0101-a: .*resolved.*remove it from data/countries_curated\.json")

    def test_missing_curated_value(self):
        self.assertRegex(self.errors([entry("mr:0101-a", "IT")], {}),
                         r"mr:0101-a: .*add .*data/countries_curated\.json")

    def test_unknown_and_deprecated_ids(self):
        dep = entry("mr:0101-z", "IT", deprecated=True)
        msg = self.errors([dep], {"mr:0101-z": "IT", "mr:0909-nemo": "IT"})
        self.assertIn("mr:0101-z: in data/countries_curated.json but deprecated", msg)
        self.assertIn("mr:0909-nemo: in data/countries_curated.json but unknown", msg)

    def test_bad_values(self):
        msg = self.errors([entry("mr:0101-a", None), entry("mr:0102-b", None), entry("mr:0103-c", None)],
                          {"mr:0101-a": "XX", "mr:0102-b": {"country": "IT", "nota": "x"}, "mr:0103-c": 7})
        self.assertIn("mr:0101-a: 'XX' is not an ISO 3166-1 alpha-2 code", msg)
        self.assertIn("mr:0102-b: unexpected keys", msg)
        self.assertIn("mr:0103-c: a value is a code, null or {country, note}", msg)

    def test_apply_raises_on_errors(self):
        with self.assertRaisesRegex(ValueError, "mr:0101-a"):
            rp.apply([entry("mr:0101-a", "IT")], GAZ, {})


if __name__ == "__main__":
    unittest.main()
