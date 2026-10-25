#!/usr/bin/env python3
"""Rename candidates: the discriminators an identity record allows for a bare ID.

A bare one-name ID (mr:0101-eugendus) takes a discriminator built by the minting
rules from its identity record (scripts/subject_records.py). R1: a place the 2004
Latin prints as an adjective keeps that adjective, in the nominative and agreeing
with the subject; otherwise the place takes its genitive. R2 (curator, 2026-10-19):
the place alone, for clerics too (no "abbas" or "episcopus" before it); a role only
when no place gives a slug. A twin's discriminator, a surname, a cognomen and -papa
come first; a role alone, or a class word (martyr, virgo, confessor), is weak.
R3: each candidate carries the la, en and it subjects it implies. Nothing is
decided here: the candidates are a curator's choices.
"""
import datetime
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import NamedTuple

import eulogy_places
from body_places import _in_a_repository
from extract_subjects import ROMAN, fold, it_label
from subject_records import CLERIC_ROLES, DECIDED, ROLE_FORMS

WEAK_ROLES = {"martyr", "virgo", "confessor"}
BIBLICAL_TITLES = ("propheta", "patriarcha", "iudex", "levita")
# a place's kinds, the one a slug takes first: the see or the monastery, then death, burial, cult
PLACE_ORDER = ("see", "monastery", "death", "burial", "cult", "origin")
MAX_CANDIDATES = 4
SCHEMA = "crmedr-changeset/v1"
EDITION = "martyrologium_romanum_2004"
CATEGORIES = ("surname", "place-genitive", "place-adjective", "role", "role-place", "epithet", "twin",
              "papa", "biblical-title")

# The bare-name drafts' place classes: the place form the draft's slug took.
DRAFT_PLACE_CLASSES = ("place-form", "align-existing")
ADJECTIVE_ENDING = re.compile(r"(ensis|anus|ana|inus|ina)$")

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


# A singular locative of the first or second declension has the genitive's form (Romæ, Gualdi
# Captaneórum); a plural (Metis) or one in -e (Areláte) does not. One in -i may still be a
# third-declension locative (Carthagini), so the form is never certain.
LOCATIVE_AS_GENITIVE = re.compile(r"(ae|i)$")


def genitive_slug(place, certain=None):
    """(genitive slug, certain): the corpus genitive when the place has one; else the certain
    genitive of the place's item (certain: {qid: genitive}, see certain_genitives); else the
    record's own genitive, not certain; else a printed locative in -ae or -i, which has the
    genitive's form, not certain; else (None, False)."""
    known = PLACE_GENITIVES.get(slug(place.get("nominative") or ""))
    if known:
        return known, True
    if certain and place.get("qid") in certain:
        return certain[place["qid"]], True
    if place.get("genitive"):
        return slug(place["genitive"]), False
    # fold() writes æ as e; the genitive keeps it as ae (Romæ -> romae)
    printed = slug(re.sub("[æÆ]", "ae", place.get("printed") or ""))
    if place.get("grammar") == "locative" and LOCATIVE_AS_GENITIVE.search(printed.split("-")[0]):
        return printed, False
    return None, False


def _ligatures(s):
    return s.replace("æ", "ae").replace("Æ", "Ae").replace("œ", "oe").replace("Œ", "Oe")


# a slug's place after one of these is a prepositional phrase (de-fabriano), not a genitive
PREPOSITIONS = {"a", "ab", "ad", "de", "e", "ex", "in"}


def _mine(entries, places):
    """{qid: {genitive: [current IDs giving it]}}: a current ID whose last k slug tokens
    (k = 3, 2, 1, the first that matches) are the slug of k printed words of one of its
    eulogy's places, the first of them capitalized, and not after a preposition. Each
    (qid, genitive) once per ID."""
    out = defaultdict(lambda: defaultdict(list))
    for e in entries:
        if e.get("deprecated"):
            continue
        tokens = e["id"][8:].split("-")
        seen = set()
        for p in places.get(e["id"], []):
            if not p.get("qid") or not p.get("la"):
                continue
            words = _ligatures(p["la"]).split()
            for k in (3, 2, 1):
                if len(tokens) <= k or tokens[-k - 1] in PREPOSITIONS:
                    continue  # the name itself, or a preposition's object, is not a genitive
                tail = "-".join(tokens[-k:])
                if any(words[i][:1].isupper() and slug(" ".join(words[i:i + k])) == tail
                       for i in range(len(words) - k + 1)):
                    if (p["qid"], tail) not in seen:
                        seen.add((p["qid"], tail))
                        out[p["qid"]][tail].append(e["id"])
                    break
    return out


def mine_genitives(entries, places):
    """{qid: Counter(genitive)}: how many current IDs give each genitive to a place item."""
    return {qid: Counter({g: len(ids) for g, ids in gens.items()}) for qid, gens in _mine(entries, places).items()}


