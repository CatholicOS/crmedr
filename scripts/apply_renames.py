#!/usr/bin/env python3
"""Apply decided rename ops (crmedr-changeset/v1) across martyrology-texts and crmedr.

A rename op renames an eulogy ID mr:MMDD-slug. The curator decides it in a review
change-set (accept, edit or reject) and exports the decided file. Nothing is
written unless every rename passes check(); an old ID that is gone from the
registry while its new ID is present counts as already applied.

Usage:
  apply_renames.py texts <decided.json> /path/to/martyrology-texts [--dry-run] [repo_root]
  apply_renames.py crmedr <decided.json> [--dry-run] [--regenerate /path/to/martyrology-texts] [repo_root]
"""
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

EDITIONS = ("martyrologium_romanum_2004", "martyrologium_romanum_2004_it_IT",
            "martyrologium_romanum_2004_en_unofficial")
LABEL_FILES = {"la": "la.json", "en": "en.json", "it": "it.json"}
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


def rekey_text(text, mapping):
    """Re-key the quoted IDs: "old" and "old|... take the new ID; nothing else."""
    if not mapping:
        return text, 0
    alt = "|".join(re.escape(k) for k in sorted(mapping, key=len, reverse=True))
    return re.subn(rf'"({alt})(?=["|])', lambda m: '"' + mapping[m.group(1)], text)


def rekey_file(path, mapping, kind, dry):
    """Re-key one file in place, checking the result first; returns the count."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    new, n = rekey_text(text, mapping)
    try:
        if kind == "json":
            json.loads(new)
        else:
            compile(new, str(path), "exec")
    except (ValueError, SyntaxError) as e:
        raise ValueError(f"{path}: the re-keyed file does not parse: {e}") from e
    if n and not dry:
        path.write_text(new, encoding="utf-8")
    return n


def set_labels(path, labels, dry):
    """Set the subject of each id in a flat i18n file; ids absent from it are an error."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    missing = [i for i in labels if f'"{i}": "' not in text]
    if missing:
        raise ValueError(f"{path}: no such IDs: {', '.join(missing)}")
    n = 0
    for mr_id, value in labels.items():
        pat = re.compile(rf'^(\s*{re.escape(json.dumps(mr_id))}: )"(?:[^"\\]|\\.)*"', re.M)
        text, k = pat.subn(lambda m: m.group(1) + json.dumps(value, ensure_ascii=False), text)
        n += k
    if n and not dry:
        path.write_text(text, encoding="utf-8")
    return n


class Report(NamedTuple):
    applied: list  # [Rename]
    skipped: list  # [Rename], already applied
    files: dict  # path -> replacements
    errors: list  # [str]
    ok: bool
    steps: bool = False  # print the next steps (crmedr)


def _report(applied, skipped, files, errors, steps=False):
    return Report(applied, skipped, files, errors, not errors, steps)


def _registry_ids(repo_root):
    registry = json.loads((Path(repo_root) / "data" / "martyrology_ids.json").read_text(encoding="utf-8"))
    return {e["id"] for e in registry["entries"]}


def _plan(changeset, repo_root):
    """(to apply, already applied, check errors) for a decided change-set."""
    todo, done = split_applied(renames(changeset), _registry_ids(repo_root))
    return todo, done, check(todo, _registry_ids(repo_root))


def _rekey_all(targets, mapping, dry, files, errors):
    """Re-key (path, kind) targets; a file that does not parse is an error."""
    for path, kind in targets:
        try:
            n = rekey_file(path, mapping, kind, dry)
        except (OSError, ValueError) as e:
            errors.append(str(e))
            continue
        if n:
            files[str(path)] = files.get(str(path), 0) + n


def apply_texts(changeset, texts_repo, repo_root, dry):
    """Step 1: re-key the 2004 edition files of martyrology-texts."""
    texts_repo = Path(texts_repo)
    todo, done, errors = _plan(changeset, repo_root)
    if errors or not todo:
        return _report([] if errors else todo, done, {}, errors)
    mapping = {r.old: r.new for r in todo}
    targets = []
    for edition in EDITIONS:
        folder = texts_repo / "data" / "editions" / edition
        targets += [(p, "json") for p in sorted(folder.glob("*.json"))]
    if not targets:
        return _report([], done, {}, [f"{texts_repo}: no 2004 edition files found"])
    files = {}
    _rekey_all(targets, mapping, True, files, errors)  # every file parses first
    if not errors and not dry:
        files = {}
        _rekey_all(targets, mapping, False, files, errors)
    return _report([] if errors else todo, done, files, errors)


def _tracked(repo_root):
    out = subprocess.run(["git", "ls-files", "data", "i18n"], cwd=repo_root, capture_output=True,
                         text=True, check=True).stdout
    return [Path(repo_root) / n for n in out.splitlines() if n.endswith(".json")]


