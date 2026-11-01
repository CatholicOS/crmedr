#!/usr/bin/env python3
"""Mark where each eulogy of the 2004 editions names its persons and places.

For the Latin editio altera 2004, the persons of data/persons.json and the
places of data/places.json; for the Italian (CEI) 2004 edition, the places and
the same persons under their Italian forms (scripts/mentions_italian.py: a person
found by none of them is proposed for review, by position in a footnote list).
Each mention is an offset span (UTF-16 code units, the unit JavaScript counts
in) in the eulogy's text or in one of its footnotes, with a `check` (a hash of
the printed words, never the words) and the Wikidata item crmedr has decided
for it (person_items.json, gazetteer.json). No text is stored: the words are
held in memory only (`form`) to match and validate. data/mentions_curated.json replaces
a eulogy's extracted mentions; the review change-set, which quotes the texts
around each doubtful mention, is written only outside the repository.
See martyrology-frontend's docs/superpowers/specs/2026-10-09-eulogy-markup-design.md.

  data/mentions.json          {"texts": {"commit"}, "editions": {edition: {id: [mention]}}}
  docs/mentions-report.md     counts and shares; IDs only

Usage:
  python3 extract_mentions.py /path/to/martyrology-texts --review /outside/the/repo/mentions-review.json [repo_root]
  python3 extract_mentions.py apply exported.json /path/to/martyrology-texts --review /outside/the/repo/mentions-review.json [repo_root]
    (writes the accepted decisions of a reviewed change-set into data/mentions_curated.json, then extracts again)

Standard library only.
"""

import datetime
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

from extract_typology import load_texts
from gazetteer_text import fold, lookup
from mentions_italian import ItalianNames, by_position, curated_forms, runs, surname_span
from extract_places import ROLES
from mentions_text import (back_ref_span, find_person, find_place, fold_map, free, from_utf16, nth_place,
                           partial_span, utf16)
from persons_text import name_key, name_subjects, person_key


# The other name printed right after a person: "Kingae seu Cunegundis", "Dativus, qui et Sanator".
CONNECTIVE = re.compile(r"\s*,?\s*(?:seu|vel|sive|qui\s+et|qu(?:ae|æ)\s+et)\s+", re.I)
NAME_WORD = re.compile(r"[^\W\d_][\w'’\-]*")
SPACES = re.compile(r"[ \t]+")
# The name printed right before a variant a person was found under: "Mamántis seu" before "Mamétis".
NAME_BEFORE = re.compile(r"([^\W\d_][\w'’\-]*)\s*,?\s*(?:seu|vel|sive|qui\s+et|qu(?:ae|æ)\s+et)\s+$", re.I)


def with_variant(src, span, taken):
    """A person's span widened over the other name printed right after it (its capitalized words),
    unless those words are taken by another mention."""
    m = CONNECTIVE.match(src, span[1])
    if not m:
        return span
    end, pos = None, m.end()
    while (w := NAME_WORD.match(src, pos)) and w.group(0)[0].isupper():
        end = w.end()
        gap = SPACES.match(src, end)
        if not gap:
            break
        pos = gap.end()
    wide = (span[0], end) if end else span
    return wide if wide == span or free((span[1], wide[1]), taken) else span


# What joins two names of one person in print, left out of their marks: "Martíni, cognoménto
# Sacerdótis", "Kingæ seu Cunegúndis", "Dativus, qui et Sanator".
JOINER = re.compile(r"\s*,?\s+(?:cogn[oó]m[eé]nto|seu|vel|sive|qu(?:i|ae|æ)\s+et)\s+", re.I)


def with_surname_after(src, span, ends, taken):
    """An Italian match widened to its whole name run when the rest of the run holds one of the
    person's surname `ends`: the religious name the subject gives ("Amata di Gesù") with the secular
    name and surname printed after it ("(Maria Rosa) de Gordon"), and a secular name found in its
    parenthesis ("Emanuele") with the religious name before it; unless those words are taken."""
    run = next((r for r in runs(src) if r[0] <= span[0] and span[1] < r[1]), None)
    if run is None or not free((run[0], span[0]), taken) or not free((span[1], run[1]), taken):
        return span
    rest = fold_map(src[span[1]:run[1]])[0]
    if any(re.search(rf"(?<!\w){re.escape(fold_map(e)[0])}(?!\w)", rest) for e in ends):
        before = src[run[0]:span[0]]
        # Back to the run's start only from inside its parenthesis: never over an honorific ("Santa").
        return run if before.count("(") > before.count(")") else (span[0], run[1])
    return span


def name_pieces(src, span):
    """A person's span as the spans of its name words, cut where a joiner stands between two names of
    the person, the joiner and the comma before it left out."""
    pieces, at = [], span[0]
    for m in JOINER.finditer(src, span[0], span[1]):
        pieces.append((at, m.start()))
        at = m.end()
    pieces.append((at, span[1]))
    return [(a, b) for a, b in pieces if b > a]


def with_name_before(src, span, taken):
    """A span found under a person's other name, widened back over the name printed before it
    ("Mamántis seu Mamétis"), unless that word is taken by another mention."""
    m = NAME_BEFORE.search(src, 0, span[0])
    if not m or not m.group(1)[0].isupper() or not free((m.start(), span[0]), taken):
        return span
    return (m.start(), span[1])


def where_key(where):
    """A mention's `where` as a key and in change-set ids: "text" or "footnote:<n>"."""
    return "text" if where == "text" else f"footnote:{where['footnote']}"


def mention_order(m):
    """The text first, then the footnotes in order; within each, by start."""
    return (0 if m["where"] == "text" else m["where"]["footnote"], m["start"])


def nth_note(notes, n):
    """The nth footnote's text (n from 1, in printed order); None when there is no such footnote."""
    return notes[n - 1] if isinstance(n, int) and 1 <= n <= len(notes) else None


def role_of(item):
    """A place item's entry in its mention's roles."""
    out = {"role": item["role"]}
    if "person" in item:
        out["name"] = item["person"]
        if "n" in item:
            out["n"] = item["n"]
    return out


# A saint's title before a name (Latin and Italian, folded), the particles that make a title part of a
# religious name ("a Sancta Terésia"), the words that open an institution's name, whose saint is its
# patron ("Ordine Sancti Ioánnis a Deo", "Régula sancti Benedícti", "Filiárum Maríæ"), and the words
# after "Maria" that make her the Virgin ("Maríæ Vírginis", "Maria Ausiliatrice").
SAINT_TITLES = {"sanctus", "sancta", "sancti", "sanctae", "sancto", "sanctum", "sanctam", "beatus", "beata",
                "beati", "beatae", "beato", "beatum", "beatam", "san", "santo", "santa", "sant", "sant'"}
