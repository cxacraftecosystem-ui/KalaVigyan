from __future__ import annotations

import uuid
from dataclasses import replace
from typing import Any

import pytest
from pydantic import ValidationError

from app.data.craft_master_loader import load_master
from app.models import Craft
from app.research.craft_page import CraftPage
from app.research.craft_page_context import PageTabs
from app.research.crafts import CraftRef
from app.services.craft_page import craft_page
from app.services.craft_page_family import FamilyCandidate, ranked_family, relative_extras
from app.services.craft_page_market import market_from_rows
from app.services.craft_page_offers import PageOffers
from app.services.craft_page_preview import register_page
from app.services.craft_page_records import ClaimFacts, page_craft
from app.services.craft_page_register import register_offers
from app.services.curation_keys import curated_id

from ..contracts.golden import golden_json
from .import_support import AJRAKH, raw
from .test_craft_page import HISTORY_CONCEPT, ajrakh_records, stored_view, uncurated_records

REGISTER_GOLDEN = "craft.page.register.golden.json"
TEXTILES = "Textiles based Craft Category"
BLOCK_PRINTING = "Hand Block Printing"
EXPORTED = "Bagru printers began sending their cloth to Europe in 1985."


def claim(key: str) -> uuid.UUID:
    return curated_id(AJRAKH, key)


@pytest.fixture(scope="module")
def ajrakh() -> CraftPage:
    return craft_page(ajrakh_records())


def test_the_masthead_names_the_family_and_kind_in_editorial_words(ajrakh: CraftPage) -> None:
    craft = ajrakh.craft
    assert (craft.display_name, craft.family_label, craft.kind_label) == (
        "Kutch Ajrakh",
        "Textiles",
        "Hand block printing",
    )
    assert (craft.category_name, craft.sub_category_name) == (TEXTILES, BLOCK_PRINTING)
    assert (
        ajrakh.suggested_questions[0]
        == "How do mordants and dyes fix the colours of Kutch Ajrakh in the cloth?"
    )


def test_the_gi_card_is_the_registry_record_its_claims_state(ajrakh: CraftPage) -> None:
    gi = raw(AJRAKH)["market"]["gi"]
    card = ajrakh.gi_card
    assert (card.status, card.application_number, card.filed_on, card.registered_on, card.journal_issue) == (
        "GI",
        gi["applicationNumber"],
        gi["filedOn"],
        gi["registeredOn"],
        gi["journalIssue"],
    )
    assert card.proprietors == gi["proprietors"]
    assert card.claim_ids == [claim(key) for key in gi["claimIds"]]


def test_dated_events_cite_the_claim_that_states_each_date(ajrakh: CraftPage) -> None:
    kinds: dict[str, list[Any]] = {}
    for event in ajrakh.events:
        kinds.setdefault(event.kind, []).append(event)
    (filed,), (registered,), (price,) = kinds["GI_FILED"], kinds["GI_REGISTERED"], kinds["PRICE"]
    assert (filed.date, filed.claim_ids) == ("2023-01-31", [claim("C132")])
    assert (registered.date, registered.claim_ids) == ("2024-04-22", [claim("C134")])
    assert (price.start, price.date, price.place, price.claim_ids) == (
        1975,
        "1975",
        "Barmer",
        [claim("C049")],
    )
    workforce = sorted(entry["year"] for entry in raw(AJRAKH)["market"]["workforce"])
    assert sorted(event.start for event in kinds["WORKFORCE"]) == workforce
    invited = next(event for event in kinds["STATED"] if event.claim_ids == [claim("C009")])
    assert (invited.start, invited.end) == (1586, 1631)
    fustat = next(event for event in kinds["STATED"] if event.claim_ids == [claim("C015")])
    assert (fustat.start, fustat.end) == (1001, 1400)
    dated = {claim_id for event in ajrakh.events for claim_id in event.claim_ids}
    assert claim("C012") not in dated
    assert claim("C133") not in dated
    spans = [(event.start, event.end) for event in ajrakh.events]
    assert spans == sorted(spans)


def test_sources_differ_rows_carry_a_key_and_a_weight(ajrakh: CraftPage) -> None:
    conflicts = raw(AJRAKH)["conflicts"]
    rows = {row.about: row for row in ajrakh.sources_differ}
    assert {row.key for row in ajrakh.sources_differ} == {f"differ-{n}" for n in range(1, len(conflicts) + 1)}
    assert rows["Whether synthetic alizarin is chemically the same as natural madder"].weight == 3
    assert rows["How many stages the ajrakh process has"].weight == 2
    assert rows["How far Dhamadka is from Bhuj"].weight == 1
    weights = [row.weight for row in ajrakh.sources_differ]
    assert weights == sorted(weights, reverse=True)


