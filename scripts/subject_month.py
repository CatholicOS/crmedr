#!/usr/bin/env python3
"""Rebuild a month's subject-identity cards, keeping the curator's decisions.

`merge` takes the month's change-set as it stands (old) and a freshly built one (rebuilt) and
writes a change-set with the rebuilt header and these operations: the old ones in the old order,
each kept as it was when decided (`decision` set, any value, or `prefilled`) and otherwise
replaced by its rebuilt version; then the rebuilt operations new to the month, in rebuilt order.
An undecided old operation the rebuilt file no longer has is dropped and named in the notes; a
decided one that is missing raises ValueError (nothing is written). Operations are keyed by
`uid`, else `id`.

A eulogy's relabel follows its rename when the rename is kept decided: the rebuilt relabel (when
the old one is not kept decided) proposes the labels of the candidate the rename's decision chose
(an accept's new_id, an edit's edited.new_id; a reject, the current labels), that candidate first
among its candidates. A chosen candidate without labels leaves the rebuilt relabel as it is, in a
note. The change-set quotes the 2004 edition: the output is refused inside a git tree.

Usage:
  python3 subject_month.py merge <old.json> <rebuilt.json> <out.json> [--repo repo_root]
"""
import json
import sys
from pathlib import Path

from body_places import _in_a_repository


def _key(op):
    return op.get("uid") or op["id"]


def _decided(op):
    return op.get("decision") is not None or bool(op.get("prefilled"))


def _chosen_labels(rename, relabel):
    """The labels the rename's decision chose, a None language filled from the relabel's current
    ones (as rename_candidates.relabel_op fills them): (labels, new_id), new_id None for a
    reject; (None, new_id) when that candidate has no labels."""
    current = relabel.get("current") or {}
    decision = rename.get("decision")
    if decision == "reject":
        return current, None
    new_id = (rename.get("edited") or {}).get("new_id") if decision == "edit" else rename.get("new_id")
    labels = next((c.get("labels") for c in rename.get("candidates") or [] if c.get("new_id") == new_id), None)
    if not labels or all(v is None for v in labels.values()):
        return None, new_id
    return {lang: labels.get(lang) if labels.get(lang) is not None else current.get(lang)
            for lang in dict.fromkeys(list(current) + list(labels))}, new_id


def _follow(rename, relabel, notes):
    """The rebuilt relabel proposing what its kept decided rename chose."""
    labels, new_id = _chosen_labels(rename, relabel)
    if labels is None:
        notes.append(f"{_key(relabel)}: the rename's chosen {new_id} has no labels, relabel left as rebuilt")
        return relabel
    current = relabel.get("current")
    first = [] if labels == current else [{"labels": labels, "from_id": new_id}]
    rest = [c for c in relabel.get("candidates") or [] if c.get("labels") not in (labels, current)]
    return {**relabel, "labels": labels, "candidates": first + rest + [{"labels": current, "from_id": None}]}


def merge(old, rebuilt):
    """The merged change-set and the notes on the old operations dropped."""
    fresh = {_key(op): op for op in rebuilt["operations"]}
    old_keys = {_key(op) for op in old["operations"]}
    lost = [_key(op) for op in old["operations"] if _key(op) not in fresh and _decided(op)]
    if lost:
        raise ValueError("decided operations missing from the rebuilt file: " + ", ".join(lost))
    ops, notes = [], []
    for op in old["operations"]:
        key = _key(op)
        if _decided(op):
            ops.append(op)
        elif key in fresh:
            ops.append(fresh[key])
        else:
            notes.append(f"{key}: undecided, absent from the rebuilt file, dropped")
    ops += [op for op in rebuilt["operations"] if _key(op) not in old_keys]
    renames = {op["id"]: op for op in old["operations"] if op.get("op") == "rename" and _decided(op)}
    ops = [_follow(renames[op["id"]], op, notes)
           if op.get("op") == "relabel" and not _decided(op) and op["id"] in renames else op for op in ops]
    merged = {k: v for k, v in rebuilt.items() if k != "operations"}
    merged["operations"] = ops
    return merged, notes


def main(argv):
    args = list(argv)
    repo = Path(__file__).resolve().parent.parent
    if "--repo" in args:
        i = args.index("--repo")
        repo = Path(args[i + 1])
        del args[i:i + 2]
    if len(args) != 4 or args[0] != "merge":
        sys.exit(__doc__)
    old_path, new_path, out = (Path(p) for p in args[1:])
    if _in_a_repository(out, repo):
        sys.exit(f"{out}: a change-set quotes the 2004 edition; keep it outside the repository")
    old = json.loads(old_path.read_text(encoding="utf-8"))
    rebuilt = json.loads(new_path.read_text(encoding="utf-8"))
    try:
        merged, notes = merge(old, rebuilt)
    except ValueError as e:
        sys.exit(str(e))
    out.write_text(json.dumps(merged, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    old_keys = {_key(op) for op in old["operations"]}
    fresh = {_key(op) for op in rebuilt["operations"]}
    kept = sum(_decided(op) for op in old["operations"])
    added = sum(_key(op) not in old_keys for op in rebuilt["operations"])
    dropped = sum(not _decided(op) and _key(op) not in fresh for op in old["operations"])
    rebuilt_n = len(old["operations"]) - kept - dropped
    print(f"{out}: kept {kept}, rebuilt {rebuilt_n}, added {added}, dropped {dropped}")
    for n in notes:
        print(n)


if __name__ == "__main__":
    main(sys.argv[1:])