NAME_PARTICLES = {"a", "ab", "de", "di", "da", "del", "della"}
INSTITUTION_STEMS = ("ordin", "regul", "regol", "institut", "istitut", "congregat", "societ", "soror", "suor",
                     "fili", "famil", "serv", "ancill", "ancell", "oblat", "carmel", "eremit", "religios", "missionar")
VIRGIN_STEMS = ("virg", "verg", "immacul", "auxili", "ausili", "dolor", "addolor", "mercede", "merced")
WORD = re.compile(r"[^\W\d_]+['’]?")
FIRST_NAME_ALONE_REACH = 4  # the words before a first name alone looked at for an institution's
# A capitalized word right after a name, past its particles: a surname, unless it is a title or a sacred
# name the edition capitalizes ("Xystus Póntifex", "Petrus Christum confessus").
NOT_SURNAME_STEMS = ("pontif", "papa", "christ", "domin", "iesu", "spirit", "eccles")
NOT_SURNAMES = {"deus", "dei", "deo", "deum"}
NEXT_SURNAME = re.compile(r"(?:\s+(?:" + "|".join(sorted(NAME_PARTICLES | {"la", "le", "du"})) + r")\b)*\s+([^\W\d_])")


def named_alone(src, span):
    """A first name alone at `span` names the saint the eulogy is about: it opens a sentence or the
    text, or follows a saint's title (not as part of a religious name: "a Sancta Terésia"), and is no
    institution's patron, not the Virgin, and not another person's full name."""
    before = [fold(w).replace("’", "'") for w in WORD.findall(src[:span[0]].split(".")[-1].split(";")[-1])]
    after = WORD.findall(src[span[1]:])[:4]
    if after and fold(after[0]).startswith(VIRGIN_STEMS):
        return False
    # Another person's own name: the first name, then a surname, after particles or not ("Ioánnes de la
    # Lande", "Radúlphus Smith").
    if ((m := NEXT_SURNAME.match(src, span[1])) and m.group(1).isupper()
            and not ((w := fold(WORD.match(src, m.start(1)).group(0))).startswith(NOT_SURNAME_STEMS)
                     or w in NOT_SURNAMES)):
        return False
    if any(w.startswith(INSTITUTION_STEMS) for w in before[-FIRST_NAME_ALONE_REACH:]):
        return False
    if before and before[-1] in SAINT_TITLES:
        return not (len(before) > 1 and before[-2] in NAME_PARTICLES)
    return not src[:span[0]].strip() or src[:span[0]].rstrip()[-1] in ".;:"