def _write_labels(rs, repo_root, dry, files, errors):
    """Labels go to i18n/{la,en,it}.json; before the re-key (dry) an ID is still the old one."""
    for lang, name in LABEL_FILES.items():
        labels = {(r.old if dry else r.new): r.labels[lang] for r in rs if r.labels.get(lang)}
        if not labels:
            continue
        path = Path(repo_root) / "i18n" / name
        try:
            n = set_labels(path, labels, dry)
        except (OSError, ValueError) as e:
            errors.append(str(e))
            continue
        if n != len(labels):
            errors.append(f"{path}: {n} of {len(labels)} labels set (a subject is not a string?)")
        if n:
            files[str(path)] = files.get(str(path), 0) + n


def _pass(todo, mapping, repo_root, dry, files, errors):
    targets = [(p, "json") for p in _tracked(repo_root)]
    targets.append((Path(repo_root) / "scripts" / "extract_registry.py", "python"))
    if dry:
        # A dry pass counts the re-keys; the labels are looked up under the old IDs.
        _rekey_all(targets, mapping, True, files, errors)
        _write_labels(todo, repo_root, True, files, errors)
    else:
        _rekey_all(targets, mapping, False, files, errors)
        _write_labels(todo, repo_root, False, files, errors)


def apply_crmedr(changeset, repo_root, dry, run=subprocess.run, regenerate=None):
    """Step 2: re-key crmedr's tracked files, write the labels, rebuild and test."""
    repo_root = Path(repo_root)
    todo, done, errors = _plan(changeset, repo_root)
    if errors or not todo:
        return _report([] if errors else todo, done, {}, errors, bool(todo))
    mapping = {r.old: r.new for r in todo}
    files = {}
    _pass(todo, mapping, repo_root, True, {}, errors)  # nothing is written if this fails
    if errors:
        return _report([], done, {}, errors)
    if dry:
        _pass(todo, mapping, repo_root, True, files, [])
        return _report(todo, done, files, errors, True)
    kept = {p: p.read_bytes() for p in (repo_root / "data" / "typology.json", repo_root / "data" / "places.json")
            if p.exists()}
    _pass(todo, mapping, repo_root, False, files, errors)
    commands = [["python3", "scripts/extract_registry.py"]]
    if regenerate:
        commands += [["python3", f"scripts/{name}.py", str(regenerate)] for name in ("extract_typology", "extract_places")]
    commands.append(["python3", "-m", "unittest", "discover", "-s", "tests"])
    if not errors:
        for cmd in commands:
            if run(cmd, cwd=repo_root).returncode != 0:
                errors.append("failed: " + " ".join(cmd))
                break
            if regenerate and cmd[1] == "scripts/extract_places.py":
                for p, before in kept.items():
                    if p.read_bytes() != before:
                        errors.append(f"{p.relative_to(repo_root)} changed after regeneration")
    return _report(todo, done, files, errors, True)


def render(report, repo_root=None):
    lines = []
    for r in report.applied:
        lines.append(f"{r.old} → {r.new}")
    for r in report.skipped:
        lines.append(f"already applied: {r.old} → {r.new}")
    for path, n in report.files.items():
        lines.append(f"  {path}: {n}")
    lines.append(f"{len(report.applied)} renames, {len(report.skipped)} already applied, "
                 f"{sum(report.files.values())} replacements in {len(report.files)} files")
    lines += [f"error: {e}" for e in report.errors]
    if report.steps and report.ok and report.applied:
        root = repo_root or "<crmedr>"
        lines += ["Next:",
                  f"  1. in martyrology-texts: CRMEDR_PATH={root} python3 -m pytest tests/test_registry_keys.py",
                  "  2. merge martyrology-texts, then crmedr",
                  "  3. AGENTS.md steps 3 and 4 (martyrology-api re-align and release; martyrology-frontend snapshot-registry and deploy)"]
    return "\n".join(lines)


def main(argv):
    if len(argv) < 2 or argv[0] not in ("texts", "crmedr"):
        sys.exit(__doc__)
    cmd, rest = argv[0], list(argv[1:])
    dry = "--dry-run" in rest
    rest = [a for a in rest if a != "--dry-run"]
    regenerate = None
    if "--regenerate" in rest:
        i = rest.index("--regenerate")
        if cmd != "crmedr" or i + 1 >= len(rest):
            sys.exit(__doc__)
        regenerate = rest[i + 1]
        rest = rest[:i] + rest[i + 2:]
    changeset = json.loads(Path(rest[0]).read_text(encoding="utf-8"))
    rest = rest[1:]
    if cmd == "texts":
        if not rest:
            sys.exit(__doc__)
        texts_repo, rest = Path(rest[0]), rest[1:]
    repo_root = Path(rest[0]) if rest else Path(__file__).resolve().parent.parent
    if cmd == "texts":
        report = apply_texts(changeset, texts_repo, repo_root, dry)
    else:
        report = apply_crmedr(changeset, repo_root, dry, regenerate=regenerate)
    print(render(report, repo_root))
    if not report.ok:
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
