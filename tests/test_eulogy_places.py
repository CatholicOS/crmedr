import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import eulogy_places as ep  # noqa: E402


def doc(*rows, mrid="mr:0101-x"):
    return {"places": {mrid: [{"role": r, "la": la, "source": "t"} for r, la in rows]}}


def gaz(**entries):
    return {"places": {k: v for k, v in entries.items()}}


class EulogyPlaces(unittest.TestCase):
    def test_resolved_in_order(self):
        g = gaz(Roma={"wikidata": "Q220", "label": "Rome", "status": "auto"},
                Antiochia={"wikidata": "Q490", "label": "Antioch", "status": "auto"})
        out = ep.eulogy_places(doc(("death", "Antiochia"), ("burial", "Roma")), g)
        self.assertEqual(out, {"mr:0101-x": [
            {"role": "death", "la": "Antiochia", "qid": "Q490", "label": "Antioch"},
            {"role": "burial", "la": "Roma", "qid": "Q220", "label": "Rome"}]})

    def test_scoped_and_unresolved(self):
        g = gaz(**{"In ecclesia": {"wikidata": "Q1", "label": "bare"},
                   "In ecclesia@mr:0101-x": {"wikidata": "Q2", "label": "scoped"},
                   "Nusquam": {"wikidata": None, "label": "?"}})
        out = ep.eulogy_places(doc(("death", "In ecclesia"), ("burial", "Nusquam"), ("work", "Ignota")), g)
        self.assertEqual(out["mr:0101-x"], [{"role": "death", "la": "In ecclesia", "qid": "Q2", "label": "scoped"}])

    def test_one_per_role_and_item(self):
        g = gaz(Roma={"wikidata": "Q220", "label": "Rome"}, Urbs={"wikidata": "Q220", "label": "Rome"})
        out = ep.eulogy_places(doc(("death", "Roma"), ("death", "Urbs"), ("death", "Roma"), ("burial", "Roma")), g)
        self.assertEqual([(p["role"], p["qid"]) for p in out["mr:0101-x"]], [("death", "Q220"), ("burial", "Q220")])

    def test_sites_are_not_the_item(self):
        g = gaz(Roma={"wikidata": "Q220", "label": "Rome", "sites": [{"wikidata": "Q9", "label": "Site"}]})
        out = ep.eulogy_places(doc(("death", "Roma")), g)
        self.assertEqual([p["qid"] for p in out["mr:0101-x"]], ["Q220"])


if __name__ == "__main__":
    unittest.main()
