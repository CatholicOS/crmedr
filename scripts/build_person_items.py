#!/usr/bin/env python3
"""Identify the persons of data/persons.json with Wikidata items.

A person is `auto` only when exactly one candidate passes every rule of the
evidence bar; every other goes to the review change-set (crmedr-changeset/v1,
op `resolve_person`) for martyrology-frontend and comes back through `apply`
as `reviewed` or `unresolved`. Decisions are per eulogy and name.
See docs/superpowers/specs/2026-10-08-persons-design.md.

  data/person_items.json          {persons: {id: {name: {wikidata, status, note?}}}}
  data/person_items_review.json   the review change-set
  docs/person-items-report.md     progress

Usage:
  python3 build_person_items.py propose [repo_root]              (network)
  python3 build_person_items.py verify-suggestions [repo_root]   (network)
  python3 build_person_items.py expand <records.json> [repo_root]  (network)
  python3 build_person_items.py apply <exported.json> [repo_root]
  python3 build_person_items.py export <MM> <out.json> [repo_root]
  python3 build_person_items.py check [repo_root]

export writes the review ops of one month's eulogies as a change-set of their own, for
suggest_subjects.py; like every change-set Jev's suggestions go on, outside any git work tree.

propose, verify-suggestions and expand also mark, on each open card, the eulogy's places
(scripts/eulogy_places.py) and the candidates whose P19/P20/P119/P937 agree with them: shown
to the curator and to Jev, never counted in the evidence bar or the candidate order.

Standard library only. Reads no private sources.
"""

import datetime
import json
import re
import sys
from pathlib import Path

import eulogy_places
from body_places import _in_a_repository
from persons_text import name_key, person_key
from subject_records import person_record
from wikidata import SAINT_STATUSES, Wikidata, WikidataError

EDITION = "martyrologium_romanum_2004"
SCHEMA = "crmedr-changeset/v1"
STATUSES = ["auto", "reviewed", "unresolved"]
QID = re.compile(r"^Q[1-9]\d*$")
CONFIDENCES = {"high", "medium", "low"}
MAX_CANDIDATES = 10
MAX_EXPANDED = 15  # an expanded op also holds the candidates of the three extra routes
# The routes that find a saint by the eulogy's own facts: at the cap, their candidates take the
# places of the last plain-search ones.
SAINT_ROUTES = ("sparql", "feast", "place", "name", "surname", "companion:P361")
# The routes whose candidates make room at the cap: the saint routes and a curator's title.
ROOM_ROUTES = SAINT_ROUTES + ("curated",)
# Celebrations whose title item a curator confirmed (eulogy -> QID); nothing is added here unconfirmed.
CURATED_TITLES = {"mr:0101-maria-dei-genetrix": "Q208542", "mr:0125-conversio-pauli-apostoli": "Q9200",
                  "mr:0211-maria-de-lourdes": "Q21532387"}
# Words of a label that are not part of the name ("Saint Basil", "San Basilio").
TITLE_WORDS = {"saint", "st", "san", "santo", "santa", "santi", "sante", "sant", "beato", "beata", "beati",
               "blessed", "the", "of", "sanctus", "sancta", "beatus",
               # Latin titles a card's name carries (Anna Prophetissa, Paulus Apostolus)
               "propheta", "prophetissa", "apostolus"}
# Latin first names' vernacular forms, the English first: searched for in this order, and
# matched as the same name when they share no stem with the Latin (Ioannes, John).
NAME_EQUIVALENTS = {
    "renatus": ("rene", "renato"),
    "antonius": ("anthony", "antoine"),
    "ioannes": ("john", "giovanni", "juan", "jean", "joao", "johannes", "jan"),
    "ioanna": ("joan", "giovanna", "juana", "jeanne", "joanna", "johanna", "jane"),
    "iacobus": ("james", "giacomo", "jacques", "jaime", "diego", "jacob", "jakob"),
    "gulielmus": ("william", "guglielmo", "guillaume", "guillermo", "wilhelm"),
    "ludovicus": ("louis", "luigi", "luis", "ludwig", "lewis"),
    "henricus": ("henry", "enrico", "henri", "enrique", "heinrich"),
    "carolus": ("charles", "carlo", "carlos", "karl"),
    "aegidius": ("giles", "egidio", "gilles"),
    "iosephus": ("joseph", "giuseppe", "jose", "josef"),
    "petrus": ("peter", "pietro", "pedro", "pierre", "pieter", "piotr"),
    "andreas": ("andrew", "andrea", "andres", "andre", "andrzej"),
    "eduardus": ("edward", "edoardo", "eduardo", "edouard"),
    "radulphus": ("ralph", "rodolfo", "raoul"),
    "humphredus": ("humphrey",),
    "nicolaus": ("nicholas", "nicola", "nicolas", "mikolaj"),
    "georgius": ("george", "giorgio", "jorge", "georges"),
    "stephanus": ("stephen", "stefano", "esteban", "etienne"),
    "hieronymus": ("jerome", "girolamo", "jeronimo"),
    "matthaeus": ("matthew", "matteo", "mateo", "matthieu"),
    "christophorus": ("christopher", "cristoforo", "cristobal", "christophe"),
    "ladislaus": ("wladyslaw", "ladislao"),
    "miecislaus": ("mieczyslaw",),
    "ceslaus": ("czeslaw",),
    "eligius": ("eloy", "eligio", "eloi"),
    "consolata": ("consuelo",),
    "elisabeth": ("elizabeth", "elisabetta", "isabel"),
    "iarognievus": ("jarogniew",),
}
# The same table in name_key form ("John" -> "iohn", "Giovanni" -> "giouanni"), for comparing.
_EQUIVALENTS = {name_key(k): {name_key(v) for v in vs} for k, vs in NAME_EQUIVALENTS.items()}
# The forms the 2004 English and Italian subjects give a Latin first name, with the times seen
# (scripts/name_forms.py), by the Latin name's key.
NAME_FORMS = json.loads((Path(__file__).resolve().parent.parent / "data" / "name_forms.json")
                        .read_text(encoding="utf-8"))["forms"]


def vernacular_forms(first):
    """A Latin first name's (name_key) vernacular forms: NAME_EQUIVALENTS's, the English first,
    then the English and the Italian of NAME_FORMS, the commonest first."""
    forms = list(next((vs for k, vs in NAME_EQUIVALENTS.items() if name_key(k) == first), ()))
    for lang in ("en", "it"):
        forms += [form for form, _ in NAME_FORMS.get(first, {}).get(lang, [])]
    out = {}
    for form in forms:
        out.setdefault(name_key(form), form)
    return list(out.values())


