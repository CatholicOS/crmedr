#!/usr/bin/env python3
"""Jev suggestions on the Italian person-mention review cards (CatholicOS/crmedr#97).

`suggest` writes `suggested` ({decision, start/end/form for an edit, probability, confidence,
model}) on every in-scope card of a review change-set whose answer reaches the threshold, and
removes it from the others; it never touches `decision` or `edited`. `evaluate` compares the
suggestions with decided change-sets and prints, per kind, the agreement at each threshold.
Answers are cached in .cache/typesafe/, so a re-run asks nothing already asked. The change-sets
quote the 2004 text: keep them outside the repository. See
docs/superpowers/specs/2026-10-15-jev-mention-suggestions-design.md.

Usage:
  python3 suggest_mentions.py suggest <review.json> [--min-confidence X] [--repo repo_root]
  python3 suggest_mentions.py evaluate <decided.json>... [--weak <decided.json>...] [--repo repo_root]

The key: TYPESAFE_API_KEY, else ~/.config/typesafe/api_key. Standard library only.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

import mentions_jev as mj
from mentions_italian import ItalianNames

# Set from the evaluation (docs/superpowers/specs/2026-10-15-jev-mention-suggestions-design.md):
# 1.0 suggests nothing until then.
DEFAULT_MIN_CONFIDENCE = 1.0
THRESHOLDS = [round(0.1 * i, 2) for i in range(10)] + [0.95]


def _read(path, default=None):
    return json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else default


def load_data(repo_root):
    data = Path(repo_root) / "data"
    mentions = _read(data / "mentions.json")["editions"]
    return {"persons": _read(data / "persons.json")["editions"]["martyrologium_romanum_2004"],
            "latin": mentions["martyrologium_romanum_2004"],
            "italian": mentions[mj.ITALIAN],
            "names": ItalianNames(_read(Path(repo_root) / "i18n" / "la.json", {}),
                                  _read(Path(repo_root) / "i18n" / "it.json", {}))}


def ask_card(op, data, client):
    """The card's suggestion before any threshold, and an error message; (None, None) when the card
    is out of scope or has no candidate. A refused key is raised: the run stops."""
    mrid = op["eulogy"]
    body, cands = mj.request_for(op, data["persons"].get(mrid, []), data["latin"].get(mrid, []),
                                 data["italian"].get(mrid, []), data["names"])
    if body is None:
        return None, None
    try:
        response = client.ask(body)
    except mj.KeyRefused:
        raise
    except mj.TypeSafeError as e:
        return None, str(e)
    question = next(iter(body["questions"]))
    s = mj.suggestion(op, (response.get("answers") or {}).get(question), cands, response.get("model", mj.MODEL))
    return s, None if s else "the answer named no option the request offered"


def suggest_ops(ops, data, client, min_confidence):
    counts = {"suggested": 0, "below": 0, "skipped": 0, "errors": 0}
    for op in ops:
        if mj.card_kind(op) is None:
            counts["skipped"] += 1
            continue
        s, error = ask_card(op, data, client)
        op.pop("suggested", None)
        if error:
            counts["errors"] += 1
            print(f"no suggestion: {op['id']}: {error}", file=sys.stderr)
        elif s is None:
            counts["skipped"] += 1
        elif s["confidence"] >= min_confidence:
            op["suggested"] = s
            counts["suggested"] += 1
        else:
            counts["below"] += 1
    return counts


def curator_decision(op):
    decision, edited = op.get("decision"), op.get("edited") or {}
    if decision == "edit":
        span = (edited.get("start"), edited.get("end"))
        return ("accept",) if span == (op.get("start"), op.get("end")) else ("edit", *span)
    return (decision,)


def _suggested(s):
    if s is None:
        return None
    return ("edit", s["start"], s["end"]) if s["decision"] == "edit" else (s["decision"],)


def evaluate_ops(ops, data, client):
    rows = []
    for op in ops:
        kind = mj.card_kind(op)
        if kind is None or op.get("decision") not in ("accept", "reject", "edit"):
            continue
        s, _ = ask_card(op, data, client)
        rows.append({"id": op["id"], "kind": kind, "decision": curator_decision(op), "suggested": s})
    return rows


def report(rows, thresholds):
    out = []
    by_kind = defaultdict(list)
    for r in rows:
        by_kind[r["kind"]].append(r)
    for kind, rs in [("all", rows)] + sorted(by_kind.items()):
        out.append(f"{kind}: {len(rs)} cards")
        for t in thresholds:
            covered = [r for r in rs if r["suggested"] and r["suggested"]["confidence"] >= t]
            agree = [r for r in covered if _suggested(r["suggested"]) == r["decision"]]
            share = round(100 * len(covered) / len(rs)) if rs else 0
            line = f"  ≥{t:.2f}: {len(covered)} suggested ({share}%)"
            if covered:
                line += f", {len(agree)} agree ({round(100 * len(agree) / len(covered))}%)"
            out.append(line)
    out.append("disagreements:")
    for r in rows:
        if r["suggested"] and _suggested(r["suggested"]) != r["decision"]:
            out.append(f"  {r['id']}: decided {r['decision']}, suggested {_suggested(r['suggested'])} "
                       f"p={r['suggested']['probability']} c={r['suggested']['confidence']}")
    return "\n".join(out)


def _args(argv):
    flags, files, weak, target = {}, [], [], None
    it = iter(argv)
    for a in it:
        if a == "--min-confidence":
            flags["min"] = float(next(it))
        elif a == "--repo":
            flags["repo"] = next(it)
        elif a == "--weak":
            target = weak
        else:
            (target if target is not None else files).append(a)
    return flags, files, weak


def main(argv):
    if not argv or argv[0] not in ("suggest", "evaluate"):
        sys.exit(__doc__)
    flags, files, weak = _args(argv[1:])
    if not files:
        sys.exit(__doc__)
    repo = Path(flags.get("repo") or Path(__file__).resolve().parent.parent)
    data = load_data(repo)
    client = mj.TypeSafe(mj.api_key(), repo / ".cache" / "typesafe")
    try:
        if argv[0] == "suggest":
            path = Path(files[0])
            doc = json.loads(path.read_text(encoding="utf-8"))
            counts = suggest_ops(doc["operations"], data, client, flags.get("min", DEFAULT_MIN_CONFIDENCE))
            path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"{path}: {counts}")
            return
        strict = [op for f in files for op in json.loads(Path(f).read_text(encoding="utf-8"))["operations"]]
        strict_ids = {op["id"] for op in strict}
        weak_ops = [op for f in weak for op in json.loads(Path(f).read_text(encoding="utf-8"))["operations"]
                    if op["id"] not in strict_ids]
        print("== strict (the curator's decisions)")
        print(report(evaluate_ops(strict, data, client), THRESHOLDS))
        if weak_ops:
            print("== weak (decided by the curator's rules)")
            print(report(evaluate_ops(weak_ops, data, client), THRESHOLDS))
    except mj.KeyRefused as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main(sys.argv[1:])
