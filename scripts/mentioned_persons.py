#!/usr/bin/env python3
"""Pipeline for the persons a eulogy only mentions (role "mentioned"; data/persons_mentioned.json).

  brief   writes, for the eulogies of one month, the material an extraction agent reads: each eulogy's
          Latin and Italian texts and footnotes, its persons (name, n, role) and its current marks as
          [kind, where, start, end, form] (offsets in UTF-16 code units, per edition).
  check   validates the proposals an extraction agent returns, before anything is applied.
  candidates  lists Wikidata candidates for each proposed person: first the items of the commemorated persons
          of the same name (persons.json, identified in person_items.json and listed in
          persons_commemorated.json; route "commemorated", with the eulogies that commemorate them), then
          wbsearchentities in la, en and it (route "search"); label, description, birth and death years.
  jev     asks Jev (TypeSafe) to choose each person's item among their candidates, or "none":
          {"<mrid>": {"<name>[#n]": {"choice": qid | "none", "p": float, "accepted": p >= 0.90 and not none}}}
          (a person without candidates: "none", p null, nothing asked).

A proposal file is {"<mrid>": [{"name": Latin nominative, "n"?: int, "where": "text" | {"footnote": n},
"la": [printed phrases], "it": [printed phrases, [] if the Italian does not name them],
"who": one line, "kind": "saint" | "other"}]}. Every named human person is marked except Christ, the
Persons of the Trinity and the Virgin Mary; a phrase covers the name with its epithets and attached office
and must not overlap a commemorated person's mark. A place mark inside a phrase is allowed (apply removes it).

Usage:
  python3 mentioned_persons.py brief MM /path/to/martyrology-texts /outside/the/repo/brief-MM.json [repo_root]
  python3 mentioned_persons.py check proposals.json /path/to/martyrology-texts [repo_root]
    (exit 1, one problem per line, when a proposal fails a check)
  python3 mentioned_persons.py candidates proposals.json /outside/the/repo/candidates.json [repo_root]
  python3 mentioned_persons.py jev candidates.json /path/to/martyrology-texts /outside/the/repo/jev.json
    (Wikidata and TypeSafe answers are cached in .cache/ beside the out file; jev exits 1 after writing
    when an answer named no option offered or a request failed)

The brief, the candidates (the proposals' phrases) and Jev's answers quote the 2004 texts: they are
written only outside any git work tree.
Standard library only.
"""

import json
import re
import sys
from pathlib import Path

import mentions_jev as mj
from body_places import _in_a_repository, write_json_atomic
from extract_mentions import load_edition, source_text, where_key, with_mentioned_marks
from mentions_text import from_utf16, utf16
from persons_text import name_key, person_key
from subject_jev import _choice, _sentences, _window
from wikidata import MONTH_NAMES, Wikidata, WikidataError

EDITIONS = {"la": "martyrologium_romanum_2004", "it": "martyrologium_romanum_2004_it_IT"}
# Latin nominatives never marked as mentioned persons: Christ, the Persons of the Trinity, the Virgin Mary.
EXCLUDED = ("Christus", "Iesus", "Dominus", "Deus", "Spiritus Sanctus", "Trinitas")
VIRGIN_NAMES = ("Maria Virgo", "Beata Maria Virgo")  # Maria alone is excluded only when `who` says the Virgin
VIRGIN_WHO = re.compile(r"\b(?:the virgin|virgin mary|blessed virgin|mother of (?:god|jesus|christ)|theotokos"
                        r"|our lady|virgo)\b", re.I)
KINDS = ("saint", "other")
SEARCH_LANGS = ("la", "en", "it")
SEARCH_LIMIT = 7
IDENTIFIED = ("auto", "reviewed")  # person_items statuses of an identified commemorated person
ACCEPT_AT = 0.90


def read_json(path, default=None):
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def is_excluded(proposal):
    """Christ, a Person of the Trinity or the Virgin Mary: not marked."""
    key = name_key(proposal.get("name") or "")
    if key in {name_key(n) for n in EXCLUDED + VIRGIN_NAMES}:
        return True
    return key == "maria" and bool(VIRGIN_WHO.search(proposal.get("who") or ""))


def current_ids(registry, month):
    """The current (not deprecated) eulogy IDs of a month, in registry order."""
    return [e["id"] for e in registry["entries"] if e.get("month") == month and not e.get("deprecated")]


def span_form(src, start, end):
    """The printed words of a mark (UTF-16 offsets in `src`)."""
    return src[from_utf16(src, start):from_utf16(src, end)]