def eulogy_mentions(text, notes, places, persons, *, lang, place_qid, person_qid):
    """One eulogy's mentions in one edition (code-point offsets), what to review,
    and how each mention was found.

    `places`: the eulogy's items in data/places.json; `persons`: its names in
    data/persons.json (empty for an edition crmedr has no persons for); `notes`:
    the texts of its footnotes, in order. Places are placed first and win an
    overlap. Longer names are placed before shorter ones, so a name inside a
    longer name ("Nema" in "Nemardus a Fictura Nema") is not marked there; of two
    names as long (two spellings of one person, "Num Ka" and "Nŭm-ka"), one with
    a decided item first; persons sharing a name, in `n` order.
    """
    mentions, review, hows = [], [], []
    taken = {"place": {}, "person": {}}
    removals = {}  # (where, place start) -> (its remove_mention, the persons found in it)

    def source(where):
        if where == "text":
            return text
        return nth_note(notes, where["footnote"])

    def spans(kind, where):
        return taken[kind].setdefault(where_key(where), [])

    def add(kind, where, span, how, **extra):
        m = {"kind": kind, "where": where, "start": span[0], "end": span[1],
             "form": source(where)[span[0]:span[1]], **extra}
        mentions.append(m)
        spans(kind, where).append(span)
        if how:  # a person's further pieces (name_pieces) count once, with the first
            hows.append((kind, where == "text", how))
        return m

    def ask(op, kind, where, span, reasoning, **extra):
        start, end = span if span else (None, None)
        review.append({"op": op, "kind": kind, "where": where, "start": start, "end": end,
                       "form": source(where)[start:end] if span else None, **extra, "reasoning": reasoning})

    for item in places:
        form = item.get(lang)
        if not form:
            continue
        if item["source"] == "lead":
            span, how = find_place(text, form, spans("place", "text")), "as printed"
            if span is None and "via" in item:
                span, how = back_ref_span(text, lang), "back-reference"
        else:
            span = nth_place(text, form, item.get("occurrence" if lang == "la" else "occurrence_it", 1))
            how = "as printed"
        same = next((m for m in mentions if m["kind"] == "place" and span == (m["start"], m["end"])), None)
        if same is not None:
            same["roles"].append(role_of(item))
            continue
        if span is None or not free(span, spans("place", "text")):
            ask("add_mention", "place", "text", None, f"the place as printed ({form}) was not found",
                qid=place_qid(item["la"]))
            continue
        add("place", "text", span, how, qid=place_qid(item["la"]), roles=[role_of(item)])

    # Persons share a name by name_key, as extract_persons.py numbers them ("Tuấn", "Tuân").
    def group(p):
        return name_key(p["name"]), where_key(p["where"])

    last = {}  # (name_key, where) -> the highest n among the persons of that name printed there
    for p in persons:
        last[group(p)] = max(last.get(group(p), 1), p.get("n", 1))
    # A name is decided when any of its persons is: its persons keep their n order among themselves.
    decided = {name_key(p["name"]) for p in persons if person_qid(person_key(p))}
    def again(p, names, alone=()):
        """Further free matches of the person's `names` after the last person of the name in a place:
        the same person named twice, or a stem match on another word; and of `alone` (the first name
        alone) where it names a saint (named_alone). The curator decides."""
        name, where, src = p["name"], p["where"], source(p["where"])
        nth = {"n": p["n"]} if "n" in p else {}
        passed = []  # first names alone that name someone else here

        def further():
            taken_ = spans("place", where) + spans("person", where) + passed
            return next(((f, by_itself) for by_itself, nms in ((False, names), (True, alone)) for nm in nms
                         if (f := find_person(src, nm, taken_))), (None, None))

        while (found := further())[0]:
            found, by_itself = found
            if by_itself and not named_alone(src, found[0]):
                passed.append(found[0])
                continue
            spans("person", where).append(found[0])  # later names are not proposed over it
            ask("add_mention", "person", where, found[0],
                f"{name} matched again: mark it if it names this person once more", name=name, **nth)

    def place(p, found, under):
        name, where, src = p["name"], p["where"], source(p["where"])
        both = spans("place", where) + spans("person", where)
        span, how, _ = found
        if lang == "it":
            span = with_surname_after(src, span, p.get("ends", []), both)
        if p.get("also"):
            span = with_variant(src, span, both)  # "Kingae seu Cunegundis": one mention
            if under != name:
                span = with_name_before(src, span, both)  # found as "Mametis": from "Mamantis seu"
        # Two names of the person printed together are marked as pieces, the joiner left out.
        for i, piece in enumerate(name_pieces(src, span)):
            add("person", where, piece, how if i == 0 else None, name=name, **({"n": p["n"]} if "n" in p else {}),
                qid=person_qid(person_key(p)))

    def across_places(p):
        """The person's match under the names printed here (the Italian forms, else the stored name), the
        places left free to it, and the places it crosses."""
        src, where = source(p["where"]), p["where"]
        taken_ = spans("person", where) + window(p)  # a list person only between their neighbours
        found = next((f for nm in p.get("forms") or [p["name"]] if (f := find_person(src, nm, taken_))), None)
        crossed = [] if not found else [(x["start"], x["end"]) for x in mentions if x["kind"] == "place"
                                        and x["where"] == where and not free(found[0], [(x["start"], x["end"])])]
        return found, crossed

    def nested(p):
        """The person's match when every place it crosses lies inside the name ("Conrádi de Placéntia
        Confalonieri", "Costanzo Sérvoli da Fabriano"): both are marked; else None."""
        found, crossed = across_places(p)
        return found if found and crossed and all(inside(c, found[0]) for c in crossed) else None

    def not_found(p):
        name, where, src = p["name"], p["where"], source(p["where"])
        nth = {"n": p["n"]} if "n" in p else {}
        both = spans("place", where) + spans("person", where)
        inside_, crossed = across_places(p)
        if inside_:
            span = inside_[0]
            if all(inside(c, span) for c in crossed):
                place(p, inside_, name)
                return
            spans("person", where).append(span)  # later names are not proposed over it
            if len(crossed) == 1 and inside(span, crossed[0]):
                # Inside a place phrase, which may name a city and not the saint ("In civitáte Sancti
                # Ioánnis"): the curator decides; the place stays.
                ask("add_mention", "person", where, span,
                    f"{name} is named inside the place phrase: mark it inside the place if it names this person",
                    name=name, **nth)
                return
            place_ = next(x for x in mentions if x["kind"] == "place" and x["where"] == where
                          and not free(span, [(x["start"], x["end"])]))
            ask("add_mention", "person", where, span, f"{name} is named inside a place phrase, which was kept",
                name=name, **nth)
            key = (where_key(where), place_["start"])
            if key in removals:  # one remove_mention per place, naming every person in it
                removals[key][1].append(name)
                removals[key][0]["reasoning"] = ("the place phrase contains the persons "
                                                 + ", ".join(removals[key][1]))
            else:
                ask("remove_mention", "place", where, (place_["start"], place_["end"]),
                    f"the place phrase contains the person {name}")
                removals[key] = (review[-1], [name])
            return
        ask("add_mention", "person", where, partial_span(src, (p.get("forms") or [name])[0], both),
            f"{name} was not found", name=name, **nth)

    # Every person by their main name first, longer names first, then their other names: a variant
    # never takes the words of a person of that name ("Maximianus seu Maximus" and a Maximus).
    # Longer first by the folded name, so spellings of one name ("Æmilia", "Aemilia") sort together.
    # Of spellings of one person ("Num Ka", "Nŭm-ka"), the one decided itself first.
    order = [p for p in sorted(persons, key=lambda p: (-len(name_key(p["name"])), name_key(p["name"]) not in decided,
                                                         p.get("n", 1), not person_qid(person_key(p))))
             if source(p["where"]) is not None]  # extract_persons.py validates footnote numbers
    # A given name two persons of the eulogy share names neither of them alone.
    given_names = Counter(fold_map(f.split()[0])[0] for p in persons for f in (p.get("forms") or [])[:1] if f.split())

    # The persons of an Italian footnote list are printed in the Latin order (`rank`): each is looked
    # for only between the persons of the list already marked before and after them in that order.
    rank_of = {(q["name"], q.get("n")): q["rank"] for q in persons if "rank" in q and q["where"] != "text"}

    def window(p):
        """The words outside a list person's place in the list, as taken spans; none outside a list."""
        if lang != "it" or (p["name"], p.get("n")) not in rank_of:
            return []
        rank, src = p["rank"], source(p["where"])
        marked = [(rank_of[(m["name"], m.get("n"))], m["start"], m["end"]) for m in mentions
                  if m["kind"] == "person" and m["where"] == p["where"] and (m["name"], m.get("n")) in rank_of]
        lo = max((e for r, _, e in marked if r < rank), default=0)
        hi = min((s for r, s, _ in marked if r > rank), default=len(src))
        return [x for x in ((0, lo), (hi, len(src))) if x[1] > x[0]]

    def look(p, fallback=False):
        """The person's first free match under the names they are printed with in this edition (the
        Italian forms, else the stored name), and the name it was found under. Persons of one name take
        its matches in print order, whatever their case ("Felíce", then "Felix"). With `fallback`, for
        the Italian: a text person by their given name alone, any person by their surname."""
        both = spans("place", p["where"]) + spans("person", p["where"]) + window(p)
        for nm in p.get("forms") or [p["name"]]:
            try:
                found = find_person(source(p["where"]), nm, both, in_order=last[group(p)] > 1)
            except re.error:  # a form the name patterns can't take
                continue
            if found:
                return found, nm
        if lang != "it" or not fallback:
            return None, None
        src = source(p["where"])
        if p["where"] == "text":  # a byname printed apart ("Canuto, detto Lavard"): the given name
            for nm in p.get("forms", []):
                given = nm.split()[0]
                if (len(given) >= 3 and nm != given and given_names[fold_map(given)[0]] < 2
                        and (found := find_person(src, given, both))):
                    return (found[0], "given name", found[2]), None  # no further matches of a bare given name
        span = surname_span(src, p.get("ends", []), both, [f.split()[0] for f in p.get("forms", []) if f.split()],
                            joined=bool(re.search(r"\set\s", p["name"])))
        return ((span, "surname", False), None) if span else (None, None)

    # The first words of the names and forms of the eulogy's persons, how many persons each opens.
    first_words = Counter(w for p in persons for w in {name_key(nm.split()[0]) for nm in [p["name"], *p.get("forms", [])]
                                                       if nm.split()})

    def first_name_alone(p, under):
        """A text person of several words named again by the first word of the name they were found
        under ("Radúlphi Sherwin", then "sanctus Radúlphus"), when no other person of the eulogy's
        names opens with it and it has three letters or more."""
        words = under.split()
        if p["where"] != "text" or len(words) < 2 or len(words[0]) < 3 or first_words[name_key(words[0])] > 1:
            return []
        return [words[0]]

    placed, later, unplaced, second = [], [], [], []
    for p in order:
        found, under = look(p)
        if not found and lang == "it":
            second.append(p)  # by a fallback, once every person has been looked for by name
            continue
        if not found:
            if p.get("also"):
                later.append(p)  # tried under their other names once every main name is placed
            else:
                unplaced.append(p)
            continue
        place(p, found, p["name"])
        placed.append(p)
        # In a list a name printed again is another person (left to the list's order), never this one.
        if p.get("n", 1) == last[group(p)] and under and (p["name"], p.get("n")) not in rank_of:
            again(p, [under], first_name_alone(p, under))
    for p in second:
        if (found := nested(p)) is not None:  # the whole name, before a given name alone
            place(p, found, p["name"])
            placed.append(p)
            continue
        found, under = look(p, fallback=True)
        if not found:
            unplaced.append(p)
            continue
        place(p, found, p["name"])
        placed.append(p)
    for p in later:
        both = spans("place", p["where"]) + spans("person", p["where"])
        found, under = next(((f, nm) for nm in p.get("also", []) if (f := find_person(source(p["where"]), nm, both))),
                            (None, None))
        if not found:
            unplaced.append(p)
            continue
        place(p, found, under)
        placed.append(p)
        if p.get("n", 1) == last[group(p)]:
            again(p, [p["name"]])
    for p in placed:  # the other names' further matches, once every person has their own words
        if p.get("also") and p.get("n", 1) == last[group(p)]:
            again(p, p["also"])
    # A footnote list prints its persons in the same order in every edition: one left over between two
    # found neighbours is proposed where the list prints a name between theirs.
    proposed = {}
    for where in {where_key(p["where"]) for p in unplaced if "rank" in p and p["where"] != "text"}:
        ranked = sorted((p for p in persons if "rank" in p and where_key(p["where"]) == where), key=lambda p: p["rank"])
        src, w = source(ranked[0]["where"]), ranked[0]["where"]
        marked = {(m.get("name"), m.get("n")): (m["start"], m["end"]) for m in mentions
                  if m["kind"] == "person" and m["where"] == w}
        found = {i: marked[(p["name"], p.get("n"))] for i, p in enumerate(ranked) if (p["name"], p.get("n")) in marked}
        given = [[f.split()[0] for f in p.get("forms", []) if f.split()] for p in ranked]
        for i, span in by_position(src, ranked, found, spans("place", w) + spans("person", w), given).items():
            proposed[id(ranked[i])] = span
    for p in unplaced:
        if id(p) in proposed:
            spans("person", p["where"]).append(proposed[id(p)])
            ask("add_mention", "person", p["where"], proposed[id(p)],
                f"{p['name']} was not found by name: proposed by its place in the list",
                name=p["name"], **({"n": p["n"]} if "n" in p else {}))
        else:
            not_found(p)

    mentions.sort(key=mention_order)
    return mentions, review, hows