def _equivalent(latin, other):
    """`other` (name_key) is a vernacular form of the Latin name (name_key): NAME_EQUIVALENTS's, or
    one NAME_FORMS saw twice or more (a form seen once may be a religious name)."""
    return other in _EQUIVALENTS.get(latin, ()) or any(
        n >= 2 and name_key(form) == other for lang in ("en", "it") for form, n in NAME_FORMS.get(latin, {}).get(lang, []))
# Persons that pass the evidence bar but are known to be wrong: always reviewed.
FORCE_REVIEW = {
    # The only "Valentinus" candidate passing is the Valentine of 14 February; the 7 January
    # eulogy is another (a commemoratio, so no death date could tell them apart).
    "mr:0107-valentinus-raetiae|Valentinus": "the item is the Valentine of 14 February, not this eulogy's",
    # One-word names of undated eulogies that matched a famous namesake (CatholicOS/crmedr#79 review);
    # Simon Peter's alias "Simeon" matched both Simeons.
    "mr:0203-simeon-et-anna-prophetissa|Simeon": "the eulogy's Simeon is the prophet of the Presentation, not Saint Peter",
    "mr:0427-simeon|Simeon": "the eulogy's Simeon is the bishop of Jerusalem, not Saint Peter",
    "mr:0206-paulus-miki-et-socii|Thomas": "a Japanese martyr, not Thomas the Apostle",
    "mr:0206-paulus-miki-et-socii|Bonaventura": "a Japanese martyr, not Saint Bonaventure",
    "mr:0212-martyres-abitinenses|Maria": "an Abitinian martyr, not the Blessed Virgin",
    # Kept from Q345 by the Marian celebrations' "Maria" until they were named by the celebration.
    "mr:0729-lazarus-et-maria|Maria": "Mary of Bethany, the sister of Lazarus, not the Blessed Virgin",
    "mr:1003-faustus-et-socii|Petrus": "a companion of Faustus, not Saint Peter",
    "mr:1003-faustus-et-socii|Caius": "a companion of Faustus, not Pope Caius",
}
SEARCH_LANGUAGES = ("la", "it", "en")
# After this many persons in a row whose lookups failed (Wikidata lagged or down), a
# run stops asking: the rest are "not processed", for the next run, instead of each
# waiting out its own retries.
MAX_CONSECUTIVE_FAILURES = 5


def _tokens(s):
    return [t for t in name_key(s).split() if len(t) > 1 and t not in TITLE_WORDS]


# A Latin ending, and the endings its vernacular forms may have instead (Paulus: Paul,
# Paolo; Augustinus: Augustine; Basilius: Basil; Caecilia: Cecilia). A name without
# one of these endings matches only itself: Leo is not Leontius, Victor not Victoria.
LATIN_ENDINGS = [("ius", {"", "io", "ius", "e"}), ("us", {"", "o", "e", "us"}), ("ia", {"ia", "ie", "a", "e", "y"}),
                 ("a", {"a", "e", ""}), ("es", {"es", "", "e", "i"}), ("is", {"is", "", "e"}), ("um", {"um", ""})]


def latin_stem(name):
    """(stem, the vernacular endings it may take) of a name with a Latin ending (LATIN_ENDINGS,
    the first that fits, leaving a stem of two letters or more): Eugendus -> eugend; None
    without one."""
    for ending, vernacular in LATIN_ENDINGS:
        if name.endswith(ending) and len(name) - len(ending) >= 2:
            return name[: -len(ending)], vernacular
    return None


def _same(latin, other):
    """The same name: equal, equivalents, or one stem with a Latin and a vernacular ending."""
    if _equivalent(latin, other):
        return True
    latin, other = latin.replace("ae", "e").replace("oe", "e"), other.replace("ae", "e").replace("oe", "e")
    if latin == other:
        return True
    stem = latin_stem(latin)
    if not stem:
        return False
    # English -ius as -y (Hilarius: Hilary, Gregorius: Gregory), on stems of four letters or more:
    # Marius is not Mary, Lucius not Lucy.
    if latin.endswith("ius") and len(stem[0]) >= 4 and other == stem[0] + "y":
        return True
    return any(other == stem[0] + v for v in stem[1])


# Name particles, left out when names are compared word by word (Latin; vernacular).
LATIN_PARTICLES = {"de", "a", "ab", "la", "y"}
ITEM_PARTICLES = {"de", "di", "da", "la", "y", "van", "von"}


def name_matches(name, candidate_names):
    """The Latin name and one of the item's names have the same words, pair by pair
    (see _same): Paulus Miki = Paul Miki."""
    latin = [t for t in _tokens(name) if t not in LATIN_PARTICLES]
    for other in candidate_names:
        words = [t for t in _tokens(other) if t not in ITEM_PARTICLES]
        if latin and len(words) == len(latin) and all(_same(a, b) for a, b in zip(latin, words)):
            return True
    return False


def _saint_marked(c):
    """A saint's or a blessed's item: a canonization status, or another statement only their items
    carry (wikidata.SAINT_SIGNALS: a feast day, a Santi e Beati or Heiligenlexikon ID…)."""
    return bool(SAINT_STATUSES & set(c.get("statuses", [])) or c.get("signals"))


def evidence(person, c):
    ev = []
    if c.get("human"):
        ev.append("human")
    if _saint_marked(c):
        ev.append("status")
    names = c.get("names", []) + [c.get("label", "")]
    if any(name_matches(nm, names) for nm in [person["name"], *person.get("also", [])]):
        ev.append("name")  # under any of the person's names
    if person["typology"] == "dies_natalis" and _death_agrees(c.get("died") or "", person["day"]):
        ev.append("death")
    if c.get("source") == GROUP_SOURCE:
        ev.append("group")  # a member of a matched companion's group (gather)
    return ev


def _death_agrees(died, day):
    """A death date on the eulogy's day (MM-DD), or, when Wikidata knows only the month, in its
    month (the user's ruling, 2026-10-09). A year alone can be checked against nothing, since a
    eulogy has no year, and does not count; nor does no date."""
    if len(died) == 10:
        return died[5:] == day
    if len(died) == 7:
        return died[5:] == day[:2]
    return False


def _required(person):
    return ["human", "status", "name"] + (["death"] if person["typology"] == "dies_natalis" else [])


