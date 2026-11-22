from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Awaitable, Callable, Collection, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.composer.simulation import DraftReply, SimulationBrief, draft_simulation, redraft_simulation
from app.core.errors import ExternalFailure, InvalidInput
from app.models.enums import EXPLAINER_DEPTHS
from app.research.blocks import ImagesBlock
from app.research.blocks_play import SIMULATION_VALUES_MAX, SimulationBlock
from app.research.crafts import CraftRef
from app.research.explainer import Block
from app.research.knowledge_pieces import SIMULATION_NAMESPACE, KnowledgePiece, placed_block
from app.research.piece_reuse import SIMULATION_KIND, reusable_simulation
from app.research.simulation_draft import (
    DraftCheck,
    Grounding,
    OfferedValue,
    RowValue,
    checked_draft,
    offered_rows,
    offered_values,
)
from app.research.structured import MODEL_SERVICE, StructuredModel
from app.research.subject_keys import topic_key
from app.science.mechanisms import Concept, section_concepts
from app.science.records import ProcessRecords

from .builder_evidence import section_facts, sources_beyond
from .builder_interface import BuildAsk, BuilderTools, Built
from .concept_pictures import ConceptPictures, PictureSearch
from .craft_matter import CraftMatter
from .section_images import SectionImagesAsk, section_images
from .simulation_datasets import cited_datasets, first_district_rows
from .simulation_grounding import (
    AnswerConcepts,
    concept_states,
    explainer_limit,
    grounded_claim_ids,
    grounding_for,
    reactions_hold,
)
from .simulation_pieces import simulation_pieces

__all__ = [
    "CHECKS_FAILED",
    "FIGURES_KEY_PREFIX",
    "HIDDEN_AGAIN",
    "NO_CONCEPT",
    "NO_MECHANISM",
    "NO_QUANTITY",
    "NO_TIME_TO_REDRAFT",
    "OUT_OF_TIME",
    "SIMULATION_BUDGET_SECONDS",
    "SIMULATION_WAIT_SECONDS",
    "MatterOf",
    "SimulationBudget",
    "SimulationBuilder",
    "StoredSimulations",
    "hidden_again",
]

logger = logging.getLogger(__name__)

SIMULATION_BUDGET_SECONDS = 60.0
SIMULATION_WAIT_SECONDS = 75.0
PROBLEMS_LOGGED = 8
FIGURES_KEY_PREFIX = "figures"
NO_CONCEPT = "NO_CONCEPT"
NO_QUANTITY = "NO_QUANTITY"
NO_MECHANISM = "NO_MECHANISM"
CHECKS_FAILED = "CHECKS_FAILED"
HIDDEN_AGAIN = "HIDDEN_AGAIN"
OUT_OF_TIME = "OUT_OF_TIME"
NO_TIME_TO_REDRAFT = "NO_TIME_TO_REDRAFT"

StoredSimulations = Callable[[Collection[uuid.UUID], str], Awaitable[list[KnowledgePiece]]]
MatterOf = Callable[[CraftRef], Awaitable[CraftMatter | None]]
DatasetRows = Callable[[BuildAsk], Awaitable[list[RowValue]]]
Clock = Callable[[], datetime]


@dataclass(frozen=True)
class SimulationBudget:
    seconds: float = SIMULATION_BUDGET_SECONDS
    timer: Callable[[], float] = field(default=time.monotonic)

    def leaves_a_redraft(self, started: float) -> bool:
        spent = self.timer() - started
        return self.seconds - spent >= spent


@dataclass(frozen=True)
class _Explained:
    block: SimulationBlock | None = None
    note: str | None = None