EDITIONS = {"martyrologium_romanum_2004": "la", "martyrologium_romanum_2004_it_IT": "it"}
ITALIAN_EDITION = "martyrologium_romanum_2004_it_IT"
PERSONS_EDITION = "martyrologium_romanum_2004"
KINDS = ("person", "place", "event")
# A span covers one name or one place designation, never more: a guard against runaway matches.
MAX_FORM_WORDS = 20
COMMENT = ("Where each eulogy of the 2004 editions names its persons and places (Latin and "
           "Italian): offsets in UTF-16 code units into the eulogy's text or its nth footnote (n from 1, "
           "in printed order), a check (the first 8 hex digits of the SHA-256 of the printed words, which "
           "are never stored), and the Wikidata item decided in person_items.json or gazetteer.json. "
           "texts.commit is the martyrology-texts commit the offsets were computed from. Generated by "
           "scripts/extract_mentions.py; corrections go in data/mentions_curated.json. Draft pending "
           "committee review.")
# The "$comment" of data/mentions_curated.json, wherever that file is written.
CURATED_COMMENT = ("Curators' corrections to data/mentions.json: for each eulogy listed, its complete list of "
                   "mentions in the shape of data/mentions.json (UTF-16 offsets and a check, never the words), "
                   "replacing the extraction. QIDs are copied from person_items.json and gazetteer.json at "
                   "extraction, whatever is written here. Written by `scripts/extract_mentions.py apply` from a "
                   "reviewed change-set (docs/mentions-changeset.md), or by hand.")
LABELS = [(("place", True), "Places in the text"), (("person", True), "Persons in the text"),
          (("person", False), "Persons in footnotes"), (("event", True), "Events in the text")]


def source_text(edition_sources, mrid, where):
    """The text a mention counts in: the eulogy's, or its nth footnote's. None when there is none."""
    texts, notes = edition_sources
    if where == "text":
        return texts.get(mrid)
    return nth_note(notes.get(mrid, []), where.get("footnote") if isinstance(where, dict) else None)


def check(words):
    """The check stored for a mention: the first 8 hex digits of the SHA-256 of
    the printed words (UTF-8). It ties a span to its words without storing them."""
    return hashlib.sha256(words.encode("utf-8")).hexdigest()[:8]


def other_persons(others, qid=lambda o: o.get("qid")):
    """The other persons a person mark names (one word for several: "quibus nomen Anastasius"),
    as the data files hold them: name, n when not the first, QID."""
    return [{"name": o.get("name"), **({"n": o["n"]} if o.get("n") not in (None, 1) else {}), "qid": qid(o)}
            for o in others]


def from_file(m, src):
    """A mention as the data files hold it (UTF-16 offsets, check) as an internal
    one (code points, the printed words in `form`). `form` is None when the words
    at its span do not pass its check: the text has changed since."""
    src = src or ""
    start, end = from_utf16(src, m["start"]), from_utf16(src, m["end"])
    words = src[start:end]
    out = {"kind": m["kind"], "where": m["where"], "start": start, "end": end,
           "form": words if words and check(words) == m.get("check") else None}
    if m["kind"] == "person":
        out["name"] = m.get("name")
        if "n" in m:
            out["n"] = m["n"]
    out["qid"] = m.get("qid")
    if m["kind"] == "person" and m.get("others"):
        out["others"] = other_persons(m["others"])
    if m.get("roles"):
        out["roles"] = m["roles"]
    return out


def curated_mention(m, items, lang, place_qid, person_qid, source):
    """A curated mention as an internal one, its QID copied from the decisions: a
    person's by its key (name, or name#n); a place's from the eulogy's place whose printed form it is,
    else from its only place."""
    out = from_file(m, source(m["where"]))
    if m["kind"] == "person":
        out["qid"] = person_qid(person_key(out))
        if out.get("others"):
            out["others"] = other_persons(out["others"], lambda o: person_qid(person_key(o)))
    else:
        item = next((it for it in items if out["form"] is not None and it.get(lang) == out["form"]),
                    items[0] if len(items) == 1 else None)
        out["qid"] = place_qid(item["la"]) if item else None
    return out


