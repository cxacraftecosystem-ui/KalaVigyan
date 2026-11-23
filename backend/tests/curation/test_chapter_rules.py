from __future__ import annotations

import uuid
from dataclasses import replace
from typing import Any

import pytest

from app.data.district_register import load_district_other_names, parse_district_other_names
from app.research.calendar import first_season
from app.research.craft_page import CraftPage
from app.research.timeline import years_stated
from app.science.reaction_colours import after_phrase
from app.services.chapter_context import PlacePoint
from app.services.chapter_preview import preview_rows
from app.services.craft_page import craft_page
from app.services.craft_page_cache import PageCache, ServedPage
from app.services.craft_page_preview import register_page
from app.services.craft_page_stamp import stamp_text
from app.services.curation_preview import dossier_records

from ..contracts.golden import SHARED
from .import_support import AJRAKH

FAMILY = "Textiles-Based-Craft-Category"
SINDH = "Q37211"
SINDH_POINT = PlacePoint(SINDH, 26.0, 69.0)


def chapter_items(page: CraftPage, chapter: str, kind: str) -> list[Any]:
    found = [item for c in page.chapters if c.key == chapter for item in c.items if item.kind == kind]
    return [item.block if item.block is not None else item.part for item in found]


def test_an_uncurated_craft_in_a_curated_family_still_offers_its_questions() -> None:
    page = register_page("Farrukhabad-Prints", family=FAMILY)
    (start,) = chapter_items(page, "glance", "start_research")
    assert start.questions == page.suggested_questions
    assert page.claims == [] and page.depth.basis == "REGISTER"


def test_a_place_with_a_stored_point_is_pinned_on_the_timeline() -> None:
    records = dossier_records(AJRAKH)
    assert records.curated is not None
    places = [
        place.model_copy(update={"wikidata_id": SINDH}) if place.name == "Sindh" else place
        for place in records.curated.places
    ]
    curated = records.curated.model_copy(update={"places": places})
    held = replace(records, curated=curated)
    rows = preview_rows(held, family=FAMILY, inputs=SHARED / "craft.page.inputs.json")
    page = craft_page(held, replace(rows, points={SINDH: SINDH_POINT}))
    (timeline,) = chapter_items(page, "history", "timeline_map")
    (sindh,) = [place for place in timeline.places if place.name == "Sindh"]
    assert (sindh.wikidata_id, sindh.latitude, sindh.longitude) == (SINDH, 26.0, 69.0)
    assert all(place.latitude is None for place in timeline.places if place.name != "Sindh")


@pytest.mark.parametrize(
    ("text", "span", "stated"),
    [
        ("Fragments of the 11th to 14th century were found in 1930.", (1001, 1400), "11th to 14th century"),
        ("Printed between 1855-79 for export.", (1855, 1879), "1855-79"),
        ("By the 1950s the practice had shrunk.", (1950, 1959), "1950s"),
        ("The GI was registered in 2006.", (2006, 2006), "2006"),
    ],
)
def test_a_dated_record_is_labelled_with_the_span_as_its_text_states_it(
    text: str, span: tuple[int, int], stated: str
) -> None:
    assert years_stated([text])[span] == stated


def test_a_season_is_the_one_the_text_names_first() -> None:
    assert first_season(["Dyeing stops in the monsoon and resumes in winter."]) == "MONSOON"
    assert first_season(["Work resumes in winter, after the monsoon."]) == "WINTER"
    assert first_season(["The cloth is washed in the river."]) is None


def test_a_long_stated_colour_change_keeps_its_last_clause_and_is_never_cut() -> None:
    short = "at first green and turns blue"
    assert after_phrase(short, 120) == short
    long = "at first " + "pale green and soft and wet " * 6 + "and then slowly turns deep blue"
    assert after_phrase(long, 120) == "turns deep blue"
    assert after_phrase("x" * 130, 120) is None


def test_district_other_names_name_a_district_the_register_holds() -> None:
    assert load_district_other_names()[449] == ("Kutch",)
    register = {"districts": [{"lgd": 449, "stateLgd": 24, "name": "Kachchh"}]}
    wrong = {"schemaVersion": 1, "districts": [{"lgd": 449, "name": "Kutch", "otherNames": ["Kachh"]}]}
    with pytest.raises(ValueError, match="Kachchh"):
        parse_district_other_names(wrong, register)


def test_the_page_cache_keeps_the_newest_pages_under_their_stamp() -> None:
    cache = PageCache(most=2)
    a, b, c = ((uuid.UUID(int=n), "OPEN") for n in (1, 2, 3))
    first = ServedPage(b"{}", "e1", "s1")
    cache.keep(a, first)
    cache.keep(b, ServedPage(b"{}", "e2", "s2"))
    assert cache.kept(a, "s1") is first
    assert cache.kept(a, "another stamp") is None
    cache.keep(c, ServedPage(b"{}", "e3", "s3"))
    assert cache.kept(b, "s2") is None
    assert cache.kept(a, "s1") is first


def test_the_stamp_names_the_site_its_citations_address() -> None:
    terms = {"claimsCount": 3}
    here = stamp_text(terms, code="c1", site="https://a.example", variant="OPEN")
    assert here != stamp_text(terms, code="c1", site="https://b.example", variant="OPEN")
    assert here != stamp_text(terms, code="c1", site="https://a.example", variant="RESEARCHER")
