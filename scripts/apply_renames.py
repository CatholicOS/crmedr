#!/usr/bin/env python3
"""Apply decided rename ops (crmedr-changeset/v1) across martyrology-texts and crmedr.

A rename op renames an eulogy ID mr:MMDD-slug. The curator decides it in a review
change-set (accept, edit or reject) and exports the decided file. Nothing is
written unless every rename passes check(); an old ID that is gone (from the
2004 editions' keys for texts, from the registry for crmedr) while its new ID is
present counts as already applied. A decided relabel op (the subject rename) sets
its eulogy's la, en and it subjects: under the new ID when the eulogy is renamed in
the same file, else under the current ID. The subject follows the ID (curator,
2026-10-25): an accept writes the subject the eulogy's decided ID implies (that
candidate's labels), and is an error when the rename is not decided or its ID is
not a candidate; an edit writes the edited labels; a reject keeps the current subjects.

A deprecated ID (an older edition's eulogy, never a key of the 2004 texts) is renamed in crmedr and
the API; texts skips it. The API step re-keys the 1630, 1749 and 1914 editions, which print an eulogy
under its 2004 ID or a deprecated one, for every rename.

Order: build_person_items.py apply <decided.json>, then texts, then crmedr, then
martyrology-texts' tests/test_registry_keys.py, then api.

Usage:
  apply_renames.py texts <decided.json> /path/to/martyrology-texts [--dry-run] [repo_root]
  apply_renames.py crmedr <decided.json> [--dry-run] [--regenerate /path/to/martyrology-texts] [repo_root]
  apply_renames.py api <decided.json> /path/to/martyrology-api [--dry-run]
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import NamedTuple

from persons_text import DISCRIMINATORS, strip_discriminator

EDITIONS = ("martyrologium_romanum_2004", "martyrologium_romanum_2004_it_IT",
            "martyrologium_romanum_2004_en_unofficial")
LABEL_FILES = {"la": "la.json", "en": "en.json", "it": "it.json"}
ID_RE = re.compile(r"^mr:\d{4}-[a-z]+(?:-[a-z]+)*$")
LANGS = ("la", "en", "it")
SCHEMA = "crmedr-changeset/v1"
# Files whose text also names an ID outside quotes (notes): an old ID standing alone is re-keyed there.
PROSE_SCRIPTS = ("scripts/extract_registry.py",)
TEXTS_TESTS = "tests/test_registry_keys.py"  # its EN_UNTRANSLATED list is keyed by ID


class Rename(NamedTuple):
    old: str
    new: str
    labels: dict  # la/en/it -> subject or None (None: leave unchanged)
    category: str | None = None  # the decided candidate's ("place-genitive", "surname", …; "typed": an
    # ID not among them); None: a relabel alone


def changeset_errors(changeset):
    """A decided file that is not a change-set is an error, not "0 renames"."""
    if not isinstance(changeset, dict) or changeset.get("schema") != SCHEMA:
        return [f"not a {SCHEMA} document"]
    if not isinstance(changeset.get("operations"), list):
        return ["the change-set has no operations list"]
    return []


def _new_id(op):
    """The new ID a rename op's decision gives (accept: its new_id; edit: the edited one), else None."""
    if op.get("decision") == "accept":
        return op["new_id"]
    if op.get("decision") == "edit":
        return (op.get("edited") or {}).get("new_id") or op["new_id"]
    return None


def _decided_renames(changeset):
    """{mrid: the first decided rename op of the eulogy}."""
    out = {}
    for op in changeset.get("operations", []):
        if op.get("op") == "rename" and _new_id(op) is not None:
            out.setdefault(op["id"], op)
    return out


def _followed(relabel, rename):
    """The subject the decided ID implies (the subject follows the ID): the relabel candidate whose
    from_id is the rename's decided new ID; else (its labels deduplicated out of the relabel) the rename
    candidate with that new_id, a None language filled from the relabel's current labels, as
    rename_candidates.relabel_op fills it. None when there is no decided rename or the decided ID is
    not a candidate (a typed ID implies no subject)."""
    new = _new_id(rename) if rename else None
    if new is None:
        return None
    for c in relabel.get("candidates") or []:
        if c.get("from_id") == new:
            return c.get("labels") or {}
    current = relabel.get("current") or {}
    for c in rename.get("candidates") or []:
        if c.get("new_id") == new:
            own = c.get("labels") or {}
            return {lang: own.get(lang) if own.get(lang) is not None else current.get(lang) for lang in LANGS}
    return None