def certain_genitives(mined):
    """(certain, conflicts): certain = {qid: genitive} given by two or more IDs and no other;
    conflicts = {qid: sorted genitives} for an item with two or more."""
    certain, conflicts = {}, {}
    for qid, counts in mined.items():
        if len(counts) > 1:
            conflicts[qid] = sorted(counts)
        else:
            (g, n), = counts.items()
            if n >= 2:
                certain[qid] = g
    return certain, conflicts


def _folded(s):
    return " " + " ".join(fold(s or "").split()) + " "


def link_places(record, places):
    """A copy of the record whose places gain the `qid` of the eulogy place whose Latin
    contains their printed form (the first such); a place with none is left as it is."""
    out = dict(record, places=[dict(p) for p in record.get("places") or []])
    for p in out["places"]:
        printed = _folded(p.get("printed"))
        if printed.strip():
            qid = next((e["qid"] for e in places if e.get("qid") and printed in _folded(e.get("la"))), None)
            if qid:
                p["qid"] = qid
    return out


def genitives_report(mined, labels):
    """The genitive report (Markdown) of _mine's result: the items with two or more genitives,
    the certain map, the genitives one ID gives. IDs, QIDs, labels and slugs only."""
    def line(qid, gens):
        parts = ", ".join(f"`{g}` ({len(ids)}: {', '.join(ids[:3])}{', …' if len(ids) > 3 else ''})"
                          for g, ids in sorted(gens.items(), key=lambda x: (-len(x[1]), x[0])))
        return f"- {qid} {labels.get(qid) or '(no label)'}: {parts}"

    def key(qid):
        return (labels.get(qid) or "", qid)

    conflicts = sorted((q for q, g in mined.items() if len(g) > 1), key=key)
    certain = sorted((q for q, g in mined.items() if len(g) == 1 and len(next(iter(g.values()))) >= 2), key=key)
    single = sorted((q for q, g in mined.items() if len(g) == 1 and len(next(iter(g.values()))) == 1), key=key)
    out = ["# Place genitives mined from the IDs", "",
           "Generated by `scripts/rename_candidates.py report`. A genitive is certain when two or more current",
           "IDs give it to a place item and none gives another; `PLACE_GENITIVES` overrides. Each genitive",
           "shows how many IDs give it and up to three of them.", "",
           f"## Items with two or more genitives ({len(conflicts)})", "",
           "Each offered as uncertain until the curator picks one in `PLACE_GENITIVES`.", ""]
    out += [line(q, mined[q]) for q in conflicts] or ["None."]
    out += ["", f"## Certain ({len(certain)})", ""]
    out += [line(q, mined[q]) for q in certain] or ["None."]
    out += ["", f"## Given by one ID ({len(single)}, uncertain)", ""]
    out += [line(q, mined[q]) for q in single] or ["None."]
    return "\n".join(out) + "\n"


def write_genitives_report(repo_root, entries=None, places=None):
    """Write docs/rename-genitives-report.md from the registry and the eulogy places."""
    repo_root = Path(repo_root)
    if entries is None:
        entries = json.loads((repo_root / "data" / "martyrology_ids.json").read_text(encoding="utf-8"))["entries"]
    if places is None:
        places = eulogy_places.load(repo_root)
    labels = {p["qid"]: p.get("label") for ps in places.values() for p in ps if p.get("qid")}
    path = repo_root / "docs" / "rename-genitives-report.md"
    path.write_text(genitives_report(_mine(entries, places), labels), encoding="utf-8")
    return path


