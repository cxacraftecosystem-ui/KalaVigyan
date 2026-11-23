from functools import cache
from typing import Any

from app.services.claim_seed import load_seed_claims, seed_id, stage_rows

MUD_SOAKING = "ie:dabu.process_stage.mud-soaking"
PASTE = "ie:dabu.process_stage.paste-preparation"
UNORDERED = {
    MUD_SOAKING,
    PASTE,
    "ie:machilipatnam-kalamkari.process_stage.block-carving",
    "ie:sanganeri.process_stage.block-carving",
}


@cache
def seed() -> dict[str, Any]:
    return load_seed_claims()


def craft_stages() -> list[dict[str, Any]]:
    return [c for c in seed()["concepts"] if c.get("stage") and c.get("craftSlug")]


def test_the_seed_states_no_ordinal_for_four_craft_stages() -> None:
    assert {c["key"] for c in craft_stages() if c["stage"].get("ordinal") is None} == UNORDERED


def test_no_stated_sequence_joins_an_unordered_stage_to_its_craft_s_ladder() -> None:
    precedes = [e for e in seed()["edges"] if e["relation"] == "PRECEDES"]
    touching = [(e["src"], e["dst"]) for e in precedes if {e["src"], e["dst"]} & UNORDERED]
    assert touching == [(MUD_SOAKING, PASTE)]


def test_a_stage_whose_place_no_source_states_gets_no_seed_stage() -> None:
    placed = {row["conceptId"] for row in stage_rows(craft_stages())}
    assert not placed & {seed_id("concept", key) for key in UNORDERED}
    assert len(placed) == len(craft_stages()) - len(UNORDERED)