def curated_place_roles(ms, items, text, lang, place_qid=lambda la: None):
    """Set the roles of a curated eulogy's place mentions in its text, by printing:
    an item marks the mention on the printing it points at (an opening place, the
    first free printing of its phrase, else a mention printed as it). A body place
    with no mention on its printing is marked there when no other mark covers it (the
    gazetteer decided it); one inside another mark, or not printed, is returned as an
    add_mention review item."""
    review = []
    marks = [m for m in ms if m["kind"] == "place" and m["where"] == "text"]
    for m in marks:
        m.pop("roles", None)
    for item in items:
        form = item.get(lang)
        if not form:
            continue
        if item["source"] == "lead":
            span = find_place(text, form) or (back_ref_span(text, lang) if "via" in item else None)
            m = next((m for m in marks if span == (m["start"], m["end"])), None) or next(
                (m for m in marks if m["form"] == form and "roles" not in m), None)
        else:
            span = nth_place(text, form, item.get("occurrence" if lang == "la" else "occurrence_it", 1))
            m = next((m for m in marks if span == (m["start"], m["end"])), None)
        if m is not None:
            m.setdefault("roles", []).append(role_of(item))
        elif item["source"] != "lead":
            covering = span and next(
                (m for m in ms if m["where"] == "text" and not free(span, [(m["start"], m["end"])])), None)
            # A place printed inside a person's name ("Conrádi de Placéntia Confalonieri"), or holding one ("basílicæ
            # sub título Sancti Michaélis"), is marked one level from it; a place across another place is proposed.
            if span and (not covering or nests((*span, "place"), [(m["start"], m["end"], m["kind"]) for m in ms
                                                                   if m["where"] == "text"])):
                m = {"kind": "place", "where": "text", "start": span[0], "end": span[1], "form": text[span[0]:span[1]],
                     "qid": place_qid(item["la"]), "roles": [role_of(item)]}
                ms.append(m)
                marks.append(m)
            elif span:
                review.append({"op": "add_mention", "kind": "place", "where": "text", "start": span[0], "end": span[1],
                               "form": text[span[0]:span[1]], "qid": place_qid(item["la"]),
                               "reasoning": f"the place {form} is printed inside the mark of {covering['form']}"})
            else:
                review.append({"op": "add_mention", "kind": "place", "where": "text", "start": None, "end": None,
                               "form": None, "qid": None,
                               "reasoning": f"the curated mentions have no mark for the place {form}"})
    if len(items) == 1:
        for m in marks:
            if "roles" not in m:
                m["roles"] = [role_of(items[0])]
    return review


def with_events(ms, events, source, lang):
    """The eulogy's marks with its events (data/events_curated.json: a council or synod by its printed
    phrase in each language and its item): the whole phrase is one event mark, and a place mark inside it
    goes (the eulogy keeps the place through data/gazetteer.json, where the phrase resolves to the city).
    `source(where)` is the text the item is printed in; its `occurrence` (from 1) picks a phrase printed
    more than once. Returns (marks, errors): a phrase not printed is an error."""
    ms, errors = list(ms), []
    for item in events:
        phrase, where = item.get(lang), item.get("where", "text")
        if not phrase:
            continue
        src = source(where) or ""
        at, n = -1, item.get("occurrence", 1)
        for _ in range(n):
            at = src.find(phrase, at + 1)
            if at < 0:
                break
        if at < 0:
            errors.append(f"the event {phrase!r} is not printed in the {where_key(where)}")
            continue
        span = (at, at + len(phrase))
        ms = [m for m in ms if not (m["kind"] == "place" and m["where"] == where
                                    and not free(span, [(m["start"], m["end"])]))]
        ms.append({"kind": "event", "where": where, "start": span[0], "end": span[1], "form": phrase,
                   "qid": item["qid"]})
    return sorted(ms, key=mention_order), errors


def build_edition(lang, texts, notes, places, persons, gazetteer, person_items, curated, events=None):
    """One edition's mentions by eulogy (code points), its review items by eulogy, and its counts."""
    out, review = {}, {}
    counts = {"expected": Counter(), "found": Counter(), "review": Counter(), "no_text": []}

    for mrid in sorted(set(places) | set(persons) | set(curated)):
        def place_qid(la, mrid=mrid):
            return (lookup(gazetteer, la, mrid) or {}).get("wikidata")

        items, names = places.get(mrid, []), persons.get(mrid, [])
        counts["expected"][("place", True)] += sum(1 for it in items if it.get(lang))
        for p in names:
            counts["expected"][("person", p["where"] == "text")] += 1
        if mrid not in texts:
            counts["no_text"].append(mrid)
            continue
        decided = person_items.get(mrid, {})

        def person_qid(key, decided=decided):
            return decided.get(key, {}).get("wikidata")

        if mrid in curated:
            ms = [curated_mention(m, items, lang, place_qid, person_qid,
                                  lambda w: source_text((texts, notes), mrid, w)) for m in curated[mrid]]
            for m in ms:
                counts["found"][(m["kind"], m["where"] == "text", "curated")] += 1
            rv = curated_place_roles(ms, items, texts[mrid], lang, place_qid)
            if rv:
                review[mrid] = rv
                counts["review"].update(r["op"] for r in rv)
        else:
            ms, rv, hows = eulogy_mentions(texts[mrid], notes.get(mrid, []), items, names, lang=lang,
                                           place_qid=place_qid, person_qid=person_qid)
            if rv:
                review[mrid] = rv
            counts["found"].update(hows)
            counts["review"].update(r["op"] for r in rv)
        if (events or {}).get(mrid):
            counts["expected"][("event", True)] += sum(1 for e in events[mrid] if e.get(lang))
            ms, errs = with_events(ms, events[mrid], lambda w: source_text((texts, notes), mrid, w), lang)
            counts["found"][("event", True, "curated")] += sum(1 for m in ms if m["kind"] == "event")
            counts.setdefault("event_errors", []).extend(f"{mrid}: {e}" for e in errs)
        if ms:
            out[mrid] = sorted(ms, key=mention_order)
    return out, review, counts


