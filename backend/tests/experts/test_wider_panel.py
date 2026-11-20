import uuid
from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest

from app.models.enums import DISCIPLINES
from app.research import expert_panel
from app.research.depth import depth_policy
from app.research.expert_panel import EXPERT_PANEL, panel_seats, speaking_seats, voiced_seats
from app.research.retrieval import ChunkHit, ClaimHit, KnowledgeHits, KnowledgeQuery
from app.services.answer_events import cited_claims, joined_claims
from app.services.artisan_seat import Heard, HeardQuote, artisan_take, stored_voices
from app.services.block_builders import BLOCK_BUILDERS
from app.services.builder_interface import BuilderTools
from app.services.claim_ledger import ClaimLedger
from app.services.expert_views import EXPERT_VIEW_WAIT_SECONDS, ExpertPanelBuilder
from app.services.seat_search import (
    SEAT_CLAIMS_MAX,
    SeatEvidence,
    seat_findings,
    seat_query,
    stored_seat_search,
)

from ..answering.fakes import stored_view
from .fixtures import (
    BHARMALJI,
    CLIENTS,
    DHAMADKA,
    FOUR_HUNDRED,
    GUESS,
    MIGRATION,
    QUESTION,
    SEVENTH_CENTURY,
    asked_seat,
    build_ask,
    cited,
    claim,
    panel_model,
    prose,
    said,
    source,
    take,
    tools,
)

BOOK = source(7, "BOOK", "Ajrakh: Patterns and Trade", "https://example.org/ajrakh-book")
FIELD = source(8, "FIELD_TESTIMONY", "Recorded at a Dhamadka workshop", "https://kalavigyan.in/field/1")
TRADE = stored_view(
    claim(10),
    "Ajrakh cloth was carried by camel caravans to markets across the desert.",
    "PROVISIONAL",
    (110, BOOK, "Ajrakh cloth was carried by camel caravans to markets across the desert", "p. 12"),
    concept_id=MIGRATION,
)
WASHED = stored_view(
    claim(11),
    "The printers wash the cloth in the river before the first print.",
    "PROVISIONAL",
    (111, FIELD, "We wash the cloth in the river before the first print", "00:01:10"),
)
EVERY_FACT = (FOUR_HUNDRED, SEVENTH_CENTURY, DHAMADKA, CLIENTS, BHARMALJI)
SPOKEN = HeardQuote(
    WASHED.id, "We wash the cloth in the river before the first print", "Abdul Khatri", "Ajrakh", "Kachchh"
)


def found_by(seat: str, *views: object) -> object:
    async def search(ask: object, briefs: object, shown: object) -> SeatEvidence:
        return SeatEvidence({seat: tuple(views)}, cited_claims(list(views), {BOOK.id: BOOK}))

    return search


def heard(*quotes: HeardQuote) -> object:
    async def voices(ask: object) -> Heard:
        return Heard(tuple(quotes), cited_claims([WASHED], {FIELD.id: FIELD}))

    return voices


def hit(view: object, rank: int) -> ClaimHit:
    return ClaimHit(
        claim_id=view.id,
        text=view.text,
        level=view.level,
        subject_type="CONCEPT",
        subject_id=MIGRATION,
        score=1 / rank,
    )


@dataclass
class FakeRetriever:
    hits: KnowledgeHits
    queries: list[KnowledgeQuery] = field(default_factory=list)

    async def search(self, query: KnowledgeQuery) -> KnowledgeHits:
        self.queries.append(query)
        return self.hits


def test_a_seat_keeps_unshown_facts_from_its_own_source_kinds() -> None:
    claims = cited((*EVERY_FACT, GUESS, TRADE))
    claims = joined_claims(claims, cited_claims([TRADE], {BOOK.id: BOOK}))
    hits = KnowledgeHits(
        craft_slug="ajrakh",
        claims=tuple(
            hit(v, n) for n, v in enumerate((GUESS, SEVENTH_CENTURY, TRADE, FOUR_HUNDRED, CLIENTS), 1)
        ),
    )
    briefs = (EXPERT_PANEL["HISTORIAN"], EXPERT_PANEL["ANTHROPOLOGIST"])
    found = seat_findings(briefs, (hits, hits), claims, {str(FOUR_HUNDRED.id)})
    assert found["HISTORIAN"] == (TRADE,)
    assert found["ANTHROPOLOGIST"] == (SEVENTH_CENTURY, TRADE, CLIENTS)
    assert SEAT_CLAIMS_MAX >= 3


