#!/usr/bin/env python3
"""Jev suggestions on the subject-identity review cards: `rename` ops and `resolve_person` ops.

`suggest` writes `jev` on every card whose answer reaches the threshold (the picked option's
probability), and removes it from the others: on a rename {decision: accept|edit, new_id for an
edit, probability, confidence, model, flags, scores: {new_id: clarity score}}; on a person card
{decision: accept|edit|reject, wikidata and source on accept and edit, reason for a reject, kind,
probability, confidence, model, flags ["kind:<kind>"] on an item picked for a name Jev reads as
other than a person}. A record field Jev doubts writes {flags: ["record:places[0]", ...], model,
scores} and no suggestion: the curator checks the record first. `jev` is kept apart from `suggested` (verify-suggestions' own,
which the curator's tool and `apply` read). Nothing here writes `decision` or `edited`.

`evaluate` compares the suggestions with decided change-sets and prints, per question family
(rename, person), the agreement at each threshold. Answers are cached in .cache/typesafe/ (git
ignored), so a re-run asks nothing already asked. The change-sets quote the 2004 texts: `suggest`
refuses one inside any git work tree. See docs/superpowers/specs/2026-10-18-subject-identity-design.md.

Usage:
  python3 suggest_subjects.py suggest <changeset.json> <records.json> /path/to/martyrology-texts
                                      [--persons] [--month MM] [--min-confidence X] [--repo repo_root]
  python3 suggest_subjects.py evaluate <decided.json>... --records <records.json>
                                      /path/to/martyrology-texts [--repo repo_root]

--persons asks only the person cards; --month MM only the cards of that month's eulogies. The key: TYPESAFE_API_KEY, else ~/.config/typesafe/api_key.
Standard library only.
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import mentions_jev as mj
import subject_jev as sj
from body_places import _in_a_repository
from extract_places import EDITION_EN, EDITION_IT
from extract_typology import latin_texts, load_texts
from rename_candidates import _record_of
from subject_records import person_record

# Until the January evaluation (the spec's "5. Evaluation"): the threshold of the mention suggestions.
DEFAULT_MIN_CONFIDENCE = 0.9
THRESHOLDS = [round(0.1 * i, 2) for i in range(10)] + [0.95]
DECIDED = ("auto", "reviewed")


def load_data(repo_root, texts_repo):
    repo_root, texts_repo = Path(repo_root), Path(texts_repo)
    read = lambda *p: json.loads(repo_root.joinpath(*p).read_text(encoding="utf-8"))  # noqa: E731
    entries = read("data", "martyrology_ids.json")["entries"]
    return {"la": latin_texts(entries, load_texts(texts_repo)),
            "en": latin_texts(entries, load_texts(texts_repo, EDITION_EN)),
            "it": latin_texts(entries, load_texts(texts_repo, EDITION_IT)),
            "labels": {lang: read("i18n", f"{lang}.json") for lang in ("en", "it")},
            "items": read("data", "person_items.json")["persons"]}


def index_records(records):
    """The records by eulogy ID."""
    out = defaultdict(list)
    for r in records:
        out[r["id"]].append(r)
    return dict(out)


def read_records(path):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    return index_records(doc["records"] if isinstance(doc, dict) else doc)


def family(op):
    return {"rename": "rename", "resolve_person": "person"}.get(op.get("op"))


def record_for(op, records):
    """A rename's record: the one whose name is the slug's token (as rename_candidates builds it);
    a person card's: its own (name and n), else the kind of its eulogy's only record
    (subject_records.person_record, as build_person_items.expand matches it)."""
    if family(op) == "rename":
        group = records.get(op["id"])
        return _record_of(op["id"], group) if group else None
    return person_record(records.get(op["eulogy"], []), op["name"], op.get("n"))


def companions(op, items):
    """The person card's companions, each with its decided item when there is one."""
    decided = items.get(op["eulogy"], {})
    out = []
    for name in op.get("companions", []):
        e = decided.get(name) or {}
        out.append({"name": name, **({"wikidata": e["wikidata"]} if e.get("status") in DECIDED
                                     and e.get("wikidata") else {})})
    return out