def evaluate(person, candidates):
    scored = []
    for c in candidates:
        c = dict(c, evidence=evidence(person, c))
        scored.append(c)
    need = _required(person)
    # A matched companion's group stands for the death day (the user's ruling, 2026-10-28: the
    # Vietnamese martyrs share 24 November, each died on his own day).
    passing = [c for c in scored if all(r in c["evidence"] or (r == "death" and "group" in c["evidence"])
                                        for r in need)]
    scored.sort(key=lambda c: (-len(c["evidence"]), c["wikidata"]))
    failed = []
    if not passing:
        best = scored[0] if scored else None
        failed = ([f"{r}: the best candidate ({best['wikidata']}) fails it" for r in need if r not in best["evidence"]]
                  if best else ["no candidate found"])
    elif len(passing) > 1:
        failed = [f"{len(passing)} candidates pass every rule: " + ", ".join(c["wikidata"] for c in passing)]
    elif _listed_one_word(person) and not _died_on(passing[0], person["day"]) and "group" not in passing[0]["evidence"]:
        # An obscure companion named by one word: the one candidate is usually a famous namesake
        # (Pope Cornelius for Cornelius of the martyrs of Lyons), unless it died on this very day.
        failed = [LISTED_ONE_WORD.format(qid=passing[0]["wikidata"])]
        passing = []
    return {"auto": passing[0] if len(passing) == 1 else None, "failed": failed,
            "candidates": scored[:MAX_CANDIDATES]}


def search_terms(name):
    """The name, and for a first name with vernacular forms (vernacular_forms) its first four (the
    English first), or for one in -us its stem."""
    words = name.split()
    terms = [name]
    first = name_key(words[0]) if words else ""
    equivalents = vernacular_forms(first)
    for vern in equivalents[:4]:
        terms.append(" ".join([vern[:1].upper() + vern[1:]] + words[1:]))
    # Richardus Whiting as Richard Whiting: a first name in -us, its stem the vernacular.
    if not equivalents and len(words) > 1 and words[0].endswith("us") and len(words[0]) > 5:
        terms.append(" ".join([words[0][:-2]] + words[1:]))
    return terms


GROUP_SOURCE = "companion:P361"


def gather(person, client, items=None):
    """The search's candidates for each of the person's names, then the members of the groups of
    the eulogy's matched companions (`items`: the decisions) whose names fit the person: a member
    found by the search too is marked as one."""
    seen = {}
    # Each of the person's names: Kinga is also sought as Cunegundis.
    terms = dict.fromkeys(t for nm in [person["name"], *person.get("also", [])] for t in search_terms(nm))
    for term in terms:
        for c in client.person_candidates(term, SEARCH_LANGUAGES):
            seen.setdefault(c["wikidata"], c)
    decided = (items or {}).get(person["eulogy"], {})
    companions = [e["wikidata"] for e in decided.values() if e.get("wikidata") and e["status"] in ("auto", "reviewed")]
    for qid in dict.fromkeys(companions):
        for c in client.relatives(qid):
            if c.get("source") == GROUP_SOURCE and _fits_group_member(person, c):
                seen[c["wikidata"]] = dict(seen.get(c["wikidata"], c), source=GROUP_SOURCE)
    return list(seen.values())


def person_index(persons_doc, entries, typology, subjects):
    by_id = {e["id"]: e for e in entries}
    out = {}
    for mrid, persons in persons_doc["editions"][EDITION].items():
        e = by_id[mrid]
        for p in persons:
            out[f"{mrid}|{person_key(p)}"] = {
                "eulogy": mrid, "name": p["name"], **({"n": p["n"]} if "n" in p else {}),
                **({"also": p["also"]} if "also" in p else {}), "where": p["where"],
                "day": f"{e['month']:02d}-{e['day']:02d}", "typology": typology.get(mrid),
                "subject": subjects.get(mrid, ""),
                # Each other name once: a repeated name is one companion to search with.
                "companions": list(dict.fromkeys(q["name"] for q in persons if q["name"] != p["name"])),
            }
    return out


def new_changeset(operations):
    return {"schema": SCHEMA, "generated_by": "scripts/build_person_items.py",
            "generated_at": datetime.date.today().isoformat(),
            "base": {"edition": EDITION, "registry": "data/persons.json"}, "operations": operations}


def make_op(key, person, result, old):
    candidates = list(result["candidates"])
    # The candidates `expand` added (companions' kin, the death day, titles) are not found by the
    # name search again: they are kept after the search's own, with their evidence recomputed.
    # A title item the search returns too keeps its provenance, which apply reads (_appliable).
    at = {c["wikidata"]: i for i, c in enumerate(candidates)}
    for c in (old or {}).get("candidates", []):
        if c.get("source") in (None, "search"):
            continue
        if c["wikidata"] not in at:
            at[c["wikidata"]] = len(candidates)
            candidates.append(dict(c, evidence=evidence(person, c)))
        elif c["source"] in TITLE_SOURCES:
            candidates[at[c["wikidata"]]] = dict(candidates[at[c["wikidata"]]], source=c["source"])
    op = {"op": "resolve_person", "id": key, **{k: person[k] for k in
          ("eulogy", "day", "typology", "subject", "name", "n", "also", "where", "companions") if k in person},
          "failed": result["failed"], "candidates": candidates}
    for k in ("suggested", "reasoning", "confidence"):
        if old and k in old:
            op[k] = old[k]
    op["decision"], op["edited"] = None, None
    return op


def _decided(items, person):
    return person_key(person) in items.get(person["eulogy"], {})


def _one_word(name):
    return len(name.split()) == 1


LISTED_ONE_WORD = ("a one-word name in a footnote list: the one candidate ({qid}) did not die on this "
                   "eulogy's day, so it may be a namesake")


def _listed_one_word(person):
    return _one_word(person["name"]) and person.get("where", "text") != "text"


def _died_on(candidate, day):
    died = candidate.get("died") or ""
    return len(died) == 10 and died[5:] == day


def _shared_items(items, index, pending):
    """The items matched in more than one eulogy, by any decided or pending match, whatever the
    name. A one-word name matched to such an item is usually a famous namesake (Augustine of Hippo
    for Augustine of Canterbury): the user's ruling after the CatholicOS/crmedr#79 review is that
    none of those one-word matches is automatic."""
    eulogies = {}
    for mrid, persons in items.items():
        for e in persons.values():
            if e.get("wikidata"):
                eulogies.setdefault(e["wikidata"], set()).add(mrid)
    for key, result in pending.items():
        eulogies.setdefault(result["auto"]["wikidata"], set()).add(index[key]["eulogy"])
    return {qid for qid, ms in eulogies.items() if len(ms) > 1}


SHARED = "the same item ({qid}) is matched in another eulogy, and this name is one word: a namesake?"
SAME_EULOGY = "the same item ({qid}) is matched for another person of this eulogy"