def test_a_seat_searches_its_question_craft_and_fields() -> None:
    ask = build_ask(("CHEMIST",), discipline="CHEMISTRY")
    query = seat_query(ask, EXPERT_PANEL["CHEMIST"])
    assert (query.craft_slug, query.mode) == (ask.request.craft.slug, "HYBRID")
    assert query.text.startswith(QUESTION) and "Ajrakh" in query.text and "Chemist" in query.text
    assert "chemistry" in query.text and "health, toxicology and safe handling" in query.text
    assert query.fields == ("CHEMISTRY", "PROCESS", "MATERIALS", "HEALTH")


async def test_without_a_retriever_a_seat_searches_nothing() -> None:
    assert (
        await stored_seat_search(tools(None))(build_ask(("HISTORIAN",)), [EXPERT_PANEL["HISTORIAN"]], set())
        == SeatEvidence()
    )


async def test_each_seat_gets_its_own_call_with_its_own_evidence_first() -> None:
    model = panel_model(
        [
            take("HISTORIAN", said(TRADE), said(FOUR_HUNDRED), said(BHARMALJI), said(CLIENTS)),
            take("ANTHROPOLOGIST", said(CLIENTS)),
        ]
    )
    builder = ExpertPanelBuilder(tools(model), search=found_by("HISTORIAN", TRADE))
    found = await builder.build(build_ask(("HISTORIAN", "ANTHROPOLOGIST")))
    historian_call, anthropologist_call = model.seat_calls
    assert [asked_seat(c["user"]) for c in model.seat_calls] == ["HISTORIAN", "ANTHROPOLOGIST"]
    assert historian_call["user"].index(f'ref="{TRADE.id}"') < historian_call["user"].index(
        f'ref="{FOUR_HUNDRED.id}"'
    )
    assert f'ref="{TRADE.id}"' not in anthropologist_call["user"]
    historian, anthropologist = found.blocks
    assert [s.text for s in historian.take] == [TRADE.text, FOUR_HUNDRED.text, BHARMALJI.text]
    assert anthropologist.seat == "ANTHROPOLOGIST"
    assert str(BOOK.id) in found.sources


async def test_a_curated_section_still_hears_a_seat_with_evidence_of_its_own() -> None:
    model = panel_model(
        [take("HISTORIAN", said(TRADE), said(SEVENTH_CENTURY)), take("ANTHROPOLOGIST", said(CLIENTS))]
    )
    builder = ExpertPanelBuilder(tools(model), search=found_by("HISTORIAN", TRADE))
    found = await builder.build(build_ask(("HISTORIAN", "ANTHROPOLOGIST"), shown=EVERY_FACT))
    assert [asked_seat(c["user"]) for c in model.calls] == ["HISTORIAN"]
    (historian,) = found.blocks
    assert [s.text for s in historian.take] == [TRADE.text, SEVENTH_CENTURY.text]


async def test_the_difference_pass_runs_once_over_the_seats_that_spoke() -> None:
    model = panel_model(
        [take("HISTORIAN", said(TRADE)), take("ANTHROPOLOGIST", said(CLIENTS))],
        [
            {
                "seat": "HISTORIAN",
                "statement": str(TRADE.id),
                "otherSeat": "ANTHROPOLOGIST",
                "otherStatement": str(SEVENTH_CENTURY.id),
            }
        ],
    )
    builder = ExpertPanelBuilder(tools(model), search=found_by("HISTORIAN", TRADE))
    historian, anthropologist = (await builder.build(build_ask(("HISTORIAN", "ANTHROPOLOGIST")))).blocks
    (compared,) = model.difference_calls
    assert "Expert HISTORIAN" in compared["user"] and "Expert ANTHROPOLOGIST" in compared["user"]
    assert (historian.differs[0].seat, anthropologist.differs[0].seat) == ("ANTHROPOLOGIST", "HISTORIAN")


async def test_the_ledger_still_drops_a_take_an_earlier_section_showed() -> None:
    model = panel_model([take("HISTORIAN", said(FOUR_HUNDRED)), take("ANTHROPOLOGIST", said(CLIENTS))])
    ask = build_ask(("HISTORIAN", "ANTHROPOLOGIST"))
    found = await ExpertPanelBuilder(tools(model)).build(ask)
    assert [view.seat for view in found.blocks] == ["HISTORIAN", "ANTHROPOLOGIST"]
    ledger = ClaimLedger()
    sources = cited().sources
    ledger.admit("s1", [prose("s1", (FOUR_HUNDRED,), cited())], sources)
    admitted = ledger.admit("s5", [*ask.blocks, *found.blocks], sources)
    assert [block.seat for block in admitted if block.kind == "expert_view"] == ["ANTHROPOLOGIST"]