def brief_marks(marks, texts, notes, mrid):
    out = []
    for m in marks:
        src = source_text((texts, notes), mrid, m["where"]) or ""
        out.append([m["kind"], m["where"], m["start"], m["end"], span_form(src, m["start"], m["end"])])
    return out


def build_brief(month, registry, sources, persons, mentions):
    """`sources`: lang -> (texts, notes); `persons`/`mentions`: lang -> {eulogy: [...]}. The eulogies of the
    month that the Latin edition prints."""
    out = {}
    for mrid in current_ids(registry, month):
        la_texts, la_notes = sources["la"]
        if mrid not in la_texts:
            continue
        it_texts, it_notes = sources["it"]
        out[mrid] = {
            "id": mrid,
            "la": la_texts[mrid], "la_footnotes": la_notes.get(mrid, []),
            "it": it_texts.get(mrid), "it_footnotes": it_notes.get(mrid, []),
            "persons": [{"name": p["name"], "n": p.get("n", 1), "role": p.get("role", "commemorated")}
                        for p in persons["la"].get(mrid, [])],
            "marks": {lang: brief_marks(mentions[lang].get(mrid, []), *sources[lang], mrid) for lang in sources},
        }
    return list(out.values())


def check_proposals(proposals, sources, persons, mentions):
    """Problems in the proposals, one message each (empty when they pass)."""
    problems = []
    for mrid, items in proposals.items():
        if mrid not in sources["la"][0]:
            problems.append(f"{mrid}: not a eulogy of the Latin edition")
            continue
        known = {person_key({**p, "name": name_key(p["name"])}) for p in persons.get(mrid, [])}
        for p in items:
            key = person_key(p)
            label = f"{mrid} {key}"
            if not isinstance(p.get("name"), str) or not p["name"]:
                problems.append(f"{mrid}: a proposal without a name")
                continue
            if p.get("kind") not in KINDS:
                problems.append(f"{label}: kind must be one of {KINDS}")
            if not isinstance(p.get("who"), str) or not p["who"].strip():
                problems.append(f"{label}: who is missing")
            if is_excluded(p):
                problems.append(f"{label}: excluded (Christ, the Trinity or the Virgin Mary are not marked)")
            if person_key({**p, "name": name_key(p["name"])}) in known:
                problems.append(f"{label}: already a person of the eulogy")
            for lang in ("la", "it"):
                if not isinstance(p.get(lang), list) or (lang == "la" and not p[lang]):
                    problems.append(f"{label}: {lang} must list the printed phrases"
                                    + (" ([] if the Italian does not name them)" if lang == "it" else ""))
                    continue
                problems += phrase_problems(mrid, p, lang, sources[lang], mentions[lang].get(mrid, []), label)
    return problems


def phrase_problems(mrid, p, lang, edition_sources, marks, label):
    """Phrases not printed in the person's `where`, or overlapping a commemorated person's mark."""
    if not p[lang]:
        return []
    key = where_key(p["where"]) if p.get("where") == "text" or isinstance(p.get("where"), dict) else None
    if key is None or source_text(edition_sources, mrid, p["where"]) is None:
        return [f"{label}: there is no {p.get('where')!r} in the {lang} edition"]
    errors = []
    found = with_mentioned_marks([], [p], {key: source_text(edition_sources, mrid, p["where"])}, lang,
                                 lambda k: None, {}, errors)
    problems = [f"{mrid}: {e}" for e in errors]
    src = source_text(edition_sources, mrid, p["where"])
    for m in found:
        s, e = utf16(src, m["start"]), utf16(src, m["end"])
        for c in marks:
            if (c["kind"] == "person" and c.get("role") != "mentioned" and where_key(c["where"]) == key
                    and s < c["end"] and c["start"] < e):
                problems.append(f"{label}: {m['form']!r} ({lang}) overlaps the mark of {c.get('name', 'a person')}")
    return problems


# Candidates

def commemorated_items(name, persons, items, commemorated):
    """{qid: eulogies commemorating it} of the eulogies' persons of this name (name_key) that are not
    mentioned, identified (auto or reviewed) with an item persons_commemorated lists; in persons order."""
    key, out = name_key(name), {}
    for mrid, plist in persons.items():
        for p in plist:
            if p.get("role") == "mentioned" or name_key(p["name"]) != key:
                continue
            item = (items.get(mrid) or {}).get(person_key(p)) or {}
            qid = item.get("wikidata")
            if item.get("status") in IDENTIFIED and qid in commemorated:
                out.setdefault(qid, list(commemorated[qid]))
    return out


