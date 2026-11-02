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
"who": one line, "kind": "saint" | "other"}]}. `where` is the person's first printing; a phrase is a
string, printed there, or {"phrase": str, "where": "text" | {"footnote": n}}, printed elsewhere (a person
named in the text and in a footnote is one proposal). Every named human person is marked except Christ, the
Persons of the Trinity and the Virgin Mary; a phrase covers the name with its epithets and attached office
and must not overlap another person's mark or another proposal's phrase (a printing over a commemorated
namesake's mark is passed over for the next one). A place mark inside a phrase is allowed (apply removes a
curated body place; an opening place needs a shorter phrase).
  decisions  joins the proposals (or their candidates file), Jev's choices and the research entries into a
          decisions file: an accepted Jev choice is reviewed, decided "jev"; a research entry
          {"<mrid>|<name>[#n]": {wikidata, decided, status, note?, candidates?}} overrides it. A proposed
          person with neither is a problem (exit 1, nothing written).
  apply   writes the decided persons of a decisions file into data/persons_mentioned.json and
          data/person_items.json, and removes from data/places_curated.json the body places printed inside
          an applied person's Latin text phrases; then data/places.json is rebuilt by extract_places.py
          before extract_mentions.py runs.
  cards   the decisions research could not settle ("doubt") as a crmedr-changeset/v1 change-set of
          resolve_person ops, for the curator, with the proposal's phrases (la, it) and who. A doubt the
          curator decides comes back as a research entry to `decisions`, then `apply`.

A decisions file is {"<mrid>|<name>[#n]": {"wikidata": qid | null, "decided": "jev" | "research" | "created" |
null, "status": "reviewed" | "unresolved" | "doubt", "note"?, "candidates"?: [qid | {wikidata, label?, ...}],
"proposal": {name, n?, where, la, it, who, kind}}}. A reviewed entry needs a QID and who decided it; an
unresolved one a note; a doubt is skipped by apply. apply never overwrites an entry that differs (exit 1,
nothing written).

Usage:
  python3 mentioned_persons.py brief MM /path/to/martyrology-texts /outside/the/repo/brief-MM.json [repo_root]
  python3 mentioned_persons.py check proposals.json /path/to/martyrology-texts [repo_root]
    (exit 1, one problem per line, when a proposal fails a check)
  python3 mentioned_persons.py candidates proposals.json /outside/the/repo/candidates.json [repo_root]
  python3 mentioned_persons.py jev candidates.json /path/to/martyrology-texts /outside/the/repo/jev.json
    (Wikidata and TypeSafe answers are cached in .cache/ beside the out file; jev exits 1 after writing
    when an answer named no option offered or a request failed)
  python3 mentioned_persons.py decisions proposals.json jev.json [research.json] /outside/the/repo/decisions.json
  python3 mentioned_persons.py apply decisions.json /path/to/martyrology-texts [repo_root]
  python3 mentioned_persons.py cards decisions.json /outside/the/repo/cards.json [repo_root]