def test_a_stage_points_to_the_disagreements_about_it(ajrakh: CraftPage) -> None:
    dossier = raw(AJRAKH)
    stage = next(entry for entry in dossier["stages"] if entry["name"] == "Red dyeing")
    timing = [stage[part]["claimId"] for part in ("duration", "season") if stage.get(part)]
    own = {*stage["claimIds"], *timing}
    expected = {
        f"differ-{n}" for n, row in enumerate(dossier["conflicts"], start=1) if own & set(row["claimIds"])
    }
    red = next(entry for entry in ajrakh.process.stages if entry.name == "Red dyeing")
    assert expected and set(red.differ) == expected


def test_materials_carry_their_botanical_name_and_compound(ajrakh: CraftPage) -> None:
    indigo = next(stage for stage in ajrakh.process.stages if stage.name == "Indigo dyeing")
    items = {item.name: item for item in indigo.materials}
    assert (items["Indigo"].botanical_name, items["Indigo"].pubchem_cid) == ("Indigofera tinctoria", 10215)
    assert (items["Caustic soda"].botanical_name, items["Caustic soda"].pubchem_cid) == (None, 14798)


def masthead_picture() -> dict[str, Any]:
    (placed,) = [p for p in raw(AJRAKH)["pictures"] if (p.get("placement") or {}).get("role") == "MASTHEAD"]
    return placed


def test_one_hero_leads_the_pictures(ajrakh: CraftPage) -> None:
    roles = [picture.role for picture in ajrakh.pictures]
    assert roles.count("HERO") == 1
    hero = next(picture for picture in ajrakh.pictures if picture.role == "HERO")
    assert hero.media.image_url == masthead_picture()["url"]
    staged = [picture for picture in raw(AJRAKH)["pictures"] if picture.get("stageId")]
    assert roles.count("STAGE") == len(staged)
    assert set(roles) - {"HERO", "STAGE"} == {"OVERVIEW"}


def test_the_environment_story_follows_the_dossier(ajrakh: CraftPage) -> None:
    steps = raw(AJRAKH)["environment"]
    shown = [(step.factor, step.place.key if step.place else None) for step in ajrakh.environment]
    assert shown == [(step["factor"], step.get("placeId")) for step in steps]
    assert ajrakh.environment[0].claim_ids == [claim(key) for key in steps[0]["claimIds"]]


def test_depth_and_tabs_are_final_at_first_paint(ajrakh: CraftPage) -> None:
    dossier = raw(AJRAKH)
    depth = ajrakh.depth
    assert (depth.basis, depth.coverage, depth.claims, depth.sources, depth.stages, depth.pictures) == (
        "CURATED",
        "FULL",
        len(dossier["claims"]),
        len(dossier["sources"]),
        len(dossier["stages"]),
        len(dossier["pictures"]),
    )
    assert ajrakh.tabs == PageTabs(
        process=True, region=True, shared_science=False, sources=True, evidence=True
    )


def test_the_family_lists_six_of_its_richest_crafts_never_a_catch_all(ajrakh: CraftPage) -> None:
    kin = [
        craft
        for craft in load_master()
        if craft.sub_category_slug == "Hand-Block-Printing"
        and craft.slug != AJRAKH
        and not craft.is_catch_all
    ]
    registered = sorted(
        (craft for craft in kin if craft.gi_status == "GI"), key=lambda craft: craft.name.casefold()
    )
    assert [relative.craft.slug for relative in ajrakh.same_family] == [
        craft.slug for craft in registered[:6]
    ]
    assert all(relative.basis == "REGISTER" and relative.hero is None for relative in ajrakh.same_family)


def candidate(slug: str, *, coverage: str | None = None, claims: int = 0, gi: str | None = "NON_GI") -> Any:
    ref = CraftRef(slug=slug, name=slug.replace("-", " "), path=f"/crafts/{slug}")
    return FamilyCandidate(ref, gi, (), coverage, claims, catch_all=slug.startswith("Other"))


