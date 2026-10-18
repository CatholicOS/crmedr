#!/usr/bin/env python3
"""Rename candidates: the discriminators an identity record allows for a bare ID.

A bare one-name ID (mr:0101-eugendus) takes a discriminator built by the minting
rules from its identity record (scripts/subject_records.py). R1: a place the 2004
Latin prints as an adjective keeps that adjective, in the nominative and agreeing
with the subject; otherwise the place takes its genitive. Nothing is decided here.
"""
import re

from extract_subjects import fold
from subject_records import CLERIC_ROLES  # noqa: F401  (re-exported for the candidates)

WEAK_ROLES = {"martyr", "virgo", "confessor"}

# folded nominative -> the corpus genitive, from the bare-name pass's place map
PLACE_GENITIVES = {
    "treviri": "trevirorum", "arverni": "arvernorum", "carnutes": "carnutum", "cenomani": "cenomanorum",
    "lemovices": "lemovicum", "pictavi": "pictavorum", "turones": "turonum", "hierosolyma": "hierosolymorum",
}


def slug(s):
    """A slug part: folded as the registry's IDs were minted, words hyphen-joined."""
    return "-".join(fold(s).split())


def adjective_slug(adjective, feminine):
    """The place adjective in the nominative, agreeing with the subject: -anus/-ana and
    -inus/-ina follow the subject's gender; -ensis is both."""
    s = slug(adjective)
    if feminine:
        return re.sub(r"(an|in)us$", r"\1a", s)
    return re.sub(r"(an|in)a$", r"\1us", s)


def genitive_slug(place):
    """(genitive slug, certain): the corpus genitive when the place has one; else the
    record's own genitive, not certain; else (None, False)."""
    known = PLACE_GENITIVES.get(slug(place.get("nominative") or ""))
    if known:
        return known, True
    if place.get("genitive"):
        return slug(place["genitive"]), False
    return None, False
