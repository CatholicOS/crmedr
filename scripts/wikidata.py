"""A small cached Wikidata client for the gazetteer (standard library only).

Search hits are summarized into candidates: Italian names (folded), Latin
labels and aliases, P9314 (Latin Place Names ID), current countries as ISO
codes, coordinates, and whether the item is a place (P31 through P279* to one
of PLACE_ROOTS). Responses are cached on disk, one file per request URL.
See docs/superpowers/specs/2026-10-01-gazetteer-design.md.
"""

import hashlib
import http.client
import json
import os
import re
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

from gazetteer_text import convention, fold

API = "https://www.wikidata.org/w/api.php"
SPARQL = "https://query.wikidata.org/sparql"
# Declared in every query: the Blazegraph endpoint predefines them, QLever's (WDQS v2) does not.
PREFIXES = ("PREFIX wd: <http://www.wikidata.org/entity/>\n"
            "PREFIX wdt: <http://www.wikidata.org/prop/direct/>\n"
            "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
            "PREFIX skos: <http://www.w3.org/2004/02/skos/core#>\n"
            "PREFIX p: <http://www.wikidata.org/prop/>\n"
            "PREFIX psv: <http://www.wikidata.org/prop/statement/value/>\n"
            "PREFIX wikibase: <http://wikiba.se/ontology#>\n")
USER_AGENT = "crmedr-gazetteer/1.0 (https://github.com/CatholicOS/crmedr)"
# human settlement, administrative territorial entity, monastery, church building,
# archaeological site, island, mountain, region, historical region, historical
# country, cave, castle, country
PLACE_ROOTS = ("Q486972", "Q56061", "Q44613", "Q16970", "Q839954", "Q23442", "Q8502",
               "Q82794", "Q1620908", "Q3024240", "Q35509", "Q23413", "Q6256")
RETRY_CODES = {429, 500, 502, 503, 504}
# Countries that places' P17 names but that carry no P297 themselves: the
# Netherlands (Q55) is the constituent country; NL sits on the Kingdom (Q29999).
EXTRA_COUNTRY_ISO = {"Q55": "NL"}

# Wikidata's canonization statuses (P411) of a saint or a blessed: saint, Catholic saint,
# canonized saint, blessed, and the titles Wikidata gives ancient and Eastern saints
# instead (Telemachus is a "Reverend Martyr"): hieromartyr, Reverend Martyr, thaumaturge,
# pre-congregation saint, great martyr, passion bearer. Not Venerable or Servant of God.
SAINT_STATUSES = {"Q43115", "Q3464126", "Q123110154", "Q2369287",
                  "Q2993173", "Q4377390", "Q1349880", "Q18344276", "Q3332786", "Q2032316"}
# A companion's kin: sibling, relative, spouse, child, mother, father.
RELATIVE_PROPS = ("P3373", "P1038", "P26", "P40", "P25", "P22")
NAME_LANGS = ("la", "it", "en", "fr", "es", "de")
# The P31 values of a person: human, human biblical figure (Anna the Prophetess, Q1774668),
# human whose existence is disputed (the legendary saints: Prisca, Q426200) and its subclass
# legendary saint (Martina, Q272101).
HUMAN_TYPES = ("Q5", "Q20643955", "Q21070568", "Q113371917")
# The saint queries bind ?h to one of them; the full-text searches ask for one of them.
HUMANS = "VALUES ?h { " + " ".join("wd:" + t for t in HUMAN_TYPES) + " } "
HUMAN_SEARCH = "haswbstatement:" + "|".join("P31=" + t for t in HUMAN_TYPES)
# Statements a saint's or a blessed's item carries, for the full-text search: canonization
# status, feast day, and the Santi e Beati, Ökumenisches Heiligenlexikon, Nominis and GCatholic
# person IDs and the Heiligen.net ID (many saints' items have one of these without a P411: Lucian
# of Lentini, Theogenes of Parium). GCatholic lists every bishop, saint or not; the name and the
# place still bound the search.
SAINT_SIGNALS = ("P411", "P841", "P6126", "P8080", "P4286", "P8366", "P10799")
# At most this many saints may bear a name searched alone (saints_by_name).
RARE_NAME_HITS = 3
# A surname more saints bear than this is too common to offer on the surname alone.
SURNAME_HITS = 8
# The signals that count as a saint's status besides P411 (summarize_person `signals`): not the
# GCatholic person ID, which bounds the search but lists bishops who are no saints.
STATUS_SIGNALS = tuple(p for p in SAINT_SIGNALS if p not in ("P411", "P8366"))
# A label's languages, in order: "mul" last, the one name Wikidata now keeps for every language
# (Cúcuta has no "en" label of its own).
LABEL_LANGS = ("en", "it", "la", "mul")
MAX_SPARQL = 25
# The months' items, which the day items (P841's values: "January 8", Q2234) are part of (P361).
MONTH_NAMES = ("January", "February", "March", "April", "May", "June", "July", "August",
               "September", "October", "November", "December")