class SimulationBuilder:
    def __init__(
        self,
        tools: BuilderTools,
        *,
        stored: StoredSimulations | None = None,
        clock: Clock | None = None,
        matter: MatterOf | None = None,
        pictures: PictureSearch | None = None,
        datasets: DatasetRows | None = None,
        budget: SimulationBudget | None = None,
    ) -> None:
        self._tools = tools
        self._stored = stored or self._stored_in_database
        self._clock = clock or (lambda: datetime.now(UTC))
        self._matter = matter
        self._pictures = ConceptPictures(pictures or self._searched_picture)
        self._datasets = datasets or self._datasets_in_database
        self._budget = budget or SimulationBudget()
        self._answers: dict[uuid.UUID, AnswerConcepts] = {}

    async def build(self, ask: BuildAsk) -> Built:
        answer = self._answers.setdefault(ask.answer_id, AnswerConcepts(explainer_limit(ask.request.depth)))
        matter = await self._matter_of(ask)
        concepts = section_concepts(matter.records, ask.blocks) if matter is not None else []
        chosen = next((concept for concept in concepts if answer.take(concept.key)), None)
        key = chosen.key if chosen is not None else _figures_key(ask, concepts, answer)
        others = [concept for concept in concepts if concept is not chosen]
        made, pictures = await asyncio.gather(
            self._explained(ask, chosen, matter) if key is not None else _nothing(),
            self._pictures.found(ask, others, answer),
        )
        if key is not None and made.block is None:
            answer.give_back(key)
            pictures += await self._pictures.found(ask, [chosen] if chosen is not None else [], answer)
        blocks: list[Block] = [*([made.block] if made.block is not None else []), *pictures]
        known = matter.records.sources if matter is not None else {}
        return Built(tuple(blocks), sources_beyond(blocks, known, ask.cited), note=made.note)

    async def _explained(
        self, ask: BuildAsk, concept: Concept | None, matter: CraftMatter | None
    ) -> _Explained:
        grounding = grounding_for(section_facts(ask.blocks, ask.cited), concept)
        quoted = offered_values(c for statement in grounding.statements for c in statement.citations)
        rows = offered_rows(await self._datasets(ask), limit=SIMULATION_VALUES_MAX - len(quoted))
        offers = [*quoted, *rows]
        if concept is None and not offers:
            return _Explained(note=NO_QUANTITY)
        stored = await self._stored(grounded_claim_ids(grounding), ask.section.discipline)
        reused = reusable_simulation(
            stored,
            facet=ask.section.discipline,
            depth=ask.request.depth or EXPLAINER_DEPTHS[-1],
            offered=grounded_claim_ids(grounding),
            current=concept_states(ask.cited.views.values(), concept),
        )
        records = matter.records if matter is not None else None
        if reused is not None and _still_played(reused, records):
            return _Explained(block=placed_block(reused, _block_id(ask)))
        if not offers and not grounding.reactions:
            logger.info("section %s states no quantity a generated explainer can draw", ask.section.id)
            return _Explained(note=NO_QUANTITY)
        hidden = [piece for piece in stored if piece.hidden_at is not None]
        made = await self._built(ask, _brief(ask, grounding, offers, hidden, concept), offers)
        if made.block is not None and hidden_again(made.block, hidden):
            logger.warning("the generated explainer of section %s adds nothing: HIDDEN", ask.section.id)
            return _Explained(note=HIDDEN_AGAIN)
        return made

    async def _built(
        self, ask: BuildAsk, brief: SimulationBrief, offers: Sequence[OfferedValue]
    ) -> _Explained:
        try:
            async with asyncio.timeout(self._budget.seconds):
                return await self._drafted(ask, brief, offers)
        except TimeoutError:
            logger.warning(
                "the generated explainer of section %s ran past its %s s budget",
                ask.section.id,
                self._budget.seconds,
            )
            return _Explained(note=OUT_OF_TIME)

    async def _drafted(
        self, ask: BuildAsk, brief: SimulationBrief, offers: Sequence[OfferedValue]
    ) -> _Explained:
        model, started = self._model(), self._budget.timer()
        reply = await draft_simulation(model, brief)
        if not reply.draft.build:
            logger.info("the model found no mechanism to show in section %s", ask.section.id)
            return _Explained(note=NO_MECHANISM)
        check = self._checked(ask, reply, offers, brief.grounding)
        if check.block is None:
            if not self._budget.leaves_a_redraft(started):
                logger.info("section %s has no time left to redraft its generated explainer", ask.section.id)
                return _Explained(note=NO_TIME_TO_REDRAFT)
            logger.info(
                "section %s redrafts its generated explainer: %s", ask.section.id, ",".join(check.rules)
            )
            reply = await redraft_simulation(model, brief, reply.draft, check.problems)
            if not reply.draft.build:
                return _Explained(note=NO_MECHANISM)
            check = self._checked(ask, reply, offers, brief.grounding)
        if check.block is None:
            logger.warning(
                "the generated explainer of section %s adds nothing; rules failed: %s; %s",
                ask.section.id,
                ",".join(check.rules),
                "; ".join(f"{p.rule} {p.detail}" for p in check.problems[:PROBLEMS_LOGGED]),
            )
            return _Explained(note=CHECKS_FAILED)
        return _Explained(block=check.block)

    def _model(self) -> StructuredModel:
        return self._tools.explainer_model or self._tools.compose_model

    def _checked(
        self, ask: BuildAsk, reply: DraftReply, offers: Sequence[OfferedValue], grounding: Grounding
    ) -> DraftCheck:
        if reply.model is None:
            raise ExternalFailure("the route that wrote the explainer named no model", service=MODEL_SERVICE)
        return checked_draft(
            reply.draft,
            offers,
            block_id=_block_id(ask),
            model=reply.model,
            created_at=self._clock(),
            grounding=grounding,
        )

    async def _stored_in_database(self, claim_ids: Collection[uuid.UUID], facet: str) -> list[KnowledgePiece]:
        async with self._tools.sessions() as session:
            return await simulation_pieces(session, claim_ids, [facet])

    async def _matter_of(self, ask: BuildAsk) -> CraftMatter | None:
        craft = ask.request.craft
        if craft is None:
            return None
        if self._matter is not None:
            return await self._matter(craft)
        return await ask.matter.read(self._tools.sessions, craft)

    async def _datasets_in_database(self, ask: BuildAsk) -> list[RowValue]:
        if ask.request.craft is None or not cited_datasets(ask.blocks):
            return []
        async with self._tools.sessions() as session:
            return await first_district_rows(session, ask.request.craft.slug, ask.blocks)

    async def _searched_picture(self, ask: BuildAsk, concept: Concept, block_id: str) -> ImagesBlock | None:
        images = await section_images(self._tools.sessions, self._tools.live)
        craft = ask.request.craft.name if ask.request.craft is not None else None
        return await images.block(
            SectionImagesAsk(block_id, craft, concept.shown_claim_ids, topic=" ".join(concept.words))
        )