def _holders(items, extra=()):
    """Who holds each item within a eulogy, {(eulogy, QID): {person keys}}: the decisions in
    `items`, plus `extra` (eulogy, person key, QID) triples not written yet."""
    out = {}
    for mrid, persons in items.items():
        for key, e in persons.items():
            if e.get("wikidata"):
                out.setdefault((mrid, e["wikidata"]), set()).add(key)
    for mrid, key, qid in extra:
        out.setdefault((mrid, qid), set()).add(key)
    return out


def propose(items, review, index, client, force_review=FORCE_REVIEW):
    # A queued op whose person is no longer in persons.json (a corrected list) is dropped: it was undecided.
    ops = {op["id"]: op for op in review["operations"] if op["id"] in index}
    not_processed = []
    failures = 0
    pending = {}  # automatic results, written once it is known which items are shared

    def keep(key, person):
        """A queued op not looked up this time takes the person's details (other names, companions)
        and keeps its candidates and reasons."""
        if key in ops:
            old = ops[key]
            ops[key] = make_op(key, person, {"failed": old["failed"], "candidates": old["candidates"]}, old)

    for key in sorted(index):
        person = index[key]
        if _decided(items, person):
            ops.pop(key, None)
            continue
        if failures >= MAX_CONSECUTIVE_FAILURES:
            not_processed.append((key, "skipped: Wikidata unavailable"))
            keep(key, person)
            continue
        try:
            result = evaluate(person, gather(person, client, items))
        except WikidataError as e:
            not_processed.append((key, str(e)))
            failures += 1
            keep(key, person)
            continue
        failures = 0
        if key in force_review:
            result["auto"] = None
            result["failed"].append("forced review: " + force_review[key])
        if result["auto"]:
            pending[key] = result
        else:
            ops[key] = make_op(key, person, result, ops.get(key))
    shared = _shared_items(items, index, pending)
    # propose withdraws its own automatic one-word matches of a shared item; a curator's
    # decision (reviewed, unresolved) it never touches.
    for key, person in index.items():
        e = items.get(person["eulogy"], {}).get(person_key(person))
        if not (e and e["status"] == "auto" and _one_word(person["name"]) and e["wikidata"] in shared):
            continue
        try:
            result = evaluate(person, gather(person, client, items))
        except WikidataError as err:
            not_processed.append((key, str(err)))
            continue
        result["failed"].append(SHARED.format(qid=e["wikidata"]))
        del items[person["eulogy"]][person_key(person)]
        if not items[person["eulogy"]]:
            del items[person["eulogy"]]
        ops[key] = make_op(key, person, result, ops.get(key))
    # Its own automatic one-word matches in a footnote list that the date rule no longer passes
    # (LISTED_ONE_WORD) are withdrawn too; a curator's decision never. A match whose item the
    # search did not return stays: its date was never checked.
    for key, person in index.items():
        e = items.get(person["eulogy"], {}).get(person_key(person))
        if not (e and e["status"] == "auto" and _listed_one_word(person)):
            continue
        try:
            candidates = gather(person, client, items)
        except WikidataError as err:
            not_processed.append((key, str(err)))
            continue
        if e["wikidata"] not in {c["wikidata"] for c in candidates}:
            continue
        result = evaluate(person, candidates)
        if result["auto"] and result["auto"]["wikidata"] == e["wikidata"]:
            continue
        del items[person["eulogy"]][person_key(person)]
        if not items[person["eulogy"]]:
            del items[person["eulogy"]]
        ops[key] = make_op(key, person, result, ops.get(key))
    held = _holders(items, [(index[k]["eulogy"], person_key(index[k]), r["auto"]["wikidata"])
                            for k, r in pending.items()])
    for key, result in pending.items():
        person, qid = index[key], result["auto"]["wikidata"]
        if len(held[(person["eulogy"], qid)]) > 1:
            result["failed"].append(SAME_EULOGY.format(qid=qid))
            ops[key] = make_op(key, person, result, ops.get(key))
        elif _one_word(person["name"]) and qid in shared:
            result["failed"].append(SHARED.format(qid=qid))
            ops[key] = make_op(key, person, result, ops.get(key))
        else:
            items.setdefault(person["eulogy"], {})[person_key(person)] = {"wikidata": qid, "status": "auto"}
            ops.pop(key, None)
    review["operations"] = sorted(ops.values(), key=lambda op: op["id"])
    review["generated_at"] = datetime.date.today().isoformat()
    return not_processed


# The roles of a eulogy's places whose saints are looked up.
PLACE_ROUTE_ROLES = ("death", "burial", "translation")
# The roles the full-text search leaves out: a place merely named or passed through tells no one apart.
FULLTEXT_SKIP_ROLES = ("mention", "journey", "education")


# The titles a vernacular subject opens with ("Saint Gudula", "Sant’Angela da Foligno").
SUBJECT_TITLES = re.compile(r"^(?:(?:Saint|Blessed|San|Santa|Santo|Beato|Beata)\s+|Sant[’']\s*)", re.I)
# A subject naming several persons ("Saints Paul Miki and companions", "Santi Lucio e Pietro").
SEVERAL = re.compile(r"^(?:Saints|Santi|Sante|Blessed\s+\w+\s+and|Beati|Beate)\b|\s(?:and|e|ed)\s|,", re.I)


def subject_name(subject):
    """A vernacular subject's name without its title (Saint Gudula: Gudula), or None for one that
    names several persons or none."""
    if not subject or SEVERAL.search(subject):
        return None
    return SUBJECT_TITLES.sub("", subject.strip(), count=1) or None


def fulltext_names(op):
    """The names the full-text search tries: each of the person's names with its vernacular
    equivalents (search_terms), then the first name's vernacular forms from its Latin ending
    (Rogerius: Roger, Rogere, Rogerio), with ae and oe read as e too (Aemiliana: Emiliana)."""
    names = [t for nm in [op["name"], *op.get("also", [])] for t in search_terms(nm)]
    first = op["name"].split()[0].lower() if op["name"].split() else ""
    for form in dict.fromkeys([first, first.replace("ae", "e").replace("oe", "e")]):
        stem = latin_stem(form)
        if stem:
            names += [(stem[0] + ending).capitalize() for ending in sorted(stem[1])]
    return [n for n in dict.fromkeys(names) if len(n) >= 3]


