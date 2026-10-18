#!/usr/bin/env python3
"""Rename candidates: the discriminators an identity record allows for a bare ID.

A bare one-name ID (mr:0101-eugendus) takes a discriminator built by the minting
rules from its identity record (scripts/subject_records.py). R1: a place the 2004
Latin prints as an adjective keeps that adjective, in the nominative and agreeing
with the subject; otherwise the place takes its genitive. R2: clerics take role and
place, others the place alone; a twin's discriminator, a surname, a cognomen and
-papa come first; a role alone, or a class word (martyr, virgo, confessor), is weak.
R3: each candidate carries the la, en and it subjects it implies. Nothing is
decided here: the candidates are a curator's choices.
"""
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import NamedTuple

from extract_subjects import ROMAN, fold, it_label
from subject_records import CLERIC_ROLES, DECIDED

WEAK_ROLES = {"martyr", "virgo", "confessor"}
BIBLICAL_TITLES = ("propheta", "patriarcha", "iudex", "levita")
# a place's kinds, the one a slug takes first: the see or the monastery, then death, burial, cult
PLACE_ORDER = ("see", "monastery", "death", "burial", "cult", "origin")
MAX_CANDIDATES = 4

# folded nominative -> the corpus genitive, from the bare-name pass's place map
PLACE_GENITIVES = {
    "treviri": "trevirorum", "arverni": "arvernorum", "carnutes": "carnutum", "cenomani": "cenomanorum",
    "lemovices": "lemovicum", "pictavi": "pictavorum", "turones": "turonum", "hierosolyma": "hierosolymorum",
}


def slug(s):
    """A slug part: folded as the registry's IDs were minted, words hyphen-joined; digits
    are kept, so that a numeric token is seen and dropped, not silently lost."""
    return "-".join(re.sub(r"\D+", lambda m: fold(m.group()), s).split())


def adjective_slug(adjective, feminine):
    """The place adjective in the nominative, agreeing with the subject: -anus/-ana and
    -inus/-ina follow the subject's gender; -ensis is both."""
    s = slug(adjective)
    if feminine:
        return re.sub(r"(an|in)us$", r"\1a", s)
    return re.sub(r"(an|in)a$", r"\1us", s)


def genitive_slug(place):
    """(genitive slug, certain): the corpus genitive when the place has one; else the
    record's own genitive, not certain; else (None, False)."""
    known = PLACE_GENITIVES.get(slug(place.get("nominative") or ""))
    if known:
        return known, True
    if place.get("genitive"):
        return slug(place["genitive"]), False
    return None, False


class Context(NamedTuple):
    taken: dict    # MMDD -> slugs in use that day, current and deprecated
    twins: dict    # mrid -> its same-saint IDs, current and deprecated (same_eulogy, shared person item)
    ids: set       # all current IDs (a current twin's discriminator wins over a deprecated one's)
    labels: dict   # lang (la, en, it) -> mrid -> subject


def load_context(repo_root):
    repo_root = Path(repo_root)
    read = lambda *p: json.loads(repo_root.joinpath(*p).read_text(encoding="utf-8"))  # noqa: E731
    entries = read("data", "martyrology_ids.json")["entries"]
    taken, twins = defaultdict(set), defaultdict(set)
    ids = {e["id"] for e in entries if not e.get("deprecated")}
    for e in entries:
        taken[e["id"][3:7]].add(e["id"][8:])
        for other in e.get("same_eulogy", []):  # both ways; not through a joint eulogy to its other saint
            twins[e["id"]].add(other)
            twins[other].add(e["id"])
    by_item = defaultdict(set)
    for mrid, names in read("data", "person_items.json")["persons"].items():
        for item in names.values():
            if item.get("status") in DECIDED and item.get("wikidata"):
                by_item[item["wikidata"]].add(mrid)
    for group in by_item.values():
        for mrid in group:
            twins[mrid] |= group - {mrid}
    return Context(taken=dict(taken),
                   twins={m: sorted(t) for m, t in twins.items() if t},
                   ids=ids, labels={lang: read("i18n", f"{lang}.json") for lang in ("la", "en", "it")})


def _primary_place(record):
    places = [p for p in record.get("places") or [] if p.get("kind") in PLACE_ORDER]
    return min(places, key=lambda p: PLACE_ORDER.index(p["kind"]), default=None)


def _display(slug_part):
    return " ".join(w.capitalize() for w in slug_part.split("-"))


def _labels(mrid, subject_la, ctx, la_words, en_tail=None, it_tail=None):
    """The la, en and it subjects with a discriminator: the Latin words after the Latin
    subject; the English and Italian tails after theirs (None when that subject is missing)."""
    en, it = ctx.labels.get("en", {}).get(mrid), ctx.labels.get("it", {}).get(mrid)
    if it:
        it = it_label(mrid, it)
    return {"la": f"{subject_la} {la_words}" if subject_la else None,
            "en": f"{en}{en_tail}" if en and en_tail is not None else en,
            "it": f"{it}{it_tail}" if it and it_tail is not None else it}