The brief, the candidates (the proposals' phrases), Jev's answers and the decisions quote the 2004 texts:
they are written only outside any git work tree.
Standard library only.
"""

import json
import re
import sys
from pathlib import Path

import build_person_items as bpi
import mentions_jev as mj
from body_places import _in_a_repository, write_json_atomic, write_text_atomic
from extract_mentions import (SCHEMA, from_file, load_edition, mentioned_wheres, source_text, where_key,
                              with_mentioned_marks)
from mentions_text import from_utf16
from extract_places import occurrences
from persons_text import mentioned_shape_errors, name_key, person_key, phrase_where
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


def internal_marks(marks, edition_sources, mrid):
    """A eulogy's marks of data/mentions.json (UTF-16 offsets) in code points, with their role."""
    return [from_file(m, source_text(edition_sources, mrid, m["where"])) | ({"role": m["role"]} if "role" in m else {})
            for m in marks]


def overlapping(a, b):
    return where_key(a["where"]) == where_key(b["where"]) and a["start"] < b["end"] and b["start"] < a["end"]


def check_proposals(proposals, sources, persons, mentions):
    """Problems in the proposals, one message each (empty when they pass)."""
    problems = []
    for mrid, items in proposals.items():
        if mrid not in sources["la"][0]:
            problems.append(f"{mrid}: not a eulogy of the Latin edition")
            continue
        known = {person_key({**p, "name": name_key(p["name"])}) for p in persons.get(mrid, [])}
        marks = {lang: internal_marks(mentions[lang].get(mrid, []), sources[lang], mrid) for lang in ("la", "it")}
        found = {"la": [], "it": []}  # (key, the proposal's marks), to check proposals against each other
        seen = set()
        for p in items:
            if not isinstance(p.get("name"), str) or not p["name"]:
                problems.append(f"{mrid}: a proposal without a name")
                continue
            key = person_key(p)
            label = f"{mrid} {key}"
            if p.get("kind") not in KINDS:
                problems.append(f"{label}: kind must be one of {KINDS}")
            if not isinstance(p.get("who"), str) or not p["who"].strip():
                problems.append(f"{label}: who is missing")
            if is_excluded(p):
                problems.append(f"{label}: excluded (Christ, the Trinity or the Virgin Mary are not marked)")
            folded = person_key({**p, "name": name_key(p["name"])})
            if folded in known:
                problems.append(f"{label}: already a person of the eulogy")
            if folded in seen:
                problems.append(f"{label}: proposed twice in the eulogy (give the second one n)")
            seen.add(folded)
            shape = mentioned_shape_errors(p)
            if shape:
                problems += [f"{mrid}: {e}" for e in shape]
                continue
            for lang in ("la", "it"):
                if not isinstance(p.get(lang), list) or (lang == "la" and not p[lang]):
                    problems.append(f"{label}: {lang} must list the printed phrases"
                                    + (" ([] if the Italian does not name them)" if lang == "it" else ""))
                    continue
                errors, new = phrase_marks(mrid, p, lang, sources[lang], marks[lang], label)
                problems += errors
                for other, theirs in found[lang]:
                    if any(overlapping(m, t) for m in new for t in theirs):
                        problems.append(f"{label}: a {lang} phrase overlaps the phrase of {other}")
                found[lang].append((key, new))
    return problems


def phrase_marks(mrid, p, lang, edition_sources, marks, label):
    """(problems, marks) of a proposal's phrases in one edition, as extract_mentions marks them among the
    eulogy's `marks` (code points): a phrase not printed in its `where`, or printed only over the mark of a
    person not mentioned, or a mark overlapping a mentioned person's mark, is a problem."""
    wheres = [w for w in mentioned_wheres(p) if any(phrase_where(p, e)[1] == w for e in p[lang])]
    missing = [w for w in wheres if source_text(edition_sources, mrid, w) is None]
    if missing:
        return [f"{label}: there is no {w!r} in the {lang} edition" for w in missing], []
    errors = []
    sources = {where_key(w): source_text(edition_sources, mrid, w) for w in wheres}
    others = [m for m in marks if not (m["kind"] == "person" and person_key(m) == person_key(p))]
    out = [m for m in with_mentioned_marks(others, [p], sources, lang, lambda k: None, {}, errors)
           if m.get("role") == "mentioned" and m["kind"] == "person" and person_key(m) == person_key(p)]
    problems = [f"{mrid}: {e} ({lang})" for e in errors]
    for m in out:
        for c in marks:
            if c["kind"] == "person" and c.get("role") == "mentioned" and overlapping(m, c):
                problems.append(f"{label}: {m['form']!r} ({lang}) overlaps the mark of the mentioned person "
                                f"{person_key(c)}")
    return problems, out


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
    """The sentence holding the person's first Latin phrase, in its `where` (subject_jev's sentences)."""
    phrase, where = phrase_where(proposal, proposal["la"][0])
    src = source_text(la_sources, mrid, where) or ""
    sentences = _sentences(src)
    if not sentences:
        return ""
    at = src.find(phrase)
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
             "latin_sentence": sentence, "latin_phrase": phrase_where(proposal, proposal["la"][0])[0],
             "italian_phrase": phrase_where(proposal, (proposal.get("it") or [None])[0])[0], "who": proposal["who"],
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


# Apply and cards

DECISION_STATUSES = ("reviewed", "unresolved", "doubt")
MENTIONED_KEYS = ("name", "n", "where", "la", "it")


def decision_problems(decisions):
    """Problems in the decisions, one message each."""
    problems = []
    for key, d in decisions.items():
        mrid, _, pkey = key.partition("|")
        prop = d.get("proposal") or {}
        if not pkey or not mrid.startswith("mr:"):
            problems.append(f"{key}: the key must be <mrid>|<name>[#n]")
        elif not isinstance(prop.get("name"), str) or person_key(prop) != pkey:
            problems.append(f"{key}: the proposal ({prop.get('name')!r}, n {prop.get('n')!r}) is not the key's person")
        status = d.get("status")
        if status not in DECISION_STATUSES:
            problems.append(f"{key}: status {status!r} is not one of {DECISION_STATUSES}")
        elif status == "reviewed":
            if not isinstance(d.get("wikidata"), str) or not bpi.QID.match(d["wikidata"]):
                problems.append(f"{key}: reviewed needs a QID, not {d.get('wikidata')!r}")
            if d.get("decided") not in bpi.DECIDED_BY:
                problems.append(f"{key}: decided {d.get('decided')!r} is not one of {bpi.DECIDED_BY}")
        elif status == "unresolved":
            if d.get("wikidata") is not None or not (d.get("note") or "").strip():
                problems.append(f"{key}: unresolved needs wikidata null and a note")
            if d.get("decided") is not None:
                problems.append(f"{key}: unresolved has no decided")
    return problems


def item_of(d):
    """The person_items.json entry of a non-doubt decision."""
    if d["status"] == "reviewed":
        out = {"wikidata": d["wikidata"], "status": "reviewed", "decided": d["decided"]}
    else:
        out = {"wikidata": None, "status": "unresolved"}
    if d.get("note"):
        out["note"] = d["note"]
    return out


def mentioned_of(proposal):
    return {k: proposal[k] for k in MENTIONED_KEYS if k in proposal}


def text_spans(proposal, la_sources, marks, mrid):
    """(start, end) of the person's Latin marks in the eulogy's text, as extract_mentions marks them among the
    eulogy's Latin `marks` (data/mentions.json): a printing over a commemorated namesake's mark is passed over.
    Footnote phrases are left out."""
    sources = {where_key(w): source_text(la_sources, mrid, w) for w in mentioned_wheres(proposal)}
    key = person_key(proposal)
    found = with_mentioned_marks(internal_marks(marks, la_sources, mrid), [proposal], sources, "la", lambda k: None,
                                 {}, [])
    return [(m["start"], m["end"]) for m in found if m["kind"] == "person" and person_key(m) == key
            and m["where"] == "text"]


def places_inside(entries, text, spans):
    """The curated place entries printed (their `occurrence`th printing) inside one of `spans` of `text`."""
    out = []
    for it in entries:
        found = occurrences(text, it["la"])
        n = it.get("occurrence") or 1
        if 1 <= n <= len(found):
            s = found[n - 1]
            if any(a <= s and s + len(it["la"]) <= b for a, b in spans):
                out.append(it)
    return out


def apply_decisions(decisions, mentioned, items, curated, la_sources, marks):
    """Add the non-doubt decisions to `mentioned` (persons_mentioned.json's document) and `items`
    (person_items.json's persons), and drop from `curated` the places inside an applied person's Latin
    text phrases. `la_sources`: the Latin (texts, footnotes); `marks`: the Latin marks by eulogy
    (data/mentions.json). A person persons_mentioned.json already lists as decided (a rerun after a partial
    apply) still gets a missing person_items.json entry. Returns (removed place lines, problems); with
    problems nothing is changed."""
    problems = decision_problems(decisions)
    if problems:
        return [], problems
    todo = {k: d for k, d in decisions.items() if d.get("status") != "doubt"}
    for key, d in todo.items():
        mrid, _, pkey = key.partition("|")
        old = (items.get(mrid) or {}).get(pkey)
        if old and old != item_of(d):
            problems.append(f"{key}: person_items.json already has {old}; it is not overwritten")
        olds = [q for q in mentioned.get(mrid, []) if person_key(q) == pkey]
        if olds and olds[0] != mentioned_of(d["proposal"]):
            problems.append(f"{key}: persons_mentioned.json already lists this person differently")
    if problems:
        return [], problems
    removed = []
    for key, d in todo.items():
        mrid, _, pkey = key.partition("|")
        p = mentioned_of(d["proposal"])
        if not any(person_key(q) == pkey for q in mentioned.get(mrid, [])):
            mentioned.setdefault(mrid, []).append(p)
        items.setdefault(mrid, {}).setdefault(pkey, item_of(d))
        if mrid in curated:
            text = la_sources[0].get(mrid, "")
            for it in places_inside(curated[mrid], text, text_spans(p, la_sources, marks.get(mrid, []), mrid)):
                curated[mrid].remove(it)
                removed.append(f"{mrid}: removed the place {it['la']!r} inside {pkey}'s name")
    return removed, []


RESEARCH_KEYS = ("wikidata", "decided", "status", "note", "candidates")


def build_decisions(proposals, jev, research):
    """The decisions file joined from the proposals (or their candidates file), Jev's choices (`jev`) and the
    research entries (`research`: {"<mrid>|<name>[#n]": {wikidata, decided, status, note?, candidates?}}, which
    override Jev). Returns (decisions, problems): a proposed person with neither an accepted Jev choice nor a
    research entry, a research entry for no proposed person, and a decision that fails decision_problems."""
    out, problems = {}, []
    for mrid, plist in proposals.items():
        for p in plist:
            key = f"{mrid}|{person_key(p)}"
            proposal = {k: v for k, v in p.items() if k != "candidates"}
            verdict_ = (jev.get(mrid) or {}).get(person_key(p)) or {}
            if key in research:
                out[key] = {k: research[key][k] for k in RESEARCH_KEYS if k in research[key]} | {"proposal": proposal}
            elif verdict_.get("accepted"):
                out[key] = {"wikidata": verdict_["choice"], "decided": "jev", "status": "reviewed",
                            "proposal": proposal}
            else:
                problems.append(f"{key}: neither an accepted Jev choice nor a research entry")
    problems += [f"{key}: a research entry for no proposed person" for key in research if key not in out]
    return out, problems + decision_problems(out)


def render_mentioned(doc):
    keys = sorted(k for k in doc if k != "$comment")
    out = {"$comment": doc["$comment"]} if "$comment" in doc else {}
    return json.dumps(out | {k: doc[k] for k in keys}, ensure_ascii=False, indent=2) + "\n"


def card_candidate(c):
    return c if isinstance(c, dict) else {"wikidata": c}


def build_cards(decisions):
    """The doubts as a change-set of resolve_person ops (`reasoning`: the research note), each with the
    proposal's printed phrases (`la`, `it`) and `who`."""
    ops = []
    for key, d in decisions.items():
        if d.get("status") != "doubt":
            continue
        mrid, _, _ = key.partition("|")
        prop = d["proposal"]
        op = {"op": "resolve_person", "id": key, "eulogy": mrid, "day": f"{mrid[3:5]}-{mrid[5:7]}",
              "name": prop["name"], **({"n": prop["n"]} if "n" in prop else {}), "where": prop["where"],
              "role": "mentioned", "who": prop.get("who"), "la": prop.get("la"), "it": prop.get("it"),
              "candidates": [card_candidate(c) for c in d.get("candidates") or []],
              "reasoning": d.get("note") or "", "decision": None, "edited": None}
        ops.append(op)
    cs = bpi.new_changeset(ops)
    cs["generated_by"] = "scripts/mentioned_persons.py"
    cs["schema"] = SCHEMA
    return cs


def apply_main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    repo_root = Path(argv[2]) if len(argv) > 2 else Path(__file__).resolve().parent.parent
    d = repo_root / "data"
    mentioned = read_json(d / "persons_mentioned.json", {})
    items_doc = read_json(d / "person_items.json")
    curated = read_json(d / "places_curated.json", {})
    marks = read_json(d / "mentions.json", {"editions": {}})["editions"].get(EDITIONS["la"], {})
    la_sources = load_edition(Path(argv[1]), EDITIONS["la"])
    decisions = read_json(argv[0])
    removed, problems = apply_decisions(decisions, mentioned, items_doc["persons"], curated, la_sources, marks)
    if problems:
        sys.exit("\n".join(problems))
    # persons_mentioned.json last: a rerun after a failed write finds its persons not yet listed.
    write_text_atomic(d / "person_items.json", bpi.render_json(items_doc["persons"]))
    if removed:
        write_text_atomic(d / "places_curated.json", json.dumps(curated, ensure_ascii=False, indent=2) + "\n")
    write_text_atomic(d / "persons_mentioned.json", render_mentioned(mentioned))
    for line in removed:
        print(line)
    print(f"applied {sum(x.get('status') != 'doubt' for x in decisions.values())} persons, "
          f"skipped {sum(x.get('status') == 'doubt' for x in decisions.values())} doubts")
    if removed:
        print("places removed from data/places_curated.json: run python3 scripts/extract_places.py "
              "../martyrology-texts to rebuild data/places.json before scripts/extract_mentions.py")


def cards_main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    repo_root = Path(argv[2]) if len(argv) > 2 else Path(__file__).resolve().parent.parent
    out = outside_git(Path(argv[1]), repo_root)
    decisions = read_json(argv[0])
    problems = decision_problems(decisions)
    if problems:
        sys.exit("\n".join(problems))
    cs = build_cards(decisions)
    write_json_atomic(out, cs)
    print(f"{len(cs['operations'])} person cards in {out}")


def decisions_main(argv):
    if len(argv) not in (3, 4):
        sys.exit(__doc__)
    out = outside_git(Path(argv[-1]), Path(__file__).resolve().parent.parent)
    research = read_json(argv[2]) if len(argv) == 4 else {}
    doc, problems = build_decisions(read_json(argv[0]), read_json(argv[1]), research)
    if problems:
        sys.exit("\n".join(problems))
    write_json_atomic(out, doc)
    print(f"wrote {len(doc)} decisions ({sum(d['status'] == 'doubt' for d in doc.values())} doubts) to {out}")


def main(argv):
    if len(argv) < 3 or argv[0] not in ("brief", "check", "candidates", "jev", "decisions", "apply", "cards"):
        sys.exit(__doc__)
    if argv[0] in ("decisions", "apply", "cards"):
        return {"decisions": decisions_main, "apply": apply_main, "cards": cards_main}[argv[0]](argv[1:])
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
