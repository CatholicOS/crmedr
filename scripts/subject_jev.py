"""Jev (TypeSafe System One) requests and suggestions on the subject-identity review cards: the
`rename` ops (ranked rename candidates) and the `resolve_person` ops (Wikidata candidates); see
docs/superpowers/specs/2026-10-18-subject-identity-design.md, "3. Jev judgments".

One request per card, its questions asked together. Jev checks the identity record against the
printed clause, judges how clearly each rename candidate names the saint and picks one, and picks
the Wikidata item. Code owns the rules: every candidate already follows them, and a suggestion is
only ever shown to the curator. Only one clause of the 2004 Latin (and of the English or Italian)
is sent, never a whole eulogy (the curator's ruling, 2026-10-18).

Standard library only.
"""

import re

from gazetteer_text import fold
from mentions_jev import MODEL
from subject_records import GRAMMAR

MAX_CLAUSE = 400
FIELD_MIN = 0.5  # a record field Jev doubts below this goes to the curator flagged, without a suggestion

GRAMMAR_CRITERIA = {
    "adjective-person": ("An adjective agreeing with the subject or with the subject's role "
                         "(\"abbatis Condatiscensis\", of an abbot)."),
    "adjective-noun": ("An adjective agreeing with another noun, such as a monastery, a church or a city "
                       "(\"in monasterio Bodacensi\")."),
    "locative": "A locative: the place where the subject died, was buried or lived (\"Romae\", \"Mediolani\").",
    "genitive": "The genitive of a place noun depending on another word (\"in territorio Lugduni\").",
    "ablative": "A place noun in the ablative, usually after a preposition (\"in Hispania\", \"ex Africa\").",
}
assert set(GRAMMAR_CRITERIA) == set(GRAMMAR)

PLACE_KIND_WORDS = {"see": "see (the city of which they were bishop)", "monastery": "monastery",
                    "death": "place of death", "burial": "place of burial", "cult": "place of cult",
                    "origin": "place of origin"}

CLARITY = [
    "a reader could not tell which saint is meant",
    "it narrows the saint down but other saints of the corpus could fit",
    "it names this saint, but not in the way readers usually know them",
    "the name readers would recognise, and no other saint of the corpus could be meant",
]

KIND_CRITERIA = {
    "person": "One real person, a saint or blessed, who can have a Wikidata item of their own.",
    "celebration_or_title": ("A feast, a mystery or a title (of the Lord, of the Virgin Mary, of a church), "
                             "not one person."),
    "anonymous_group": "A group of martyrs or saints named together, without names of their own.",
    "not_identifiable": "A person the clause does not say enough about to tell who they were.",
}

HONORIFIC = re.compile(r"^(?:(?:saints?|st\.?|blessed|venerable|san|santo|santa|santi|sante|beat[oaie])\s+|sant')")


# The clauses sent

def _nth(text, printed, occurrence):
    at = -1
    for _ in range(occurrence + 1):
        at = text.find(printed, at + 1)
        if at < 0:
            return None
    return at


def _sentences(text):
    """(start, sentence) of each sentence of `text`, split after each "." and ";"."""
    return [(m.start(), m.group()) for m in re.finditer(r"[^.;]+[.;]?", text) if m.group().strip()]