def _year(date):
    """The year of a summarize_person date ("0340", "-0300-05"), as an int; None without one."""
    m = re.match(r"-?\d+", date or "")
    return int(m.group()) if m else None


def _candidate(qid, summary, route):
    return {"wikidata": qid, "label": summary.get("label"), "description": summary.get("description") or "",
            "born": _year(summary.get("born")), "died": _year(summary.get("died")), "route": route}


def person_candidates(proposal, client, persons, items, commemorated):
    found = commemorated_items(proposal["name"], persons, items, commemorated)
    people = client.people(list(found)) if found else {}
    out = [_candidate(q, people.get(q, {}), "commemorated") | {"eulogies": e} for q, e in found.items()]
    for s in client.person_candidates(proposal["name"], SEARCH_LANGS, limit=SEARCH_LIMIT):
        if s["wikidata"] not in found:  # person_candidates lists each item once
            out.append(_candidate(s["wikidata"], s, "search"))
    return out


def build_candidates(proposals, client, persons, items, commemorated):
    """The proposals, each person with its `candidates`. `persons`: the Latin edition's persons by eulogy;
    `items`: person_items.json's persons; `commemorated`: persons_commemorated.json's items."""
    return {mrid: [p | {"candidates": person_candidates(p, client, persons, items, commemorated)} for p in plist]
            for mrid, plist in proposals.items()}


# Jev

def day_of(mrid):
    """"December 7" for mr:1207-…; None for an ID without a day."""
    m = re.match(r"mr:(\d\d)(\d\d)-", mrid)
    return f"{MONTH_NAMES[int(m.group(1)) - 1]} {int(m.group(2))}" if m and 1 <= int(m.group(1)) <= 12 else None


def latin_sentence(proposal, la_sources, mrid):
    """The sentence of the person's `where` holding their first Latin phrase (subject_jev's sentences)."""
    src = source_text(la_sources, mrid, proposal["where"]) or ""
    sentences = _sentences(src)
    if not sentences:
        return ""
    at = src.find(proposal["la"][0])
    if at < 0:
        return _window(sentences[0][1], 0)
    start, sentence = next((s, t) for s, t in reversed(sentences) if s <= at)
    return _window(sentence, at - start)


def _state_candidate(c):
    out = {k: c.get(k) for k in ("label", "description", "born", "died", "route")}
    if c.get("route") == "commemorated":
        out["commemorated_in"] = [{"eulogy": e, "day": day_of(e)} for e in c.get("eulogies") or []]
    return out


def jev_request(mrid, proposal, sentence):
    cands = proposal["candidates"]
    where = proposal["where"]
    state = {"eulogy": mrid, "day": day_of(mrid), "name": proposal["name"],
             "where": "text" if where == "text" else f"footnote {where['footnote']}",
             "latin_sentence": sentence, "latin_phrase": proposal["la"][0],
             "italian_phrase": (proposal.get("it") or [None])[0], "who": proposal["who"],
             "candidates": {c["wikidata"]: _state_candidate(c) for c in cands}}
    criteria = {c["wikidata"]: f"`candidates.{c['wikidata']}`: {c.get('label') or c['wikidata']}"
                + (f" ({c['description']})" if c.get("description") else "") for c in cands}
    criteria["none"] = "None of these items is this person."
    return {"model": mj.MODEL, "state": state, "questions": {"item": {
        "type": "choice",
        "instructions": ("The eulogy of the Roman Martyrology for `day` mentions the person `name` (printed as "
                         "`latin_phrase` in `latin_sentence`, and as `italian_phrase` in the Italian), identified as "
                         "`who`. Which of the `candidates` (Wikidata items) is this person? A candidate "
                         "`commemorated_in` other eulogies is a saint the Martyrology commemorates on those days. "
                         "Answer none if no candidate is this person."),
        "criteria": criteria}}}


def verdict(answer, ids):
    """{choice, p, accepted} from Jev's answer; None when it names no option offered."""
    if _choice(answer, ids + ["none"]) is None:
        return None
    pick = answer["choice"]
    p = answer["probabilities"][pick]
    return {"choice": pick, "p": p, "accepted": p >= ACCEPT_AT and pick != "none"}