def _given_names(op):
    """The first word of each of the person's names, its stem without the Latin ending (Eugend,
    for Eugende and Eugendo; with ae and oe read as e too), and the vernacular equivalents of a
    Latin one."""
    given = {}
    for nm in [op["name"], *op.get("also", [])]:
        first = nm.split()[0] if nm.split() else ""
        if first:
            given[first] = None
            for form in (first.lower(), first.lower().replace("ae", "e").replace("oe", "e")):
                stem = latin_stem(form)
                if stem:
                    given[stem[0]] = None
            given.update(dict.fromkeys(vernacular_forms(name_key(first))))
    return list(given)


def _name_fits(latin, other):
    """A Latin name and an item's name: the first words are the same name (_same), and the other
    words of the Latin name appear among the item's (Renatus Lego = René Lego, not René Dupont);
    name particles are left out on both sides."""
    latin = [t for t in _tokens(latin) if t not in LATIN_PARTICLES]
    words = [t for t in _tokens(other) if t not in ITEM_PARTICLES]
    if not latin or not words or not _same(latin[0], words[0]):
        return False
    return all(any(_same(w, o) for o in words[1:]) for w in latin[1:])


def _named(op):
    """A test of a list of names: one of them fits one of the op's names (_name_fits)."""
    return lambda names: any(_name_fits(nm, other) for nm in [op["name"], *op.get("also", [])] for other in names)


def _companion_items(op, items, ops=None):
    """The items of the op's companions: the decided ones (auto or reviewed) first, then the
    preselected candidate of an undecided companion's own card when its evidence is a strong match
    (human, status and death on the eulogy's day). `ops`: the review's ops by id."""
    decided = items.get(op["eulogy"], {})
    found = [e["wikidata"] for e in (decided.get(c) for c in op.get("companions", []))
             if e and e["status"] in ("auto", "reviewed") and e.get("wikidata")]
    for c in op.get("companions", []):
        other = (ops or {}).get(f"{op['eulogy']}|{c}")
        if not other or (decided.get(c) or {}).get("status") in ("auto", "reviewed"):
            continue
        cands = other.get("candidates") or []
        qid = (other.get("suggested") or {}).get("wikidata")
        pick = next((x for x in cands if x["wikidata"] == qid), None) if qid else (cands[0] if cands else None)
        if pick and {"human", "status", "death"} <= set(pick.get("evidence", [])) and pick["wikidata"] not in found:
            found.append(pick["wikidata"])
    return found


def _expansion(op, record, items, client, ops=None, places=(), vernacular=()):
    """New candidates for one op from the extra routes, in the order they are tried. `vernacular`:
    the eulogy's English and Italian subject names (subject_name), searched as the person's own
    names when the eulogy names no companion."""
    if record["kind"] == "celebration":
        found = client.title_candidates(op["subject"])
        qid = CURATED_TITLES.get(op["eulogy"])
        if qid and qid not in {c["wikidata"] for c in found}:
            curated = client.person(qid)
            if curated:
                found.append(dict(curated, source="curated"))
        return found
    found = []
    for qid in _companion_items(op, items, ops):
        companion = client.person(qid)
        if companion and companion.get("human"):
            # kin may bear another name; a group's other members (P361) must fit the person
            found += [c for c in client.relatives(qid)
                      if c.get("source") != "companion:P361" or _fits_group_member(op, c)]
    if op["typology"] == "dies_natalis":
        month, day = (int(x) for x in op["day"].split("-"))
        named = _named(op)
        found += [c for c in client.saints_by_death_day(month, day, _given_names(op), record.get("death_year"), named)
                  if named(c.get("names", []) + [c.get("label", "")])]
    # The day the eulogy commemorates is often the item's feast (P841) when its death is dated to
    # the year only, or not at all.
    month, day = (int(x) for x in op["day"].split("-"))
    named = _named(op)
    found += [c for c in client.saints_by_feast_day(month, day, _given_names(op), named)
              if named(c.get("names", []) + [c.get("label", "")])]
    qids = list(dict.fromkeys(p["qid"] for p in places if p["role"] in PLACE_ROUTE_ROLES and p.get("qid")))
    if qids:
        named = _named(op)
        found += [c for c in client.saints_by_place(qids, _given_names(op), named)
                  if named(c.get("names", []) + [c.get("label", "")])]
    labels = list(dict.fromkeys(p["label"] for p in places if p["role"] not in FULLTEXT_SKIP_ROLES and p.get("label")))
    # A search for one of the person's own names matched it in every language (Kyros of
    # Constantinople, Thillo of Solignac), which the loaded labels cannot show: no name check after
    # it. A first-name form of a longer name ("Maria" for Maria Dominica Mantovani) finds every
    # Maria of the place: its hits must fit the name.
    own_vernacular = [] if op.get("companions") else [v for v in vernacular if v]
    own = {t for nm in [op["name"], *op.get("also", []), *own_vernacular] for t in search_terms(nm)}
    one_word = len(op["name"].split()) == 1
    named, seen = _named(op), {c["wikidata"] for c in found}
    fulltext = fulltext_names(op)
    names = list(dict.fromkeys([*fulltext[:1], *own_vernacular, *fulltext[1:]]))

    def fits(name, c):
        return one_word or name in own or named(c.get("names", []) + [c.get("label", "")])

    if labels:
        for name in names:
            for c in client.saints_by_name_and_place(name, labels):
                if c["wikidata"] not in seen and fits(name, c):
                    seen.add(c["wikidata"])
                    found.append(c)
    if not any(_is_saint(c) for c in [*op["candidates"], *found]):
        # No saint yet (Nathalan's item has no place): a name few saints bear, searched alone.
        for name in names:
            for c in client.saints_by_name(name):
                if c["wikidata"] not in seen and fits(name, c):
                    seen.add(c["wikidata"])
                    found.append(c)
        # Nor by the first name, which the Latin translates (Eduardus Stransham: Edward Stransham):
        # the surname, printed as on Wikidata.
        for term in _surnames(op):
            for c in client.saints_by_surname(term):
                if c["wikidata"] not in seen:
                    seen.add(c["wikidata"])
                    found.append(c)
    return found


def _surnames(op):
    """The surname terms of the person's names: the words that end it, after the first name, the
    shortest first ("David", "Vilar David", "Maria Vilar David"); a one-word term of four letters
    or more and no particle; none for one word."""
    terms = []
    for nm in [op["name"], *op.get("also", [])]:
        words = nm.split()
        for i in range(len(words) - 1, 0, -1):
            if i < len(words) - 1 or (len(words[i]) >= 4 and words[i].lower() not in LATIN_PARTICLES):
                terms.append(" ".join(words[i:]))
    return list(dict.fromkeys(terms))