def request_for(op, data, records):
    """(request, record) for one card; (None, None) when it cannot be asked: a rename without a
    record, a card without candidates, or a eulogy without its Latin text."""
    if family(op) is None or not op.get("candidates"):
        return None, None
    record = record_for(op, records)
    if family(op) == "rename":
        mrid = op["id"]
        la_text = data["la"].get(mrid)
        if record is None or not la_text:
            return None, None
        labels = data["labels"]
        vernacular = sj.vernacular_clause(data["en"].get(mrid), labels["en"].get(mrid),
                                          data["it"].get(mrid), labels["it"].get(mrid))
        return sj.rename_request(op, record, sj.clause(la_text, record), vernacular), record
    la_text = data["la"].get(op["eulogy"])
    if not la_text:
        return None, None
    la_clause = sj.clause(la_text, record or {"name": op["name"]})
    return sj.person_request(op, record, la_clause, companions(op, data["items"])), record


def eulogy(op):
    return op["id"] if family(op) == "rename" else op["eulogy"]


def in_scope(op, persons, month=None):
    if month and eulogy(op)[3:5] != month:
        return False
    return family(op) == "person" if persons else family(op) is not None


def ask_op(op, data, records, client):
    """(suggestion before any threshold, flagged, error); all None when the card cannot be asked.
    flagged: the `jev` of a rename whose record Jev doubts, {flags, model, scores}, else None.
    A refused key is raised: the run stops."""
    body, record = request_for(op, data, records)
    if body is None:
        return None, None, None
    try:
        response = client.ask(body)
    except mj.KeyRefused:
        raise
    except mj.TypeSafeError as e:
        return None, None, str(e)
    answers, model = response.get("answers") or {}, response.get("model", mj.MODEL)
    flagged = None
    if family(op) == "rename":
        flags = sj.record_flags(answers)
        if flags:
            flagged = {"flags": flags, "model": model, "scores": sj.clarity_scores(op, answers)}
        s = sj.rename_suggestion(op, answers, record, model)
    else:
        s = sj.person_suggestion(op, answers, model)
    error = None if s or flagged else "the answer named no option the request offered"
    return s, flagged, error


def require_key(ops, data, records, client):
    """Stop before any card changes when there is no key and some card's request is not cached."""
    if getattr(client, "key", True):
        return
    for op in ops:
        body, _ = request_for(op, data, records)
        if body is not None and not client.cached(body):
            raise mj.TypeSafeError("no TypeSafe key: set TYPESAFE_API_KEY or write ~/.config/typesafe/api_key")


def suggest_ops(ops, data, records, client, min_confidence, persons=False, month=None):
    scope = [op for op in ops if in_scope(op, persons, month)]
    require_key(scope, data, records, client)
    counts = {"suggested": 0, "below": 0, "flagged": 0, "skipped": len(ops) - len(scope), "errors": 0}
    for op in scope:
        s, flagged, error = ask_op(op, data, records, client)
        if s is None and flagged is None and error is None:
            counts["skipped"] += 1
            continue
        op.pop("jev", None)
        if error:
            counts["errors"] += 1
            print(f"no suggestion: {op['id']}: {error}", file=sys.stderr)
        elif s and s["probability"] >= min_confidence:
            op["jev"] = s
            counts["suggested"] += 1
        elif flagged:
            op["jev"] = flagged
            counts["flagged"] += 1
        else:
            counts["below"] += 1
    return counts


def curator_outcome(op):
    """What the curator's decision applies: the new ID of a rename, the item of a person card (an
    accept falls back to `suggested`, then to the first candidate, as `apply` does); None for a
    reject."""
    decision, edited = op.get("decision"), op.get("edited") or {}
    if decision == "reject":
        return None
    if family(op) == "rename":
        return edited.get("new_id") if decision == "edit" else op.get("new_id")
    if decision == "edit":
        return edited.get("wikidata")
    return sj.preselected(op)


def suggested_outcome(op, s):
    """What taking Jev's suggestion would apply, in curator_outcome's terms."""
    if s["decision"] == "reject":
        return None
    if family(op) == "person":
        return s["wikidata"]
    return s["new_id"] if s["decision"] == "edit" else op.get("new_id")