def _build(record, mrid, subject_la, ctx):
    """(candidates, dropped): every candidate the rules allow, in tier order, then the
    hard-rule drops (numeric token, taken that day, twin disagreement, more than four)."""
    mmdd, base = mrid[3:7], mrid[8:]
    name_tokens = base.split("-")
    role_en, role_it = record.get("role_en"), record.get("role_it")
    roles = [r["role"] for r in record.get("roles") or [] if r.get("role")]
    out, dropped = [], []

    def add(disc, category, labels, basis, weak=False, certain=True):
        out.append({"new_id": f"mr:{mmdd}-{base}-{disc}", "category": category, "weak": weak,
                    "certain": certain, "labels": labels, "basis": basis})

    # A twin's discriminator: its slug after this ID's name tokens, cut at a joint eulogy's
    # "et" or "socii" (mr:0102-basilius-magnus-et-gregorius-nazianzenus -> magnus).
    by_disc = {}
    for twin in ctx.twins.get(mrid, []):
        tokens = twin[8:].split("-")
        if tokens[:len(name_tokens)] != name_tokens:
            continue
        disc = tokens[len(name_tokens):]
        cut = next((i for i, t in enumerate(disc) if t in ("et", "socii")), None)
        if cut is not None:
            disc = disc[:cut]
        if disc:
            by_disc.setdefault("-".join(disc), []).append((twin, cut is not None))
    # A current twin first, then the discriminator most twins share, then the twins' order.
    order = sorted(by_disc, key=lambda d: (not any(t in ctx.ids for t, _ in by_disc[d]), -len(by_disc[d])))
    for disc in order:
        twins = by_disc[disc]
        words = _display(disc)
        labels = _labels(mrid, subject_la, ctx, words, f" {words}", f" {words}")
        # A twin of its own takes the twin's subjects; a joint eulogy's subject is not this saint's.
        own = sorted((t for t, joint in twins if not joint), key=lambda t: t not in ctx.ids)
        if own:
            for lang in ("la", "en", "it"):
                subject = ctx.labels.get(lang, {}).get(own[0])
                if subject:
                    labels[lang] = it_label(own[0], subject) if lang == "it" else subject
        add(disc, "twin", labels, "twin " + ", ".join(t for t, _ in twins))

    if record.get("surname"):
        s = record["surname"]
        add(slug(s), "surname", _labels(mrid, subject_la, ctx, s, f" {s}", f" {s}"), f"surname {s}")
    cog = record.get("cognomen")
    if cog and cog.get("value"):
        v = cog["value"]
        add(slug(v), "epithet", _labels(mrid, subject_la, ctx, v, f" {v}", f" {v}"),
            f"cognomen {v} ({cog.get('source')})")
    place = _primary_place(record)

    def role_labels(role, words=None):
        return _labels(mrid, subject_la, ctx, words or role,
                       f", {role_en}" if role_en else None, f", {role_it}" if role_it else None)

    if "papa" in roles and not set(name_tokens) & ROMAN:
        add("papa", "papa", role_labels("papa"), "role papa, no ordinal")
    title = next((r for r in roles if r in BIBLICAL_TITLES), None)
    if title and place is None:
        add(title, "biblical-title", role_labels(title), f"biblical title {title}, no place")

    cleric = next((r for r in roles if r in CLERIC_ROLES), None)
    if place is not None:
        if str(place.get("grammar", "")).startswith("adjective-") and place.get("adjective"):
            form, certain = adjective_slug(place["adjective"], record.get("feminine")), True
            category = "place-adjective"
        else:
            form, certain = genitive_slug(place)
            category = "place-genitive"
        if form is None:
            dropped.append((f"mr:{mmdd}-{base}-{slug(place.get('nominative') or '')}",
                             f"no genitive for {place.get('nominative')}"))
        else:
            basis = f"{place['kind']} {place.get('printed')} ({place.get('grammar')})"
            if cleric:
                add(f"{cleric}-{form}", "role-place",
                    _labels(mrid, subject_la, ctx, f"{cleric} {_display(form)}",
                            f", {role_en} of {place['en']}" if role_en else f" of {place['en']}",
                            f", {role_it} di {place['it']}" if role_it else f" di {place['it']}"),
                    f"{cleric} + {basis}", certain=certain)
            add(form, category, _labels(mrid, subject_la, ctx, _display(form),
                                        f" of {place['en']}", f" di {place['it']}"), basis, certain=certain)

    kept = _keep(out, dropped, mmdd, base, ctx)
    # Nothing kept (a cleric with no place, a place with no genitive, every slug taken...):
    # a role alone (a cleric's, else a lay role like monachus), else a class word; both weak.
    # A pope with an ordinal needs none.
    if not kept and not ("papa" in roles and set(name_tokens) & ROMAN):
        others = [r for r in roles if r not in WEAK_ROLES and r != "papa"]
        r = cleric or (others[0] if others else (roles[0] if roles else None))
        if r:
            add(r, "role", role_labels(r), f"{r}, nothing else kept", weak=True)
            kept = _keep(out[-1:], dropped, mmdd, base, ctx)
    return kept, dropped


def _keep(out, dropped, mmdd, base, ctx):
    """The candidates the hard rules keep (at most four); the others go to dropped."""
    kept, seen = [], set()
    for c in out:
        new_slug = c["new_id"][8:]
        if c["new_id"] in seen:
            continue
        seen.add(c["new_id"])
        if any(ch.isdigit() for ch in new_slug):
            dropped.append((c["new_id"], "numeric token"))
        elif new_slug == base or "--" in new_slug or new_slug.endswith("-"):
            dropped.append((c["new_id"], "empty discriminator"))
        elif new_slug in ctx.taken.get(mmdd, set()):
            dropped.append((c["new_id"], "taken that day"))
        elif c["category"] != "twin" and any(k["category"] == "twin" for k in kept):
            dropped.append((c["new_id"], "twin disagreement"))
        elif len(kept) == MAX_CANDIDATES:
            dropped.append((c["new_id"], "beyond four"))
        else:
            kept.append(c)
    return kept


def candidates(record, mrid, subject_la, ctx):
    """The rename candidates of a bare ID, the rules' first choice first (at most four)."""
    return _build(record, mrid, subject_la, ctx)[0]


def rejected(record, mrid, ctx):
    """(new ID, reason) of the candidates the hard rules drop, for the report."""
    return _build(record, mrid, ctx.labels.get("la", {}).get(mrid), ctx)[1]