def test_the_richest_relative_comes_first() -> None:
    found = [
        candidate("Zari", claims=3, gi="GI"),
        candidate("Thin-Dossier", coverage="THIN"),
        candidate("Other-Prints", claims=90),
        candidate("Seeded", claims=40),
        candidate("Own", coverage="FULL"),
        candidate("Full-Dossier", coverage="FULL"),
        candidate("Abu", claims=3),
    ]
    ranked = [item.craft.slug for item in ranked_family(found, own_slug="Own")]
    assert ranked == ["Full-Dossier", "Thin-Dossier", "Seeded", "Zari", "Abu"]


def test_sources_are_numbered_in_reading_order(ajrakh: CraftPage) -> None:
    gi = ajrakh.masthead.gi.citations if ajrakh.masthead.gi else []
    plate = ajrakh.masthead.picture.sentences if ajrakh.masthead.picture else []
    lede = [citation for sentence in [*plate, *ajrakh.lede] for citation in sentence.citations]
    first = [citation.source_id for citation in [*gi, *lede]]
    numbered = [source.id for source in ajrakh.sources]
    assert numbered[: len(dict.fromkeys(first))] == list(dict.fromkeys(first))
    shown = {citation.source_id for citation in ajrakh.shown_citations(kin=True)}
    assert set(numbered[: len(shown)]) == shown


def test_a_glossary_term_is_never_taken_for_the_crafts_own_name() -> None:
    records = ajrakh_records()
    assert records.curated is not None
    term = records.curated.glossary[0]
    named = term.model_copy(update={"names": ["ajrakh", "અજરખ"], "script": None})
    curated = records.curated.model_copy(update={"glossary": [named, *records.curated.glossary[1:]]})
    page = craft_page(replace(records, curated=curated))
    stated = [name["text"] for name in raw(AJRAKH)["nativeNames"]]
    assert [name.name for name in page.craft.local_names] == stated
    assert not {"ajrakh", "અજરખ"} & set(stated)
    assert page.glossary[0].names == ["ajrakh", "અજરખ"]


def test_a_craft_known_only_to_the_register_gets_a_complete_page() -> None:
    page = CraftPage.model_validate(golden_json(REGISTER_GOLDEN))
    assert (page.curated, page.depth.basis, page.claims) == (False, "REGISTER", [])
    assert {(source.group, source.from_.slug if source.from_ else None) for source in page.sources} == {
        ("KIN", AJRAKH)
    }
    assert (page.craft.slug, page.craft.family_label, page.craft.kind_label) == (
        "Farrukhabad-Prints",
        "Textiles",
        "Hand block printing",
    )
    assert page.suggested_questions == [
        "How do mordants and dyes fix the colours of Farrukhabad Prints in the cloth?",
        "What are the stages of Farrukhabad Prints, from plain cloth to finished print?",
        "What do local water and climate give to the colours of Farrukhabad Prints?",
    ]
    assert page.tabs == PageTabs(
        process=False, region=True, shared_science=False, sources=False, evidence=False
    )
    assert (page.gi_card.status, page.gi_card.claim_ids) == ("GI", [])
    first = page.same_family[0]
    assert (first.craft.slug, first.basis, first.coverage) == (AJRAKH, "CURATED", "FULL")
    assert first.hero is not None and first.hero.media.image_url == masthead_picture()["url"]
    assert first.lede is not None and first.lede.text == raw(AJRAKH)["overview"]["lede"][0]["text"]
    assert len(page.same_family) == 6


def test_a_catch_all_row_is_shown_by_its_kind() -> None:
    craft = Craft(
        id=uuid.UUID(int=901),
        slug="Other-Hand-Block-Print",
        name="Other Hand Block Print",
        localName=None,
        category=TEXTILES,
        giStatus="NON_GI",
        stateOfPractice=["All India"],
        stateOfOrigin=[],
        isCatchAll=True,
    )
    shown = page_craft(craft, (TEXTILES, BLOCK_PRINTING))
    assert shown.display_name == "Other hand block printing"
    page = craft_page(replace(uncurated_records(), craft=shown, catch_all=True))
    assert page.suggested_questions[1] == (
        "What are the stages of hand block printing, from plain cloth to finished print?"
    )


def test_a_previewed_catch_all_row_is_shown_and_asked_about_by_its_kind() -> None:
    page = register_page("Other-Hand-Block-Print")
    assert page.craft.display_name == "Other hand block printing"
    assert page.suggested_questions == [
        "How do mordants and dyes fix the colours of a block print in the cloth?",
        "What are the stages of hand block printing, from plain cloth to finished print?",
        "Why do water and climate matter so much to hand block printing?",
    ]


