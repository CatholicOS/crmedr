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
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

from gazetteer_text import fold

API = "https://www.wikidata.org/w/api.php"
SPARQL = "https://query.wikidata.org/sparql"
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


def _names(raw, lang):
    out = []
    if lang in raw.get("labels", {}):
        out.append(raw["labels"][lang]["value"])
    out += [a["value"] for a in raw.get("aliases", {}).get(lang, [])]
    return out


def summarize(raw):
    claims = raw.get("claims", {})
    labels = raw.get("labels", {})
    label = next((labels[lang]["value"] for lang in ("en", "it", "la") if lang in labels), raw["id"])
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
        "iso_self": p297[0] if p297 else None,
        "coords": [coords["latitude"], coords["longitude"]] if coords else None,
        "types": list(dict.fromkeys(_value(c)["id"] for c in claims.get("P31", [])
                                    if isinstance(_value(c), dict))),
    }


class Wikidata:
    def __init__(self, cache_dir, fetch=http_get):
        self.cache_dir = cache_dir
        self.fetch = fetch
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._iso = None
        self._types_path = cache_dir / "place_types.json"
        self._types = (json.loads(self._types_path.read_text(encoding="utf-8"))
                       if self._types_path.exists() else {})

    def _get(self, url):
        path = self.cache_dir / (hashlib.sha1(url.encode()).hexdigest() + ".json")
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        data = self.fetch(url)
        _write_atomic(path, json.dumps(data, ensure_ascii=False))
        return data

    def _api(self, **params):
        params.update(format="json", maxlag="5")
        return self._get(API + "?" + urllib.parse.urlencode(params))

    def _search(self, text, limit=10):
        data = self._api(action="wbsearchentities", search=text, language="it", uselang="it",
                         type="item", limit=str(limit))
        return [x["id"] for x in data.get("search", [])]

    def _entities(self, qids):
        out = {}
        for i in range(0, len(qids), 50):
            data = self._api(action="wbgetentities", ids="|".join(qids[i:i + 50]),
                             props="labels|aliases|descriptions|claims", languages="it|la|en")
            for qid, raw in data.get("entities", {}).items():
                if "missing" not in raw:
                    out[qid] = raw
        return out

    def _place_types(self, classes):
        unknown = sorted(set(classes) - set(self._types))
        if unknown:
            roots = " ".join("wd:" + r for r in PLACE_ROOTS)
            values = " ".join("wd:" + c + " " for c in unknown)
            query = (f"SELECT DISTINCT ?c WHERE {{ VALUES ?c {{ {values}}} "
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
            query = "SELECT ?c ?iso WHERE { ?c wdt:P297 ?iso }"
            data = self._get(SPARQL + "?" + urllib.parse.urlencode({"query": query, "format": "json"}))
            self._iso = dict(EXTRA_COUNTRY_ISO)
            for b in data["results"]["bindings"]:
                self._iso.setdefault(b["c"]["value"].rsplit("/", 1)[1], b["iso"]["value"])
        return self._iso

    def _enrich(self, summaries):
        countries = self._country_iso()
        places = self._place_types([t for s in summaries for t in s["types"]])
        for s in summaries:
            s["countries"] = [countries.get(q) or q for q in s["country_qids"]]
            s["country"] = s["countries"][0] if len(s["countries"]) == 1 and countries.get(
                s["country_qids"][0]) else None
            s["place_type"] = any(t in places for t in s["types"])
        return summaries

    def candidates(self, text):
        qids = self._search(text)
        raws = self._entities(qids)
        return self._enrich([summarize(raws[q]) for q in qids if q in raws])

    def candidate(self, qid):
        raw = self._entities([qid]).get(qid)
        return self._enrich([summarize(raw)])[0] if raw else None

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
                    out.add(c["iso_self"])
                out.update(x for x in c["countries"] if len(x) == 2)
        return out
