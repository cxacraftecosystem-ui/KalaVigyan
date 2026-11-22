import dataclasses
import uuid

import pytest
from pydantic import ValidationError

from app.research.blocks_matter import ReactionStep, StepEnergy
from app.science.process_view import craft_process
from app.science.reaction_player import reaction_player, reaction_player_problems
from app.science.records import ProcessRecords

from .golden_process import golden_records

IRON_ACETATE = uuid.UUID("d9643f49-fefc-5e3a-ad08-a5ae499a4161")
FIXTURE_KJ_PER_MOL = -89.5


def energetic(kj_per_mol: float) -> tuple[ProcessRecords, uuid.UUID]:
    records = golden_records()
    reaction = next(r for r in records.reactions if r.id == IRON_ACETATE)
    claim = reaction.citations[0][0]
    changed = dataclasses.replace(reaction, delta_h=(kj_per_mol, claim))
    reactions = tuple(changed if r.id == IRON_ACETATE else r for r in records.reactions)
    return dataclasses.replace(records, reactions=reactions), claim


def iron_step(records: ProcessRecords) -> ReactionStep:
    block = reaction_player(records, block_id="s4.b2")
    assert block is not None
    return next(step for step in block.steps if step.reaction_id == IRON_ACETATE)


def test_a_step_carries_the_reaction_s_stored_and_cited_delta_h() -> None:
    records, claim = energetic(FIXTURE_KJ_PER_MOL)
    dumped = iron_step(records).model_dump(mode="json", by_alias=True)
    assert dumped["deltaH"] == {"kjPerMol": -89.5, "claimId": str(claim)}


def test_the_step_shows_the_same_delta_h_the_process_tab_shows() -> None:
    records, _ = energetic(FIXTURE_KJ_PER_MOL)
    views = [r for p in craft_process(records).processes for s in p.stages for r in s.reactions]
    view = next(r for r in views if r.id == IRON_ACETATE)
    step = iron_step(records)
    assert view.delta_h is not None and step.delta_h is not None
    assert (step.delta_h.kj_per_mol, step.delta_h.claim_id) == (
        view.delta_h.kj_per_mol,
        str(view.delta_h.claim_id),
    )


def test_a_reaction_without_a_stored_delta_h_leaves_the_field_out() -> None:
    block = reaction_player(golden_records(), block_id="s4.b2")
    assert block is not None
    assert all("deltaH" not in step for step in block.model_dump(mode="json", by_alias=True)["steps"])


def test_a_delta_h_whose_claim_the_step_does_not_cite_is_refused() -> None:
    records, _ = energetic(FIXTURE_KJ_PER_MOL)
    payload = iron_step(records).model_dump(mode="json", by_alias=True)
    payload["deltaH"]["claimId"] = str(uuid.UUID(int=7))
    with pytest.raises(ValidationError, match="ΔH only from a claim it cites"):
        ReactionStep.model_validate(payload)


def test_a_stored_step_whose_delta_h_differs_from_its_row_is_refused() -> None:
    records, claim = energetic(FIXTURE_KJ_PER_MOL)
    block = reaction_player(records, block_id="s4.b2")
    assert block is not None
    changed = [
        step.model_copy(update={"delta_h": StepEnergy(kj_per_mol=-90.0, claim_id=str(claim))})
        if step.reaction_id == IRON_ACETATE
        else step
        for step in block.steps
    ]
    stored = block.model_copy(update={"steps": changed})
    assert reaction_player_problems(stored, records) == [
        f"reaction {IRON_ACETATE} does not match its stored row"
    ]