def relabel_errors(changeset):
    """Error strings for the accepted relabels that follow no candidate: the eulogy's rename is not
    decided in the file, or its decided ID is not one of the candidates."""
    errors, decided = [], _decided_renames(changeset)
    for op in changeset.get("operations", []):
        if op.get("op") != "relabel" or op.get("decision") != "accept" \
                or _followed(op, decided.get(op["id"])) is not None:
            continue
        rename = decided.get(op["id"])
        if rename is None:
            errors.append(f"{op['id']}: the subject follows the ID, but the eulogy's rename is not decided")
        else:
            errors.append(f"{op['id']}: the subject follows the ID, but the decided ID {_new_id(rename)} is not"
                          " a candidate: edit the subject instead")
    return errors


def relabels(changeset):
    """{mrid: labels} of the decided relabels: accept takes the subject the eulogy's decided ID
    implies (_followed; an accept that follows no candidate is left out, see relabel_errors), edit
    the edited labels, reject none (every subject None: left unchanged). An `edit` with an empty
    language (missing, "" or null) gives None for it: that language's current subject is kept."""
    out, decided = {}, _decided_renames(changeset)
    for op in changeset.get("operations", []):
        if op.get("op") != "relabel":
            continue
        decision = op.get("decision")
        if decision == "accept":
            labels = _followed(op, decided.get(op["id"]))
            if labels is None:
                continue
        elif decision == "edit":
            labels = (op.get("edited") or {}).get("labels") or {}
        elif decision == "reject":
            labels = {}
        else:
            continue
        out[op["id"]] = {lang: labels.get(lang) or None for lang in LANGS}
    return out


def _renamed(changeset):
    """The IDs a decided rename of the change-set renames."""
    return {op["id"] for op in changeset.get("operations", [])
            if op.get("op") == "rename" and op.get("decision") in ("accept", "edit")}


def relabel_only(changeset):
    """Rename(mrid, mrid, labels) of each decided relabel that sets a subject of an ID the file
    does not rename, in file order of the relabels."""
    renamed = _renamed(changeset)
    return [Rename(mrid, mrid, labels) for mrid, labels in relabels(changeset).items()
            if mrid not in renamed and any(labels.values())]


def renames(changeset):
    """The decided renames of a change-set, in file order. A decided relabel of the eulogy gives
    the labels; else the rename candidate's (and an edit's subject_la)."""
    out = []
    decided = relabels(changeset)
    for op in changeset.get("operations", []):
        if op.get("op") != "rename":
            continue
        decision = op.get("decision")
        edited = op.get("edited") or {}
        new = _new_id(op)
        if new is None:
            continue
        labels, category = dict.fromkeys(LANGS), "typed"
        for cand in op.get("candidates") or []:
            if cand.get("new_id") == new:
                cl = cand.get("labels") or {}
                labels = {lang: cl.get(lang) or None for lang in LANGS}
                category = cand.get("category") or category
                break
        if decision == "edit" and edited.get("subject_la"):
            labels["la"] = edited["subject_la"]
        if op["id"] in decided:
            labels = dict(decided[op["id"]])
        out.append(Rename(op["id"], new, labels, category))
    return out


def split_applied(rs, ids):
    """(to apply, already applied): an old ID gone with its new ID present is applied."""
    todo, done = [], []
    for r in rs:
        (done if r.old not in ids and r.new in ids else todo).append(r)
    return todo, done


