# Body places: roles in the API and on the site — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve each place mention's `roles` from martyrology-api, and show them on romanmartyrology.com: in the place popup of the eulogy text, and in the index of places and on the map, where every place a eulogy names is listed with its role and can be filtered by role.

**Architecture:** Two repositories, two PRs. martyrology-api's `MentionBase` gains an optional `roles` list (closed role set, `name` / `n` as for persons), served as crmedr writes it (null for a person); the same PR pins crmedr `c091e5a` and bumps the version to 0.18.0. In martyrology-frontend, `Mention` gains `roles`; a new `PlaceRoles` message namespace (gender-free noun phrases, six locales) labels them; the popup lists them; the places snapshot keeps every resolved place of a eulogy with its roles (it kept only the first), so the index of places lists a eulogy under each of its places with a `?role=` filter, and the map has one marker per (eulogy, place) with a role filter beside the typology one.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, pytest, uv (martyrology-api); Next.js, React, TypeScript, next-intl (typed messages), Vitest + Testing Library, Leaflet (martyrology-frontend).

**Spec:** `docs/superpowers/specs/2026-10-14-body-places-design.md` (rollout step 5: "martyrology-api: `roles` on mentions, pin bump, release; martyrology-frontend: the display"). Plans 1 and 2 are merged (crmedr #129, #130; martyrology-frontend #149).

## Global Constraints

- Roles: the closed set `death, burial, translation, dedication, cult, birth, education, religious_life, ministry, foundation, exile, journey, mention`, in that order (crmedr `ROLES`; frontend `PLACE_ROLES` in `lib/body-places.ts`).
- A role entry is `{role}` plus `name` / `n` when the item is one person's (`name` as person mentions call it; `n` from 2).
- crmedr `main` (`c091e5a`) already writes `roles` on all 8,528 place mentions (opening places only until the user's review is applied); `data/places.json` items carry `role` (and `person` / `n` on curated items).
- martyrology-api: API deploys only by publishing a GitHub release, after a version-bump PR; `gh release create` needs the full SHA for `--target`; the release is the user's call (ask before publishing).
- martyrology-frontend: every message key in all six locales (`messages/{en,it,fr,de,es,pt}.json`); a value equal to English needs a `SAME_AS_ENGLISH` entry in `lib/__tests__/messages.test.ts`; no browser dialogs.
- Commit trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_01H2QwGLjGJersugqyQ4o2tf`; PR footer `🤖 Generated with [Claude Code](https://claude.com/claude-code)` plus the session URL; merge commits.

## Review Focus

1. A place mention without `roles` (an API older than 0.18.0, or a curated mention crmedr wrote without them): the popup shows no role line and nothing breaks; Task 3 test `shows no role line without roles`.
2. A eulogy naming one place twice with two roles, or two printed forms of one place (`Romæ`, `in Urbe`): one index line and one marker for that (eulogy, place), listing both roles; Task 4 test `one entry per place, its roles merged`.
3. Map identity: with several places per eulogy, selecting a list row or clicking a cluster must reveal the right marker; keys are `<eulogy>@<qid>`, never the eulogy ID alone; Task 6 test `two places of one eulogy are two entries with their own keys`.
4. An index letter with no line of the chosen role: the role links go to the first letter (`/read/<ed>/places?role=…`), never to a letter page that would 404; Task 5 test `role links go to the first letter`.
5. A role the frontend does not know (a future crmedr role): shown as its ID spelled out, never a missing-message error; Task 3 test `an unknown role is spelled out`.

---

## Part A — martyrology-api (branch `feat/place-roles` from `main`)

### Task 1: `roles` on place mentions

**Files:**
- Modify: `src/martyrology_api/models.py` (`MentionBase`, new `PlaceRoleOut`, `PLACE_ROLES`)
- Modify: `src/martyrology_api/mentions.py` (`served`)
- Test: `tests/test_mentions.py`, `tests/test_openapi.py`

**Interfaces:**
- Produces: `PLACE_ROLES: tuple[str, ...]`; `class PlaceRoleOut(BaseModel)` with `role: Literal[...]`, `name: str | None = None`, `n: int | None = Field(default=None, ge=2)`, `extra="forbid"`; `MentionBase.roles: list[PlaceRoleOut] | None = None`; `served()` sets `roles` to None on a person; the OpenAPI `MentionOut.required` gains `"roles"`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_mentions.py`)

```python
def test_served_keeps_a_places_roles_in_order():
    rome = _m("Romæ", kind="place", start=7, end=11, qid="Q220",
              roles=[{"role": "birth"}, {"role": "ministry", "name": "Pionius"}, {"role": "burial", "name": "Felix", "n": 2}])
    out = served([rome], "Natale Romæ", [])[0].model_dump()
    assert out["roles"] == [
        {"role": "birth", "name": None, "n": None},
        {"role": "ministry", "name": "Pionius", "n": None},
        {"role": "burial", "name": "Felix", "n": 2},
    ]


def test_a_place_without_roles_is_served_with_null_roles():
    assert served([_m("Romæ", kind="place", start=7, end=11)], "Natale Romæ", [])[0].roles is None


def test_served_gives_a_person_no_roles_whatever_crmedr_wrote():
    felix = _m("Felix", start=7, end=12, name="Felix", roles=[{"role": "birth"}])
    assert served([felix], "Natale Felix", [])[0].roles is None


@pytest.mark.parametrize("bad", [
    [{"role": "nativity"}],  # not in the closed set
    [{"role": "birth", "n": 1}],  # n is from 2
    [{"role": "birth", "where": "text"}],  # nothing else in a role
])
def test_a_malformed_role_is_refused(bad):
    with pytest.raises(ValidationError):
        _m(kind="place", roles=bad)
```

In `tests/test_openapi.py::test_openapi_documents_the_mentions_of_a_eulogy`, change the `required` assertion and add the role schema checks:

```python
    assert set(m["required"]) == {"kind", "where", "start", "end", "form", "qid", "name", "n", "roles"}
    role = c["PlaceRoleOut"]
    assert role["properties"]["role"]["enum"][:2] == ["death", "burial"]
    assert len(role["properties"]["role"]["enum"]) == 13
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_mentions.py tests/test_openapi.py -q 2>&1 | tail -8`
Expected: FAIL — `roles` is ignored (no attribute / `None` where a list is expected; the malformed roles are accepted); `KeyError: 'PlaceRoleOut'`.

- [ ] **Step 3: Implement**

In `src/martyrology_api/models.py`, before `class MentionBase`:

```python
# crmedr's ROLES (scripts/extract_places.py), in its order: the role a place plays in a eulogy.
PLACE_ROLES = (
    "death", "burial", "translation", "dedication", "cult", "birth", "education",
    "religious_life", "ministry", "foundation", "exile", "journey", "mention",
)


class PlaceRoleOut(BaseModel):
    """The role a place plays in the eulogy (crmedr `roles`): died, buried, born, a see… there.
    `name` / `n` say whose role it is when the eulogy has several persons, as person mentions
    name them; null when it is everyone's."""

    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)

    role: Literal[PLACE_ROLES]  # type: ignore[valid-type]
    name: str | None = None
    n: int | None = Field(default=None, ge=2)
```

If the type checker or Pydantic rejects `Literal[PLACE_ROLES]`, spell the thirteen literals out in `Literal[...]` and set `PLACE_ROLES = typing.get_args(PlaceRole)` from a `PlaceRole = Literal[...]` alias instead.

In `MentionBase`, after `n`, and extend its docstring with one sentence (`roles`: a place's roles in the eulogy, in crmedr's item order; null for a person, or a place crmedr gave none):

```python
    # crmedr's roles: what the place is to the eulogy; null for a person.
    roles: list[PlaceRoleOut] | None = None
```

In `mentions.py::served`, beside the `name` override:

```python
            if m.kind == "place":
                served_as["name"] = None  # a place has no nominative, whatever crmedr wrote
            else:
                served_as["roles"] = None  # a person has no role as a place has
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest -q 2>&1 | tail -3 && uv run ruff check src tests && uv run ruff format --check src tests`
Expected: all pass; ruff clean (run `uv run ruff format src tests` if the format check fails, then rerun).

- [ ] **Step 5: Commit**

```bash
git add src/martyrology_api/models.py src/martyrology_api/mentions.py tests/test_mentions.py tests/test_openapi.py
git commit -m "mentions: serve a place's roles (crmedr#12)"
```

### Task 2: pin crmedr `c091e5a`, version 0.18.0, smoke test, PR

**Files:**
- Modify: `vendor/crmedr` (submodule), `Dockerfile` (`CRMEDR_REF`), `pyproject.toml`, `src/martyrology_api/__init__.py`, `uv.lock`

No new test: the gate is the real-data smoke test.

- [ ] **Step 1: Pin and bump**

```bash
git -C vendor/crmedr fetch -q origin && git -C vendor/crmedr checkout -q c091e5a3e97d00cf9d40e80833abe08c8da341b1
sed -i 's/^ARG CRMEDR_REF=.*/ARG CRMEDR_REF=c091e5a3e97d00cf9d40e80833abe08c8da341b1/' Dockerfile
sed -i 's/^version = "0.17.10"/version = "0.18.0"/' pyproject.toml
sed -i 's/^__version__ = "0.17.10"/__version__ = "0.18.0"/' src/martyrology_api/__init__.py
uv lock
```

- [ ] **Step 2: Smoke-test the vendored data**

```bash
uv run python - <<'EOF'
from fastapi.testclient import TestClient
from martyrology_api.app import create_app
from martyrology_api.config import Settings
app = create_app(Settings(_env_file=None, data_path="data/editions:vendor/texts/data/editions",
                          crmedr_path="vendor/crmedr", clbdr_path="vendor/clbdr", restricted_texts_access="public"))
with TestClient(app) as c:
    e = c.get("/api/v1/elogium/mr:0101-almachius").json()
    places = [m for p in e["editions"].values() for m in p.get("mentions", []) if m["kind"] == "place"]
    print(places[0]["roles"], len(places))
EOF
uv run pytest -q 2>&1 | tail -2
```

Expected: `[{'role': 'death', 'name': None, 'n': None}] 2` (Latin and Italian), the startup log reporting mentions served and none dropped for the 2004 editions; tests pass. If the elogium route's JSON nests mentions differently, read `EulogyOut` in `models.py` and adapt the print, not the assertion that the first place mention has `roles`.

- [ ] **Step 3: Commit, push, open the PR**

```bash
git add vendor/crmedr Dockerfile pyproject.toml src/martyrology_api/__init__.py uv.lock
git commit -m "Release 0.18.0: place roles on mentions; pin crmedr c091e5a (crmedr#12)"
git push -u origin feat/place-roles
gh pr create --title "Place roles on mentions; release 0.18.0 (crmedr#12)" --body "…"
```

The PR body says what `roles` is, that only opening places carry roles until the body-places review is applied (later crmedr pins add them with no API change), and that publishing the v0.18.0 release after merge deploys it. Footer as in Global Constraints. Do not publish the release: ask the user.

---

## Part B — martyrology-frontend (branch `feat/place-roles` from `main`)

### Task 3: roles in the place popup

**Files:**
- Modify: `lib/types.ts` (`Mention`), `lib/body-places.ts`, `components/markup/MentionPlaceCard.tsx`, `messages/{en,it,fr,de,es,pt}.json`, `lib/__tests__/messages.test.ts` (only if needed)
- Test: `components/__tests__/MentionPlaceCard.test.tsx`, `lib/__tests__/body-places.test.ts`

**Interfaces:**
- Produces:
  - `interface MentionRole { role: string; name?: string | null; n?: number | null }` (in `lib/types.ts`); `Mention.roles?: MentionRole[] | null`.
  - `type RolesT = ReturnType<typeof useTranslations<"PlaceRoles">>`; `roleLabel(t: RolesT, role: string): string`; `roleText(t: RolesT, r: MentionRole): string` (in `lib/body-places.ts`).
  - Messages: `PlaceRoles.<role>` for the 13 roles and `PlaceRoles.of` (`"{role} ({name})"`).

- [ ] **Step 1: Write the failing tests**

In `lib/__tests__/body-places.test.ts` add (render a probe through `@/test/intl` to get a real `t`):

```tsx
import { render, screen } from "@/test/intl";
import { useTranslations } from "next-intl";
import { roleText } from "@/lib/body-places";
import type { MentionRole } from "@/lib/types";

function Probe({ r }: { r: MentionRole }) {
  const t = useTranslations("PlaceRoles");
  return <p>{roleText(t, r)}</p>;
}

describe("roleText", () => {
  it("labels a role, with whose when given", () => {
    render(<><Probe r={{ role: "birth" }} /><Probe r={{ role: "ministry", name: "Pionius" }} /><Probe r={{ role: "burial", name: "Felix", n: 2 }} /></>);
    expect(screen.getByText("Place of birth")).toBeInTheDocument();
    expect(screen.getByText("Place of ministry (Pionius)")).toBeInTheDocument();
    expect(screen.getByText("Place of burial (Felix 2)")).toBeInTheDocument();
  });

  it("an unknown role is spelled out", () => {
    render(<Probe r={{ role: "pilgrimage_site" }} />);
    expect(screen.getByText("pilgrimage site")).toBeInTheDocument();
  });
});
```

(The file is `.ts`: rename it to `body-places.test.tsx` with `git mv` so it can hold JSX.)

In `components/__tests__/MentionPlaceCard.test.tsx` add:

```tsx
  it("lists the place's roles in the interface language, with whose", async () => {
    card("it", { ...caesarea, roles: [{ role: "birth" }, { role: "ministry", name: "Basilius" }] });
    expect(screen.getByRole("list", { name: "Ruoli del luogo" })).toHaveTextContent("Luogo di nascita");
    expect(screen.getByText("Luogo del ministero (Basilius)")).toBeInTheDocument();
    await waitFor(() => expect(mapSpy).toHaveBeenCalled());
  });

  it("shows no role line without roles", async () => {
    card();
    expect(screen.queryByRole("list", { name: "Roles of the place" })).not.toBeInTheDocument();
    await waitFor(() => expect(mapSpy).toHaveBeenCalled());
  });
```

- [ ] **Step 2: Run them to verify they fail**

Run: `npx vitest run lib/__tests__/body-places.test.tsx components/__tests__/MentionPlaceCard.test.tsx`
Expected: FAIL — `roleText` is not exported; no list "Ruoli del luogo".

- [ ] **Step 3: Implement**

Messages — `en.json`, a new top-level namespace, and `Markup.roles` (the list's accessible name):

```json
"PlaceRoles": {
  "death": "Place of death", "burial": "Place of burial", "translation": "Place of translation",
  "dedication": "Place of dedication", "cult": "Place of cult", "birth": "Place of birth",
  "education": "Place of education", "religious_life": "Place of religious life",
  "ministry": "Place of ministry", "foundation": "Place of a foundation", "exile": "Place of exile",
  "journey": "Place on a journey", "mention": "Named in the eulogy", "of": "{role} ({name})"
}
```

`"Markup": { …, "roles": "Roles of the place" }`.

Italian: `"Luogo della morte", "Luogo della sepoltura", "Luogo della traslazione", "Luogo della dedicazione", "Luogo del culto", "Luogo di nascita", "Luogo della formazione", "Luogo della vita religiosa", "Luogo del ministero", "Luogo di una fondazione", "Luogo dell'esilio", "Luogo di un viaggio", "Nominato nell'elogio", "{role} ({name})"`, `Markup.roles` "Ruoli del luogo". French, German, Spanish, Portuguese likewise, as noun phrases ("Lieu de naissance", "Geburtsort", "Lugar de nacimiento", "Local de nascimento"…): noun phrases carry no grammatical gender of the saint, which "born here" would in five of the six languages. `PlaceRoles.of` is `"{role} ({name})"` in every locale: add `"PlaceRoles.of": ALL` to `SAME_AS_ENGLISH`, and any other value the test flags as equal to English.

`lib/types.ts`, before `Mention`, and in `Mention` after `n`:

```ts
/** The role a place plays in a eulogy (crmedr `roles`); `name` / `n` say whose, as person mentions name them. */
export interface MentionRole {
  role: string;
  name?: string | null;
  n?: number | null;
}
```

```ts
  /** A place's roles in the eulogy, in crmedr's order; null for a person. Absent from APIs older than v0.18.0. */
  roles?: MentionRole[] | null;
```

`lib/body-places.ts` (append):

```ts
import type { useTranslations } from "next-intl";
import type { MentionRole } from "@/lib/types";

export type RolesT = ReturnType<typeof useTranslations<"PlaceRoles">>;

/** A role's label in the interface language; a role this site does not know yet, spelled out from its ID. */
export function roleLabel(t: RolesT, role: string): string {
  return t.has(role as PlaceRole) ? t(role as PlaceRole) : role.replace(/_/g, " ");
}

/** A role's label, with whose role it is when the eulogy says ("Place of ministry (Pionius)"). */
export function roleText(t: RolesT, r: MentionRole): string {
  const label = roleLabel(t, r.role);
  return r.name ? t("of", { role: label, name: r.n ? `${r.name} ${r.n}` : r.name }) : label;
}
```

(Put the two `import type` lines at the top of the file.)

`components/markup/MentionPlaceCard.tsx`: `const tRoles = useTranslations("PlaceRoles");`, import `roleText`, and after the italic `mention.form` paragraph:

```tsx
      {mention.roles && mention.roles.length > 0 && (
        <ul aria-label={t("roles")} className="mt-1 text-sm">
          {mention.roles.map((r, i) => (
            <li key={i}>{roleText(tRoles, r)}</li>
          ))}
        </ul>
      )}
```

(Shown whether or not the entity has loaded: the roles come with the mention.)

- [ ] **Step 4: Run tests**

Run: `npx vitest run lib/__tests__/body-places.test.tsx components/__tests__/MentionPlaceCard.test.tsx lib/__tests__/messages.test.ts && npx tsc --noEmit`
Expected: PASS; no type errors.

- [ ] **Step 5: Commit**

```bash
git add lib/types.ts lib/body-places.ts lib/__tests__/body-places.test.tsx components/markup/MentionPlaceCard.tsx components/__tests__/MentionPlaceCard.test.tsx messages/*.json lib/__tests__/messages.test.ts
git commit -m "reader: a place's roles in its popup (crmedr#12)"
```

### Task 4: the snapshot keeps every resolved place of a eulogy, with its roles

**Files:**
- Modify: `scripts/snapshot-registry.mjs` (`buildPlaces`, `resolvedQids`), `lib/places.ts`, `data/places-snapshot.json` (regenerated)
- Modify (fixtures only): every test that builds a `PlacesSnapshot` (`grep -rln "eulogies" lib/__tests__ components/__tests__` and keep those whose fixture has `place:` records: `snapshot.test.ts`, `places-index.test.ts`, `map-data.test.ts`, `MapPage.test.tsx`, `PlacesRoute.test.tsx`, and any other the grep finds)
- Test: `lib/__tests__/snapshot.test.ts`

**Interfaces:**
- Produces (in `lib/places.ts`):
  ```ts
  export interface PlaceAt { place: string; la: string; it?: string; roles: MentionRole[] }
  export interface EulogyPlaces { typology: string | null; places: PlaceAt[] }
  export interface PlacesSnapshot { places: Record<string, PlaceInfo>; eulogies: Record<string, EulogyPlaces> }
  ```
  One `PlaceAt` per QID per eulogy, in crmedr's item order (the opening place first); `la` / `it` are the first item's; `roles` every item's on that QID, in order, `{role}` plus `name` (crmedr `person`) / `n`.
  `EulogyPlace` is removed.

Fixture rule for the tests this changes: `{place: Q, la: L, it?: I, typology: T}` becomes `{typology: T, places: [{place: Q, la: L, it?: I, roles: [{role: "death"}]}]}`.

- [ ] **Step 1: Write the failing tests** — in `snapshot.test.ts`'s `describe("buildPlaces")`, replace the expected `eulogies` of the first test with:

```ts
      eulogies: {
        "mr:0101-almachius": { typology: "dies_natalis", places: [{ place: "Q220", la: "Romæ", it: "A Roma", roles: [{ role: "death" }] }] },
        "mr:0102-x": { typology: "depositio", places: [{ place: "Q490", la: "Mediolani", roles: [{ role: "burial" }] }] },
        "mr:0104-z": { typology: "dies_natalis", places: [{ place: "Q999", la: "Insula", roles: [{ role: "death" }] }] },
      },
```

(rename that test to "gives each eulogy its resolved places with their roles, typology, and the places' coordinates and labels"), and add:

```ts
  it("one entry per place, its roles merged", () => {
    const doc = { places: { "mr:0105-w": [
      { role: "death", la: "Romæ", source: "lead" },
      { role: "birth", la: "Mediolani", source: "curated" },
      { role: "burial", la: "in Urbe", source: "curated", person: "Felix", n: 2 },
      { role: "ministry", la: "Nusquam", source: "curated" },
    ] } };
    const gaz = { places: { ...gazetteerDoc.places, "in Urbe": { wikidata: "Q220", label: "Rome", country: "IT", status: "reviewed" } } };
    expect(buildPlaces(doc, gaz, { typology: {} }, coords).eulogies["mr:0105-w"]).toEqual({
      typology: null,
      places: [
        { place: "Q220", la: "Romæ", roles: [{ role: "death" }, { role: "burial", name: "Felix", n: 2 }] },
        { place: "Q490", la: "Mediolani", roles: [{ role: "birth" }] },
      ],
    });
    expect(resolvedQids(doc, gaz)).toEqual(["Q220", "Q490"]);
  });
```

Convert the other `buildPlaces` tests' expectations by the fixture rule.

- [ ] **Step 2: Run to verify it fails**

Run: `npx vitest run lib/__tests__/snapshot.test.ts`
Expected: FAIL — the eulogies still have the old shape; the second place is missing.

- [ ] **Step 3: Implement**

In `scripts/snapshot-registry.mjs`, replace `firstResolved` with:

```js
/**
 * A eulogy's stated places that the gazetteer resolves to a Wikidata item: one per item, in the
 * order crmedr states them (the opening place first), its first printed forms, and every stated
 * role on it, with whose role it is when the eulogy says.
 * @param {StatedPlace[]} stated
 * @param {Record<string, GazetteerPlace>} gazetteer
 */
function resolvedPlaces(stated, gazetteer) {
  /** @type {Map<string, {place: string, la: string, it?: string, roles: {role: string, name?: string, n?: number}[], g: GazetteerPlace}>} */
  const out = new Map();
  for (const s of stated) {
    const g = gazetteer[s.la];
    if (!g?.wikidata) continue;
    const role = { role: s.role, ...(s.person ? { name: s.person } : {}), ...(s.person && s.n ? { n: s.n } : {}) };
    const hit = out.get(g.wikidata);
    if (hit) hit.roles.push(role);
    else out.set(g.wikidata, { place: g.wikidata, la: s.la, ...(s.it ? { it: s.it } : {}), roles: [role], g });
  }
  return [...out.values()];
}
```

Update the `StatedPlace` typedef to `{role: string, la: string, it?: string, source?: string, person?: string, n?: number}`. In `resolvedQids`, add every `resolvedPlaces(...)` QID. In `buildPlaces`:

```js
  for (const [id, stated] of Object.entries(placesDoc.places)) {
    const hits = resolvedPlaces(stated, gazetteerDoc.places);
    if (hits.length === 0) continue;
    for (const hit of hits) {
      places[hit.place] ??= {
        label: hit.g.label ?? hit.place,
        country: hit.g.country ?? "",
        coords: coords[hit.place] ?? null,
        // In LABEL_LANGS order: Wikidata answers in any order, which would reorder the snapshot on every run.
        ...(labels[hit.place] ? { labels: Object.fromEntries(LABEL_LANGS.flatMap((l) => (l in labels[hit.place] ? [[l, labels[hit.place][l]]] : []))) } : {}),
      };
    }
    eulogies[id] = {
      typology: typologyDoc.typology[id] ?? null,
      places: hits.map(({ g: _g, ...p }) => p),
    };
  }
```

and its JSDoc / the `eulogies` typedef to the new shape; the doc comment's first sentence becomes "each current eulogy's places (those it states that the gazetteer resolves, the opening place first) with their roles".

`lib/places.ts`: replace `EulogyPlace` with `PlaceAt` / `EulogyPlaces` from the Interfaces block (import `MentionRole` from `@/lib/types`), and `PlacesSnapshot.eulogies: Record<string, EulogyPlaces>`.

Convert the fixtures by the rule. `lib/places-index.ts` and `lib/map-data.ts` stop compiling: make each read the first place for now (`const ep = snap.eulogies[c.id]; const first = ep?.places[0];` and use `first.place`, `first.la`, `first[form]`, `ep.typology`), so this task stays green; Tasks 5 and 6 replace that.

- [ ] **Step 4: Regenerate the snapshot and run everything**

Run: `npm run snapshot-registry -- ../crmedr && git diff --stat data/ && npm test 2>&1 | tail -3 && npx tsc --noEmit`
Expected: `data/places-snapshot.json` rewritten in the new shape (still 4,228 eulogies, nearly all with one place); other snapshot files unchanged except as the crmedr pin moved them (read `git diff --stat`: if files other than `places-snapshot.json` change, they are crmedr changes since the last snapshot; keep them only if they come from merged crmedr work, and say so in the PR); tests pass; no type errors.

- [ ] **Step 5: Commit**

```bash
git add scripts/snapshot-registry.mjs lib/places.ts lib/places-index.ts lib/map-data.ts data/places-snapshot.json lib/__tests__ components/__tests__
git commit -m "places snapshot: every resolved place of a eulogy, with its roles (crmedr#12)"
```

(`git add lib/__tests__ components/__tests__` adds only modified tracked fixtures; check `git status` first that nothing untracked is there.)

### Task 5: the index of places: a eulogy under each of its places, its roles, a role filter

**Files:**
- Modify: `lib/places-index.ts`, `components/PlacesIndex.tsx`, `components/LetterNav.tsx`, `app/[locale]/read/[edition]/places/page.tsx`, `app/[locale]/read/[edition]/places/[letter]/page.tsx`, `app/[locale]/read/[edition]/places/shared.tsx`, `messages/*.json`
- Test: `lib/__tests__/places-index.test.ts`, `components/__tests__/PlacesIndex.test.tsx`

**Interfaces:**
- Consumes: `EulogyPlaces`, `PlaceAt` (Task 4); `roleLabel`, `RolesT` (Task 3); `PLACE_ROLES`.
- Produces:
  - `PlaceLine` gains `key: string` (`<eulogy>@<qid>`) and `roles: MentionRole[]`.
  - `placesIndex(catalog, snap, edition, locale, role?: string | null)`: with `role`, only the lines having it (places with none dropped, letters recomputed); `PlacesIndexData` gains `roles: [string, number][]` (lines per role over the whole index, unfiltered, in `PLACE_ROLES` order) and `role: string | null`. `placed` / `printed` still count eulogies, unfiltered.
  - `LetterBar` / `LetterPager` gain an optional `query?: string` appended to each letter link.
  - `PlacesPage({ locale, edition, slug, role })`; routes read `searchParams.role`, kept only when in `PLACE_ROLES`.
  - Messages: `Places.roleFilter` ("Role"), `Places.allRoles` ("All").

- [ ] **Step 1: Write the failing tests**

In `lib/__tests__/places-index.test.ts` (read its existing fixtures first; build a snapshot with one eulogy at two places):

```ts
  it("lists a eulogy under each of its places, with that place's roles", () => {
    const snap = { places: { Q220: ROME, Q490: MILAN }, eulogies: {
      "mr:0101-a": { typology: "dies_natalis", places: [
        { place: "Q220", la: "Romæ", roles: [{ role: "death" }] },
        { place: "Q490", la: "Mediolani", roles: [{ role: "birth" }] },
      ] } } };
    const idx = placesIndex([entry("mr:0101-a", "01-01")], snap, "martyrologium_romanum_2004", "en");
    const lines = idx.letters.flatMap((l) => l.places).map((p) => [p.qid, p.lines.map((x) => [x.key, x.roles])]);
    expect(lines).toEqual([
      ["Q490", [["mr:0101-a@Q490", [{ role: "birth" }]]]],
      ["Q220", [["mr:0101-a@Q220", [{ role: "death" }]]]],
    ]);
    expect(idx.placed).toBe(1);
    expect(idx.roles).toEqual([["death", 1], ["birth", 1]]);
  });

  it("a role keeps only its lines, and the places and letters that have them", () => {
    // the same snap as the test above: hoist it to the describe block
    const idx = placesIndex([entry("mr:0101-a", "01-01")], snap, "martyrologium_romanum_2004", "en", "birth");
    expect(idx.letters.map((l) => l.letter)).toEqual(["M"]);
    expect(idx.role).toBe("birth");
    expect(idx.roles).toEqual([["death", 1], ["birth", 1]]);
  });
```

(`ROME`, `MILAN`, `entry` stand for the file's existing place / catalog-entry fixtures or helpers; if it has none by those names, define them at the top of the new tests from the file's existing literals: `ROME = { label: "Rome", country: "IT", coords: [41.9, 12.5] }`, `MILAN = { label: "Milan", country: "IT", coords: [45.5, 9.2] }`, `entry = (id, day) => ({ id, day_printed: day, present: true, entry: 1, subject: id })` cast to `CatalogEntryOut`.)

In `components/__tests__/PlacesIndex.test.tsx` (its hand-made `PlacesIndexData` gains `roles: [["death", 2], ["birth", 1]]`, `role: null`, and each line `key` and `roles`):

```tsx
  it("shows a line's roles unless it is only the place of death", () => {
    // one line with roles [{role:"death"}], one with [{role:"birth"},{role:"ministry",name:"Pionius"}]
    renderIndex(data);
    expect(screen.getByText(/Place of birth · Place of ministry \(Pionius\)/)).toBeInTheDocument();
    expect(screen.queryByText(/Place of death/)).not.toBeInTheDocument();
  });

  it("role links go to the first letter", () => {
    renderIndex(data);
    const nav = screen.getByRole("navigation", { name: "Role" });
    expect(within(nav).getByRole("link", { name: "Place of birth (1)" })).toHaveAttribute("href", "/en/read/martyrologium_romanum_2004/places?role=birth");
    expect(within(nav).getByText("All")).not.toHaveAttribute("href"); // the current choice is not a link
  });

  it("letter links keep the role", () => {
    renderIndex({ ...data, role: "birth" });
    for (const a of within(screen.getByRole("navigation", { name: "Letters" })).queryAllByRole("link"))
      expect(a.getAttribute("href")).toMatch(/\?role=birth$/);
  });
```

(`renderIndex` stands for how the file renders `PlacesIndex`; use its existing call and props.)

- [ ] **Step 2: Run them to verify they fail**

Run: `npx vitest run lib/__tests__/places-index.test.ts components/__tests__/PlacesIndex.test.tsx`
Expected: FAIL — only the first place is indexed; no `roles`/`role` on the data; no "Role" navigation.

- [ ] **Step 3: Implement**

`lib/places-index.ts` — `PlaceLine` gains:

```ts
  /** `<eulogy>@<qid>`: a eulogy is listed once under each place it names. */
  key: string;
  /** What the place is to the eulogy (crmedr roles), in crmedr's order. */
  roles: MentionRole[];
```

`PlacesIndexData` gains `roles: [string, number][]` (doc: "lines per role over the whole index, in crmedr's role order, whatever role is chosen") and `role: string | null`. In `placesIndex(catalog, snap, edition, locale, role: string | null = null)`, the loop body becomes:

```ts
    const ep = snap.eulogies[c.id];
    const at = (ep?.places ?? []).filter((pa) => snap.places[pa.place]);
    if (!ep || at.length === 0) continue;
    placed++;
    for (const pa of at) {
      for (const r of new Set(pa.roles.map((x) => x.role))) roleCount.set(r, (roleCount.get(r) ?? 0) + 1);
      if (role && !pa.roles.some((x) => x.role === role)) continue;
      const place = snap.places[pa.place];
      let p = byPlace.get(pa.place);
      if (!p) {
        p = { qid: pa.place, label: placeLabel(place, pa.place, locale), labelLang: placeLabelLang(place, locale), country: place.country, lines: [] };
        byPlace.set(pa.place, p);
      }
      p.lines.push({
        id: c.id,
        key: `${c.id}@${pa.place}`,
        day: { mm: Number(m[1]), dd: Number(m[2]) },
        entry: c.entry ?? null,
        subject: c.subject ?? c.id,
        printed: (form && pa[form]) || null,
        typology: ep.typology,
        roles: pa.roles,
      });
    }
```

with `const roleCount = new Map<string, number>();` before the loop, and the return:

```ts
  const rank = (r: string) => (PLACE_ROLES as readonly string[]).indexOf(r) + 1 || PLACE_ROLES.length + 1;
  return { letters, placed, printed, role, roles: [...roleCount].sort(([a], [b]) => rank(a) - rank(b)) };
```

(Cross-references are built from `places`, which now holds only the places with lines of the chosen role: a "see" for a place not shown is not made. Keep it so.)

`components/LetterNav.tsx`: both components take `query = ""` and append it: `` href={`${base}/${letterSlug(l)}${query}`} `` (and the pager's two links).

`components/PlacesIndex.tsx`:
- `const tRoles = useTranslations("PlaceRoles");`, import `roleLabel, roleText`.
- `const q = index?.role ? `?role=${encodeURIComponent(index.role)}` : "";` passed as `query={q}` to `LetterBar` / `LetterPager`.
- Each line: `key={line.key}`, and after the typology span:

  ```tsx
                {!(line.roles.length === 1 && line.roles[0].role === "death") && line.roles.length > 0 && (
                  <span className="text-slate-600"> · {line.roles.map((r) => roleText(tRoles, r)).join(" · ")}</span>
                )}
  ```

  (A place of death alone is the norm, as the dies natalis is for the typology: it goes unsaid.)
- Above the letter bar, when `index.roles.length > 1`:

  ```tsx
            <nav aria-label={t("roleFilter")} className="mb-3 text-center text-sm">
              {index.role ? <Link href={`/read/${ed}/places`} className="underline">{t("allRoles")}</Link> : <span>{t("allRoles")}</span>}
              {index.roles.map(([r, n]) => (
                <Fragment key={r}>
                  {" · "}
                  {index.role === r ? (
                    <span>{roleLabel(tRoles, r)} ({n})</span>
                  ) : (
                    <Link href={`/read/${ed}/places?role=${encodeURIComponent(r)}`} className="underline">{roleLabel(tRoles, r)} ({n})</Link>
                  )}
                </Fragment>
              ))}
            </nav>
  ```

  (`Fragment` from `react`.) The empty state stays as is; when a role is chosen and `index.letters` is empty, show `t("empty")` as today.

Routes: `places/page.tsx` and `[letter]/page.tsx` take `searchParams: Promise<{ role?: string | string[] }>`, and pass `role: typeof sp.role === "string" && (PLACE_ROLES as readonly string[]).includes(sp.role) ? sp.role : null` to `PlacesPage`, which passes it to `placesIndex`. A role-filtered letter page with no such letter 404s as an unknown letter does today; the role links never lead there.

Messages: `Places.roleFilter` "Role" / it "Ruolo" / fr "Rôle" / de "Rolle" / es "Papel" / pt "Papel"; `Places.allRoles` "All" / "Tutti" / "Tous" / "Alle" / "Todos" / "Todos".

- [ ] **Step 4: Run tests**

Run: `npm test 2>&1 | tail -3 && npx tsc --noEmit && npm run lint 2>&1 | tail -2`
Expected: all pass; no type or lint errors.

- [ ] **Step 5: Commit**

```bash
git add lib/places-index.ts components/PlacesIndex.tsx components/LetterNav.tsx "app/[locale]/read/[edition]/places" messages/*.json lib/__tests__/places-index.test.ts components/__tests__/PlacesIndex.test.tsx lib/__tests__/messages.test.ts
git commit -m "index of places: every place a eulogy names, with its roles and a role filter (crmedr#12)"
```

### Task 6: the map: one marker per (eulogy, place), its roles, a role filter

**Files:**
- Modify: `lib/map-data.ts`, `components/MapPage.tsx`, `components/MapSidebar.tsx`, `components/EulogyMap.tsx`, `messages/*.json`
- Test: `lib/__tests__/map-data.test.ts`, `components/__tests__/MapSidebar.test.tsx`, `components/__tests__/MapPage.test.tsx`, `components/__tests__/EulogyMap.test.tsx`

**Interfaces:**
- Consumes: `EulogyPlaces` (Task 4), `roleLabel`, `roleText` (Task 3), `PLACE_ROLES`.
- Produces:
  - `MapEntry` gains `key: string` (`<eulogy>@<qid>`, the entry's identity everywhere: markers, selection, list rows, cluster picks) and `roles: MentionRole[]`. `id` stays the eulogy ID (shown, and the reader link).
  - `MapFilters` gains `hiddenRoles: Set<string>`; an entry is shown while any of its roles is not hidden (an entry with no roles always is).
  - `facetCounts` returns `roles: [string, number][]` too (entries per role, under the search and the other two facets; `PLACE_ROLES` order), and the typology and country counts honour the role facet.
  - `MapPage`'s `selected` / `place` and `MapSidebar`'s `selected` / `onSelect` / `EulogyMap`'s `onSelect` / `onPlace` carry entry keys.
  - Messages: `Map.roleLegend` ("Role of the place").

- [ ] **Step 1: Write the failing tests**

`lib/__tests__/map-data.test.ts` (read its fixtures first; same snapshot as Task 5's test):

```ts
  it("two places of one eulogy are two entries with their own keys", () => {
    const { entries } = mapEntries([entry("mr:0101-a", "01-01")], snapTwo, "en");
    expect(entries.map((e) => [e.key, e.id, e.qid, e.roles])).toEqual([
      ["mr:0101-a@Q220", "mr:0101-a", "Q220", [{ role: "death" }]],
      ["mr:0101-a@Q490", "mr:0101-a", "Q490", [{ role: "birth" }]],
    ]);
  });

  it("hiding a role hides the entries that have no other", () => {
    const { entries } = mapEntries([entry("mr:0101-a", "01-01")], snapTwo, "en");
    const f = { query: "", hiddenTypologies: new Set<string>(), countries: new Set<string>(), hiddenRoles: new Set(["birth"]) };
    expect(filterEntries(entries, f).map((e) => e.key)).toEqual(["mr:0101-a@Q220"]);
    expect(facetCounts(entries, { ...f, hiddenRoles: new Set() }).roles).toEqual([["death", 1], ["birth", 1]]);
  });
```

(`snapTwo` = the two-place snapshot of Task 5's test, both places with coordinates; `entry` as there. Every existing `MapFilters` literal in the tests gains `hiddenRoles: new Set()`.)

`components/__tests__/MapSidebar.test.tsx`: the props' `facets` gain `roles: [["death", 2], ["birth", 1]]` and results' entries `key` / `roles`; add:

```tsx
  it("filters by role", () => {
    const onFilters = vi.fn();
    render(<MapSidebar {...props} onFilters={onFilters} />);
    const group = screen.getByRole("group", { name: "Role of the place" });
    fireEvent.click(within(group).getByRole("checkbox", { name: "Place of birth (1)" }));
    expect(onFilters.mock.lastCall![0].hiddenRoles).toEqual(new Set(["birth"]));
  });

  it("selects a row by its entry key", () => {
    const onSelect = vi.fn();
    render(<MapSidebar {...props} onSelect={onSelect} />);
    fireEvent.click(screen.getAllByRole("button", { name: new RegExp(props.results[0].subject) })[0]);
    expect(onSelect).toHaveBeenCalledWith(props.results[0].key);
  });
```

`components/__tests__/EulogyMap.test.tsx`: wherever it asserts `onSelect` / `onPlace` with an eulogy ID, the entries gain `key` and the assertions expect keys (read the file; change only those assertions and fixtures).

- [ ] **Step 2: Run them to verify they fail**

Run: `npx vitest run lib/__tests__/map-data.test.ts components/__tests__/MapSidebar.test.tsx components/__tests__/EulogyMap.test.tsx`
Expected: FAIL — one entry per eulogy, no `key`/`roles`; no "Role of the place" group; `onSelect` called with the eulogy ID.

- [ ] **Step 3: Implement**

`lib/map-data.ts`:
- `MapEntry` gains `key` and `roles` (doc comments as in the Interfaces block); `MapFilters` gains `hiddenRoles`.
- `mapEntries` loop: for each `pa` of `ep.places` whose place has coordinates, push an entry with `key: \`${c.id}@${pa.place}\``, `qid: pa.place`, `la: pa.la`, `roles: pa.roles` (the rest as today); `unmapped` counts printed eulogies none of whose places has coordinates. Sort as today, then by the place's position in `ep.places` (stable sort keeps it: push in order).
- Filters:

  ```ts
  const roleOk = (e: MapEntry, f: MapFilters) => e.roles.length === 0 || e.roles.some((r) => !f.hiddenRoles.has(r.role));
  ```

  `filterEntries` adds `&& roleOk(e, f)`; `facetCounts`: typologies counted under `countryOk && roleOk`, countries under `typologyOk && roleOk`, and

  ```ts
  const roleRank = (r: string) => (PLACE_ROLES as readonly string[]).indexOf(r) + 1 || PLACE_ROLES.length + 1;
  const roles = new Map<string, number>();
  for (const e of searched.filter((e) => typologyOk(e, f) && countryOk(e, f)))
    for (const r of new Set(e.roles.map((x) => x.role))) roles.set(r, (roles.get(r) ?? 0) + 1);
  // …
  return { typologies, countries, roles: [...roles].sort(([a], [b]) => roleRank(a) - roleRank(b)) };
  ```

`components/MapPage.tsx`: `NO_FILTERS` gains `hiddenRoles: new Set()`; `atPlace` filters by `e.key`; `selected` holds `{ key: string; n: number }` (rename `id` → `key`) and `MapSidebar` gets `selected={selected?.key ?? null}`.

`components/MapSidebar.tsx`: `facets` type gains `roles`; `selected` / `onSelect` doc says entry key; rows `key={e.key}`, `aria-current` / highlight compare `p.selected === e.key`, `onClick={() => p.onSelect(e.key)}`; under the row's ID line, when the roles are not just `death`, a third line `<span className="block text-xs text-slate-600 dark:text-slate-400">{e.roles.map((r) => roleText(tRoles, r)).join(" · ")}</span>`; and after the typology fieldset, when `p.facets.roles.length > 1`:

```tsx
      <fieldset className="flex flex-col gap-1">
        <legend className="mb-1 font-medium">{t("roleLegend")}</legend>
        {p.facets.roles.map(([r, n]) => (
          <label key={r} className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={!p.filters.hiddenRoles.has(r)}
              onChange={() => p.onFilters({ ...p.filters, hiddenRoles: toggle(p.filters.hiddenRoles, r) })}
            />
            {roleLabel(tRoles, r)} ({n})
          </label>
        ))}
      </fieldset>
```

(`const tRoles = useTranslations("PlaceRoles");`. A fieldset with a legend is a "group" named by it, which the test queries.)

`components/EulogyMap.tsx`: `selected: { key: string; n: number } | null`; `PlacedMarker = CircleMarker & { entryKey?: string }`; markers keyed and picked by `e.key` (`markers.current.set(e.key, …)`, `.on("click", () => onSelectRef.current(e.key))`, `m.entryKey = e.key`, the cluster pick maps `m.entryKey`, the reveal effect reads `markers.current.get(selected.key)`); `popupFor` gains a `tRoles` argument (kept in a ref like `tRef`) and, after the typology line, when the roles are not just `death`: `root.append(el("p", e.roles.map((r) => roleText(tRoles, r)).join(" · ")))`.

Messages: `Map.roleLegend` "Role of the place" / it "Ruolo del luogo" / fr "Rôle du lieu" / de "Rolle des Ortes" / es "Papel del lugar" / pt "Papel do local".

- [ ] **Step 4: Run tests**

Run: `npm test 2>&1 | tail -3 && npx tsc --noEmit && npm run lint 2>&1 | tail -2 && npm run build 2>&1 | tail -3`
Expected: all pass; type, lint and build clean.

- [ ] **Step 5: Commit, push, open the PR**

```bash
git add lib/map-data.ts components/MapPage.tsx components/MapSidebar.tsx components/EulogyMap.tsx messages/*.json lib/__tests__/map-data.test.ts components/__tests__/MapSidebar.test.tsx components/__tests__/MapPage.test.tsx components/__tests__/EulogyMap.test.tsx lib/__tests__/messages.test.ts
git commit -m "map: one marker per place a eulogy names, with its roles and a role filter (crmedr#12)"
git push -u origin feat/place-roles
gh pr create --title "Place roles: popup, index of places and map (crmedr#12)" --body "…"
```

The PR body: the popup's roles need API v0.18.0 (absent before, nothing breaks); the index and map read the snapshot, so they show the opening places' roles now and the reviewed body places after the next `snapshot-registry` once `body_places.py apply` has run; links the martyrology-api PR. Footer as in Global Constraints. Deploy after merge only with the user's go-ahead.