def test_region_and_sources_are_offered_only_where_a_place_is_known() -> None:
    assert register_offers(["All India"], ()) == PageOffers()
    assert register_offers(["Uttar Pradesh"], ()) == PageOffers(region=True)
    assert register_offers([], [{"sourceId": "S"}]) == PageOffers(region=True, region_sources=True)


def test_a_craft_has_one_gi_record_at_most() -> None:
    row = {
        "applicationNumber": "1",
        "certificateNumber": None,
        "filedOn": None,
        "registeredOn": None,
        "journalIssue": None,
        "proprietors": [],
        "authorisedUserCount": None,
        "claimIds": [uuid.UUID(int=1)],
    }
    with pytest.raises(ValueError, match="one GI record"):
        market_from_rows([row, row], [], [])


def test_stored_claims_that_state_a_year_become_events() -> None:
    base = uncurated_records()
    view = stored_view(5, EXPORTED, HISTORY_CONCEPT)
    facts = {**base.facts, view.id: ClaimFacts("LIVE_RESEARCH", False, None, "Trade", "HISTORICAL_CONTEXT")}
    page = craft_page(replace(base, views=(*base.views, view), facts=facts))
    assert [(event.kind, event.start, event.claim_ids) for event in page.events] == [
        ("STATED", 1985, [view.id])
    ]
    assert (page.depth.basis, page.depth.coverage) == ("STORED_CLAIMS", None)
    assert page.same_family == [] and page.environment == [] and page.craft.local_names == []


def test_a_hidden_place_is_never_pointed_at() -> None:
    records = ajrakh_records()
    assert records.curated is not None
    pointed = next(group.place_key for group in records.curated.communities if group.place_key)
    places = [
        place.model_copy(update={"claim_ids": [uuid.UUID(int=999)]}) if place.key == pointed else place
        for place in records.curated.places
    ]
    page = craft_page(replace(records, curated=records.curated.model_copy(update={"places": places})))
    assert pointed not in {place.key for place in page.places}
    listed = {place.key for place in page.places}
    assert all(group.place_key in listed for group in page.communities if group.place_key)
    assert all(step.place.key in listed for step in page.environment if step.place)
    assert all(group.place is None for group in page.communities if group.place_key is None)


def test_the_contract_refuses_a_part_pointing_at_an_unlisted_place(ajrakh: CraftPage) -> None:
    body = ajrakh.model_dump(mode="json", by_alias=True)
    body["communities"][0]["placeKey"] = "nowhere"
    with pytest.raises(ValidationError, match="nowhere"):
        CraftPage.model_validate(body)


def test_an_environment_step_names_a_listed_factor(ajrakh: CraftPage) -> None:
    body = ajrakh.model_dump(mode="json", by_alias=True)
    body["environment"][0]["factor"] = "WIND"
    with pytest.raises(ValidationError, match="factor"):
        CraftPage.model_validate(body)


def test_a_relative_leads_with_the_hero_its_own_page_shows() -> None:
    records = ajrakh_records()
    assert records.curated is not None
    hidden = set(records.curated.pictures[0].claim_ids)
    views = tuple(view for view in records.views if view.id not in hidden)
    own = craft_page(replace(records, views=views))
    hero = next(picture for picture in own.pictures if picture.role == "HERO")
    extras = relative_extras(records.curated, records.media, None, ({view.id for view in views}, {}))
    assert extras.hero is not None and extras.hero.media.id == hero.media.id
    assert hero.media.image_url != raw(AJRAKH)["pictures"][0]["url"]


def test_the_craft_is_named_in_its_own_scripts_by_the_dossier_s_reviewed_native_names(
    ajrakh: CraftPage,
) -> None:
    stated = raw(AJRAKH)["nativeNames"]
    assert [(name["text"], name["language"], name["script"], name["claimId"]) for name in stated] == [
        ("اجرڪ", "sd", "Arab", "C152"),
        ("ajrak", "sd", "Latn", "C152"),
    ]
    assert [(name.name, name.language, name.script, name.claim_ids) for name in ajrakh.craft.local_names] == [
        (name["text"], name["language"], name["script"], [claim(name["claimId"])]) for name in stated
    ]


def test_a_native_name_whose_claim_the_page_does_not_show_is_left_out() -> None:
    records = ajrakh_records()
    hidden = replace(records, views=tuple(view for view in records.views if view.id != claim("C152")))
    assert craft_page(hidden).craft.local_names == []
    assert craft_page(uncurated_records()).craft.local_names == []