def hidden_again(block: SimulationBlock, hidden: Sequence[KnowledgePiece]) -> bool:
    try:
        key = topic_key(SIMULATION_NAMESPACE, block.concept)
    except InvalidInput:
        return False
    claims = sorted({uuid.UUID(claim) for claim in block.cited_claim_ids()})
    return any(piece.topic_key == key and piece.claim_ids == claims for piece in hidden)


def _figures_key(ask: BuildAsk, concepts: Sequence[Concept], answer: AnswerConcepts) -> str | None:
    key = f"{FIGURES_KEY_PREFIX}:{ask.answer_id}:{ask.section.id}"
    return key if not concepts and answer.take(key) else None


async def _nothing() -> _Explained:
    return _Explained(note=NO_CONCEPT)


def _still_played(piece: KnowledgePiece, records: ProcessRecords | None) -> bool:
    return isinstance(piece.payload, SimulationBlock) and reactions_hold(piece.payload, records)


def _brief(
    ask: BuildAsk,
    grounding: Grounding,
    offers: Sequence[OfferedValue],
    hidden: Sequence[KnowledgePiece],
    concept: Concept | None,
) -> SimulationBrief:
    return SimulationBrief(
        question=ask.request.english_question or ask.request.question,
        craft=ask.request.craft.name if ask.request.craft is not None else None,
        section=ask.section.title,
        discipline=ask.section.discipline,
        shown=tuple(dict.fromkeys(block.kind for block in ask.blocks)),
        statements=tuple(statement.text for statement in grounding.statements),
        offers=tuple(offers),
        hidden=tuple(
            dict.fromkeys(
                piece.payload.concept for piece in hidden if isinstance(piece.payload, SimulationBlock)
            )
        ),
        concept=concept.label if concept is not None else None,
        grounding=grounding,
    )


def _block_id(ask: BuildAsk) -> str:
    return f"{ask.section.id}.{SIMULATION_KIND}"