def _window(sentence, at):
    """The sentence, stripped; at most MAX_CLAUSE characters around the index `at` within it."""
    lead = len(sentence) - len(sentence.lstrip())
    sentence, at = sentence.strip(), max(0, at - lead)
    if len(sentence) <= MAX_CLAUSE:
        return sentence
    start = max(0, min(at - MAX_CLAUSE // 2, len(sentence) - MAX_CLAUSE))
    return sentence[start:start + MAX_CLAUSE]


def _name_stem(name):
    word = fold(name or "").split(" ")[0]
    return word[:-2] if len(word) > 4 else word


def clause(la_text, record):
    """The sentence of `la_text` holding the record's first cited form (its earliest role or place
    in print order); without one, the first sentence holding a word of the record's name; else the
    first sentence. At most MAX_CLAUSE characters."""
    found = []
    for item in (record.get("roles") or []) + (record.get("places") or []):
        printed, occ = item.get("printed"), item.get("occurrence")
        if isinstance(printed, str) and printed and isinstance(occ, int):
            at = _nth(la_text, printed, occ)
            if at is not None:
                found.append(at)
    sentences = _sentences(la_text)
    if not sentences:
        return ""
    if found:
        at = min(found)
        start, sentence = next((s, t) for s, t in reversed(sentences) if s <= at)
        return _window(sentence, at - start)
    stem = _name_stem(record.get("name"))
    for _, sentence in sentences:
        if stem and any(w.startswith(stem) for w in re.findall(r"\w+", fold(sentence))):
            return _window(sentence, 0)
    return _window(sentences[0][1], 0)


def bare_name(label):
    """The first name of a vernacular subject, folded, without its honorific ("Saint Basil" -> "basil")."""
    s = fold(label or "")
    while m := HONORIFIC.match(s):
        s = s[m.end():]
    words = re.findall(r"\w+", s)
    return words[0] if words else ""


def _sentence_naming(text, label):
    name = bare_name(label)
    if not name:
        return None
    for _, sentence in _sentences(text or ""):
        if re.search(rf"\b{re.escape(name)}\b", fold(sentence)):
            return _window(sentence, 0)
    return None


def vernacular_clause(en_text, en_label, it_text, it_label):
    """The sentence of the English text naming the English subject's name, else that of the Italian;
    "" when neither names it."""
    return _sentence_naming(en_text, en_label) or _sentence_naming(it_text, it_label) or ""


# Rename cards

def _record_state(record):
    """What Jev reads of a record: its claims and the printed words, not its grammar labels."""
    out = {k: record.get(k) for k in ("name", "kind", "feminine", "surname")}
    if record.get("cognomen"):
        out["cognomen"] = record["cognomen"].get("value")
    out["roles"] = [{"role": r.get("role"), "printed": r.get("printed")} for r in record.get("roles") or []]
    out["places"] = [{k: p.get(k) for k in ("kind", "printed", "nominative", "adjective", "en") if p.get(k)}
                     for p in record.get("places") or []]
    return out


def _candidate_ids(cands, prefix):
    return [f"{prefix}{i}" for i in range(len(cands))]


def rename_request(op, record, la_clause, vernacular):
    """The request for one rename card: the record check, the place grammar, a clarity score per
    candidate (c0..cN, in op order) and the pick among them."""
    ids = _candidate_ids(op["candidates"], "c")
    state = {"eulogy": op["id"], "subject_la": op.get("subject_la"), "clause": la_clause,
             "vernacular_clause": vernacular, "record": _record_state(record),
             "candidates": {cid: {"new_id": c["new_id"], "category": c["category"], "labels": c.get("labels")}
                            for cid, c in zip(ids, op["candidates"])}}
    questions = {}
    for i, _ in enumerate(record.get("places") or []):
        questions[f"place_grammar_{i}"] = {
            "type": "choice",
            "instructions": (f"How does `clause` print the place `record.places[{i}].printed`, a place of the "
                             "subject of `clause`?"),
            "criteria": GRAMMAR_CRITERIA}
    for i, _ in enumerate(record.get("roles") or []):
        questions[f"field_roles_{i}"] = {
            "type": "noul",
            "instructions": (f"Does `clause` say that the subject was `record.roles[{i}].role` (printed there as "
                             f"`record.roles[{i}].printed`)?")}
    for i, p in enumerate(record.get("places") or []):
        kind = PLACE_KIND_WORDS.get(p.get("kind"), "place")
        questions[f"field_places_{i}"] = {
            "type": "noul",
            "instructions": (f"Does `clause` say that `record.places[{i}].nominative` (printed there as "
                             f"`record.places[{i}].printed`) is the subject's {kind}?")}
    for cid in ids:
        questions[f"clarity_{cid}"] = {
            "type": "score",
            "instructions": (f"How clearly and conventionally does the ID `candidates.{cid}.new_id`, with its "
                             f"labels `candidates.{cid}.labels`, name the subject of `clause` among all the saints "
                             "of the Roman Martyrology?"),
            "criteria": CLARITY}
    questions["pick"] = {
        "type": "choice",
        "instructions": ("Every one of the `candidates` follows the ID rules. Which is the best ID for the subject "
                         "of `clause`: the name readers would recognise, that no other saint of the Roman "
                         "Martyrology could be meant by?"),
        "criteria": {cid: f"`candidates.{cid}`: {c['new_id']} ({c['category']})"
                     for cid, c in zip(ids, op["candidates"])}}
    return {"model": MODEL, "state": state, "questions": questions}


FIELD = re.compile(r"field_(roles|places)_(\d+)")


def record_flags(answers):
    """"record:<field>" for each record field whose noul is below FIELD_MIN, in question order."""
    out = []
    for q, a in (answers or {}).items():
        m = FIELD.fullmatch(q)
        if m and isinstance(a, dict) and a.get("type") == "noul" and isinstance(a.get("noul"), (int, float)) \
                and a["noul"] < FIELD_MIN:
            out.append(f"record:{m.group(1)}[{m.group(2)}]")
    return out


def grammar_flags(record, answers):
    """"grammar:places[i]:<Jev's choice>" for each place whose grammar Jev reads otherwise."""
    out = []
    for i, p in enumerate((record or {}).get("places") or []):
        a = (answers or {}).get(f"place_grammar_{i}")
        if isinstance(a, dict) and a.get("type") == "choice" and a.get("choice") in GRAMMAR \
                and a["choice"] != p.get("grammar"):
            out.append(f"grammar:places[{i}]:{a['choice']}")
    return out


def clarity_scores(op, answers):
    """{new_id: Jev's clarity score} of each rename candidate with a score answer."""
    ids = _candidate_ids(op["candidates"], "c")
    out = {}
    for cid, c in zip(ids, op["candidates"]):
        a = (answers or {}).get(f"clarity_{cid}")
        if isinstance(a, dict) and a.get("type") == "score" and isinstance(a.get("score"), (int, float)):
            out[c["new_id"]] = a["score"]
    return out


def _choice(answer, ids):
    """(pick, probability, confidence) of a choice answer naming one of `ids`; None otherwise."""
    if not isinstance(answer, dict) or answer.get("type") != "choice":
        return None
    pick, probabilities = answer.get("choice"), answer.get("probabilities")
    if not isinstance(pick, str) or pick not in ids or not isinstance(probabilities, dict):
        return None
    probability, confidence = probabilities.get(pick), answer.get("confidence")
    if not _number(probability):
        return None
    return pick, round(probability, 4), round(confidence if _number(confidence) else 0.0, 4)


def _number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def rename_suggestion(op, answers, record=None, model=MODEL):
    """The rename card's suggestion: accept (Jev picks the op's new_id), edit (another candidate),
    or None when the pick is not a request id or a record field is doubted (see record_flags).
    It carries the grammar flags and the clarity scores."""
    if record_flags(answers):
        return None
    ids = _candidate_ids(op["candidates"], "c")
    chosen = _choice((answers or {}).get("pick"), ids)
    if chosen is None:
        return None
    pick, probability, confidence = chosen
    cand = op["candidates"][ids.index(pick)]
    out = {"decision": "accept" if cand["new_id"] == op["new_id"] else "edit"}
    if out["decision"] == "edit":
        out["new_id"] = cand["new_id"]
    out.update(probability=probability, confidence=confidence, model=model, flags=grammar_flags(record, answers),
               scores=clarity_scores(op, answers))
    return out


# Person cards

def _person_candidate(c):
    out = {k: c.get(k) for k in ("wikidata", "label", "description", "born", "died", "feast") if c.get(k)}
    out["names"] = (c.get("names") or [])[:5]
    out["evidence"] = c.get("evidence") or []
    out["places"] = [{k: v for k, v in p.items() if k != "qid"} for p in c.get("places") or []]
    out["place_labels"] = c.get("place_labels") or {}
    return out


def person_request(op, record, la_clause, companions):
    """The request for one person card: what the name stands for, and the item among the candidates
    (q0..qN, in op order) or none. `companions`: [{name, wikidata?}] with their decided items."""
    ids = _candidate_ids(op["candidates"], "q")
    state = {"eulogy": op["eulogy"], "day": op.get("day"), "typology": op.get("typology"), "name": op["name"]}
    if op.get("n"):
        state["n"] = op["n"]
    state["clause"] = la_clause
    if record:
        state["record"] = _record_state(record)
        if record.get("death_year") is not None:
            state["record"]["death_year"] = record["death_year"]
    state["companions"] = companions
    state["places"] = [{"role": p["role"], "label": p["label"]} for p in op.get("places") or []]
    state["candidates"] = {qid: _person_candidate(c) for qid, c in zip(ids, op["candidates"])}
    criteria = {qid: f"`candidates.{qid}`: {c['wikidata']} {c.get('label', '')}".rstrip()
                + (f" ({c['description']})" if c.get("description") else "")
                for qid, c in zip(ids, op["candidates"])}
    criteria["none"] = "None of these items is this person."
    return {"model": MODEL, "state": state, "questions": {
        "kind": {"type": "choice",
                 "instructions": "What does `name` stand for in `clause`, a eulogy of the Roman Martyrology for `day`?",
                 "criteria": KIND_CRITERIA},
        "item": {"type": "choice",
                 "instructions": ("Which of the `candidates` (Wikidata items) is the person `name` of `clause`? "
                                  "Weigh the day of the eulogy (`day`, a day of death when `typology` is "
                                  "dies_natalis), the `record`, and the `companions` named with them with their "
                                  "decided items. Answer none if no candidate is this person."),
                 "criteria": criteria}}}


def preselected(op):
    """The item a person card's accept applies, exactly as build_person_items._resolve applies it:
    verify-suggestions' `suggested`, else the first candidate; None without either."""
    cands = op.get("candidates") or []
    return (op.get("suggested") or {}).get("wikidata") or (cands[0]["wikidata"] if cands else None)


def person_suggestion(op, answers, model=MODEL):
    """The person card's suggestion: accept (Jev picks the item an accept applies), edit (another
    candidate); both carry the picked `wikidata` and its `source`, and flags ["kind:<kind>"] when
    Jev reads the name as other than a person; reject (none, or kind not_identifiable); None when
    the pick is not a request id."""
    answers = answers or {}
    kind = _choice(answers.get("kind"), KIND_CRITERIA)
    base = {"model": model}
    if kind:
        base["kind"] = kind[0]
    if kind and kind[0] == "not_identifiable":
        return {"decision": "reject", "reason": "Jev: the clause does not say who this person was",
                "probability": kind[1], "confidence": kind[2], **base}
    ids = _candidate_ids(op["candidates"], "q")
    chosen = _choice(answers.get("item"), ids + ["none"])
    if chosen is None:
        return None
    pick, probability, confidence = chosen
    base.update(probability=probability, confidence=confidence)
    if pick == "none":
        return {"decision": "reject", "reason": "Jev: none of the candidates is this person", **base}
    cand = op["candidates"][ids.index(pick)]
    decision = "accept" if cand["wikidata"] == preselected(op) else "edit"
    out = {"decision": decision, "wikidata": cand["wikidata"], "source": cand.get("source", "search"), **base}
    if base.get("kind", "person") != "person":
        out["flags"] = [f"kind:{base['kind']}"]
    return out