MONTHS = ("Q108", "Q109", "Q110", "Q118", "Q119", "Q120", "Q121", "Q122", "Q123", "Q124", "Q125", "Q126")
# A place with more saints than this is too common to tell them apart by place: no candidates.
MAX_PLACE_SAINTS = 200
GREGORIAN, JULIAN = "Q1985727", "Q1985786"  # the calendar models of a Wikidata date
# The query service stores a Julian-model date converted to the proleptic Gregorian calendar:
# from two days earlier (the 1st century) to thirteen days later (since 1900) than its Julian day.
JULIAN_SHIFT = range(-2, 14)

# The interface languages of martyrology-frontend, for the reader's person popups.
DETAIL_LANGS = ("en", "it", "fr", "de", "es", "pt")
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
# P1480 (sourcing circumstances) = circa.
CIRCA = "Q5727902"


def _stored_days(month, day):
    """A SPARQL condition on ?d and ?cal: the dates the query service may store for a death on
    that day. The day itself in the Gregorian model; in the Julian model, the Gregorian days a
    Julian date of that month and day becomes (JULIAN_SHIFT; in a leap year, so that 29 February
    is among them), as a day range per month. A FILTER, not a VALUES join: the service times
    out joining every death date with a list of days."""
    shifted = [date(2000, month, day) + timedelta(k) for k in JULIAN_SHIFT]
    ranges = {}
    for d in shifted:
        lo, hi = ranges.get(d.month, (d.day, d.day))
        ranges[d.month] = (min(lo, d.day), max(hi, d.day))
    julian = " || ".join(f"MONTH(?d) = {m} && DAY(?d) >= {lo} && DAY(?d) <= {hi}" for m, (lo, hi) in ranges.items())
    return (f"?cal = wd:{GREGORIAN} && MONTH(?d) = {month} && DAY(?d) = {day} || "
            f"?cal = wd:{JULIAN} && ({julian})")


def _julian(year, month, day):
    """The Julian calendar date of a proleptic Gregorian one (astronomical years), through
    the Julian day number."""
    a = (14 - month) // 12
    y, m = year + 4800 - a, month + 12 * a - 3
    jdn = day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045
    c = jdn + 32082
    d = (4 * c + 3) // 1461
    e = c - 1461 * d // 4
    m = (5 * e + 2) // 153
    return d - 4800 + m // 10, m + 3 - 12 * (m // 10), e - (153 * m + 2) // 5 + 1


def _death_day(value, calendar):
    """(year, month, day) of a query service date in its own calendar model: as stored for a
    Gregorian one, back to the Julian calendar for a Julian one; None for another model."""
    m = re.match(r"(-?\d+)-(\d\d)-(\d\d)", value)
    if not m or calendar not in (GREGORIAN, JULIAN):
        return None
    ymd = tuple(int(x) for x in m.groups())
    return ymd if calendar == GREGORIAN else _julian(*ymd)


def _name_words(name):
    """A name's words, folded, a hyphen or an apostrophe read as a space ("Pierre-François")."""
    return fold(name).replace("-", " ").replace("'", " ").split()


def _best_named(rows, given, matches=None):
    """QIDs of the persons in SPARQL rows (?p ?l ?s) having a label or alias with a word starting
    with one of the `given` names, folded; the best first: those whose names pass `matches` (a
    test of a list of names), then those with more statuses, then by QID."""
    starts = tuple(f for f in (fold(g) for g in given) if f)
    names, found = {}, {}
    for b in rows:
        qid = b["p"]["value"].rsplit("/", 1)[1]
        names.setdefault(qid, set()).add(b["l"]["value"])
        if any(w.startswith(starts) for w in fold(b["l"]["value"]).split()):
            found.setdefault(qid, set()).add(b["s"]["value"].rsplit("/", 1)[1])
    return sorted(found, key=lambda q: (not (matches and matches(sorted(names[q]))), -len(found[q]),
                                        int(q[1:])))


class WikidataError(Exception):
    pass


