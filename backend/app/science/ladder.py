from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence

from app.research.blocks import (
    ExplainerSentence,
    LadderCondition,
    LadderMaterial,
    LadderStage,
    ProcessLadderBlock,
)
from app.research.citations import Citation
from app.research.composition import StageOption
from app.research.quotes import quote_occurs
from app.research.vocabulary import FACT_LEVELS, weakest_level
from app.schemas.science import CitedClaim, ProcessStageView, ProcessView, StageCondition

from .process_view import craft_process
from .records import ProcessRecords, StageRecord

__all__ = ["ladder_problems", "ladder_stage_options", "process_ladder", "stated_condition"]


def ladder_stage_options(records: ProcessRecords) -> list[StageOption]:
    return [
        StageOption(id=stage.id, ordinal=stage.ordinal, name=stage.name)
        for process in craft_process(records).processes
        for stage in process.stages
        if stage.ordered and _facts(stage.claims)
    ]


def process_ladder(
    records: ProcessRecords, *, block_id: str, stage_ids: Sequence[uuid.UUID]
) -> ProcessLadderBlock | None:
    wanted = set(stage_ids)
    processes = craft_process(records).processes
    chosen = max(processes, key=lambda p: sum(stage.id in wanted for stage in p.stages), default=None)
    if chosen is None:
        return None
    stages = _ladder_stages(chosen, wanted, block_id)
    if not stages:
        return None
    return ProcessLadderBlock(
        id=block_id,
        kind="process_ladder",
        version=1,
        reuse=None,
        craft=records.craft,
        process_id=chosen.id,
        stages=stages,
    )


def ladder_problems(block: ProcessLadderBlock, records: ProcessRecords) -> list[str]:
    if block.craft != records.craft:
        return [f"ladder {block.id} is for {block.craft.slug}, not {records.craft.slug}"]
    stored = {stage.id: stage for stage in records.stages if stage.process_id == block.process_id}
    if not stored:
        return [f"process {block.process_id} is not stored for {records.craft.slug}"]
    problems: list[str] = []
    for stage in block.stages:
        row = stored.get(stage.stage_id)
        if row is None:
            problems.append(f"stage {stage.stage_id} is not a stored stage of process {block.process_id}")
            continue
        if (stage.ordinal, stage.name, stage.stage_type) != (row.ordinal, row.name, row.stage_type):
            problems.append(f"stage {stage.stage_id} does not match its stored row")
        if not row.ordered and not stage.unnumbered:
            problems.append(f"stage {stage.stage_id} has no order a source states, so no ladder numbers it")
        problems += _stage_problems(stage, row, records)
    return problems


def _ladder_stages(process: ProcessView, wanted: set[uuid.UUID], block_id: str) -> list[LadderStage]:
    stages: list[LadderStage] = []
    count = 0
    for view in process.stages:
        facts = _facts(view.claims) if view.id in wanted else []
        if not facts:
            continue
        sentences = [_sentence(f"{block_id}.{count + n}", claim) for n, claim in enumerate(facts, start=1)]
        count += len(sentences)
        stages.append(_ladder_stage(view, sentences))
    return stages


def _ladder_stage(view: ProcessStageView, sentences: list[ExplainerSentence]) -> LadderStage:
    materials = [
        LadderMaterial(
            material_id=m.id, name=m.name, kind=m.kind, role=m.role, citations=_citations(_facts(m.claims))
        )
        for m in view.materials
        if _facts(m.claims)
    ]
    return LadderStage(
        stage_id=view.id,
        ordinal=view.ordinal,
        unnumbered=None if view.ordered else True,
        name=view.name,
        stage_type=view.stage_type,
        level=weakest_level(sentence.level for sentence in sentences),
        sentences=sentences,
        materials=materials,
        conditions=[
            c for c in (stated_condition(condition) for condition in view.conditions) if c is not None
        ],
        reaction_ids=[reaction.id for reaction in view.reactions],
    )


def stated_condition(condition: StageCondition) -> LadderCondition | None:
    facts = {claim.id: claim for claim in _facts(condition.claims)}
    for reading in condition.readings:
        claim = facts.get(reading.claim_id)
        quoted = (
            [c for c in claim.citations if c.quote and quote_occurs(reading.stated, c.quote)] if claim else []
        )
        if quoted:
            return LadderCondition(label=condition.label, stated=reading.stated, citations=quoted)
    return None


def _sentence(sentence_id: str, claim: CitedClaim) -> ExplainerSentence:
    return ExplainerSentence(
        id=sentence_id, text=claim.text, level=claim.level, citations=list(claim.citations), terms=[]
    )


def _stage_problems(stage: LadderStage, row: StageRecord, records: ProcessRecords) -> list[str]:
    problems = [
        f"stage {stage.stage_id} sentence {sentence.id} is not one of its stored claims"
        for sentence in stage.sentences
        if not _states_a_stage_claim(sentence, row, records)
    ]
    materials = {m.id: m for m in records.materials if m.stage_id == row.id}
    for material in stage.materials:
        stored = materials.get(material.material_id)
        if stored is None or not {c.claim_id for c in material.citations} <= {
            str(i) for i in stored.claim_ids
        }:
            problems.append(f"stage {stage.stage_id} material {material.material_id} is not stored for it")
    stated = {(c.label, r.stated) for c in records.conditions if c.owner_id == row.id for r in c.readings}
    problems += [
        f"stage {stage.stage_id} condition {condition.label!r} is not stored for it"
        for condition in stage.conditions
        if (condition.label, condition.stated) not in stated
    ]
    reactions = {reaction.id for reaction in records.reactions if reaction.stage_id == row.id}
    problems += [
        f"stage {stage.stage_id} reaction {reaction_id} is not stored for it"
        for reaction_id in stage.reaction_ids
        if reaction_id not in reactions
    ]
    return problems


def _states_a_stage_claim(sentence: ExplainerSentence, row: StageRecord, records: ProcessRecords) -> bool:
    claim_ids = {citation.claim_id for citation in sentence.citations}
    if len(claim_ids) != 1:
        return False
    claim = records.claims.get(uuid.UUID(claim_ids.pop()))
    if claim is None or claim.id not in row.claim_ids:
        return False
    english = sentence.original if sentence.translated else sentence.text
    known = {citation.id for citation in claim.citations}
    return english == claim.text and all(citation.id in known for citation in sentence.citations)


def _facts(claims: Iterable[CitedClaim]) -> list[CitedClaim]:
    return [claim for claim in claims if claim.level in FACT_LEVELS]


def _citations(claims: Iterable[CitedClaim]) -> list[Citation]:
    return [citation for claim in claims for citation in claim.citations]
