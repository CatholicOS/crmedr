# Gazetteer into the registry (places, sub-project 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Copy each place's gazetteer resolution onto the registry's `places[]` items and derive every current entry's `country` from its resolved opening place (else a curated file), with the Holy Land always `PS`.

**Architecture:** A new offline script `scripts/registry_places.py` holds a pure `apply(entries, gazetteer, curated)` plus a CLI that rewrites the committed registry through `extract_registry.write_json` / `write_markdown` (verified to round-trip the committed files byte for byte) and a `--check` mode used by a test. `extract_registry.py` drops `COUNTRY_CORRECTIONS` and calls `apply` after merging places, so the workbook's country is never output. The gazetteer gains a convention check and loses the sub-project-3 preview.

**Tech Stack:** Python 3 stdlib, `unittest` (`python3 -m unittest discover -s tests`).

**Spec:** `docs/superpowers/specs/2026-10-14-registry-place-countries-design.md`

## Global Constraints

- The workbook (`Roman Martyrology LA IT EN with IDs.xlsx`) is not a source: no value is taken from it, and the new step runs without it.
- Country rule for each current entry: (1) the gazetteer `country` of the entry's opening place (`source: "lead"`) when its gazetteer entry has a non-null `wikidata`; (2) otherwise `data/countries_curated.json`; (3) `COUNTRY_CONVENTIONS` (`IL → PS`, `scripts/gazetteer_text.py`) applied last.
- No current entry, no place item and no gazetteer entry may end up `IL`.
- Deprecated entries are untouched (they keep `country`, have no `places`).
- Place item fields: `wikidata`, `label`, `country`, and `text_says` (only gazetteer `text_says` items whose `it` equals the item's `it`; omitted when none). No `modern` field. Queued (no gazetteer key) or `unresolved` (`wikidata: null`) places get none of these fields.
- Curated values: ISO 3166-1 alpha-2 code (in `gazetteer_text.ISO_CODES`), `null`, or `{"country": <code|null>, "note": <str>}`.
- Never `git add` the whole `data/` or `docs/` directory (there may be untracked work in progress); add files by name.
- Commit messages end with:
  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01H2QwGLjGJersugqyQ4o2tf
  ```

## Review Focus

- A queued place (no gazetteer key) on an entry's opening place: the entry must fall back to the curated file, and the item must get no new fields — test in Task 2.
- One Latin place printed with two different Italian phrases (gazetteer `text_says` for only one): each place item carries only its own claim — test in Task 2.
- Running `registry_places.py` twice: the second run changes nothing (idempotent; stale fields from an earlier run are replaced, not duplicated) — test in Task 2.
- A gazetteer review that resolves one of the 37 queued places, committed without rerunning the script: `--check` must fail and name the ID, telling the user to remove it from the curated file — test in Task 2 (validation) and Task 3 (`--check`).
- A reviewer-set `IL` in the gazetteer (as Lod is today): `build_gazetteer.py check` must reject it — test in Task 1.

---

### Task 1: Gazetteer: enforce the Holy Land convention, drop the sub-project-3 preview

**Files:**
- Modify: `scripts/build_gazetteer.py` (`place_index` ~line 59, `validate` ~line 226, `render_report` ~line 353, `load_state` ~line 404)
- Modify: `data/gazetteer.json` (the `Dióspoli seu Lyddæ in Palæstína` entry)
- Modify: `docs/gazetteer-report.md` (regenerated)
- Test: `tests/test_gazetteer.py`

**Interfaces:**
- Produces: `place_index(places) -> {la: {"it": [...], "occurrences": [...]}}` (the `entries` parameter and `lead_countries` are removed); `validate(...)` additionally errors on a country that `convention()` would change.

- [ ] **Step 1: Write the failing tests**

In `tests/test_gazetteer.py`:
- In `test_index` (~line 370): call `bg.place_index(places)` (drop `entries`), and expect `{"it": [...], "occurrences": [...]}` with no `lead_countries` key for both places.
- Remove the `"lead_countries": ...` key from every hand-built index dict (lines ~359, ~513-514, ~598, ~703-704).
- In `ReportTest.test_report_sections`: delete the assertion `self.assertIn("| `mr:0101-a` | Fictópoli | DE | FR |", md)` and add `self.assertNotIn("Preview", md)`.
- Add to the class that tests `validate` (search for `def test_` calls of `bg.validate(`; put it next to the ISO-code test):

```python
    def test_holy_land_convention(self):
        gaz = {"Fictópoli": {"wikidata": "Q1", "label": "Fictopolis", "country": "IL", "status": "reviewed"}}
        index = {"Fictópoli": {"it": [], "occurrences": ["mr:0101-a"]}}
        errors = bg.validate(gaz, index)
        self.assertTrue(any("IL" in e and "PS" in e for e in errors), errors)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_gazetteer -v 2>&1 | tail -20`
Expected: FAIL (`place_index()` missing argument / `lead_countries` mismatch; `Preview` found; holy-land test finds no error).

- [ ] **Step 3: Implement**

In `scripts/build_gazetteer.py`:

```python
def place_index(places):
    index = {}
    for mr_id, items in places.items():
        for it in items:
            slot = index.setdefault(it["la"], {"it": set(), "occurrences": set()})
            if "it" in it:
                slot["it"].add(it["it"])
            slot["occurrences"].add(mr_id)
    return {la: {"it": sorted(v["it"]), "occurrences": sorted(v["occurrences"])}
            for la, v in index.items()}
```

In `load_state`, drop the `entries = …martyrology_ids.json…` line and call `place_index(places)`. Grep for any other `place_index(` caller (`grep -n "place_index(" scripts/*.py`) and drop its second argument.

In `validate`, right after the existing "not an ISO 3166-1 alpha-2 code" check for an entry's country, add (import `convention` from `gazetteer_text` if not already imported; check the file's imports):

```python
        if e.get("country") and convention(e["country"]) != e["country"]:
            errors.append(f"{where}: country {e['country']} must be {convention(e['country'])} "
                          "(COUNTRY_CONVENTIONS in scripts/gazetteer_text.py)")
```

(`where` is the variable the surrounding checks already use for the entry's label; reuse it.)

In `render_report`, delete the `preview = [...]` computation and the five list items from `"## Preview: registry country differs from the opening place",` through the `*([f"| `{m}` | … preview] or ["| | | | |"]),` line.

In `data/gazetteer.json`, change the `"Dióspoli seu Lyddæ in Palæstína"` entry's `"country": "IL"` to `"country": "PS"`.

- [ ] **Step 4: Run the tests and the offline check**

Run: `python3 -m unittest tests.test_gazetteer 2>&1 | tail -3 && python3 scripts/build_gazetteer.py check`
Expected: `OK`; `ok: 2480 places decided, 37 queued`.

- [ ] **Step 5: Regenerate the report offline**

```bash
python3 - <<'EOF'
import sys, json
from pathlib import Path
sys.path.insert(0, "scripts")
import build_gazetteer as bg
root = Path(".")
gaz, review, index = bg.load_state(root)
(root / "docs" / "gazetteer-report.md").write_text(bg.render_report(gaz, index, review["operations"]), encoding="utf-8")
EOF
git diff --stat docs/gazetteer-report.md
```
Expected: only the Preview section disappears (`git diff docs/gazetteer-report.md` shows deletions only).

- [ ] **Step 6: Commit**

```bash
git add scripts/build_gazetteer.py tests/test_gazetteer.py data/gazetteer.json docs/gazetteer-report.md
git commit -m "gazetteer: enforce the Holy Land convention (Lod is PS); drop the sub-project 3 preview (#12)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01H2QwGLjGJersugqyQ4o2tf"
```

---

### Task 2: `registry_places.apply` and its validation

**Files:**
- Create: `scripts/registry_places.py`
- Test: `tests/test_registry_places.py`

**Interfaces:**
- Consumes: `gazetteer_text.ISO_CODES` (frozenset of codes), `gazetteer_text.convention(iso) -> iso`.
- Produces:
  - `validate(entries, gazetteer, curated) -> list[str]` — `entries`: the registry's `entries` list (current + deprecated); `gazetteer`: the `places` dict of `data/gazetteer.json`; `curated`: the `countries` dict of `data/countries_curated.json`.
  - `apply(entries, gazetteer, curated) -> list[dict]` — new list; raises `ValueError` (message: the errors joined by newlines) when `validate` returns errors.
  - `has_resolved_lead(entry, gazetteer) -> bool`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_registry_places.py`:

```python
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import registry_places as rp  # noqa: E402

GAZ = {
    "Fictópoli": {"wikidata": "Q1", "label": "Fictopolis", "country": "FR", "status": "auto"},
    "Altrópoli": {"wikidata": "Q2", "label": "Altropolis", "country": "DE", "status": "reviewed",
                  "text_says": [{"country": "AT", "it": "A Altropoli, nell’odierna Austria"}]},
    "Hierosólymæ": {"wikidata": "Q1218", "label": "Jerusalem", "country": "PS", "status": "reviewed"},
    "Nullópoli": {"wikidata": None, "status": "unresolved", "note": "n"},
}


def entry(mr_id, country, *places, **extra):
    e = {"id": mr_id, "month": 1, "day": 1, "entry": 1, "asterisk": False, "country": country}
    if places:
        e["places"] = [dict(p) for p in places]
    return e | extra


def lead(la, it=None, role="death"):
    p = {"role": role, "la": la, "source": "lead"}
    return p | ({"it": it} if it else {})


class ApplyTest(unittest.TestCase):
    def test_resolved_lead_sets_country_and_fields(self):
        out = rp.apply([entry("mr:0101-a", "IT", lead("Fictópoli", "A Fictopoli"))], GAZ, {})
        self.assertEqual(out[0]["country"], "FR")
        self.assertEqual(out[0]["places"][0], {"role": "death", "la": "Fictópoli", "it": "A Fictopoli",
                                               "source": "lead", "wikidata": "Q1", "label": "Fictopolis",
                                               "country": "FR"})

    def test_text_says_filtered_by_it(self):
        out = rp.apply([entry("mr:0101-a", "DE", lead("Altrópoli", "A Altropoli, nell’odierna Austria")),
                        entry("mr:0102-b", "DE", lead("Altrópoli", "Ad Altropoli"))], GAZ, {})
        self.assertEqual(out[0]["places"][0]["text_says"], [{"country": "AT", "it": "A Altropoli, nell’odierna Austria"}])
        self.assertNotIn("text_says", out[1]["places"][0])

    def test_queued_lead_falls_back_to_curated_and_gets_no_fields(self):
        out = rp.apply([entry("mr:0101-a", "IT", lead("Ignótia", "A Ignozia"))], GAZ, {"mr:0101-a": "ES"})
        self.assertEqual(out[0]["country"], "ES")
        self.assertEqual(out[0]["places"][0], lead("Ignótia", "A Ignozia"))

    def test_unresolved_place_gets_no_fields(self):
        out = rp.apply([entry("mr:0101-a", "IT", lead("Nullópoli"))], GAZ, {"mr:0101-a": "IT"})
        self.assertEqual(out[0]["places"][0], lead("Nullópoli"))

    def test_no_lead_uses_curated_value_note_and_null(self):
        curated_place = {"role": "cult", "la": "Fictópoli", "source": "curated"}
        out = rp.apply([entry("mr:0101-a", "IT", curated_place), entry("mr:0102-b", None),
                        entry("mr:0103-c", "IT")],
                       GAZ, {"mr:0101-a": "IT", "mr:0102-b": None, "mr:0103-c": {"country": "DE", "note": "died at Köln"}})
        self.assertEqual([e["country"] for e in out], ["IT", None, "DE"])
        self.assertEqual(out[0]["places"][0]["wikidata"], "Q1")  # curated (body) places get fields too

    def test_holy_land_convention_on_both_paths(self):
        gaz = GAZ | {"Lyddæ": {"wikidata": "Q207540", "label": "Lod", "country": "IL", "status": "reviewed"}}
        out = rp.apply([entry("mr:0101-a", "IL", lead("Lyddæ")), entry("mr:0102-b", "IL")], gaz, {"mr:0102-b": "IL"})
        self.assertEqual([e["country"] for e in out], ["PS", "PS"])
        self.assertEqual(out[0]["places"][0]["country"], "PS")

    def test_deprecated_untouched(self):
        dep = entry("mr:0101-z", "IL", deprecated=True, attested_in="x")
        out = rp.apply([dep], GAZ, {})
        self.assertEqual(out, [dep])

    def test_idempotent(self):
        entries = [entry("mr:0101-a", "IT", lead("Altrópoli", "A Altropoli, nell’odierna Austria"))]
        once = rp.apply(entries, GAZ, {})
        self.assertEqual(rp.apply(once, GAZ, {}), once)

    def test_key_order_of_place_items(self):
        out = rp.apply([entry("mr:0101-a", "IT", lead("Altrópoli", "A Altropoli, nell’odierna Austria"))], GAZ, {})
        self.assertEqual(list(out[0]["places"][0]),
                         ["role", "la", "source", "it", "wikidata", "label", "country", "text_says"])

    def test_input_not_mutated(self):
        entries = [entry("mr:0101-a", "IT", lead("Fictópoli"))]
        rp.apply(entries, GAZ, {})
        self.assertEqual(entries[0]["country"], "IT")
        self.assertNotIn("wikidata", entries[0]["places"][0])


class ValidateTest(unittest.TestCase):
    def errors(self, entries, curated):
        return "\n".join(rp.validate(entries, GAZ, curated))

    def test_resolved_lead_in_curated_file(self):
        self.assertRegex(self.errors([entry("mr:0101-a", "FR", lead("Fictópoli"))], {"mr:0101-a": "FR"}),
                         r"mr:0101-a: .*resolved.*remove it from data/countries_curated\.json")

    def test_missing_curated_value(self):
        self.assertRegex(self.errors([entry("mr:0101-a", "IT")], {}),
                         r"mr:0101-a: .*add .*data/countries_curated\.json")

    def test_unknown_and_deprecated_ids(self):
        dep = entry("mr:0101-z", "IT", deprecated=True)
        msg = self.errors([dep], {"mr:0101-z": "IT", "mr:0909-nemo": "IT"})
        self.assertIn("mr:0101-z: in data/countries_curated.json but deprecated", msg)
        self.assertIn("mr:0909-nemo: in data/countries_curated.json but unknown", msg)

    def test_bad_values(self):
        msg = self.errors([entry("mr:0101-a", None), entry("mr:0102-b", None), entry("mr:0103-c", None)],
                          {"mr:0101-a": "XX", "mr:0102-b": {"country": "IT", "nota": "x"}, "mr:0103-c": 7})
        self.assertIn("mr:0101-a: 'XX' is not an ISO 3166-1 alpha-2 code", msg)
        self.assertIn("mr:0102-b: unexpected keys", msg)
        self.assertIn("mr:0103-c: a value is a code, null or {country, note}", msg)

    def test_apply_raises_on_errors(self):
        with self.assertRaisesRegex(ValueError, "mr:0101-a"):
            rp.apply([entry("mr:0101-a", "IT")], GAZ, {})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_registry_places 2>&1 | tail -3`
Expected: FAIL / ERROR with `ModuleNotFoundError: No module named 'registry_places'`.

- [ ] **Step 3: Implement**

Create `scripts/registry_places.py`:

```python
#!/usr/bin/env python3
"""Copy the gazetteer onto the registry's places and derive each current entry's country.

Each place item of a current entry whose place the gazetteer resolves gets the
place's `wikidata`, `label`, `country` and the `text_says` claims of its own
Italian phrase. An entry's `country` is the country of its opening place when
the gazetteer resolves it, otherwise the value in data/countries_curated.json;
COUNTRY_CONVENTIONS (the Holy Land is PS) applies last. Deprecated entries are
untouched. No private source and no network are needed.

Usage:
  python3 scripts/registry_places.py [--check] [repo_root]

--check writes nothing and fails when the committed registry differs from what
the script would write (rerun it after build_gazetteer.py apply or after editing
data/gazetteer.json or data/countries_curated.json).
"""
from gazetteer_text import ISO_CODES, convention

PLACE_FIELDS = ("wikidata", "label", "country", "text_says")
CURATED = "data/countries_curated.json"


def _resolved(gazetteer, la):
    g = gazetteer.get(la)
    return g if g and g.get("wikidata") else None


def _lead(entry):
    return next((p for p in entry.get("places", []) if p["source"] == "lead"), None)


def has_resolved_lead(entry, gazetteer):
    lead = _lead(entry)
    return lead is not None and _resolved(gazetteer, lead["la"]) is not None


def _curated_country(value):
    return value["country"] if isinstance(value, dict) else value


def validate(entries, gazetteer, curated):
    errors = []
    current = {e["id"]: e for e in entries if not e.get("deprecated")}
    known = {e["id"] for e in entries}
    for mr_id in sorted(set(curated) - set(current)):
        errors.append(f"{mr_id}: in {CURATED} but {'deprecated' if mr_id in known else 'unknown'}")
    for mr_id, e in sorted(current.items()):
        if has_resolved_lead(e, gazetteer) and mr_id in curated:
            errors.append(f"{mr_id}: its opening place is resolved in the gazetteer; remove it from {CURATED}")
        elif not has_resolved_lead(e, gazetteer) and mr_id not in curated:
            errors.append(f"{mr_id}: no resolved opening place; add its country to {CURATED}")
    for mr_id, value in sorted(curated.items()):
        if isinstance(value, dict):
            if set(value) - {"country", "note"}:
                errors.append(f"{mr_id}: unexpected keys {sorted(set(value) - {'country', 'note'})}")
        elif value is not None and not isinstance(value, str):
            errors.append(f"{mr_id}: a value is a code, null or {{country, note}}")
            continue
        code = _curated_country(value)
        if code is not None and code not in ISO_CODES:
            errors.append(f"{mr_id}: {code!r} is not an ISO 3166-1 alpha-2 code")
    return errors


def _place(item, g):
    out = {k: v for k, v in item.items() if k not in PLACE_FIELDS}
    if g:
        out |= {"wikidata": g["wikidata"], "label": g["label"], "country": convention(g["country"])}
        claims = [c for c in g.get("text_says", []) if "it" in item and c["it"] == item["it"]]
        if claims:
            out["text_says"] = claims
    return out


def apply(entries, gazetteer, curated):
    errors = validate(entries, gazetteer, curated)
    if errors:
        raise ValueError("\n".join(errors))
    out = []
    for e in entries:
        if e.get("deprecated"):
            out.append(e)
            continue
        e = dict(e)
        if "places" in e:
            e["places"] = [_place(p, _resolved(gazetteer, p["la"])) for p in e["places"]]
        lead = _lead(e)
        code = (_resolved(gazetteer, lead["la"])["country"] if has_resolved_lead(e, gazetteer)
                else _curated_country(curated[e["id"]]))
        e["country"] = convention(code) if code else None
        out.append(e)
    return out
```

Note: `_place` strips the four fields before re-adding, which keeps the output idempotent; `item` keys stay first, in their order (in the registry: `role, la, it, source`).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest tests.test_registry_places -v 2>&1 | tail -3`
Expected: `OK` (15 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/registry_places.py tests/test_registry_places.py
git commit -m "registry_places: copy the gazetteer onto places and derive country (#12)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01H2QwGLjGJersugqyQ4o2tf"
```

---

### Task 3: The CLI, the seeded curated file, and the rewritten registry

**Files:**
- Modify: `scripts/registry_places.py` (add `load`, `render`, `main`)
- Create: `data/countries_curated.json`
- Modify: `data/martyrology_ids.json`, `registry/*.md` (regenerated)
- Test: `tests/test_registry_places.py`

**Interfaces:**
- Consumes: `apply`, `has_resolved_lead` (Task 2); `extract_registry.write_json(entries, deprecated, repo_root)`, `extract_registry.write_markdown(entries, repo_root)` (both write into `repo_root/data` and `repo_root/registry`; importing `extract_registry` does not need `openpyxl`).
- Produces: `main(argv) -> int` (0 ok, 1 when `--check` finds differences or validation fails).

- [ ] **Step 1: Save the countries before the change (for Task 5's table)**

```bash
SP=/tmp/claude-1000/-home-johnrdorazio-development-CatholicOS-org-crmedr/6fa842aa-7b89-4eba-a9c3-16ad1b27025d/scratchpad
git show main:data/martyrology_ids.json > $SP/registry-before.json
```

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_registry_places.py` (add `import json`, `import shutil`, `import tempfile` at the top):

```python
ROOT = Path(__file__).resolve().parent.parent


class CommittedDataTest(unittest.TestCase):
    def test_committed_registry_is_current(self):
        self.assertEqual(rp.main(["--check", str(ROOT)]), 0)


class CheckTest(unittest.TestCase):
    def test_check_reports_a_stale_country(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for rel in ("data/martyrology_ids.json", "data/gazetteer.json", "data/countries_curated.json"):
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(ROOT / rel, root / rel)
            shutil.copytree(ROOT / "registry", root / "registry")
            reg = json.loads((root / "data/martyrology_ids.json").read_text(encoding="utf-8"))
            e = next(x for x in reg["entries"] if x["id"] == "mr:0101-basilius")
            e["country"] = "GR"
            (root / "data/martyrology_ids.json").write_text(
                json.dumps(reg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self.assertEqual(rp.main(["--check", str(root)]), 1)
            self.assertEqual(rp.main([str(root)]), 0)
            self.assertEqual(rp.main(["--check", str(root)]), 0)
```

- [ ] **Step 3: Run them to verify they fail**

Run: `python3 -m unittest tests.test_registry_places 2>&1 | tail -3`
Expected: ERROR, `module 'registry_places' has no attribute 'main'`.

- [ ] **Step 4: Implement the CLI**

Add to `scripts/registry_places.py` (imports at the top of the module, below the docstring: `import json`, `import sys`, `import tempfile`, `from pathlib import Path`, and `import extract_registry as reg`):

```python
def load(repo_root):
    data = repo_root / "data"
    registry = json.loads((data / "martyrology_ids.json").read_text(encoding="utf-8"))
    gazetteer = json.loads((data / "gazetteer.json").read_text(encoding="utf-8"))["places"]
    curated = json.loads((repo_root / CURATED).read_text(encoding="utf-8"))["countries"]
    return registry["entries"], gazetteer, curated


def render(entries, repo_root):
    """Write the registry files for entries under repo_root (data/ and registry/)."""
    current = [e for e in entries if not e.get("deprecated")]
    deprecated = [e for e in entries if e.get("deprecated")]
    reg.write_json(current, deprecated, repo_root)
    reg.write_markdown(current, repo_root)


def _files(root):
    paths = [root / "data" / "martyrology_ids.json", *sorted((root / "registry").glob("*.md"))]
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in paths}


def main(argv):
    check = "--check" in argv
    rest = [a for a in argv if a != "--check"]
    repo_root = Path(rest[0]) if rest else Path(__file__).resolve().parent.parent
    entries, gazetteer, curated = load(repo_root)
    try:
        out = apply(entries, gazetteer, curated)
    except ValueError as e:
        print(f"invalid {CURATED}:\n{e}", file=sys.stderr)
        return 1
    if not check:
        render(out, repo_root)
        print(f"wrote data/martyrology_ids.json and registry/*.md "
              f"({sum(has_resolved_lead(e, gazetteer) for e in out if not e.get('deprecated'))} countries "
              f"from opening places, {len(curated)} curated)")
        return 0
    with tempfile.TemporaryDirectory() as d:
        render(out, Path(d))
        want, have = _files(Path(d)), _files(repo_root)
    stale = sorted(k for k in want if want[k] != have.get(k))
    changed = [n["id"] for n, o in zip(out, entries) if n != o]
    if stale:
        print("out of date: " + ", ".join(stale) + "\nentries: " + ", ".join(changed[:20])
              + "\nrun: python3 scripts/registry_places.py", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

`reg.write_json` / `write_markdown` take `repo_root` and create `data/` and `registry/` under it. Check that `extract_registry` still imports from `scripts/` when the script runs as `python3 scripts/registry_places.py` (Python adds the script's directory to `sys.path`, so `import extract_registry` and `import gazetteer_text` work).

- [ ] **Step 5: Seed `data/countries_curated.json`**

This one-off run reads only the committed registry (never the workbook). Notes come from the `COUNTRY_CORRECTIONS` comments of the six entries that have no resolved opening place.

```bash
python3 - <<'EOF'
import json, sys
sys.path.insert(0, "scripts")
import registry_places as rp
from gazetteer_text import convention
reg = json.load(open("data/martyrology_ids.json", encoding="utf-8"))["entries"]
gaz = json.load(open("data/gazetteer.json", encoding="utf-8"))["places"]
NOTES = {
    "mr:1115-albertus-magnus": "no opening place; died in Cologne",
    "mr:0320-nicetas": "Pojani (Apollonia)",
    "mr:0731-ignatius-de-loyola": "no opening place; died in Rome",
    "mr:0622-paulinus": "no opening place; Nola",
    "mr:1123-columbanus": "no opening place; died at Bobbio",
    "mr:0304-casimirus": "died at Grodno (the text says \"in Lituania\")",
}
countries = {}
for e in reg:
    if e.get("deprecated") or rp.has_resolved_lead(e, gaz):
        continue
    code = convention(e["country"]) if e.get("country") else None
    countries[e["id"]] = {"country": code, "note": NOTES[e["id"]]} if e["id"] in NOTES else code
assert set(NOTES) <= set(countries), set(NOTES) - set(countries)
out = {
    "$comment": "The modern country (ISO 3166-1 alpha-2, or null) of each current eulogy whose opening "
                "place the gazetteer does not resolve: no opening place, or one still awaiting review. "
                "A value is a code, null or {country, note}. Hand-curated; an entry leaves this file once "
                "its opening place is resolved (scripts/registry_places.py says so). Every other current "
                "eulogy takes the country of its opening place from data/gazetteer.json; the Holy Land is "
                "PS throughout. See docs/canonicalization-report.md (Countries from opening places).",
    "countries": dict(sorted(countries.items())),
}
open("data/countries_curated.json", "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
print(len(countries), "curated;", sum(1 for v in countries.values() if v is None), "null")
EOF
```
Expected: `416 curated; 24 null` (give or take the null count; 416 must match `378 + 38`).

- [ ] **Step 6: Rewrite the registry and run the tests**

Run: `python3 scripts/registry_places.py && python3 -m unittest tests.test_registry_places 2>&1 | tail -3`
Expected: `wrote ... (4224 countries from opening places, 416 curated)`; `OK`.

Sanity checks:

```bash
python3 - <<'EOF'
import json
SP = "/tmp/claude-1000/-home-johnrdorazio-development-CatholicOS-org-crmedr/6fa842aa-7b89-4eba-a9c3-16ad1b27025d/scratchpad"
old = {e["id"]: e for e in json.load(open(f"{SP}/registry-before.json"))["entries"]}
new = json.load(open("data/martyrology_ids.json"))
print(new["entry_count"], new["current_count"], new["deprecated_count"])
cur = [e for e in new["entries"] if not e.get("deprecated")]
assert not [e["id"] for e in cur if e.get("country") == "IL"]
assert [e["id"] for e in new["entries"]] == list(old)
assert all(e == old[e["id"]] for e in new["entries"] if e.get("deprecated"))
changed = [(e["id"], old[e["id"]].get("country"), e.get("country")) for e in cur if e.get("country") != old[e["id"]].get("country")]
print(len(changed), "countries changed")
EOF
git diff --stat
```
Expected: counts unchanged; `109 countries changed` (80 from opening places + 29 IL → PS); only `data/martyrology_ids.json`, `data/countries_curated.json` and `registry/*.md` changed. Spot-check `mr:0125-teresia-grillo` → IT, `mr:1219-maria-eva-de-providentia-et-maria-martha-de-iesu` → BY, `mr:0413-ioannes-bernardus-rousseau` → RE, `mr:1225-nativitas-domini` → PS.

- [ ] **Step 7: Run the whole suite**

Run: `python3 -m unittest discover -s tests 2>&1 | tail -3`
Expected: `OK`.

- [ ] **Step 8: Commit**

```bash
git add scripts/registry_places.py tests/test_registry_places.py data/countries_curated.json data/martyrology_ids.json registry/*.md
git commit -m "registry: places carry their Wikidata item; country follows the opening place (#12)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01H2QwGLjGJersugqyQ4o2tf"
```

---

### Task 4: `extract_registry.py` stops making countries

**Files:**
- Modify: `scripts/extract_registry.py` (delete the `COUNTRY_CORRECTIONS` block ~lines 1106-1147 and its use ~line 6195; `write_json` `$comment`; `write_markdown` intro; `main`)
- Modify: `data/martyrology_ids.json`, `registry/*.md` (regenerated with the new header texts)
- Test: `tests/test_registry.py`

**Interfaces:**
- Consumes: `registry_places.apply(entries, gazetteer, curated)`, `registry_places.load`-style reading of `data/gazetteer.json` and `data/countries_curated.json`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_registry.py`:

```python
class RegistryCountryTest(unittest.TestCase):
    def test_no_country_corrections(self):
        self.assertFalse(hasattr(r, "COUNTRY_CORRECTIONS"))

    def test_header_texts_describe_the_opening_place(self):
        with tempfile.TemporaryDirectory() as d:
            r.write_json([dict(ENTRY)], [], Path(d))
            r.write_markdown([dict(ENTRY)], Path(d))
            comment = json.loads((Path(d) / "data" / "martyrology_ids.json").read_text(encoding="utf-8"))["$comment"]
            md = (Path(d) / "registry" / "01-january.md").read_text(encoding="utf-8")
        self.assertIn("opening place", comment)
        self.assertIn("modern country of the place the elogium opens with", md)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m unittest tests.test_registry 2>&1 | tail -3`
Expected: FAIL (`COUNTRY_CORRECTIONS` exists; header texts lack the phrases).

- [ ] **Step 3: Implement**

In `scripts/extract_registry.py`:
- Delete the comment block starting `# Country codes the workbook got wrong (issue #8).` through the closing `}` of `COUNTRY_CORRECTIONS = {…}`.
- Delete the line `country = COUNTRY_CORRECTIONS.get(mr_id, country)` in `extract()`.
- In `write_json`, append to the `$comment` string: `" Each current entry's country is the modern country of its opening place (data/gazetteer.json), else data/countries_curated.json; the Holy Land is PS (scripts/registry_places.py)."`
- In `write_markdown`, replace `"`Country` is the ISO 3166-1 alpha-2 code of the modern country of the " "place of the elogium; "` with `"`Country` is the ISO 3166-1 alpha-2 code of the modern country of the " "place the elogium opens with (else a curated country; the Holy Land is PS); "`.
- In `main()`, after `entries = add_places(entries, places)`, add:

```python
    import registry_places  # the countries: never the workbook's (#12)
    gazetteer_path = repo_root / "data" / "gazetteer.json"
    gazetteer = json.load(open(gazetteer_path, encoding="utf-8"))["places"] if gazetteer_path.exists() else {}
    curated = json.load(open(repo_root / registry_places.CURATED, encoding="utf-8"))["countries"]
    entries = registry_places.apply(entries, gazetteer, curated)
```

(`apply` only reads `deprecated` to skip entries, and current entries here have none, so it is safe before `load_deprecated`.)

- Update the module docstring if it says where `country` comes from (`grep -n -i country scripts/extract_registry.py | head`).

- [ ] **Step 4: Regenerate and run the tests**

Run: `python3 scripts/registry_places.py && python3 -m unittest discover -s tests 2>&1 | tail -3`
Expected: `OK`. `git diff --stat` shows `data/martyrology_ids.json` (the `$comment` only) and the 12 `registry/*.md` intros.

- [ ] **Step 5: Commit**

```bash
git add scripts/extract_registry.py tests/test_registry.py data/martyrology_ids.json registry/*.md
git commit -m "extract_registry: drop COUNTRY_CORRECTIONS; countries come from registry_places (#12)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01H2QwGLjGJersugqyQ4o2tf"
```

---

### Task 5: Documentation

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/canonicalization-report.md`

- [ ] **Step 1: AGENTS.md**

- In the pipeline list, after step 5 (`build_gazetteer.py`), add a step (renumber the later steps):
  > **`scripts/registry_places.py`** copies the gazetteer onto the registry: each place item whose place is resolved gets `wikidata`, `label`, `country` and the `text_says` of its own Italian phrase, and each current entry's `country` becomes the country of its opening place, else the value in `data/countries_curated.json`, with the Holy Land as `PS` throughout. Offline, stdlib only, no private sources and no workbook. `extract_registry.py` calls it too.
  > - Run: `python3 scripts/registry_places.py` after `build_gazetteer.py apply` or any edit of `data/gazetteer.json` or `data/countries_curated.json`; `--check` (run by the tests) fails when the committed registry is out of date
- In step 1, remove any mention of the workbook as the source of `country` if present.
- Under "Where hand-corrections live", remove nothing about `COUNTRY_CORRECTIONS` (it is not listed) but add:
  > - `data/countries_curated.json` — the country of each current eulogy whose opening place the gazetteer does not resolve (code, `null`, or `{country, note}`); an entry leaves the file once its opening place is resolved. Every other country is fixed in `data/gazetteer.json`.

- [ ] **Step 2: canonicalization-report.md**

- At the end of the "Country-code corrections (September 2026)" section, add: "`COUNTRY_CORRECTIONS` was retired in October 2026: these codes now come from the opening place or from `data/countries_curated.json` (next section)."
- After the "Gazetteer (October 2026)" subsection (the end of the Places section), add a `### Countries from opening places (October 2026)` subsection: the rule (opening place → curated → `IL → PS`), the decisions (actual modern country over the text and old borders; the Holy Land is `PS` because the registry names the territory as historically called and takes no part in current disputes, each place's Wikidata item giving its current status; the workbook is no source), and the table of changed countries generated by:

```bash
python3 - <<'EOF'
import json
SP = "/tmp/claude-1000/-home-johnrdorazio-development-CatholicOS-org-crmedr/6fa842aa-7b89-4eba-a9c3-16ad1b27025d/scratchpad"
old = {e["id"]: e for e in json.load(open(f"{SP}/registry-before.json"))["entries"]}
for e in json.load(open("data/martyrology_ids.json"))["entries"]:
    if e.get("deprecated") or e.get("country") == old[e["id"]].get("country"):
        continue
    lead = next((p for p in e.get("places", []) if p["source"] == "lead"), None)
    place = f"{lead['label']} ({lead['wikidata']})" if lead and "wikidata" in lead else "no opening place"
    print(f"| `{e['id']}` | {place} | {old[e['id']].get('country') or ''} | {e['country'] or ''} |")
EOF
```
  with the header `| ID | Opening place | Before | After |` / `| --- | --- | --- | --- |`, and one line of counts above it ("109 entries: 80 from their opening place, 29 Holy Land entries with no opening place moved from IL to PS"; use the real numbers).

- [ ] **Step 3: Check and commit**

Run: `python3 -m unittest discover -s tests 2>&1 | tail -3 && python3 scripts/registry_places.py --check && echo current`
Expected: `OK`, `current`.

```bash
git add AGENTS.md docs/canonicalization-report.md
git commit -m "docs: countries from opening places, countries_curated.json (#12)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01H2QwGLjGJersugqyQ4o2tf"
```
