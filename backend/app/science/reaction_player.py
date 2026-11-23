from __future__ import annotations

import uuid
from collections.abc import Collection, Iterable, Mapping

from app.research.blocks import ExplainerSentence, LadderCondition
from app.research.blocks_matter import ReactionNote, ReactionPlayerBlock, ReactionStep, StepEnergy
from app.research.citations import Citation
from app.research.vocabulary import FACT_LEVELS
from app.schemas.science import CitedClaim, ProcessStageView, ReactionView

from .ladder import stated_condition
from .process_view import craft_process
from .reaction_colours import step_colours
from .records import ProcessRecords

__all__ = [
    "NOTES_PER_STEP_MAX",
    "REACTION_STEPS_MAX",
    "STEP_CONDITIONS_MAX",
    "reaction_player",
    "reaction_player_problems",
]

REACTION_STEPS_MAX = 12
NOTES_PER_STEP_MAX = 4
STEP_CONDITIONS_MAX = 4

Played = tuple[ProcessStageView, ReactionView]
NoteKey = tuple[uuid.UUID, str, frozenset[str]]


def reaction_player(
    records: ProcessRecords, *, block_id: str, cited_claim_ids: Collection[str] = ()
) -> ReactionPlayerBlock | None:
    played = _chosen(_played(records), cited_claim_ids)
    if not played:
        return None
    return ReactionPlayerBlock(
        id=block_id,
        kind="reaction_player",
        version=1,
        reuse=None,
        steps=[_step(stage, view) for stage, view in played],
        notes=_notes(played, block_id),
    )


def reaction_player_problems(block: ReactionPlayerBlock, records: ProcessRecords) -> list[str]:
    stored = {view.id: (stage, view) for stage, view in _played(records)}
    problems: list[str] = []
    for step in block.steps:
        found = stored.get(step.reaction_id)
        if found is None:
            problems.append(f"reaction {step.reaction_id} is not a stored reaction of {records.craft.slug}")
            continue
        row = _step(*found)
        if _shown(step) != _shown(row) or not _details_match(step, row):
            problems.append(f"reaction {step.reaction_id} does not match its stored row")
        linked = {citation.id for citation in row.citations}
        if any(citation.id not in linked for citation in step.citations):
            problems.append(f"reaction {step.reaction_id} cites a passage that is not linked to it")
    allowed = _note_keys(stored)
    problems += [
        f"note {note.sentence.id} is not a stored claim of reaction {note.reaction_id}"
        for note in block.notes
        if _note_key(note) not in allowed
    ]
    return problems


def _played(records: ProcessRecords) -> list[Played]:
    return [
        (stage, reaction)
        for process in craft_process(records).processes
        for stage in process.stages
        for reaction in stage.reactions
    ]


def _chosen(played: list[Played], cited_claim_ids: Collection[str]) -> list[Played]:
    if len(played) <= REACTION_STEPS_MAX:
        return played

    def unrelated(position: int) -> bool:
        return not any(str(claim.id) in cited_claim_ids for claim in played[position][1].claims)

    kept = sorted(range(len(played)), key=lambda position: (unrelated(position), position))
    return [played[position] for position in sorted(kept[:REACTION_STEPS_MAX])]


def _step(stage: ProcessStageView, view: ReactionView) -> ReactionStep:
    citations = _citations(view.claims)
    return ReactionStep(
        reaction_id=view.id,
        stage_id=stage.id,
        kind=view.kind,
        label=view.label,
        species=list(view.species),
        equation=view.equation,
        balanced=view.balanced,
        level=view.level,
        citations=citations,
        stage=stage.name,
        conditions=_conditions(stage, view),
        colours=step_colours(citations),
        delta_h=_energy(view),
    )


def _energy(view: ReactionView) -> StepEnergy | None:
    if view.delta_h is None:
        return None
    return StepEnergy(kj_per_mol=view.delta_h.kj_per_mol, claim_id=str(view.delta_h.claim_id))


def _conditions(stage: ProcessStageView, view: ReactionView) -> list[LadderCondition]:
    found: dict[tuple[str, str], LadderCondition] = {}
    for condition in (*view.conditions, *stage.conditions):
        stated = stated_condition(condition)
        if stated is not None:
            found.setdefault((stated.label, stated.stated), stated)
    return list(found.values())[:STEP_CONDITIONS_MAX]


def _notes(played: Iterable[Played], block_id: str) -> list[ReactionNote]:
    notes: list[ReactionNote] = []
    seen: set[uuid.UUID] = set()
    for _, view in played:
        facts = [claim for claim in _facts(view.claims) if claim.id not in seen][:NOTES_PER_STEP_MAX]
        seen.update(claim.id for claim in facts)
        notes += [
            ReactionNote(reaction_id=view.id, sentence=_sentence(f"{block_id}.{len(notes) + n}", claim))
            for n, claim in enumerate(facts, start=1)
        ]
    return notes


def _facts(claims: Iterable[CitedClaim]) -> list[CitedClaim]:
    return [claim for claim in claims if claim.level in FACT_LEVELS]


def _sentence(sentence_id: str, claim: CitedClaim) -> ExplainerSentence:
    return ExplainerSentence(
        id=sentence_id, text=claim.text, level=claim.level, citations=list(claim.citations), terms=[]
    )


def _citations(claims: Iterable[CitedClaim]) -> list[Citation]:
    seen: dict[str, Citation] = {}
    for claim in claims:
        for citation in claim.citations:
            seen.setdefault(citation.id, citation)
    return list(seen.values())


def _shown(step: ReactionStep) -> tuple[object, ...]:
    return (step.stage_id, step.kind, step.label, step.species, step.equation, step.balanced)


def _details_match(step: ReactionStep, row: ReactionStep) -> bool:
    shown = (
        (step.stage, row.stage),
        (step.conditions, row.conditions),
        (step.colours, row.colours),
        (step.delta_h, row.delta_h),
    )
    return all(not mine or mine == stored for mine, stored in shown)


def _note_keys(stored: Mapping[uuid.UUID, Played]) -> set[NoteKey]:
    return {
        (view.id, claim.text, frozenset(citation.id for citation in claim.citations))
        for _, view in stored.values()
        for claim in _facts(view.claims)
    }


def _note_key(note: ReactionNote) -> NoteKey:
    sentence = note.sentence
    return (
        note.reaction_id,
        sentence.original or sentence.text,
        frozenset(citation.id for citation in sentence.citations),
    )