def _fits_group_member(op, c):
    """A companion's group member (P361) fits the person: one of its names fits one of the
    person's (_named), or it shares one of the person's surnames (a later word of four letters or
    more: Aloysius Versiglia is Louis Versiglia in the labels loaded) that is no given name of the
    eulogy (Anna, in Maria Anna Vaillot, is Anna Hamard's)."""
    names = c.get("names", []) + [c.get("label", "")]
    if _named(op)(names):
        return True
    given = {t[0] for nm in op.get("companions", []) if (t := _tokens(nm))}
    surnames = {t for nm in [op["name"], *op.get("also", [])] for t in _tokens(nm)[1:]
                if len(t) >= 4 and t not in given}
    return bool(surnames & {t for nm in names for t in _tokens(nm)})


def _decided_op(op):
    return op.get("decision") is not None or bool(op.get("prefilled"))


def _drop_unfit_group_members(op):
    """Drop the companions' group members (companion:P361) whose names do not fit the person, as
    an earlier expand added them; on a decided or prefilled card the first candidate (an accept
    without a suggestion means it) and the decided pick stay."""
    pick = (op.get("edited") or {}).get("wikidata")
    first = _decided_op(op)
    op["candidates"] = [c for i, c in enumerate(op["candidates"])
                        if (first and i == 0) or c["wikidata"] == pick or c.get("source") != "companion:P361"
                        or _fits_group_member(op, c)]
    # An accept applies the suggestion first: one naming a dropped candidate goes, with its reasons.
    if (op.get("suggested") or {}).get("wikidata") not in {c["wikidata"] for c in op["candidates"]}:
        for k in ("suggested", "reasoning", "confidence"):
            op.pop(k, None)


def expand(review, items, records, client, places=None, vernacular=None):
    """Add candidates from the companions' kin, the saints of the death day and the titles to each
    op with a record (subject_records.person_record: its own, else the kind of its eulogy's only
    record); `records`: the identity records by eulogy id. Decisions are not touched. Returns
    (op id, error) for each op whose lookups failed, left as it was."""
    not_processed = []
    failures = 0
    by_id = {o["id"]: o for o in review["operations"]}
    for op in review["operations"]:
        record = person_record(records.get(op["eulogy"], []), op["name"], op.get("n"))
        if not record:
            continue
        for c in op["candidates"]:
            c.setdefault("source", "search")
        _drop_unfit_group_members(op)
        if failures >= MAX_CONSECUTIVE_FAILURES:
            not_processed.append((op["id"], "skipped: Wikidata unavailable"))
            continue
        try:
            found = _expansion(op, record, items, client, by_id, (places or {}).get(op["eulogy"], ()),
                               (vernacular or {}).get(op["eulogy"], ()))
        except WikidataError as e:
            not_processed.append((op["id"], str(e)))
            failures += 1
            continue
        failures = 0
        have = {c["wikidata"]: c for c in op["candidates"]}
        added = []
        for c in found:
            if c["wikidata"] not in have:
                have[c["wikidata"]] = c
                added.append(dict(c, evidence=evidence(op, c)))
            elif c.get("source") in TITLE_SOURCES:
                have[c["wikidata"]]["source"] = c["source"]  # a title item the search found too
        added.sort(key=lambda c: (c.get("source") not in ROOM_ROUTES, -len(c["evidence"]), c["wikidata"]))
        _make_room(op, sum(c.get("source") in ROOM_ROUTES for c in added))
        # Existing candidates keep their places: an accept without a suggestion means candidates[0].
        op["candidates"] += added[:max(0, MAX_EXPANDED - len(op["candidates"]))]
    review["generated_at"] = datetime.date.today().isoformat()
    return not_processed


def _make_room(op, wanted):
    """Drop the last plain-search candidates (never the first, nor the decided pick) so that
    `wanted` candidates from ROOM_ROUTES fit under MAX_EXPANDED: Emeritus of Abitinae, found by his
    feast behind 15 namesakes from the search."""
    short = wanted - (MAX_EXPANDED - len(op["candidates"]))
    pick = (op.get("edited") or {}).get("wikidata")
    weak = [i for i, c in enumerate(op["candidates"])
            if i > 0 and c.get("source") == "search" and c["wikidata"] != pick]
    drop = set(weak[len(weak) - short:]) if short > 0 else set()
    op["candidates"] = [c for i, c in enumerate(op["candidates"]) if i not in drop]


def _is_saint(c):
    return bool(c) and c.get("human") and _saint_marked(c)


# The routes whose candidates are items of any kind (a feast, a title: Theotokos), not persons.
TITLE_SOURCES = {"title", "curated"}


def _appliable(c):
    """An item a card may resolve to: a celebration's title item, or a human with a saint status."""
    return bool(c) and (c.get("source") in TITLE_SOURCES or _is_saint(c))


def _resolve(op, client):
    key, decision = op["id"], op.get("decision")
    edited, suggested = op.get("edited") or {}, op.get("suggested") or {}
    if decision == "reject":
        reason = (edited.get("reason") or "").strip()
        if not reason:
            return None, f"{key}: reject needs a reason (edited.reason)"
        return {"wikidata": None, "status": "unresolved", "note": reason}, None
    if decision not in ("accept", "edit"):
        return None, f"{key}: unknown decision {decision!r}"
    candidates = op.get("candidates", [])
    # An edit names its item; only an accept falls back to the suggestion or the top candidate.
    qid = edited.get("wikidata") if decision == "edit" else (
        suggested.get("wikidata") or (candidates[0]["wikidata"] if candidates else None))
    if not qid or not QID.match(qid):
        return None, f"{key}: no item chosen"
    on_op = next((c for c in candidates if c["wikidata"] == qid), None)
    if not _appliable(on_op or client.person(qid)):
        return None, f"{key}: {qid} is not a human with a saint or blessed status"
    return {"wikidata": qid, "status": "reviewed"}, None


def apply_decisions(items, review, exported, index, client):
    if exported.get("schema") != SCHEMA:
        raise ValueError(f"not a {SCHEMA} document")
    decided, errors = {}, []
    for op in exported.get("operations", []):
        if op.get("op") != "resolve_person" or op.get("decision") is None:
            continue
        key = op["id"]
        if key not in index:
            errors.append(f"{key}: not a person of data/persons.json")
            continue
        if _decided(items, index[key]):
            errors.append(f"{key}: already decided")
            continue
        entry, error = _resolve(op, client)
        if error:
            errors.append(error)
        else:
            decided[key] = entry
    held = _holders(items, [(index[k]["eulogy"], person_key(index[k]), e["wikidata"])
                            for k, e in decided.items() if e["wikidata"]])
    for (mrid, qid), keys in sorted(held.items()):
        if len(keys) > 1:
            errors.append(f"{mrid}: {qid} would be the item of more than one person ({', '.join(sorted(keys))})")
    if errors:
        raise ValueError("no decision applied:\n" + "\n".join(errors))
    for key, entry in decided.items():
        items.setdefault(index[key]["eulogy"], {})[person_key(index[key])] = entry
    review["operations"] = [op for op in review["operations"] if op["id"] not in decided]
    return len(decided)