def validate(by_edition, source):
    """Errors in internal mentions (code points): each span holds its words (a
    curated one whose check failed has none), a span is short, a person has a name
    and a place none, no two overlap in one text."""
    errors = []
    for edition, by_id in by_edition.items():
        for mrid, ms in by_id.items():
            seen = {}
            for m in ms:
                tag = f"{edition} {mrid} {m.get('name') or m['kind']} at {where_key(m['where'])}:{m['start']}"
                if m.get("kind") not in KINDS:
                    errors.append(f"{tag}: unknown kind {m.get('kind')!r}")
                src = source(edition, mrid, m["where"])
                if src is None:
                    errors.append(f"{tag}: {where_key(m['where'])} has no text")
                    continue
                if (m.get("form") is None or not 0 <= m["start"] < m["end"] <= len(src)
                        or src[m["start"]:m["end"]] != m["form"]):
                    errors.append(f"{tag}: the span does not pass its check (has the text changed?)")
                    continue
                if len(m["form"].split()) > MAX_FORM_WORDS:
                    errors.append(f"{tag}: more than {MAX_FORM_WORDS} words")
                if (m["kind"] == "person") != bool(m.get("name")):
                    errors.append(f"{tag}: a person needs a name, and a place has none")
                if "others" in m:
                    keys = [person_key(m), *(person_key(o) for o in m["others"] or [])]
                    if (m["kind"] != "person" or not m["others"] or not all(o.get("name") for o in m["others"])
                            or len(set(keys)) != len(keys)):
                        errors.append(f"{tag}: the other persons of a mark are named persons, each once, "
                                      "and only a person mark has them")
                for r in m.get("roles", []):
                    if m["kind"] != "place" or r.get("role") not in ROLES:
                        errors.append(f"{tag}: role {r.get('role')!r} is not a place role")
                span = (m["start"], m["end"], m["kind"])
                if not nests(span, seen.get(where_key(m["where"]), [])):
                    errors.append(f"{tag}: overlaps another mention")
                seen.setdefault(where_key(m["where"]), []).append(span)
    return errors


def inside(a, b):
    """Whether span `a` lies within span `b` and is not `b` itself."""
    return b[0] <= a[0] and a[1] <= b[1] and (a[0], a[1]) != (b[0], b[1])


def nests(span, others):
    """Whether a mark (start, end, kind) may stand beside the marks already placed in its text: each one
    it overlaps holds it or is held by it, of the other kind, one level deep (a place inside a person's
    name, "Conrádi de Placéntia Confalonieri"; a person inside a place phrase)."""
    for o in others:
        if free(span[:2], [o[:2]]):
            continue
        outer, inner = (o, span) if inside(span, o) else (span, o) if inside(o, span) else (None, None)
        if outer is None or outer[2] == inner[2]:
            return False
        if any(inside(outer, x) or (x is not inner and inside(x, inner)) for x in others + [span]):
            return False
    return True


def to_file(m, src):
    """An internal mention as the data files hold it: UTF-16 offsets and the
    check of its words in place of the words. The one place that fixes the order
    of a file mention's keys."""
    out = {"kind": m["kind"], "where": m["where"], "start": utf16(src, m["start"]), "end": utf16(src, m["end"]),
           "check": check(m["form"])}
    if m["kind"] == "person":
        out["name"] = m["name"]
        if "n" in m:
            out["n"] = m["n"]
    out["qid"] = m["qid"]
    if m["kind"] == "person" and m.get("others"):
        out["others"] = other_persons(m["others"])
    if m.get("roles"):
        out["roles"] = m["roles"]
    return out


def to_utf16(by_edition, source):
    """The mentions as the data files hold them, eulogies sorted."""
    return {edition: {mrid: [to_file(m, source(edition, mrid, m["where"])) for m in by_id[mrid]]
                      for mrid in sorted(by_id)}
            for edition, by_id in by_edition.items()}


def render_json(by_edition, source, commit):
    doc = {"$comment": COMMENT, "texts": {"commit": commit}, "editions": to_utf16(by_edition, source)}
    return json.dumps(doc, ensure_ascii=False, indent=2) + "\n"


def render_report(counts_by_edition):
    """Counts and shares by edition; the IDs of the eulogies without a text. No text is quoted."""
    lines = ["# Mentions report", "",
             "Generated by `scripts/extract_mentions.py`: counts and eulogy IDs, no text. "
             "The doubtful mentions are in the review change-set, which is kept outside this repository.", ""]
    for edition, c in counts_by_edition.items():
        lines += [f"## {edition}", "", "| Mentions | Expected | Marked | Share | How |", "| --- | --- | --- | --- | --- |"]
        for key, label in LABELS:
            expected = c["expected"][key]
            if not expected:
                continue
            hows = {how: n for (kind, in_text, how), n in c["found"].items() if (kind, in_text) == key}
            marked = sum(hows.values())
            detail = ", ".join(f"{how} {n}" for how, n in sorted(hows.items()))
            lines.append(f"| {label} | {expected} | {marked} | {100 * marked / expected:.1f}% | {detail} |")
        ops = ", ".join(f"{op} {n}" for op, n in sorted(c["review"].items())) or "none"
        lines += ["", f"Review operations: {ops}.", ""]
        if c.get("twin"):
            lines += ["Eulogies whose text the edition files under their `same_eulogy` twin; their mentions are "
                      "recorded under the twin's ID: "
                      + ", ".join(f"`{m}` (as `{t}`)" for m, t in sorted(c["twin"].items())) + ".", ""]
        if c["no_text"]:
            lines += ["Eulogies with persons or places but no text of their own in this edition: "
                      + ", ".join(f"`{m}`" for m in c["no_text"]) + ".", ""]
    return "\n".join(lines)