def check(rs, ids=None):
    """Error strings for the renames (empty: all pass).

    ids = every registry ID, current and deprecated (a deprecated ID, an older edition's, is renamed
    in crmedr and the API); ids None skips the registry checks (texts and the API judge by their own keys)."""
    errors = []
    olds = {r.old for r in rs}
    seen = {}
    for r in rs:
        head = f"{r.old} → {r.new}"
        if ids is not None and r.old not in ids:
            errors.append(f"{head}: no such ID")
        numeric = any(t.isdigit() for t in r.new.split("-")[1:])
        if numeric:
            errors.append(f"{head}: a numeric token")
        elif not ID_RE.match(r.new) or not ID_RE.match(r.old):
            errors.append(f"{head}: not mr:MMDD-slug")
            continue
        if r.new[3:7] != r.old[3:7]:
            errors.append(f"{head}: the day changes")
        if ids is not None and r.new in ids:
            errors.append(f"{head}: {r.new} already exists")
        if r.new in olds:
            errors.append(f"{head}: {r.new} is renamed too")
        seen[r.new] = seen.get(r.new, 0) + 1
        if seen[r.new] == 2:
            errors.append(f"{head}: two renames give {r.new}")
    return errors


def _alternation(ids):
    return "|".join(re.escape(k) for k in sorted(ids, key=len, reverse=True))


def _standalone(ids):
    """An ID standing alone: not part of a longer ID or of another namespace (x:mr:...)."""
    return re.compile(rf"(?<![\w:-])({_alternation(ids)})(?![\w-])")


def rekey_text(text, mapping, prose=False):
    """Re-key the quoted IDs: "old", "old|... and a per-eulogy gazetteer key's "...@old" take the
    new ID; nothing else.

    prose: also an old ID standing alone in text (a note's "(mr:0114-euphrasius)")."""
    if not mapping:
        return text, 0
    if prose:
        return _standalone(mapping).subn(lambda m: mapping[m.group(1)], text)
    return re.subn(rf'(?<=["@])({_alternation(mapping)})(?=["|])', lambda m: mapping[m.group(1)], text)


