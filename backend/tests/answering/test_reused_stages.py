import uuid

from app.research.blocks import ProcessLadderBlock
from app.research.planning import PlanRequest
from app.research.sections import SectionSpec
from app.services.answer_events import CitedClaims
from app.services.block_builders import BlockBuilders
from app.services.piece_lookup import ReusedSection
from app.services.reused_sections import ReuseBuilds

from ..science.golden_process import CRAFT, KUT, PA, RED, golden_records, stage_id
from .fakes import FakeEnrichment

PROCESS = SectionSpec(id="s1", discipline="PROCESS", title="How Kutch Ajrakh is made", order=1)
FROM_KUT_TO_RED = "What are the steps of making Kutch Ajrakh, from the iron-black printing to the red dyeing?"


def builds(question: str) -> ReuseBuilds:
    request = PlanRequest(question=question, mode="HYBRID", craft=CRAFT)
    return ReuseBuilds(BlockBuilders([]), uuid.uuid4(), request, process=golden_records())


async def test_a_reused_process_section_shows_the_stages_its_question_names() -> None:
    enrichment = await FakeEnrichment().tools().for_answer(CRAFT)
    placed = builds(FROM_KUT_TO_RED).placed(
        PROCESS, ReusedSection(pieces=(), cited=CitedClaims()), enrichment
    )
    (ladder,) = placed.blocks
    assert isinstance(ladder, ProcessLadderBlock)
    assert ladder.id == "s1.ladder"
    assert [stage.stage_id for stage in ladder.stages] == [stage_id(KUT), stage_id(PA), stage_id(RED)]
    assert placed.built == (ladder,)


async def test_a_reused_section_whose_question_names_no_stage_is_left_as_stored() -> None:
    enrichment = await FakeEnrichment().tools().for_answer(CRAFT)
    question = "Why is Kutch Ajrakh printed near water?"
    placed = builds(question).placed(PROCESS, ReusedSection(pieces=(), cited=CitedClaims()), enrichment)
    assert (placed.blocks, placed.built) == ((), ())
