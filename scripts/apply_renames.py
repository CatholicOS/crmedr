#!/usr/bin/env python3
"""Apply decided rename ops (crmedr-changeset/v1) across martyrology-texts and crmedr.

A rename op renames an eulogy ID mr:MMDD-slug. The curator decides it in a review
change-set (accept, edit or reject) and exports the decided file. Nothing is
written unless every rename passes check(); an old ID that is gone from the
registry while its new ID is present counts as already applied.
"""
import json
import re
from pathlib import Path
from typing import NamedTuple

ID_RE = re.compile(r"^mr:\d{4}-[a-z]+(?:-[a-z]+)*$")
LANGS = ("la", "en", "it")


class Rename(NamedTuple):
    old: str
    new: str
    labels: dict  # la/en/it -> subject or None (None: leave unchanged)


def renames(changeset):
    """The decided renames of a change-set, in file order."""
    out = []
    for op in changeset.get("ops", []):
        if op.get("op") != "rename":
            continue
        decision = op.get("decision")
        edited = op.get("edited") or {}
        if decision == "accept":
            new = op["new_id"]
        elif decision == "edit":
            new = edited.get("new_id") or op["new_id"]
        else:
            continue
        labels = dict.fromkeys(LANGS)
        for cand in op.get("candidates") or []:
            if cand.get("new_id") == new:
                cl = cand.get("labels") or {}
                labels = {lang: cl.get(lang) or None for lang in LANGS}
                break
        if decision == "edit" and edited.get("subject_la"):
            labels["la"] = edited["subject_la"]
        out.append(Rename(op["id"], new, labels))
    return out


def split_applied(rs, ids):
    """(to apply, already applied): an old ID gone with its new ID present is applied."""
    todo, done = [], []
    for r in rs:
        (done if r.old not in ids and r.new in ids else todo).append(r)
    return todo, done


def check(rs, ids):
    """Error strings for the renames (empty: all pass); ids = every registry ID."""
    errors = []
    olds = {r.old for r in rs}
    seen = {}
    for r in rs:
        head = f"{r.old} → {r.new}"
        if r.old not in ids:
            errors.append(f"{head}: no such ID")
        numeric = any(t.isdigit() for t in r.new.split("-")[1:])
        if numeric:
            errors.append(f"{head}: a numeric token")
        elif not ID_RE.match(r.new) or not ID_RE.match(r.old):
            errors.append(f"{head}: not mr:MMDD-slug")
            continue
        if r.new[3:7] != r.old[3:7]:
            errors.append(f"{head}: the day changes")
        if r.new in ids:
            errors.append(f"{head}: {r.new} already exists")
        if r.new in olds:
            errors.append(f"{head}: {r.new} is renamed too")
        seen[r.new] = seen.get(r.new, 0) + 1
        if seen[r.new] == 2:
            errors.append(f"{head}: two renames give {r.new}")
    return errors