def _write_atomic(path, text):
    """Write to a temporary file beside `path`, then move it into place, so an
    interrupted run never leaves a truncated cache file."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _retry_after(headers, attempt):
    value = (headers or {}).get("Retry-After")
    return int(value) if value and value.isdigit() else 2 ** attempt


def http_get(url, retries=6, sleep=time.sleep):
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                data = json.load(r)
        except urllib.error.HTTPError as e:
            if e.code not in RETRY_CODES:
                raise WikidataError(f"HTTP {e.code} for {url}") from e
            sleep(_retry_after(e.headers, attempt))
            continue
        except (OSError, http.client.HTTPException, ValueError):
            # URLError, timeouts, resets, truncated bodies, an HTML error page.
            sleep(2 ** attempt)
            continue
        if isinstance(data, dict) and "error" in data:
            if data["error"].get("code") == "maxlag":
                sleep(5)
                continue
            raise WikidataError(f"{data['error'].get('code')} for {url}")
        return data
    raise WikidataError(f"gave up after {retries} attempts: {url}")


def _value(claim):
    return claim.get("mainsnak", {}).get("datavalue", {}).get("value")


def current_country_qids(claims):
    current = [c for c in claims.get("P17", [])
               if c.get("rank") != "deprecated" and "P582" not in c.get("qualifiers", {})
               and isinstance(_value(c), dict)]
    preferred = [c for c in current if c.get("rank") == "preferred"]
    return list(dict.fromkeys(_value(c)["id"] for c in (preferred or current)))


def current_qids(claims, prop):
    """The items `prop` names now: not a deprecated statement, nor one with an end time (P582)."""
    return list(dict.fromkeys(_value(c)["id"] for c in claims.get(prop, [])
                              if c.get("rank") != "deprecated" and "P582" not in c.get("qualifiers", {})
                              and isinstance(_value(c), dict) and "id" in _value(c)))


def _names(raw, lang):
    out = []
    if lang in raw.get("labels", {}):
        out.append(raw["labels"][lang]["value"])
    out += [a["value"] for a in raw.get("aliases", {}).get(lang, [])]
    return out


def summarize(raw):
    claims = raw.get("claims", {})
    labels = raw.get("labels", {})
    label = next((labels[lang]["value"] for lang in LABEL_LANGS if lang in labels), raw["id"])
    descs = raw.get("descriptions", {})
    p297 = [_value(c) for c in claims.get("P297", []) if c.get("rank") != "deprecated"]
    coords = next((_value(c) for c in claims.get("P625", []) if isinstance(_value(c), dict)), None)
    return {
        "wikidata": raw["id"],
        "label": label,
        "description": next((descs[lang]["value"] for lang in ("it", "en") if lang in descs), ""),
        "names_it": sorted({fold(n) for n in _names(raw, "it")}),
        "la": sorted(set(_names(raw, "la"))),
        "p9314": bool(claims.get("P9314")),
        # The Latin Place Names slug ("m/moguntiae") is the place's Latin form.
        "p9314_names": sorted({t for c in claims.get("P9314", []) if isinstance(_value(c), str)
                               for t in fold(_value(c).split("/", 1)[-1]).split("-") if t}),
        "country_qids": current_country_qids(claims),
        # The areas it lies in now.
        "admin_qids": current_qids(claims, "P131"),
        # Where a historical place lies today (P3842: Roman Cilicia → Turkey).
        "present_qids": current_qids(claims, "P3842"),
        # Where an event took place (P276: the First Council of Ephesus → Ephesus).
        "location_qids": current_qids(claims, "P276"),
        "iso_self": p297[0] if p297 else None,
        "coords": [coords["latitude"], coords["longitude"]] if coords else None,
        "types": list(dict.fromkeys(_value(c)["id"] for c in claims.get("P31", [])
                                    if isinstance(_value(c), dict))),
    }


def _date(claims, prop):
    """The first dated value of `prop` as YYYY, YYYY-MM or YYYY-MM-DD by its precision: preferred
    statements first, deprecated ones never (a day added as preferred beside a year-only one wins)."""
    ranked = sorted((c for c in claims.get(prop, []) if c.get("rank") != "deprecated"),
                    key=lambda c: c.get("rank") != "preferred")
    for c in ranked:
        v = _value(c)
        if isinstance(v, dict) and "time" in v:
            t, p = v["time"].lstrip("+"), v.get("precision", 9)
            return t[:10] if p >= 11 else t[:7] if p == 10 else t[:4]
    return None


def _other_names(raw):
    """A bare item's names (_with_other_names): its labels in any language, then its sitelinks'
    titles."""
    return list(dict.fromkeys([v["value"] for v in raw.get("labels", {}).values()]
                              + [v["title"] for v in raw.get("sitelinks", {}).values()]))


def summarize_person(raw):
    claims = raw.get("claims", {})
    labels = raw.get("labels", {})
    descs = raw.get("descriptions", {})
    ids = lambda prop: list(dict.fromkeys(_value(c)["id"] for c in claims.get(prop, [])  # noqa: E731
                                          if isinstance(_value(c), dict) and "id" in _value(c)))
    other = [] if any(lang in labels for lang in LABEL_LANGS) else _other_names(raw)
    return {
        "wikidata": raw["id"],
        "label": next((labels[lang]["value"] for lang in LABEL_LANGS if lang in labels), other[0] if other else raw["id"]),
        "description": next((descs[lang]["value"] for lang in ("en", "it") if lang in descs), ""),
        "names": sorted({n for lang in ("la", "it", "en") for n in _names(raw, lang)} | set(other)),
        "human": any(t in ids("P31") for t in HUMAN_TYPES),
        "statuses": ids("P411"),
        "born": _date(claims, "P569"),
        "died": _date(claims, "P570"),
        "feast": ids("P841"),
        "signals": [p for p in STATUS_SIGNALS
                    if any(c.get("rank") != "deprecated" for c in claims.get(p, []))],
        "birth_place": current_qids(claims, "P19"),
        "death_place": current_qids(claims, "P20"),
        "burial_place": current_qids(claims, "P119"),
        "work_places": current_qids(claims, "P937"),
    }


# Wikidata time precision: 9 year (10 month and 11 day read as the year), 8 decade, 7 century.
LIFE_PRECISION = {8: "decade", 7: "century"}
YEAR = re.compile(r"([+-]?)(\d+)-")


def life_date(claims, prop):
    """The best dated value of `prop` for the reader: its year (negative before
    Christ), its precision ("year", "decade" or "century") and whether a P1480
    qualifier says circa. Preferred statements first, deprecated ones never, and
    one coarser than a century skipped; None when nothing is left. Unlike _date,
    which the review cards use, it keeps precision and circa apart."""
    ranked = sorted((c for c in claims.get(prop, []) if c.get("rank") != "deprecated"),
                    key=lambda c: c.get("rank") != "preferred")
    for c in ranked:
        v = _value(c)
        if not (isinstance(v, dict) and "time" in v):
            continue
        p = v.get("precision", 9)
        m = YEAR.match(v["time"])
        if p < 7 or not m:
            continue
        quals = c.get("qualifiers", {}).get("P1480", [])
        circa = any((q.get("datavalue", {}).get("value") or {}).get("id") == CIRCA for q in quals)
        year = int(m.group(2)) * (-1 if m.group(1) == "-" else 1)
        return {"year": year, "precision": "year" if p >= 9 else LIFE_PRECISION[p], "circa": circa}
    return None


class Wikidata:
    def __init__(self, cache_dir, fetch=http_get, refresh=False):
        """refresh=True fetches again what the cache already holds (once per URL in this run) and
        updates the cache: for re-reading items that changed on Wikidata."""
        self.cache_dir = cache_dir
        self.fetch = fetch
        self.refresh = refresh
        self._fetched = set()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._iso = None
        self._types_path = cache_dir / "place_types.json"
        self._types = (json.loads(self._types_path.read_text(encoding="utf-8"))
                       if self._types_path.exists() else {})

    def _get(self, url):
        path = self.cache_dir / (hashlib.sha1(url.encode()).hexdigest() + ".json")
        if path.exists() and (not self.refresh or url in self._fetched):
            return json.loads(path.read_text(encoding="utf-8"))
        data = self.fetch(url)
        self._fetched.add(url)
        _write_atomic(path, json.dumps(data, ensure_ascii=False))
        return data

    def _api(self, **params):
        params.update(format="json", maxlag="5")
        return self._get(API + "?" + urllib.parse.urlencode(params))

    def _search(self, text, limit=10, language="it"):
        data = self._api(action="wbsearchentities", search=text, language=language, uselang=language,
                         type="item", limit=str(limit))
        return [x["id"] for x in data.get("search", [])]

    def _entities(self, qids):
        out = {}
        for i in range(0, len(qids), 50):
            data = self._api(action="wbgetentities", ids="|".join(qids[i:i + 50]),
                             props="labels|aliases|descriptions|claims", languages="it|la|en|mul")
            for qid, raw in data.get("entities", {}).items():
                if "missing" not in raw:
                    out[qid] = raw
        return out

    def _person_entities(self, qids):
        """_entities, and for an item with no label in LABEL_LANGS (a Swahili Wikipedia stub) its
        labels in every language and its sitelinks, so that it has a name to show and match."""
        out = self._entities(qids)
        bare = [q for q, raw in out.items() if not any(lang in raw.get("labels", {}) for lang in LABEL_LANGS)]
        for i in range(0, len(bare), 50):
            data = self._api(action="wbgetentities", ids="|".join(bare[i:i + 50]), props="labels|sitelinks")
            for qid, raw in data.get("entities", {}).items():
                if qid in out and "missing" not in raw:
                    out[qid] = {**out[qid], "labels": raw.get("labels", {}), "sitelinks": raw.get("sitelinks", {})}
        return out

    def _place_types(self, classes):
        unknown = sorted(set(classes) - set(self._types))
        if unknown:
            roots = " ".join("wd:" + r for r in PLACE_ROOTS)
            values = " ".join("wd:" + c + " " for c in unknown)
            query = PREFIXES + (f"SELECT DISTINCT ?c WHERE {{ VALUES ?c {{ {values}}} "
                     f"?c wdt:P279* ?r . VALUES ?r {{ {roots} }} }}")
            data = self._get(SPARQL + "?" + urllib.parse.urlencode({"query": query, "format": "json"}))
            found = {b["c"]["value"].rsplit("/", 1)[1] for b in data["results"]["bindings"]}
            self._types.update({c: c in found for c in unknown})
            _write_atomic(self._types_path, json.dumps(self._types, sort_keys=True))
        return {c for c in classes if self._types[c]}

    def _country_iso(self):
        # One query for every country code, instead of fetching each country's
        # (very large) entity per search.
        if self._iso is None:
            query = PREFIXES + "SELECT ?c ?iso WHERE { ?c wdt:P297 ?iso }"
            data = self._get(SPARQL + "?" + urllib.parse.urlencode({"query": query, "format": "json"}))
            self._iso = dict(EXTRA_COUNTRY_ISO)
            for b in data["results"]["bindings"]:
                self._iso.setdefault(b["c"]["value"].rsplit("/", 1)[1], b["iso"]["value"])
        return self._iso

    def _enrich(self, summaries):
        countries = self._country_iso()
        places = self._place_types([t for s in summaries for t in s["types"]])
        for s in summaries:
            s["countries"] = [convention(countries.get(q)) if countries.get(q) else q for q in s["country_qids"]]
            s["country"] = s["countries"][0] if len(s["countries"]) == 1 and countries.get(
                s["country_qids"][0]) else None
            # A territory with its own ISO code (Réunion, Guam) is its country, though
            # P17 names the sovereign state.
            if s["iso_self"]:
                s["country"] = convention(s["iso_self"])
            elif not any(countries.get(q) for q in s["country_qids"]):
                present = (self._countries_of(s.get("present_qids") or [], countries)
                           or self._countries_of(s.get("location_qids") or [], countries))
                iso = None if present else self._fallback_country(s, countries)
                if present:
                    s["countries"] = present
                    s["country"] = present[0] if len(present) == 1 else None
                elif iso:
                    s["country"], s["countries"] = iso, [iso]
            s["place_type"] = any(t in places for t in s["types"])
        return summaries

    def _countries_of(self, qids, countries):
        """The ISO countries of these items, in order: a country itself, else the current P17 of
        an area, else where that area lies today (its P3842). For a historical place's P3842
        (Roman Cilicia lies in Turkey, Dalmatia in Croatia and Bosnia) and an event's location
        (P276: the First Council of Ephesus took place at Ephesus, TR). Unlike a successor state,
        both name where the place is now."""
        areas = self._entities([q for q in qids if q not in countries])
        today = {q: current_qids(raw.get("claims", {}), "P3842") for q, raw in areas.items()}
        later = self._entities([t for ts in today.values() for t in ts if t not in countries])
        found = []
        for q in qids:
            if q in countries:
                found.append(countries[q])
                continue
            codes = [countries[c] for c in current_country_qids(areas.get(q, {}).get("claims", {})) if c in countries]
            for t in ([] if codes else today.get(q, [])):
                codes += [countries[t]] if t in countries else [
                    countries[c] for c in current_country_qids(later.get(t, {}).get("claims", {})) if c in countries]
            found += codes
        return list(dict.fromkeys(convention(c) for c in found))

    def _fallback_country(self, s, countries):
        """The one ISO country of a place Wikidata gives no country (no P17 at all): that of the
        areas it lies in (P131: Bethany, the Quds Governorate, PS). None unless exactly one code
        results. A historical state's successor is never used: it is not where a place lies today
        (Taiwan under Japanese rule is not in Japan)."""
        if s["country_qids"] or not s.get("admin_qids"):
            return None
        areas = self._entities(s["admin_qids"])
        found = {countries[q] for raw in areas.values() for q in current_country_qids(raw.get("claims", {}))
                 if q in countries}
        return convention(found.pop()) if len(found) == 1 else None

    def candidates(self, text, language="it"):
        qids = self._search(text, language=language)
        raws = self._entities(qids)
        return self._enrich([summarize(raws[q]) for q in qids if q in raws])

    def items(self, qids):
        """Enriched summaries of these items, by QID, fetched 50 at a time; a missing one is left out."""
        raws = self._entities(list(dict.fromkeys(qids)))
        return {s["wikidata"]: s for s in self._enrich([summarize(raws[q]) for q in dict.fromkeys(qids) if q in raws])}

    def candidate(self, qid):
        raw = self._entities([qid]).get(qid)
        return self._enrich([summarize(raw)])[0] if raw else None

    def person_candidates(self, name, languages=("la", "it", "en")):
        qids = list(dict.fromkeys(q for lang in languages for q in self._search(name, language=lang)))
        raws = self._person_entities(qids)
        return [summarize_person(raws[q]) for q in qids if q in raws]

    def _sparql(self, query):
        data = self._get(SPARQL + "?" + urllib.parse.urlencode({"query": PREFIXES + query, "format": "json"}))
        return data["results"]["bindings"]

    def _tagged(self, sources):
        """Person summaries of {qid: source}, in that order, each with its "source"."""
        raws = self._person_entities(list(sources))
        return [{**summarize_person(raws[q]), "source": s} for q, s in sources.items() if q in raws]

    def relatives(self, qid):
        """The companion's kin (sibling, relative, spouse, child, mother, father) and
        the other members of its groups (P361), as person candidates."""
        raw = self._entities([qid]).get(qid)
        sources = {}
        for prop in RELATIVE_PROPS:
            for c in (raw or {}).get("claims", {}).get(prop, []):
                v = _value(c)
                if isinstance(v, dict) and "id" in v:
                    sources.setdefault(v["id"], "companion:" + prop)
        for c in (raw or {}).get("claims", {}).get("P361", []):
            v = _value(c)
            if isinstance(v, dict) and "id" in v:
                for b in self._sparql(f"SELECT DISTINCT ?m WHERE {{ ?m wdt:P361 wd:{v['id']} }}"):
                    sources.setdefault(b["m"]["value"].rsplit("/", 1)[1], "companion:P361")
        sources.pop(qid, None)
        return self._tagged(sources)

    def saints_by_death_day(self, month, day, given, year=None, matches=None):
        """Saints and blessed who died on that day (and year, when known), dated to the day,
        whose label or alias has a word starting with one of the `given` names, folded.
        The query is bounded by status and death day; the names and the exact day (a
        Julian-model date back in its own calendar) are checked here, since the endpoint
        cannot fold accents. At most MAX_SPARQL, the best first: those whose names pass
        `matches` (a test of a list of names), then those with more statuses."""
        statuses = " ".join("wd:" + s for s in sorted(SAINT_STATUSES))
        langs = ", ".join(f'"{lang}"' for lang in NAME_LANGS)
        years = f" FILTER(YEAR(?d) >= {int(year) - 1} && YEAR(?d) <= {int(year) + 1})" if year else ""
        rows = self._sparql(
            f"SELECT DISTINCT ?p ?l ?s ?d ?prec ?cal WHERE {{ VALUES ?s {{ {statuses} }} {HUMANS}"
            f"?p wdt:P31 ?h; wdt:P411 ?s; p:P570/psv:P570 [wikibase:timeValue ?d; "
            f"wikibase:timePrecision ?prec; wikibase:timeCalendarModel ?cal] . "
            f"FILTER(?prec >= 11 && ({_stored_days(int(month), int(day))})){years} "
            f"?p rdfs:label|skos:altLabel ?l . FILTER(LANG(?l) IN ({langs})) }} ORDER BY ?p")
        kept = []
        for b in rows:
            on_day = _death_day(b["d"]["value"], b["cal"]["value"].rsplit("/", 1)[1])
            if int(b["prec"]["value"]) < 11 or on_day is None or on_day[1:] != (int(month), int(day)) or (year and on_day[0] != int(year)):
                continue
            kept.append(b)
        best = _best_named(kept, given, matches)
        return self._tagged({q: "sparql" for q in best[:MAX_SPARQL]})

    def saints_by_feast_day(self, month, day, given, matches=None):
        """Humans whose feast day (P841) is that day, whose label or alias has a word starting with
        one of the `given` names, folded: John of Réôme's death is dated to the year only. At most
        MAX_SPARQL, the best first, as saints_by_death_day orders them."""
        langs = ", ".join(f'"{lang}"' for lang in NAME_LANGS)
        label = f"{MONTH_NAMES[month - 1]} {day}"
        rows = self._sparql(
            f'SELECT DISTINCT ?p ?l ?s WHERE {{ ?f wdt:P361 wd:{MONTHS[month - 1]}; rdfs:label "{label}"@en . '
            f"{HUMANS}?p wdt:P31 ?h; wdt:P841 ?f . BIND(?f AS ?s) "
            f"?p rdfs:label|skos:altLabel ?l . FILTER(LANG(?l) IN ({langs})) }} ORDER BY ?p")
        best = _best_named(rows, given, matches)
        return self._tagged({q: "feast" for q in best[:MAX_SPARQL]})

    def saints_by_place(self, qids, given, matches=None):
        """Saints and blessed who died or are buried (P20, P119) in one of these places, whose
        label or alias has a word starting with one of the `given` names, folded. Bounded by
        status and place; the names are checked here. When the query finds more than
        MAX_PLACE_SAINTS distinct persons the place is too common to help: []. At most
        MAX_SPARQL, the best first, as saints_by_death_day orders them."""
        if not qids:
            return []
        statuses = " ".join("wd:" + s for s in sorted(SAINT_STATUSES))
        places = " ".join("wd:" + q for q in qids)
        langs = ", ".join(f'"{lang}"' for lang in NAME_LANGS)
        rows = self._sparql(
            f"SELECT DISTINCT ?p ?l ?s WHERE {{ VALUES ?s {{ {statuses} }} VALUES ?place {{ {places} }} {HUMANS}"
            f"?p wdt:P31 ?h; wdt:P411 ?s; (wdt:P20|wdt:P119) ?place . "
            f"?p rdfs:label|skos:altLabel ?l . FILTER(LANG(?l) IN ({langs})) }} ORDER BY ?p")
        if len({b["p"]["value"] for b in rows}) > MAX_PLACE_SAINTS:
            return []
        best = _best_named(rows, given, matches)
        return self._tagged({q: "place" for q in best[:MAX_SPARQL]})

    def saints_by_name_and_place(self, name, labels):
        """Saints and blessed that Wikidata's full-text search finds for the name with one of these
        place labels ("Florentius Vienne"): it reads labels, aliases and descriptions in every
        language, so it finds an item whose place statements are missing or unknown. Humans with
        one of the SAINT_SIGNALS only; at most 5 per place, in the search's order, tagged "place"."""
        found = {}
        for label in dict.fromkeys(labels):
            data = self._api(action="query", list="search", srnamespace="0", srlimit="5",
                             srsearch=f"{name} {label} {HUMAN_SEARCH} haswbstatement:{'|'.join(SAINT_SIGNALS)}")
            for hit in data.get("query", {}).get("search", []):
                found.setdefault(hit["title"], "place")
        return self._tagged(found) if found else []

    def saints_by_name(self, name):
        """The saints and blessed the full-text search finds for the name alone, when no more than
        RARE_NAME_HITS bear it (Nathalan, whose item has no place): a common name finds too many to
        offer. The name is sought in labels and aliases only (inlabel), not in descriptions that
        merely mention it. Humans with one of the SAINT_SIGNALS only, tagged "name"."""
        data = self._api(action="query", list="search", srnamespace="0", srlimit=str(RARE_NAME_HITS + 1),
                         srsearch=f"inlabel:{name} {HUMAN_SEARCH} haswbstatement:{'|'.join(SAINT_SIGNALS)}")
        hits = [hit["title"] for hit in data.get("query", {}).get("search", [])]
        if not hits or len(hits) > RARE_NAME_HITS:
            return []
        return self._tagged(dict.fromkeys(hits, "name"))

    def saints_by_surname(self, surname):
        """The saints and blessed whose label or alias has this surname (a phrase: "Vilar David"),
        when no more than SURNAME_HITS bear it: the surname is printed as on Wikidata while the
        Latin first name is not (Eduardus Stransham: Edward Stransham). Humans with one of the
        SAINT_SIGNALS only, whose label or alias in some language has every word of the surname
        (the search matches any language; the summaries load a few), tagged "surname"."""
        data = self._api(action="query", list="search", srnamespace="0", srlimit=str(SURNAME_HITS + 1),
                         srsearch=f'inlabel:"{surname}" {HUMAN_SEARCH} haswbstatement:{"|".join(SAINT_SIGNALS)}')
        hits = [hit["title"] for hit in data.get("query", {}).get("search", [])]
        if not hits or len(hits) > SURNAME_HITS:
            return []
        words = set(_name_words(surname))
        names = self._api(action="wbgetentities", ids="|".join(hits), props="labels|aliases").get("entities", {})
        bearing = [q for q in hits if any(words <= set(_name_words(n["value"]))
                                          for n in [*names.get(q, {}).get("labels", {}).values(),
                                                    *(a for al in names.get(q, {}).get("aliases", {}).values() for a in al)])]
        return self._tagged(dict.fromkeys(bearing, "surname"))

    def title_candidates(self, text, languages=("la", "it", "en")):
        """Items of any kind (a feast, a title: Theotokos), without the human filter."""
        qids = list(dict.fromkeys(q for lang in languages for q in self._search(text, language=lang)))
        return self._tagged({q: "title" for q in qids})

    def labels(self, qids, languages=("en", "it")):
        """{qid: {lang: label or None}} of these items in these languages, fetched 50 at a time
        (cached); a missing item is left out."""
        raws = self._entities(list(dict.fromkeys(qids)))
        return {q: {lang: ((raws[q].get("labels") or {}).get(lang) or {}).get("value") for lang in languages}
                for q in dict.fromkeys(qids) if q in raws}

    def person(self, qid):
        raw = self._person_entities([qid]).get(qid)
        return summarize_person(raw) if raw else None

    def people(self, qids):
        """Person summaries of these items, by QID, fetched 50 at a time; a missing one is left out."""
        raws = self._person_entities(list(dict.fromkeys(qids)))
        return {q: summarize_person(raws[q]) for q in dict.fromkeys(qids) if q in raws}

    def details_entities(self, qids):
        """For the reader's popups: descriptions, claims and Wikipedia sitelinks in
        the interface languages, by QID. Labels are not asked: the frontend's
        persons snapshot already has them."""
        out = {}
        for i in range(0, len(qids), 50):
            data = self._api(action="wbgetentities", ids="|".join(qids[i:i + 50]),
                             props="descriptions|claims|sitelinks", languages="|".join(DETAIL_LANGS),
                             sitefilter="|".join(f"{lang}wiki" for lang in DETAIL_LANGS))
            for qid, raw in data.get("entities", {}).items():
                if "missing" not in raw:
                    out[qid] = raw
        return out

    def commons_files(self, files):
        """Commons' extmetadata (author, license) for each file name as P18 gives
        it, without "File:"; a missing file is left out."""
        out = {}
        for i in range(0, len(files), 50):
            titles = "|".join("File:" + f for f in files[i:i + 50])
            data = self._get(COMMONS_API + "?" + urllib.parse.urlencode(
                {"action": "query", "titles": titles, "prop": "imageinfo", "iiprop": "extmetadata",
                 "redirects": "1", "format": "json", "maxlag": "5"}))
            query = data.get("query", {})
            # a title the API normalized or redirected maps back to every name that led to it
            sources = {}
            for r in query.get("redirects", []) + query.get("normalized", []):
                sources.setdefault(r["to"].removeprefix("File:"), []).append(r["from"].removeprefix("File:"))
            for page in query.get("pages", {}).values():
                info = page.get("imageinfo")
                if info:
                    names, todo = set(), [page["title"].removeprefix("File:")]
                    while todo:
                        name = todo.pop()
                        if name not in names:
                            names.add(name)
                            todo.extend(sources.get(name, []))
                    for name in names & set(files[i:i + 50]):
                        out[name] = info[0].get("extmetadata", {})
        return out

    def region_coords(self, text):
        """Coordinates of the non-country items with that exact Italian name. A
        country's name ("Francia") has none: the country check covers it, and
        hamlets that share the name must not set a distance."""
        name = fold(text)
        named = [c for c in self.candidates(text) if name in c["names_it"]]
        if any(c["iso_self"] for c in named):
            return []
        return [c["coords"] for c in named if c["coords"]]

    def region_countries(self, text):
        name = fold(text)
        out = set()
        for c in self.candidates(text):
            if name in c["names_it"]:
                if c["iso_self"]:
                    out.add(convention(c["iso_self"]))
                out.update(x for x in c["countries"] if len(x) == 2)
        return out