def rekey_file(path, mapping, kind, dry, prose=False):
    """Re-key one file in place, checking the result first; returns the count."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    new, n = rekey_text(text, mapping, prose)
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
    steps: str = ""  # the subcommand whose next steps to print ("texts", "crmedr")
    leftovers: tuple = ()  # "path:line" of tracked files not re-keyed that still name an old ID
    relabeled: tuple = ()  # [Rename(mrid, mrid, labels)], subjects set under an ID not renamed


def _report(applied, skipped, files, errors, steps="", leftovers=(), relabeled=()):
    return Report(applied, skipped, files, errors, not errors, steps, tuple(leftovers), tuple(relabeled))


def _git_files(repo, *paths):
    out = subprocess.run(["git", "ls-files", *paths], cwd=repo, capture_output=True, text=True, check=True).stdout
    return [Path(repo) / n for n in out.splitlines()]


def scan(repo, mapping, targets=()):
    """path:line of each tracked file of repo that will still name an old ID: a file the run
    re-keys with prose (every standalone ID) is skipped; one it re-keys quoted IDs only is read
    as it will be after the re-key (a comment that names an old ID is listed)."""
    if not mapping:
        return []
    pat, out = _standalone(mapping), []
    kinds = {Path(p): prose for p, _, prose in targets}
    for path in _git_files(repo):
        if kinds.get(path) is True or not path.is_file():
            continue
        data = path.read_bytes()
        if b"\0" in data:
            continue
        text = data.decode("utf-8", "replace")
        if path in kinds:
            text = rekey_text(text, mapping)[0]
        for i, line in enumerate(text.splitlines(), 1):
            if pat.search(line):
                out.append(f"{path.relative_to(repo)}:{i}")
    return out


def _rekey_all(targets, mapping, dry, files, errors):
    """Re-key (path, kind, prose) targets; a file that does not parse is an error."""
    for path, kind, prose in targets:
        try:
            n = rekey_file(path, mapping, kind, dry, prose)
        except (OSError, ValueError) as e:
            errors.append(str(e))
            continue
        if n:
            files[str(path)] = files.get(str(path), 0) + n


def _edition_keys(paths):
    """The top-level keys of the 2004 edition files (the eulogy IDs of the texts)."""
    keys = set()
    for path in paths:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(doc, dict):
            keys.update(doc)
    return keys


def apply_texts(changeset, texts_repo, repo_root, dry):
    """Step 1: re-key martyrology-texts' tracked 2004 edition files (and its registry-keys test).

    Judged by the texts' own keys: an old ID that is a key is applied; an old ID absent with its
    new ID a key is already applied; neither is an error. repo_root (crmedr) is not read."""
    texts_repo = Path(texts_repo)
    errors = changeset_errors(changeset)
    if errors:
        return _report([], [], {}, errors)
    try:
        tracked = set(_git_files(texts_repo))
    except (OSError, subprocess.CalledProcessError):
        return _report([], [], {}, [f"{texts_repo}: not a git work tree"])
    editions = []
    for edition in EDITIONS:
        folder = texts_repo / "data" / "editions" / edition
        found = sorted(p for p in tracked if p.parent == folder and p.suffix == ".json")
        if not found:
            return _report([], [], {}, [f"{folder}: no tracked edition files found"])
        editions += found
    try:
        keys = _edition_keys(editions)
    except (OSError, ValueError) as e:
        return _report([], [], {}, [f"the 2004 edition files do not parse: {e}"])
    # A deprecated ID names an eulogy of an older edition (the API's): never a key of the 2004 texts.
    try:
        deprecated = _registry(repo_root)[1]
    except (OSError, ValueError, KeyError):
        deprecated = set()
    todo, done = split_applied([r for r in renames(changeset) if r.old not in deprecated], keys)
    errors = check(todo) + relabel_errors(changeset)
    for r in todo:
        if r.old not in keys:
            errors.append(f"{r.old} → {r.new}: neither ID is a key of the 2004 editions")
        elif r.new in keys:
            errors.append(f"{r.old} → {r.new}: {r.new} is already a key of the 2004 editions")
    if errors or not todo:
        return _report([] if errors else todo, done, {}, errors, "" if errors else "texts")
    mapping = {r.old: r.new for r in todo}
    targets = [(p, "json", False) for p in editions]
    tests = texts_repo / TEXTS_TESTS
    if tests in tracked:
        targets.append((tests, "python", False))
    files = {}
    _rekey_all(targets, mapping, True, files, errors)  # every file parses first
    if errors:
        return _report([], done, {}, errors)
    leftovers = scan(texts_repo, mapping, targets)
    if not dry:
        files = {}
        _rekey_all(targets, mapping, False, files, errors)
    return _report([] if errors else todo, done, files, errors, "texts", leftovers)


API_FOLDERS = ("data/editions", "scripts/data")  # the API's older editions and their alignment inputs
MRID = re.compile(r'"(mr:\d{4}-[a-z]+(?:-[a-z]+)*)"')


def apply_api(changeset, api_repo, dry):
    """Step 3: re-key martyrology-api's tracked JSON under data/editions/ (the 1630, 1749 and 1914 editions,
    their alignment, footnotes, marginalia and errata) and scripts/data/ (alignment overrides), for every
    rename, current or deprecated: an older edition prints an eulogy under its 2004 ID, or under a deprecated
    one. Judged by the IDs those files name: an old ID named is applied; an old ID gone with its new ID named is
    already applied; neither is an eulogy no older edition prints, left alone."""
    api_repo = Path(api_repo)
    errors = changeset_errors(changeset)
    if errors:
        return _report([], [], {}, errors)
    try:
        tracked = _git_files(api_repo, *API_FOLDERS)
    except (OSError, subprocess.CalledProcessError):
        return _report([], [], {}, [f"{api_repo}: not a git work tree"])
    found = [p for p in tracked if p.suffix == ".json"]
    named = set()
    for p in found:
        named.update(MRID.findall(p.read_text(encoding="utf-8")))
    rs = renames(changeset)
    errors = check(rs) + relabel_errors(changeset)
    todo = [r for r in rs if r.old in named]
    done = [r for r in rs if r.old not in named and r.new in named]
    errors += [f"{r.old} → {r.new}: {r.new} is already named by the older editions" for r in todo if r.new in named]
    if errors or not todo:
        return _report([] if errors else todo, done, {}, errors, "")
    mapping = {r.old: r.new for r in todo}
    targets = [(p, "json", False) for p in found]
    files = {}
    _rekey_all(targets, mapping, True, files, errors)  # every file parses first
    if errors:
        return _report([], done, {}, errors)
    leftovers = scan(api_repo, mapping, targets)
    if not dry:
        files = {}
        _rekey_all(targets, mapping, False, files, errors)
    return _report([] if errors else todo, done, files, errors, "api", leftovers)


def _registry(repo_root):
    """(every registry ID, the deprecated ones)."""
    registry = json.loads((Path(repo_root) / "data" / "martyrology_ids.json").read_text(encoding="utf-8"))
    entries = registry["entries"]
    return {e["id"] for e in entries}, {e["id"] for e in entries if e.get("deprecated")}


def _person_errors(changeset, todo, repo_root):
    """Person decisions on a renamed eulogy must be applied first: their keys name the old ID."""
    path = Path(repo_root) / "data" / "person_items_review.json"
    if not path.exists():
        return []
    try:
        queued = {op.get("id") for op in json.loads(path.read_text(encoding="utf-8"))["operations"]}
    except (ValueError, KeyError, TypeError, AttributeError) as e:
        return [f"{path.name}: not a readable crmedr-changeset ({e.__class__.__name__}): fix or regenerate it first"]
    renamed = {r.old for r in todo}
    held = sorted(op["id"] for op in changeset["operations"]
                  if op.get("op") == "resolve_person" and op.get("decision") is not None
                  and op.get("eulogy") in renamed and op.get("id") in queued)
    if not held:
        return []
    shown = ", ".join(held[:5]) + (f" and {len(held) - 5} more" if len(held) > 5 else "")
    return [f"{len(held)} person decisions on renamed eulogies are still queued in {path.name} ({shown}): "
            "run `python3 scripts/build_person_items.py apply <decided.json>` first"]


def check_relabels(only, ids, deprecated=frozenset()):
    """Error strings for the relabels of IDs not renamed: the ID must be a current registry ID."""
    errors = []
    for r in only:
        if r.old not in ids:
            errors.append(f"{r.old}: relabel of no such ID")
        elif r.old in deprecated:
            errors.append(f"{r.old}: deprecated IDs are not relabeled")
    return errors


def subject_type_errors(rs):
    """Error strings for the subjects set to something other than a string."""
    return [f"{r.old}: the {lang} subject is not a string"
            for r in rs for lang, value in r.labels.items() if value and not isinstance(value, str)]


def _plan(changeset, repo_root):
    """(to apply, already applied, relabels of IDs not renamed, check errors) for crmedr, judged
    against its registry. A decided relabel whose rename is already applied is written under the
    new ID (a relabel may be decided after its rename was applied); a reject writes the relabel's
    current labels there, what the card showed as "keep current"."""
    errors = changeset_errors(changeset)
    if errors:
        return [], [], [], errors
    ids, deprecated = _registry(repo_root)
    todo, done = split_applied(renames(changeset), ids)
    decided = relabels(changeset)
    current = {op["id"]: {lang: (op.get("current") or {}).get(lang) or None for lang in LANGS}
               for op in changeset["operations"] if op.get("op") == "relabel" and op.get("decision") == "reject"}
    applied = [Rename(r.new, r.new, current.get(r.old, r.labels), r.category) for r in done if r.old in decided]
    only = relabel_only(changeset) + [r for r in applied if any(r.labels.values())]
    errors = (check(todo, ids) + check_relabels(only, ids, deprecated) + relabel_errors(changeset)
              + subject_type_errors(todo + only))
    if not errors:
        errors = _person_errors(changeset, todo, repo_root)
    return todo, done, only, errors


def _targets(repo_root):
    """(path, kind, prose) of what crmedr re-keys: tracked data/ and i18n/ JSON (prose too) and
    tracked scripts/*.py (quoted IDs; prose in PROSE_SCRIPTS), never apply_renames.py itself."""
    repo_root = Path(repo_root)
    targets = [(p, "json", True) for p in _git_files(repo_root, "data", "i18n") if p.suffix == ".json"]
    for p in _git_files(repo_root, "scripts"):
        rel = p.relative_to(repo_root).as_posix()
        if p.parent == repo_root / "scripts" and p.suffix == ".py" and rel != "scripts/apply_renames.py":
            targets.append((p, "python", rel in PROSE_SCRIPTS))
    return targets


# Discriminators that are part of a person's name ("Sanctus Iosephus Kalinowski" names Iosephus Kalinowski).
NAME_PARTS = ("surname",)
DISCRIMINATORS_COMMENT = ("The words a rename's discriminator added to each eulogy's subject, by language "
                          "(\"Romae\" in \"Sanctus Almachius Romae\", \"di Roma\" in \"Sant’Almachio di "
                          "Roma\"): no part of a person's name; persons_text.name_subjects drops them. Written "
                          "by scripts/apply_renames.py when a relabel extends a subject.")


def _record_discriminators(rs, repo_root, files):
    """Record, under the new ID and by language, the words each relabel adds after the current
    subject without its recorded discriminator (the subject follows the ID): a reworded discriminator
    replaces the record, a subject rewritten otherwise drops it. A surname is part of the name and
    records nothing; a relabel alone only rewords a discriminator already recorded."""
    repo_root = Path(repo_root)
    subjects = {lang: json.loads((repo_root / "i18n" / name).read_text(encoding="utf-8"))
                for lang, name in LABEL_FILES.items()}
    path = repo_root / DISCRIMINATORS
    doc = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {
        "$comment": DISCRIMINATORS_COMMENT, "discriminators": {}}
    found = doc["discriminators"]
    n = 0
    for r in rs:
        for lang in LABEL_FILES:
            old, new = subjects[lang].get(r.new), r.labels.get(lang)
            if not isinstance(old, str) or not new:
                continue  # the subject is left unchanged
            entry = found.get(r.new, {})
            recorded = entry.get(lang)
            base = strip_discriminator(old, recorded)
            sep = next((s for s in (", ", " ") if new.startswith(base + s)), None)
            discriminates = r.category not in (None, *NAME_PARTS) or (r.category is None and recorded)
            words = new[len(base + sep):] if sep and discriminates else None  # "San Milziade, papa"
            if words == recorded:
                continue
            if words:
                entry[lang] = words
                found[r.new] = entry
            else:
                del entry[lang]
                if not entry:
                    del found[r.new]
            n += 1
    if n:
        doc["discriminators"] = dict(sorted(found.items()))
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        files[str(path)] = files.get(str(path), 0) + n


def _write_labels(rs, repo_root, dry, files, errors):
    """Labels go to i18n/{la,en,it}.json; before the re-key (dry) an ID is still the old one."""
    if not dry:
        _record_discriminators(rs, repo_root, files)
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


def _pass(todo, mapping, targets, repo_root, dry, files, errors):
    # A dry pass counts the re-keys; the labels are looked up under the old IDs. todo holds the
    # relabels of IDs not renamed too (old == new).
    _rekey_all(targets, mapping, dry, files, errors)
    _write_labels(todo, repo_root, dry, files, errors)


def apply_crmedr(changeset, repo_root, dry, run=subprocess.run, regenerate=None):
    """Step 2: re-key crmedr's tracked files, write the labels, rebuild and test."""
    repo_root = Path(repo_root)
    todo, done, only, errors = _plan(changeset, repo_root)
    if errors or not (todo or only):
        return _report([], done, {}, errors)
    mapping = {r.old: r.new for r in todo}
    targets = _targets(repo_root)
    files = {}
    _pass(todo + only, mapping, targets, repo_root, True, {}, errors)  # nothing is written if this fails
    if errors:
        return _report([], done, {}, errors)
    leftovers = scan(repo_root, mapping, targets)
    if dry:
        _pass(todo + only, mapping, targets, repo_root, True, files, [])
        return _report(todo, done, files, errors, "crmedr", leftovers, only)
    _pass(todo + only, mapping, targets, repo_root, False, files, errors)
    # typology and places must come out of the regeneration as the re-key left them; their key
    # order may differ, since a rename can move an ID in sort order
    kept = {p: json.loads(p.read_text(encoding="utf-8"))
            for p in (repo_root / "data" / "typology.json", repo_root / "data" / "places.json") if p.exists()}
    commands = [["python3", "scripts/extract_registry.py"]]
    scratch = tempfile.TemporaryDirectory() if regenerate else None
    if regenerate:
        texts = str(regenerate)
        # extract_mentions writes a review change-set that quotes the texts: outside the repository
        review = str(Path(scratch.name) / "mentions-review.json")
        commands += [["python3", f"scripts/{name}.py", texts]
                     for name in ("extract_typology", "extract_places")]
        commands += [["python3", "scripts/registry_places.py"], ["python3", "scripts/extract_persons.py", texts],
                     ["python3", "scripts/extract_mentions.py", texts, "--review", review]]
    commands.append(["python3", "-m", "unittest", "discover", "-s", "tests"])
    try:
        for cmd in ([] if errors else commands):
            if run(cmd, cwd=repo_root).returncode != 0:
                errors.append("failed: " + " ".join(cmd))
                break
            if cmd[1] == "scripts/extract_places.py":
                changed = [str(p.relative_to(repo_root)) for p, before in kept.items()
                           if json.loads(p.read_text(encoding="utf-8")) != before]
                if changed:
                    errors.append(f"{', '.join(changed)} changed after regeneration")
                    break
    finally:
        if scratch:
            scratch.cleanup()
    return _report(todo, done, files, errors, "crmedr", leftovers, only)


def render(report, repo_root=None):
    lines = []
    for r in report.applied:
        lines.append(f"{r.old} → {r.new}")
    for r in report.skipped:
        lines.append(f"already applied: {r.old} → {r.new}")
    for r in report.relabeled:
        lines.append(f"relabeled: {r.old}")
    for path, n in report.files.items():
        lines.append(f"  {path}: {n}")
    lines.append(f"{len(report.applied)} renames, {len(report.skipped)} already applied, "
                 + (f"{len(report.relabeled)} relabeled, " if report.relabeled else "")
                 + f"{sum(report.files.values())} replacements in {len(report.files)} files")
    lines += [f"error: {e}" for e in report.errors]
    if report.leftovers:
        lines.append(f"still naming an old ID ({len(report.leftovers)} lines in tracked files this run does not re-key):")
        lines += [f"  {where}" for where in report.leftovers]
    if report.ok and report.applied and report.steps == "texts":
        lines += ["Next (order: build_person_items.py apply, texts, crmedr, texts' test_registry_keys):",
                  "  python3 scripts/apply_renames.py crmedr <decided.json> [--regenerate /path/to/martyrology-texts]"]
    if report.ok and (report.applied or report.relabeled) and report.steps == "crmedr":
        root = repo_root or "<crmedr>"
        lines += ["Next (order: build_person_items.py apply, texts, crmedr, texts' test_registry_keys):",
                  f"  1. in martyrology-texts: CRMEDR_PATH={root} python3 -m pytest tests/test_registry_keys.py",
                  "  2. regenerate the generated reports (docs/*-report.md): --regenerate rewrites typology, places,"
                  " persons and mentions; build_gazetteer.py and build_person_items.py write the gazetteer and"
                  " person-items reports",
                  "  3. merge martyrology-texts, then crmedr",
                  "  4. AGENTS.md step 3, martyrology-api: python3 scripts/apply_renames.py api <decided.json>"
                  " /path/to/martyrology-api (the 1630, 1749 and 1914 editions); pin vendor/crmedr, vendor/texts and"
                  " the Dockerfile's CRMEDR_REF to the merge commits; publish a release",
                  "  5. AGENTS.md step 4, martyrology-frontend: npm run snapshot-registry, then deploy"]
    return "\n".join(lines)


def main(argv):
    if len(argv) < 2 or argv[0] not in ("texts", "crmedr", "api"):
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
    if len(rest) < (2 if cmd in ("texts", "api") else 1):
        sys.exit(__doc__)
    changeset = json.loads(Path(rest[0]).read_text(encoding="utf-8"))
    rest = rest[1:]
    if cmd == "api":
        report = apply_api(changeset, Path(rest[0]), dry)
        print(render(report))
        if not report.ok:
            sys.exit(1)
        return
    if cmd == "texts":
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