def texts_commit(texts_repo):
    """The martyrology-texts commit checked out at `texts_repo`; None when it is not a git checkout."""
    try:
        out = subprocess.run(["git", "-C", str(texts_repo), "rev-parse", "HEAD"],
                             capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip() or None


SCHEMA = "crmedr-changeset/v1"
CONTEXT_WIDTH = 40
MAX_CLAUSE = 160  # at most this many characters after a person's span, to the clause's end


def _read(path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def context(src, start, end, after=CONTEXT_WIDTH):
    """The words around a span and the code-point offset at which they start in
    `src`: about CONTEXT_WIDTH characters before it and `after` after it, cut at spaces."""
    a = max(0, start - CONTEXT_WIDTH)
    if a > 0:
        space = src.find(" ", a, start)
        a = space + 1 if space >= 0 else a
    b = min(len(src), end + after)
    if b < len(src):
        space = src.rfind(" ", end, b)
        b = space if space > end else b
    return src[a:b], a


def op_key(r):
    """What ends a spanless op's id: the person's key (name, or name#n), or the place's QID (one place
    per eulogy, so unique); "place" for a place without a QID."""
    if r["kind"] == "person":
        return person_key(r)
    return r.get("qid") or "place"


def review_ops(edition, review_by_id, source):
    """The review items of one edition as change-set operations (UTF-16 offsets).
    An item without a span quotes the whole text it is about (context_start 0)."""
    ops, seen = [], set()
    for mrid in sorted(review_by_id):
        for r in review_by_id[mrid]:
            src = source(edition, mrid, r["where"])
            if r["start"] is None:
                ctx, at, start, end = src, 0, None, None
            else:
                # A person's add may cover only the name's first word (found in part): the context runs
                # on long enough for the curator to select the whole name ("Ioséphi … González").
                # It runs at least to the end of the clause: a printed name may be much longer than the
                # person's ("Láuræ a Sancta Catharína Senénsi Montoya y Upegui").
                after = CONTEXT_WIDTH
                if r["kind"] == "person":
                    clause = re.search(r"[,;.:]", src[r["end"]:])
                    after = max(CONTEXT_WIDTH, 2 * len(r.get("name") or ""),
                                min(MAX_CLAUSE, clause.start() + 2 if clause else 0))  # past ", "
                ctx, at = context(src, r["start"], r["end"], after)
                start, end = utf16(src, r["start"]), utf16(src, r["end"])
            key = op_key(r) if start is None else start
            op_id = f"{edition}|{mrid}|{where_key(r['where'])}|{key}"
            if op_id in seen:  # two ops sharing an id, e.g. a remove and an add at one offset
                op_id += f"|{r['op']}"
            seen.add(op_id)
            op = {"op": r["op"], "id": op_id, "edition": edition, "eulogy": mrid, "where": r["where"],
                  "start": start, "end": end, "form": r["form"], "kind": r["kind"]}
            if r["op"] == "add_mention" and r["kind"] == "person":
                op["name"] = r["name"]
                if "n" in r:
                    op["n"] = r["n"]
            op.update(context=ctx, context_start=utf16(src, at), reasoning=r["reasoning"], decision=None)
            if r["op"] == "add_mention":
                op["edited"] = None
            ops.append(op)
    return ops


def new_changeset(operations):
    return {"schema": SCHEMA, "generated_by": "scripts/extract_mentions.py",
            "generated_at": datetime.date.today().isoformat(),
            "base": {"edition": PERSONS_EDITION, "registry": "data/mentions.json"}, "operations": operations}


def load_edition(texts_repo, edition):
    """An edition's texts, and its footnotes' texts by eulogy (none for an edition without footnotes.json)."""
    notes = _read(texts_repo / "data" / "editions" / edition / "footnotes.json", {})
    return load_texts(texts_repo, edition), {k: [f["text"] for f in v] for k, v in notes.items()}


def file_under_twins(entries, texts, places, persons):
    """Re-key to its twin's ID a current eulogy that has no text under its own ID
    when a `same_eulogy` twin has one: the edition files the text, its footnotes and
    the API's lookups by the twin's ID. Returns the places, the persons,
    {current ID: twin ID} of every eulogy filed (for the report), and of those whose
    persons were filed (which the person decisions and the Latin marks follow). Each
    kind is filed apart: a twin with places (or persons) of its own keeps them, and
    the current eulogy's are left where they were (they would mark the same text twice)."""
    places, persons, twins, person_twins = dict(places), dict(persons), {}, {}
    for e in entries:
        mrid = e["id"]
        if e.get("deprecated") or mrid in texts or not (mrid in places or mrid in persons):
            continue
        twin = next((t for t in e.get("same_eulogy", []) if t in texts), None)
        if twin is None:
            continue
        for by_id in (places, persons):
            if mrid in by_id and twin not in by_id:
                by_id[twin] = by_id.pop(mrid)
                twins[mrid] = twin
                if by_id is persons:
                    person_twins[mrid] = twin
    return places, persons, twins, person_twins


def italian_persons(persons, names, latin, person_twins, misprints=()):
    """The persons of data/persons.json as the Italian edition looks for them: each with the Italian
    forms of its name (`forms`), the untranslated ends of it a surname search anchors on (`ends`) and,
    when the Latin marks it, where the Latin prints it (`rank`: the footnote, 0 for the text, then the
    offset), which orders a footnote list; without `also`, the Latin's other names. A name the edition
    misprints where the person is printed (data/misprints.json: "Emillia" for Emilia) is looked for as
    printed first: a misprint is printed once there, and the intended form may name another person."""
    misprinted = {}  # (mrid, where key) -> [(intended, printed)]
    for mp in misprints:
        if mp.get("edition") == ITALIAN_EDITION:
            where = {"footnote": mp["footnote"]} if "footnote" in mp else "text"
            misprinted.setdefault((mp["id"], where_key(where)), []).append((mp["intended"], mp["printed"]))
    out = {}
    for mrid, ps in persons.items():
        filed = person_twins.get(mrid, mrid)  # the Latin marks of persons filed under a twin's ID
        rank = {(m["name"], m.get("n")): (0 if m["where"] == "text" else m["where"]["footnote"], m["start"])
                for m in latin.get(filed, []) if m["kind"] == "person"}
        out[mrid] = []
        for p in ps:
            q = {k: v for k, v in p.items() if k != "also"}
            q["forms"], q["ends"] = names.forms(mrid, p["name"]), names.surname(p["name"])
            for intended, printed in misprinted.get((mrid, where_key(p["where"])), []):
                word = re.compile(rf"(?<!\w){re.escape(intended)}(?!\w)")
                q["forms"] = list(dict.fromkeys([f2 for f in q["forms"] for f2 in (word.sub(printed, f), f)]))
            if (p["name"], p.get("n")) in rank:
                q["rank"] = rank[(p["name"], p.get("n"))]
            out[mrid].append(q)
    return out


def extract(texts_repo, repo_root, review_path):
    data = repo_root / "data"
    places = _read(data / "places.json")["places"]
    persons = _read(data / "persons.json")["editions"][PERSONS_EDITION]
    gazetteer = _read(data / "gazetteer.json", {"places": {}})["places"]
    person_items = _read(data / "person_items.json", {"persons": {}})["persons"]
    curated = _read(data / "mentions_curated.json", {"editions": {}})["editions"]
    entries = _read(data / "martyrology_ids.json", {"entries": []})["entries"]
    events = {k: v for k, v in _read(data / "events_curated.json", {}).items() if not k.startswith("$")}
    sources, by_edition, review, counts = {}, {}, {}, {}
    names = ItalianNames(name_subjects(repo_root, "la"), name_subjects(repo_root, "it"),
                         curated_forms(_read(data / "persons_curated.json", {})))
    latin_twins = {}
    for edition, lang in EDITIONS.items():  # the Latin first: its marks order the Italian footnote lists
        sources[edition] = load_edition(texts_repo, edition)
        ed_persons = (persons if edition == PERSONS_EDITION
                      else italian_persons(persons, names, by_edition[PERSONS_EDITION], latin_twins,
                                           _read(data / "misprints.json", {"misprints": []})["misprints"]))
        ed_places, ed_persons, twins, person_twins = file_under_twins(entries, sources[edition][0], places, ed_persons)
        if edition == PERSONS_EDITION:
            latin_twins = person_twins
        by_edition[edition], review[edition], counts[edition] = build_edition(
            lang, *sources[edition], ed_places, ed_persons, gazetteer,
            {person_twins.get(k, k): v for k, v in person_items.items()},  # the decisions follow their persons
            curated.get(edition, {}), events)
        counts[edition]["twin"] = twins

    def source(edition, mrid, where):
        return source_text(sources[edition], mrid, where)

    errors = validate(by_edition, source) + [f"{edition} {e}" for edition in EDITIONS
                                              for e in counts[edition].get("event_errors", [])]
    if errors:
        sys.exit("invalid mentions:\n" + "\n".join(errors))
    (data / "mentions.json").write_text(render_json(by_edition, source, texts_commit(texts_repo)), encoding="utf-8")
    (repo_root / "docs" / "mentions-report.md").write_text(render_report(counts), encoding="utf-8")
    ops = [op for edition in EDITIONS for op in review_ops(edition, review[edition], source)]
    review_path.write_text(json.dumps(new_changeset(ops), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    total = sum(len(ms) for by_id in by_edition.values() for ms in by_id.values())
    print(f"wrote data/mentions.json: {total} mentions; {len(ops)} to review in {review_path}")


MENTION_OPS = {"add_mention", "set_span", "remove_mention"}


def _same(m, where, start, end):
    return m["where"] == where and m["start"] == start and m["end"] == end


def apply_decisions(curated_editions, mentions_editions, exported):
    """Apply the accepted (or edited) mention operations of `exported`, in UTF-16
    offsets; a rejected one curates its eulogy as it stands, so it is not proposed again. Each eulogy an operation touches starts from its curated entry, else
    from data/mentions.json, and is written back into `curated_editions`. A mention
    an operation adds or moves carries the operation's `form` and no `check` until
    `apply` checks it against the texts. Returns how many operations were applied,
    and the errors."""
    applied, errors = 0, []
    for op in exported.get("operations", []):
        if op.get("op") not in MENTION_OPS or op.get("decision") not in ("accept", "edit", "reject"):
            continue
        edition, mrid, where = op["edition"], op["eulogy"], op["where"]
        tag = op.get("id") or f"{edition} {mrid}"
        edited = (op.get("edited") or {}) if op["decision"] == "edit" else {}
        by_id = curated_editions.setdefault(edition, {})
        current = [dict(m) for m in by_id.get(mrid, mentions_editions.get(edition, {}).get(mrid, []))]
        if op["decision"] == "reject":
            # The eulogy is curated as it stands, so the rejected proposal is not made again.
            by_id.setdefault(mrid, sorted(current, key=mention_order))
            continue
        if op["op"] == "add_mention":
            span = {k: edited.get(k, op.get(k)) for k in ("start", "end", "form")}
            if span["start"] is None or span["end"] is None or not span["form"]:
                errors.append(f"{tag}: an added mention needs a span")
                continue
            m = {"kind": op["kind"], "where": where, **span}
            if op["kind"] == "person":
                m["name"] = op["name"]
                if op.get("n"):
                    m["n"] = op["n"]
            m["qid"] = None  # copied from the decisions at extraction
            others = edited.get("others", op.get("others"))
            if op["kind"] == "person" and others:
                m["others"] = other_persons(others, lambda o: None)
            current.append(m)
        else:
            old = op["from"] if op["op"] == "set_span" else op
            hit = [m for m in current if _same(m, where, old["start"], old["end"])]
            if not hit:
                errors.append(f"{tag}: no such mention to {op['op'].split('_')[0]}")
                continue
            if op["op"] == "remove_mention":
                current = [m for m in current if m not in hit]
            else:
                to = {**op["to"], **edited}
                for m in hit:
                    m.pop("check", None)
                    m.update(start=to["start"], end=to["end"], form=to["form"])
        by_id[mrid] = sorted(current, key=mention_order)
        applied += 1
    return applied, errors


def _internal(m, src):
    """A curated mention as an internal one. A pending one (it carries a `form`)
    keeps its words only when they are the text at its span; any other is checked
    against its `check`, as at extraction."""
    if "form" not in m:
        return from_file(m, src)
    out = from_file(m, src)  # no check: no words
    start, end = out["start"], out["end"]
    out["form"] = m["form"] if (src or "")[start:end] == m["form"] else None
    return out


def apply(exported, texts_repo, repo_root):
    """Write the accepted operations of `exported` into data/mentions_curated.json,
    after checking every curated span against the texts. Nothing is written when one
    fails. Returns how many operations were applied."""
    data = repo_root / "data"
    mentions = _read(data / "mentions.json", {"editions": {}})["editions"]
    doc = _read(data / "mentions_curated.json", {"$comment": CURATED_COMMENT, "editions": {}})
    applied, errors = apply_decisions(doc["editions"], mentions, exported)
    errors += [f"{edition}: not an edition with mentions" for edition in doc["editions"] if edition not in EDITIONS]
    # Texts are read as extraction reads them: filed under a twin's ID, the eulogy's operations name that ID.
    sources = {edition: load_edition(texts_repo, edition) for edition in doc["editions"] if edition in EDITIONS}

    def source(edition, mrid, where):
        return source_text(sources[edition], mrid, where)

    internal = {edition: {mrid: [_internal(m, source(edition, mrid, m["where"])) for m in ms]
                          for mrid, ms in by_id.items()}
                for edition, by_id in doc["editions"].items() if edition in sources}
    errors += validate(internal, source)
    if errors:
        sys.exit("not applied:\n" + "\n".join(errors))
    doc["editions"] = to_utf16(internal, source)
    (data / "mentions_curated.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                                                encoding="utf-8")
    return applied


def main(argv):
    if "--review" not in argv or argv.index("--review") + 1 >= len(argv):
        sys.exit(__doc__)
    i = argv.index("--review")
    review_path, argv = Path(argv[i + 1]), argv[:i] + argv[i + 2:]
    if not argv:
        sys.exit(__doc__)
    applying = argv[0] == "apply"
    if applying:
        if len(argv) < 3:
            sys.exit(__doc__)
        exported, argv = Path(argv[1]), argv[2:]
    texts_repo = Path(argv[0])
    repo_root = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parent.parent
    if review_path.resolve().is_relative_to(repo_root.resolve()):
        sys.exit("the review change-set quotes the 2004 texts: write it outside the repository "
                 "(martyrology-frontend's CHANGESETS_DIR)")
    if applying and exported.resolve().is_relative_to(repo_root.resolve()):
        sys.exit("an exported change-set quotes the 2004 texts: keep it outside the repository "
                 "(martyrology-frontend's CHANGESETS_DIR)")
    if applying:
        print(f"applied {apply(json.loads(exported.read_text(encoding='utf-8')), texts_repo, repo_root)} operations")
    extract(texts_repo, repo_root, review_path)


if __name__ == "__main__":
    main(sys.argv[1:])