def run_jev(candidates, la_sources, client):
    """({mrid: {person_key: verdict}}, problems). A refused key, or no key for a request not cached, is raised."""
    out, problems = {}, []
    for mrid, plist in candidates.items():
        for p in plist:
            key = person_key(p)
            if not p.get("candidates"):
                out.setdefault(mrid, {})[key] = {"choice": "none", "p": None, "accepted": False}
                continue
            body = jev_request(mrid, p, latin_sentence(p, la_sources, mrid))
            if not getattr(client, "key", True) and not client.cached(body):
                raise mj.TypeSafeError("no TypeSafe key: set TYPESAFE_API_KEY or write ~/.config/typesafe/api_key")
            try:
                response = client.ask(body)
            except mj.KeyRefused:
                raise
            except mj.TypeSafeError as e:
                problems.append(f"{mrid} {key}: {e}")
                continue
            v = verdict((response.get("answers") or {}).get("item"), [c["wikidata"] for c in p["candidates"]])
            if v is None:
                problems.append(f"{mrid} {key}: the answer named no option the request offered")
                continue
            out.setdefault(mrid, {})[key] = v
    return out, problems


def load_sources(texts_repo):
    return {lang: load_edition(Path(texts_repo), ed) for lang, ed in EDITIONS.items()}


def load_data(repo_root):
    d = Path(repo_root) / "data"
    persons = read_json(d / "persons.json")["editions"]
    mentions = read_json(d / "mentions.json")["editions"]
    return ({lang: persons.get(ed, {}) for lang, ed in EDITIONS.items()},
            {lang: mentions.get(ed, {}) for lang, ed in EDITIONS.items()})


def outside_git(out, repo_root):
    if _in_a_repository(out, repo_root):
        sys.exit(f"{out}: it quotes the 2004 texts: write it outside any git work tree")
    return out


def main(argv):
    if len(argv) < 3 or argv[0] not in ("brief", "check", "candidates", "jev"):
        sys.exit(__doc__)
    default_root = Path(__file__).resolve().parent.parent
    if argv[0] == "candidates":
        repo_root = Path(argv[3]) if len(argv) > 3 else default_root
        out = outside_git(Path(argv[2]), repo_root)
        d = repo_root / "data"
        persons = read_json(d / "persons.json")["editions"].get(EDITIONS["la"], {})
        items = read_json(d / "person_items.json")["persons"]
        commemorated = read_json(d / "persons_commemorated.json")["items"]
        client = Wikidata(out.parent / ".cache" / "wikidata")
        try:
            doc = build_candidates(read_json(argv[1]), client, persons, items, commemorated)
        except WikidataError as e:  # what was fetched stays cached: run again
            sys.exit(f"Wikidata: {e}")
        write_json_atomic(out, doc)
        print(f"wrote the candidates of {sum(len(v) for v in doc.values())} persons to {out}")
        return
    if argv[0] == "jev":
        if len(argv) < 4:
            sys.exit(__doc__)
        out = outside_git(Path(argv[3]), default_root)
        client = mj.TypeSafe(mj.api_key(), out.parent / ".cache" / "typesafe")
        try:
            doc, problems = run_jev(read_json(argv[1]), load_sources(argv[2])["la"], client)
        except mj.TypeSafeError as e:  # a refused key, or no key: nothing written
            sys.exit(str(e))
        write_json_atomic(out, doc)
        accepted = sum(v["accepted"] for per in doc.values() for v in per.values())
        print(f"wrote Jev's choice for {sum(len(v) for v in doc.values())} persons ({accepted} accepted) to {out}")
        for line in problems:
            print(line)
        if problems:
            sys.exit(1)
        return
    if argv[0] == "brief":
        if len(argv) < 4 or not argv[1].isdigit() or not 1 <= int(argv[1]) <= 12:
            sys.exit(__doc__)
        repo_root = Path(argv[4]) if len(argv) > 4 else default_root
        out = Path(argv[3])
        if _in_a_repository(out, repo_root):
            sys.exit("the brief quotes the 2004 texts: write it outside any git work tree")
        persons, mentions = load_data(repo_root)
        registry = read_json(repo_root / "data" / "martyrology_ids.json")
        brief = build_brief(int(argv[1]), registry, load_sources(argv[2]), persons, mentions)
        out.write_text(json.dumps(brief, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"wrote {len(brief)} eulogies to {out}")
        return
    repo_root = Path(argv[3]) if len(argv) > 3 else default_root
    persons, mentions = load_data(repo_root)
    problems = check_proposals(read_json(argv[1]), load_sources(argv[2]), persons["la"], mentions)
    for line in problems:
        print(line)
    if problems:
        sys.exit(1)
    print("proposals ok")


if __name__ == "__main__":
    main(sys.argv[1:])