def verify_suggestions(review, client):
    errors = []
    for op in review["operations"]:
        s = op.get("suggested")
        if not s:
            continue
        if op.get("confidence") not in CONFIDENCES:
            errors.append(f"{op['id']}: confidence {op.get('confidence')!r} not in {sorted(CONFIDENCES)}")
        qid = s.get("wikidata")
        if not isinstance(qid, str) or not QID.match(qid):
            errors.append(f"{op['id']}: suggested wikidata {qid!r} is not a QID")
            continue
        if all(c["wikidata"] != qid for c in op["candidates"]):
            c = client.person(qid)
            if c is None:
                errors.append(f"{op['id']}: no such item {qid}")
                continue
            op["candidates"].append(dict(c, evidence=evidence(op, c)))
        c = next(c for c in op["candidates"] if c["wikidata"] == qid)
        if not _appliable(c):
            errors.append(f"{op['id']}: suggested {qid} is not a human with a saint or blessed status")
    return errors


# The candidate's place properties that answer a eulogy place of each role, in order; a role
# not here (mention, cult, journey, ...) is never agreement.
ROLE_PROPS = {"death": ("death_place", "burial_place"), "burial": ("burial_place", "death_place"),
              "translation": ("burial_place", "death_place"), "birth": ("birth_place",),
              "ministry": ("work_places", "death_place"), "religious_life": ("work_places", "death_place"),
              "foundation": ("work_places", "death_place")}
VIA = {"death_place": "P20", "burial_place": "P119", "birth_place": "P19", "work_places": "P937"}


def _near(a, b, admin):
    """The same item, or one P131 step apart either way."""
    return a == b or b in admin.get(a, ()) or a in admin.get(b, ())


def place_agreement(places, c, admin):
    """[{role, qid, label, via}]: the eulogy places the candidate agrees with, each by the first
    property of its role that does. `admin` is {qid: P131 qids}."""
    out = []
    for p in places:
        via = next((prop for prop in ROLE_PROPS.get(p["role"], ())
                    if any(_near(q, p["qid"], admin) for q in c.get(prop, []))), None)
        if via:
            out.append({"role": p["role"], "qid": p["qid"], "label": p["label"], "via": VIA[via]})
    return out


def annotate_places(ops, by_eulogy, client):
    """Mark on each open op its eulogy's places and, per candidate, those it agrees with (`places`,
    and "place" last in its evidence) and the labels of its place properties (`place_labels`).

    A candidate carried over from an old op, with none of the place properties or no saint
    `signals`, gets them from its person summary first (one `client.people` call), and "status"
    in its evidence when a signal marks it a saint. Evidence only: the order and `auto` are
    left as they are. Idempotent, and run last, since other steps recompute `evidence`. One
    `client.items` call; a WikidataError from either call propagates before any op is touched.
    Decided and prefilled ops are left alone."""
    ops = [op for op in ops if op.get("decision") is None and not op.get("prefilled")]
    bare = list(dict.fromkeys(c["wikidata"] for op in ops for c in op["candidates"]
                              if c.get("wikidata") and (not any(prop in c for prop in VIA) or "signals" not in c)))
    people = client.people(bare) if bare else {}
    props = lambda c: (c if any(prop in c for prop in VIA)  # noqa: E731
                       else {prop: people.get(c.get("wikidata"), {}).get(prop, []) for prop in VIA})
    qids = list(dict.fromkeys([p["qid"] for op in ops for p in by_eulogy.get(op["eulogy"], [])]
                              + [q for op in ops for c in op["candidates"] for prop in VIA
                                 for q in props(c).get(prop, [])]))
    found = client.items(qids) if qids else {}
    for op in ops:
        for c in op["candidates"]:
            if c.get("wikidata") in people and not any(prop in c for prop in VIA):
                c.update({prop: people[c["wikidata"]].get(prop, []) for prop in VIA})
            if c.get("wikidata") in people and "signals" not in c:
                c["signals"] = people[c["wikidata"]].get("signals", [])
            if _saint_marked(c) and "status" not in c.get("evidence", []):
                ev = c.get("evidence", [])
                c["evidence"] = ev[:1] + ["status"] + ev[1:] if ev[:1] == ["human"] else ["status"] + ev
    admin = {q: s.get("admin_qids", []) for q, s in found.items()}
    label = lambda q, own=None: own or found.get(q, {}).get("label") or q  # noqa: E731
    for op in ops:
        places = [dict(p, label=label(p["qid"], p.get("label"))) for p in by_eulogy.get(op["eulogy"], [])]
        op["places"] = [{"role": p["role"], "label": p["label"], "qid": p["qid"]} for p in places]
        for c in op["candidates"]:
            c["evidence"] = [e for e in c.get("evidence", []) if e != "place"]
            c.pop("place_labels", None)
            c["places"] = place_agreement(places, c, admin)
            if c["places"]:
                c["evidence"].append("place")
            labels = {prop: [label(q) for q in c[prop]] for prop in VIA if c.get(prop)}
            if labels:
                c["place_labels"] = labels


def validate(items, index, ops=()):
    errors = []
    names = {}
    for key, p in index.items():
        names.setdefault(p["eulogy"], set()).add(person_key(p))
    for mrid, persons in items.items():
        for name, e in persons.items():
            where = f"{mrid}|{name}"
            if name not in names.get(mrid, set()):
                errors.append(f"{where}: not a person of data/persons.json")
            if e.get("status") not in STATUSES:
                errors.append(f"{where}: status {e.get('status')!r}")
            elif e["status"] == "unresolved":
                if e.get("wikidata") is not None or not (e.get("note") or "").strip():
                    errors.append(f"{where}: unresolved needs wikidata null and a note")
            elif not isinstance(e.get("wikidata"), str) or not QID.match(e["wikidata"]):
                errors.append(f"{where}: wikidata {e.get('wikidata')!r} is not a QID")
    for (mrid, qid), keys in sorted(_holders(items).items()):
        if len(keys) > 1:
            errors.append(f"{mrid}: {qid} is the item of more than one person ({', '.join(sorted(keys))})")
    for op in ops:
        if op["id"] not in index:
            errors.append(f"{op['id']}: queued but not a person of data/persons.json")
    return errors