def test_expert_depth_seats_up_to_twelve_and_every_seat_of_the_field(monkeypatch: pytest.MonkeyPatch) -> None:
    assert [depth_policy(depth).max_experts for depth in ("BASIC", "DETAILED", "EXPERT")] == [2, 4, 12]
    materials = (
        "CHEMIST",
        "PHYSICIST",
        "MATERIALS_SCIENTIST",
        "TECHNOLOGIST",
        "GEOLOGIST",
        "BOTANIST",
        "CONSERVATOR",
    )
    assert speaking_seats("MATERIALS", (), depth="EXPERT") == materials
    assert speaking_seats("MATERIALS", ("CONSERVATOR",), depth="EXPERT")[0] == "CONSERVATOR"
    assert speaking_seats("MATERIALS", (), depth="DETAILED") == ()
    assert all(len(panel_seats(d, tuple(EXPERT_PANEL), depth="EXPERT")) <= 12 for d in DISCIPLINES)
    monkeypatch.setattr(expert_panel, "depth_policy", lambda depth: SimpleNamespace(max_experts=3))
    assert speaking_seats("MATERIALS", (), depth="EXPERT") == materials[:3]


async def test_the_artisan_seat_quotes_one_artisan_from_a_field_transcript() -> None:
    model = panel_model([take("HISTORIAN", said(FOUR_HUNDRED))])
    builder = ExpertPanelBuilder(tools(model), voices=heard(SPOKEN))
    found = await builder.build(build_ask(("HISTORIAN",), depth="EXPERT"))
    assert voiced_seats("HISTORY", ("HISTORIAN",), depth="EXPERT") == ("ARTISAN",)
    *_, artisan = found.blocks
    (sentence,) = artisan.take
    assert artisan.seat == "ARTISAN"
    assert sentence.text == (
        "In one artisan's account, Abdul Khatri, who practises Ajrakh in Kachchh district, said: "
        "“We wash the cloth in the river before the first print”"
    )
    assert [c.source_id for c in sentence.citations] == [str(FIELD.id)]
    assert str(FIELD.id) in found.sources
    assert all("ARTISAN" not in call["user"] for call in model.calls)


async def test_the_artisan_seat_stays_hidden_without_transcripts() -> None:
    model = panel_model([take("HISTORIAN", said(FOUR_HUNDRED))])
    silent = await ExpertPanelBuilder(tools(model), voices=heard()).build(
        build_ask(("HISTORIAN",), depth="EXPERT")
    )
    assert "ARTISAN" not in [view.seat for view in silent.blocks]
    assert not any("artisan" in s.text.lower() for view in silent.blocks for s in view.take)
    shown = Heard((SPOKEN,), cited_claims([WASHED], {FIELD.id: FIELD}))
    assert artisan_take(shown, {str(WASHED.id)}) == ()


async def test_the_artisan_seat_reads_no_transcript_with_field_voices_off() -> None:
    chunk = ChunkHit(
        chunk_id=uuid.uuid4(),
        source_id=FIELD.id,
        ordinal=0,
        text="We wash the cloth",
        score=1.0,
        source_kind="BOOK",
    )
    retriever = FakeRetriever(KnowledgeHits(craft_slug="ajrakh", chunks=(chunk,)))
    armed = BuilderTools(
        sessions=object(), live=None, plan_model=None, compose_model=None, retriever=retriever
    )
    ask = build_ask(("HISTORIAN",), depth="EXPERT")
    assert await stored_voices(armed, enabled=lambda: False)(ask) == Heard()
    assert retriever.queries == []
    assert await stored_voices(armed, enabled=lambda: True)(ask) == Heard()
    (query,) = retriever.queries
    assert query.chunk_acls == ("PUBLIC", "SIGNED_IN")


def test_the_panel_builder_waits_long_enough_for_a_call_per_seat() -> None:
    (entry,) = [entry for entry in BLOCK_BUILDERS if entry.kind == "expert_view"]
    assert entry.wait_seconds == EXPERT_VIEW_WAIT_SECONDS == 90.0