def evaluate_ops(ops, data, records, client):
    decided = [op for op in ops if family(op) and op.get("decision") in ("accept", "reject", "edit")]
    require_key(decided, data, records, client)
    rows = []
    for op in decided:
        s, flagged, error = ask_op(op, data, records, client)
        if s is None and flagged is None and error is None:
            continue
        row = {"id": op["id"], "family": family(op), "decided": curator_outcome(op),
               "suggested": s and {"outcome": suggested_outcome(op, s), "probability": s["probability"],
                                   "confidence": s["confidence"]}}
        if flagged:
            row["flags"] = flagged["flags"]
        if error:
            row["error"] = error
        rows.append(row)
    return rows


def _show(outcome):
    return outcome if outcome is not None else "none"


def report(rows, thresholds):
    out = []
    by_family = defaultdict(list)
    for r in rows:
        by_family[r["family"]].append(r)
    for name, rs in [("all", rows)] + sorted(by_family.items()):
        flagged = sum(1 for r in rs if r.get("flags"))
        out.append(f"{name}: {len(rs)} cards" + (f", {flagged} with record flags" if flagged else ""))
        for t in thresholds:
            covered = [r for r in rs if r["suggested"] and r["suggested"]["probability"] >= t]
            agree = [r for r in covered if r["suggested"]["outcome"] == r["decided"]]
            share = round(100 * len(covered) / len(rs)) if rs else 0
            line = f"  ≥{t:.2f}: {len(covered)} suggested ({share}%)"
            if covered:
                line += f", {len(agree)} agree ({round(100 * len(agree) / len(covered))}%)"
            out.append(line)
    failed = [r for r in rows if r.get("error")]
    if failed:  # scored as no suggestion above: the coverage is lower than the model's
        out.append("errors:")
        out += [f"  {r['id']}: {r['error']}" for r in failed]
    out.append("disagreements:")
    for r in rows:
        s = r["suggested"]
        if s and s["outcome"] != r["decided"]:
            out.append(f"  {r['id']}: decided {_show(r['decided'])}, suggested {_show(s['outcome'])} "
                       f"p={s['probability']} c={s['confidence']}")
    return "\n".join(out)


def _args(argv):
    flags, files = {}, []
    it = iter(argv)
    for a in it:
        if a == "--min-confidence":
            flags["min"] = float(next(it))
        elif a == "--repo":
            flags["repo"] = next(it)
        elif a == "--records":
            flags["records"] = next(it)
        elif a == "--persons":
            flags["persons"] = True
        elif a == "--month":
            flags["month"] = next(it, "")
        else:
            files.append(a)
    return flags, files


def main(argv):
    if not argv or argv[0] not in ("suggest", "evaluate"):
        sys.exit(__doc__)
    flags, files = _args(argv[1:])
    repo = Path(flags.get("repo") or Path(__file__).resolve().parent.parent)
    if argv[0] == "suggest":
        if len(files) != 3:
            sys.exit(__doc__)
        path, records_path, texts_repo = (Path(f) for f in files)
        if "month" in flags and not re.fullmatch(r"0[1-9]|1[0-2]", flags["month"]):
            sys.exit(f"--month {flags['month']}: expected MM (e.g. 01)")
        if _in_a_repository(path, repo):
            sys.exit(f"{path}: a change-set quotes the 2004 edition; keep it outside the repository")
    else:
        if len(files) < 2 or "records" not in flags:
            sys.exit(__doc__)
        records_path, texts_repo = Path(flags["records"]), Path(files[-1])
    data = load_data(repo, texts_repo)
    records = read_records(records_path)
    client = mj.TypeSafe(mj.api_key(), repo / ".cache" / "typesafe")
    try:
        if argv[0] == "suggest":
            doc = json.loads(path.read_text(encoding="utf-8"))
            counts = suggest_ops(doc["operations"], data, records, client,
                                 flags.get("min", DEFAULT_MIN_CONFIDENCE), flags.get("persons", False),
                                 flags.get("month"))
            path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            print(f"{path}: {counts}")
            return
        ops = [op for f in files[:-1] for op in json.loads(Path(f).read_text(encoding="utf-8"))["operations"]]
        print(report(evaluate_ops(ops, data, records, client), THRESHOLDS))
    except mj.TypeSafeError as e:  # a refused key, or no key with requests to make: nothing written
        sys.exit(str(e))


if __name__ == "__main__":
    main(sys.argv[1:])