class Context(NamedTuple):
    taken: dict    # MMDD -> slugs in use that day, current and deprecated
    twins: dict    # mrid -> its same-saint IDs, current and deprecated (same_eulogy, shared person item)
    ids: set       # all current IDs (a current twin's discriminator wins over a deprecated one's)
    labels: dict   # lang (la, en, it) -> mrid -> subject
    genitives: dict = {}  # place QID -> its certain corpus genitive (certain_genitives)
    places: dict = {}     # mrid -> the eulogy's places (eulogy_places.load)


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
    places = eulogy_places.load(repo_root)
    return Context(taken=dict(taken),
                   twins={m: sorted(t) for m, t in twins.items() if t},
                   ids=ids, labels={lang: read("i18n", f"{lang}.json") for lang in ("la", "en", "it")},
                   genitives=certain_genitives(mine_genitives(entries, places))[0], places=places)


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
    record = link_places(record, ctx.places.get(mrid, []))
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
        # The Latin words may follow the Latin subject; never an English or Italian one.
        labels = {"la": f"{subject_la} {words}" if subject_la else None, "en": None, "it": None}
        # A twin of its own lends its subjects; a joint eulogy's subject is not this saint's.
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
        # The printed Latin cognomen is not an English or Italian one ("Saint Basil Magnus"): the curator fills them.
        add(slug(v), "epithet", {"la": f"{subject_la} {v}" if subject_la else None, "en": None, "it": None},
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
            form, certain = genitive_slug(place, ctx.genitives)
            category = "place-genitive"
        if form is None:
            dropped.append((f"mr:{mmdd}-{base}-{slug(place.get('nominative') or '')}",
                             f"no genitive for {place.get('nominative')}"))
        else:
            basis = f"{place['kind']} {place.get('printed')} ({place.get('grammar')})"
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


def is_bare(mrid):
    """A slug of one name token after mr:MMDD-, no hyphen."""
    return "-" not in mrid[8:]


def _record_of(mrid, group):
    """The first-named subject's record: the one whose name is the slug's token; else the first."""
    return next((r for r in group if slug(r.get("name") or "") == mrid[8:]), group[0])


def draft_category(cls, new_id):
    """The category of a bare-name draft: the first part of its class (a comma list: "epithet,low,
    weak-epithet") that is one; a place class takes the form of the slug's last token; with none,
    the last token tells: a role ("papa" is its own), a place adjective, else a place genitive."""
    last = new_id.rsplit("-", 1)[-1]
    place = "place-adjective" if ADJECTIVE_ENDING.search(last) else "place-genitive"
    for part in (cls or "").split(","):
        part = part.strip()
        if part in CATEGORIES:
            return part
        if part in DRAFT_PLACE_CLASSES:
            return place
    if last in ROLE_FORMS:
        return "papa" if last == "papa" else "role"
    return place


def _confidence(cands):
    first = cands[0]
    if first["basis"] == "bare-name draft" or first["weak"] or (first["category"] in ("place-genitive", "role-place")
                                         and not first["certain"]):
        return "low"
    return "medium" if len(cands) > 1 else "high"


def build_changeset(records, ctx, subjects_la, old=None):
    """One rename op per bare ID in the records, its candidates and the earlier bare-name
    draft (old: mrid -> that draft's op) merged in; an ID with no candidates and no draft is
    skipped, listed on stderr."""
    old = old or {}
    by_id = defaultdict(list)
    for r in records:
        by_id[r["id"]].append(r)
    ops = []
    for mrid in sorted(by_id):
        if not is_bare(mrid):
            continue
        subject_la = subjects_la.get(mrid) or ""
        cands = candidates(_record_of(mrid, by_id[mrid]), mrid, subject_la, ctx)
        draft = old.get(mrid)
        if draft and draft.get("new_id") and all(c["new_id"] != draft["new_id"] for c in cands):
            cands.append({"new_id": draft["new_id"], "category": draft_category(draft.get("class"), draft["new_id"]),
                          "draft_class": draft.get("class"), "weak": False,
                          "labels": {"la": draft.get("subject_la"), "en": None, "it": None},
                          "basis": "bare-name draft", "certain": False})
        if not cands:
            print(f"{mrid}: no candidates and no draft, skipped", file=sys.stderr)
            continue
        first = cands[0]
        ops.append({"op": "rename", "id": mrid, "new_id": first["new_id"], "uid": "subject:" + mrid,
                    "class": first["category"], "confidence": _confidence(cands),
                    "candidates": cands,
                    "reasoning": "; ".join(f"also: {c['new_id']} ({c['category']})" for c in cands[1:]),
                    "subject_la": subject_la, "decision": None})
    return {"schema": SCHEMA, "generated_by": "scripts/rename_candidates.py",
            "generated_at": datetime.date.today().isoformat(),
            "base": {"edition": EDITION, "registry": "data/martyrology_ids.json"}, "operations": ops}


def load_old(paths):
    """The bare-name drafts of these change-sets by ID; a later file wins."""
    old = {}
    for path in paths:
        for op in json.loads(Path(path).read_text(encoding="utf-8")).get("operations", []):
            if op.get("op") == "rename" and op.get("new_id"):
                old[op["id"]] = op
    return old


def main(argv):
    argv = list(argv)
    olds = []
    usage = (__doc__ + "\nusage: rename_candidates.py build <records.json> <out.json> [--old <changeset>...] [repo_root]"
             "\n       rename_candidates.py report [repo_root]   (docs/rename-genitives-report.md only)")
    while "--old" in argv:
        i = argv.index("--old")
        if i + 1 == len(argv):
            sys.exit(usage)
        olds.append(argv[i + 1])
        del argv[i:i + 2]
    if argv[:1] == ["report"] and len(argv) <= 2:
        repo_root = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parent.parent
        print(f"genitives report in {write_genitives_report(repo_root)}")
        return 0
    if len(argv) < 3 or argv[0] != "build":
        sys.exit(usage)
    records_path, out = Path(argv[1]), Path(argv[2])
    repo_root = Path(argv[3]) if len(argv) > 3 else Path(__file__).resolve().parent.parent
    if _in_a_repository(out, repo_root):
        sys.exit(f"{out}: a change-set quotes the 2004 edition; write it outside the repository")
    records = json.loads(records_path.read_text(encoding="utf-8"))
    if isinstance(records, dict):
        records = records["records"]
    ctx = load_context(repo_root)
    report = write_genitives_report(repo_root, places=ctx.places)
    changeset = build_changeset([r for r in records if r["id"] in ctx.ids], ctx, ctx.labels["la"], load_old(olds))
    out.write_text(json.dumps(changeset, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(changeset['operations'])} rename operations in {out}; genitives report in {report}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
