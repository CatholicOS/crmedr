#!/usr/bin/env python3
"""The places a eulogy prints, as Wikidata items (evidence for who its subject is).

data/places.json lists, per eulogy, the Latin phrases of its places with their role (death,
burial, ...); data/gazetteer.json resolves each phrase to an item. Only the entry's own
`wikidata` counts: the `sites` of a possible-sites marker are not the eulogy's place.
"""
import json
from pathlib import Path

from gazetteer_text import lookup


def eulogy_places(places_doc, gazetteer):
    """{mrid: [{"role", "la", "qid", "label"}]} in places_doc order, one per (role, item).

    `places_doc` and `gazetteer` are the whole documents ({"places": ...}). A phrase with no
    gazetteer entry, or an entry with no `wikidata`, is left out."""
    gaz = gazetteer["places"]
    out = {}
    for mrid, rows in places_doc["places"].items():
        seen, found = set(), []
        for row in rows:
            entry = lookup(gaz, row["la"], mrid)
            qid = entry.get("wikidata") if entry else None
            if not qid or (row["role"], qid) in seen:
                continue
            seen.add((row["role"], qid))
            found.append({"role": row["role"], "la": row["la"], "qid": qid, "label": entry.get("label")})
        out[mrid] = found
    return out


def load(repo_root):
    """eulogy_places of data/places.json and data/gazetteer.json under `repo_root`."""
    read = lambda name: json.loads(Path(repo_root).joinpath("data", name).read_text(encoding="utf-8"))  # noqa: E731
    return eulogy_places(read("places.json"), read("gazetteer.json"))