def unaccounted(items, index, ops, skipped=()):
    """The persons with neither a status nor a queued review, except those whose lookup failed."""
    queued = {op["id"] for op in ops} | set(skipped)
    return [f"{key}: neither a status nor a queued review" for key, p in sorted(index.items())
            if key not in queued and not _decided(items, p)]


def render_json(items):
    doc = {"$comment": "Wikidata items of the persons of data/persons.json, by eulogy and name. auto: exactly one "
                       "candidate passed the evidence bar; reviewed: chosen by a curator; unresolved: no item "
                       "(note says why). Generated by scripts/build_person_items.py; see "
                       "docs/superpowers/specs/2026-10-08-persons-design.md. Draft pending committee review.",
           "statuses": STATUSES, "persons": {k: items[k] for k in sorted(items)}}
    return json.dumps(doc, ensure_ascii=False, indent=2) + "\n"


def render_report(items, index, ops, not_processed=()):
    counts = {s: sum(1 for v in items.values() for e in v.values() if e["status"] == s) for s in STATUSES}
    lines = ["# Person items report", "", "Generated by `scripts/build_person_items.py`.", "",
             f"- Persons: {len(index)}",
             *(f"- {s}: {counts[s]}" for s in STATUSES),
             f"- Queued for review: {len(ops)}", f"- Not processed (lookup failed): {len(not_processed)}", ""]
    # The user's ruling (2026-10-09): automatic matches of eulogies that do not mark a death
    # stay automatic, listed here for a curator to scan; a wrong one goes into FORCE_REVIEW.
    undated = sorted(f"{key}: {items[p['eulogy']][person_key(p)]['wikidata']}" for key, p in index.items()
                     if p["typology"] != "dies_natalis"
                     and items.get(p["eulogy"], {}).get(person_key(p), {}).get("status") == "auto")
    lines += [f"## Automatic without a date check, to scan ({len(undated)})", "",
              "Eulogies that do not mark the day of death: name, status and a single candidate decided.", ""]
    lines += [f"- {x}" for x in undated] + [""]
    if not_processed:
        lines += ["## Not processed", ""] + [f"- {k}: {e}" for k, e in not_processed] + [""]
    return "\n".join(lines)


def _read(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def month_changeset(review, month):
    """The review ops of the eulogies of one month (MM), as a change-set of their own."""
    return new_changeset([op for op in review["operations"] if op["eulogy"][3:5] == month])


def export(argv):
    if len(argv) < 2 or not re.fullmatch(r"0[1-9]|1[0-2]", argv[0]):
        sys.exit(__doc__)
    month, out = argv[0], Path(argv[1])
    repo_root = Path(argv[2]) if len(argv) > 2 else Path(__file__).resolve().parent.parent
    if _in_a_repository(out, repo_root):
        sys.exit(f"{out}: Jev's suggestions go on this change-set; write it outside any git work tree")
    changeset = month_changeset(_read(repo_root / "data" / "person_items_review.json", new_changeset([])), month)
    out.write_text(json.dumps(changeset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(changeset['operations'])} person cards in {out}")


def main(argv):
    if not argv or argv[0] not in {"propose", "verify-suggestions", "expand", "apply", "export", "check"}:
        sys.exit(__doc__)
    cmd, rest = argv[0], argv[1:]
    if cmd == "export":
        return export(rest)
    exported = None
    if cmd in ("apply", "expand"):
        if not rest:
            sys.exit(__doc__)
        exported = json.loads(Path(rest[0]).read_text(encoding="utf-8"))
        rest = rest[1:]
        if cmd == "expand":  # records: a list, or {"records": [...]}; one per person (name, n)
            records = exported["records"] if isinstance(exported, dict) else exported
            exported = {}
            for r in records:
                exported.setdefault(r["id"], []).append(r)
    repo_root = Path(rest[0]) if rest else Path(__file__).resolve().parent.parent
    data = repo_root / "data"
    entries = _read(data / "martyrology_ids.json", {})["entries"]
    typology = _read(data / "typology.json", {"typology": {}})["typology"]
    subjects = _read(repo_root / "i18n" / "la.json", {})
    index = person_index(_read(data / "persons.json", {}), entries, typology, subjects)
    items = _read(data / "person_items.json", {"persons": {}})["persons"]
    review = _read(data / "person_items_review.json", new_changeset([]))
    not_processed = []
    # Only the commands that use the places read their files (apply and check do not).
    places = eulogy_places.load(repo_root) if cmd in ("propose", "verify-suggestions", "expand") else None
    client = Wikidata(repo_root / ".cache" / "wikidata")
    if cmd == "propose":
        not_processed = propose(items, review, index, client)
    elif cmd == "verify-suggestions":
        errors = verify_suggestions(review, client)
        if errors:
            sys.exit("\n".join(errors))
    elif cmd == "expand":
        vernacular = {}
        for lang in ("en", "it"):
            for mrid, subject in _read(repo_root / "i18n" / f"{lang}.json", {}).items():
                name = subject_name(subject)
                if name and name not in vernacular.get(mrid, []):
                    vernacular.setdefault(mrid, []).append(name)
        not_processed = expand(review, items, exported, client, places, vernacular)
    elif cmd == "apply":
        print(f"applied {apply_decisions(items, review, exported, index, client)} decisions")
    if cmd in ("propose", "verify-suggestions", "expand"):
        # Last: the steps above recompute `evidence`, which drops "place".
        try:
            annotate_places(review["operations"], places, client)
        except WikidataError as e:
            not_processed.append(("places", str(e)))
    errors = validate(items, index, review["operations"]) + unaccounted(
        items, index, review["operations"], [key for key, _ in not_processed])
    if errors:
        sys.exit("invalid person items:\n" + "\n".join(errors))
    if cmd == "check":
        print("ok")
        return
    (data / "person_items.json").write_text(render_json(items), encoding="utf-8")
    (data / "person_items_review.json").write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n",
                                                   encoding="utf-8")
    (repo_root / "docs" / "person-items-report.md").write_text(
        render_report(items, index, review["operations"], not_processed), encoding="utf-8")
    for key, err in not_processed:
        print(f"not processed: {key}: {err}")
    if any(key == "places" for key, _ in not_processed):
        sys.exit("places were not annotated (Wikidata failed); the files are written without them: run again")


if __name__ == "__main__":
    main(sys.argv[1:])
