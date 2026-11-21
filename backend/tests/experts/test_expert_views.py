import json

import pytest

from app.composer.expert_differences import DifferenceAsk, difference_message, difference_schema
from app.composer.expert_takes import ProposedDifference, SeatAsk, seat_message, seat_schema
from app.models.enums import DISCIPLINES
from app.research.blocks_people import expert_pairing_problems
from app.research.composition import ComposeFocus
from app.research.expert_panel import EXPERT_PANEL, speaking_seats
from app.research.structured import schema_problems
from app.research.untrusted import untrusted_block
from app.services.block_builders import BLOCK_BUILDERS, BUILDER_WAIT_MAX_SECONDS, BlockBuilders
from app.services.expert_views import ExpertPanelBuilder, difference_refusal, panel_candidates

from ..answering.fakes import SpentModel
from .fixtures import (
    BHARMALJI,
    CLIENTS,
    DHAMADKA,
    FOUR_HUNDRED,
    GI,
    GUESS,
    KHAMIR,
    QUESTION,
    SEVENTH_CENTURY,
    asked_seat,
    build_ask,
    cited,
    differ,
    panel_model,
    said,
    take,
    tools,
)

MATERIALS_SEATED = (
    "CHEMIST",
    "ECONOMIST",
    "PHYSICIST",
    "MATERIALS_SCIENTIST",
    "TECHNOLOGIST",
    "GEOLOGIST",
    "BOTANIST",
    "CONSERVATOR",
    "HISTORIAN",
    "TOXICOLOGIST",
)
HISTORY_SEATED = ("HISTORIAN", "ECONOMIST", "ANTHROPOLOGIST", "DESIGN_HISTORIAN", "POLICY_EXPERT")


async def built(ask_seats: tuple[str, ...], model: object, **changes: object) -> list:
    found = await ExpertPanelBuilder(tools(model)).build(build_ask(ask_seats, **changes))
    return list(found.blocks)


@pytest.mark.parametrize(
    ("depth", "seats"),
    [
        ("BASIC", ("CHEMIST",)),
        ("DETAILED", ("CHEMIST", "PHYSICIST", "MATERIALS_SCIENTIST")),
        (
            "EXPERT",
            (
                "CHEMIST",
                "PHYSICIST",
                "MATERIALS_SCIENTIST",
                "TECHNOLOGIST",
                "GEOLOGIST",
                "BOTANIST",
                "CONSERVATOR",
            ),
        ),
    ],
)
def test_a_depth_seats_its_first_experts_and_a_section_hears_those_of_its_field(
    depth: str, seats: tuple[str, ...]
) -> None:
    assert speaking_seats("MATERIALS", MATERIALS_SEATED, depth=depth) == seats


@pytest.mark.parametrize(
    ("depth", "offered"),
    [
        ("BASIC", ["HISTORIAN"]),
        ("DETAILED", ["HISTORIAN", "ANTHROPOLOGIST", "DESIGN_HISTORIAN"]),
        ("EXPERT", ["HISTORIAN", "ANTHROPOLOGIST", "DESIGN_HISTORIAN", "POLICY_EXPERT"]),
    ],
)
async def test_the_panel_call_offers_only_the_section_s_seats(depth: str, offered: list[str]) -> None:
    model = panel_model([take("HISTORIAN", said(FOUR_HUNDRED)), take("ECONOMIST", said(CLIENTS))])
    views = await built(HISTORY_SEATED, model, depth=depth)
    assert [asked_seat(call["user"]) for call in model.seat_calls] == offered
    assert model.difference_calls == []
    assert [view.seat for view in views] == ["HISTORIAN"]


async def test_an_expert_sentence_without_a_quote_drops_that_expert_s_view() -> None:
    unquoted = {"text": SEVENTH_CENTURY.text, "quotes": []}
    model = panel_model(
        [
            take("HISTORIAN", said(FOUR_HUNDRED), unquoted),
            take("ANTHROPOLOGIST", said(CLIENTS)),
        ]
    )
    views = await built(("HISTORIAN", "ANTHROPOLOGIST"), model)
    assert [view.seat for view in views] == ["ANTHROPOLOGIST"]
    assert [sentence.text for sentence in views[0].take] == [CLIENTS.text]


@pytest.mark.parametrize(
    "bad",
    [
        said(GUESS),
        said(
            FOUR_HUNDRED,
            "The technique came to Kutch from Sindh some 500 years ago.",
            "came to Kutch from Sindh some 400 years ago at the behest of the King of Kutch",
        ),
        {"text": "Khatris came to Kutch.", "quotes": [{"source": "openalex:W1", "quote": FOUR_HUNDRED.text}]},
    ],
)
async def test_an_uncited_or_unsupported_expert_sentence_drops_the_view(bad: dict) -> None:
    model = panel_model([take("HISTORIAN", said(BHARMALJI), bad)])
    assert await built(("HISTORIAN",), model) == []


@pytest.mark.parametrize(
    "text",
    [
        "The technique came to Kutch from Sindh in March, at the behest of the King of Kutch.",
        "The technique came to Kachchh from Sindh at the behest of the King of Kutch.",
        "The technique came to Kutch from Sindh in the monsoon, at the behest of the King of Kutch.",
    ],
    ids=["a month", "a district", "a season"],
)
async def test_a_take_naming_a_time_or_place_no_source_states_drops_the_view(text: str) -> None:
    quote = "came to Kutch from Sindh some 400 years ago at the behest of the King of Kutch"
    model = panel_model(
        [take("HISTORIAN", said(FOUR_HUNDRED, text, quote)), take("ANTHROPOLOGIST", said(CLIENTS))]
    )
    views = await built(("HISTORIAN", "ANTHROPOLOGIST"), model)
    assert [view.seat for view in views] == ["ANTHROPOLOGIST"]


async def test_experts_differ_shows_both_stored_claims_with_their_own_citations() -> None:
    model = panel_model(
        [take("HISTORIAN", said(BHARMALJI)), take("ANTHROPOLOGIST", said(CLIENTS))],
        [differ("HISTORIAN", FOUR_HUNDRED, "ANTHROPOLOGIST", SEVENTH_CENTURY)],
    )
    historian, anthropologist = await built(("HISTORIAN", "ANTHROPOLOGIST"), model)
    (mine,) = historian.differs
    (theirs,) = anthropologist.differs
    assert (mine.seat, theirs.seat) == ("ANTHROPOLOGIST", "HISTORIAN")
    assert (mine.this_view.text, mine.other_view.text) == (FOUR_HUNDRED.text, SEVENTH_CENTURY.text)
    assert (theirs.this_view.text, theirs.other_view.text) == (SEVENTH_CENTURY.text, FOUR_HUNDRED.text)
    assert [c.source_id for c in mine.this_view.citations] == [str(GI.id)]
    assert [c.source_id for c in mine.other_view.citations] == [str(KHAMIR.id)]
    assert expert_pairing_problems([historian, anthropologist]) == []
    assert (historian.agrees_with, anthropologist.agrees_with) == ([], [])


async def test_a_difference_citing_one_source_on_both_sides_is_refused() -> None:
    proposal = ProposedDifference("HISTORIAN", str(FOUR_HUNDRED.id), "ANTHROPOLOGIST", str(DHAMADKA.id))
    assert (
        difference_refusal(proposal, {"HISTORIAN", "ANTHROPOLOGIST"}, cited())
        == f"both statements cite {GI.id}"
    )
    model = panel_model(
        [take("HISTORIAN", said(BHARMALJI)), take("ANTHROPOLOGIST", said(CLIENTS))],
        [differ("HISTORIAN", FOUR_HUNDRED, "ANTHROPOLOGIST", DHAMADKA)],
    )
    views = await built(("HISTORIAN", "ANTHROPOLOGIST"), model)
    assert [(view.seat, view.differs) for view in views] == [("HISTORIAN", []), ("ANTHROPOLOGIST", [])]


async def test_a_difference_about_two_subjects_is_refused() -> None:
    proposal = ProposedDifference("HISTORIAN", str(FOUR_HUNDRED.id), "ANTHROPOLOGIST", str(CLIENTS.id))
    refusal = difference_refusal(proposal, {"HISTORIAN", "ANTHROPOLOGIST"}, cited())
    assert refusal == "the statements concern different subjects"
    model = panel_model(
        [take("HISTORIAN", said(BHARMALJI)), take("ANTHROPOLOGIST", said(CLIENTS))],
        [differ("HISTORIAN", FOUR_HUNDRED, "ANTHROPOLOGIST", CLIENTS)],
    )
    assert all(view.differs == [] for view in await built(("HISTORIAN", "ANTHROPOLOGIST"), model))


@pytest.mark.parametrize(
    ("proposal", "refusal"),
    [
        (("HISTORIAN", FOUR_HUNDRED, "HISTORIAN", SEVENTH_CENTURY), "an expert does not differ with itself"),
        (("HISTORIAN", FOUR_HUNDRED, "ECONOMIST", SEVENTH_CENTURY), "both experts give a view"),
        (("HISTORIAN", FOUR_HUNDRED, "ANTHROPOLOGIST", GUESS), "both statements are stored claims"),
        (("HISTORIAN", FOUR_HUNDRED, "ANTHROPOLOGIST", FOUR_HUNDRED), "does not differ with itself"),
    ],
)
def test_a_difference_is_kept_only_between_two_views_on_two_stored_facts(
    proposal: tuple, refusal: str
) -> None:
    seat, mine, other_seat, theirs = proposal
    found = difference_refusal(
        ProposedDifference(seat, str(mine.id), other_seat, str(theirs.id)),
        {"HISTORIAN", "ANTHROPOLOGIST"},
        cited(),
    )
    assert found is not None and refusal in found


async def test_a_view_that_only_restates_its_section_is_not_seated() -> None:
    model = panel_model([take("HISTORIAN", said(SEVENTH_CENTURY)), take("ANTHROPOLOGIST", said(CLIENTS))])
    (anthropologist,) = await built(("HISTORIAN", "ANTHROPOLOGIST"), model)
    assert (anthropologist.seat, anthropologist.agrees_with) == ("ANTHROPOLOGIST", [])


async def test_a_view_that_restates_its_section_stays_seated_for_its_difference() -> None:
    model = panel_model(
        [take("HISTORIAN", said(SEVENTH_CENTURY)), take("ANTHROPOLOGIST", said(CLIENTS))],
        [differ("HISTORIAN", FOUR_HUNDRED, "ANTHROPOLOGIST", SEVENTH_CENTURY)],
    )
    historian, anthropologist = await built(("HISTORIAN", "ANTHROPOLOGIST"), model)
    assert [sentence.text for sentence in historian.take] == [SEVENTH_CENTURY.text]
    assert (historian.differs[0].seat, anthropologist.differs[0].seat) == ("ANTHROPOLOGIST", "HISTORIAN")
    assert (historian.differs[0].this_view.text, historian.differs[0].other_view.text) == (
        FOUR_HUNDRED.text,
        SEVENTH_CENTURY.text,
    )


async def test_a_view_adding_one_new_claim_is_seated_whole() -> None:
    model = panel_model([take("HISTORIAN", said(SEVENTH_CENTURY), said(FOUR_HUNDRED))])
    (historian,) = await built(("HISTORIAN",), model)
    assert [sentence.text for sentence in historian.take] == [SEVENTH_CENTURY.text, FOUR_HUNDRED.text]


async def test_no_panel_is_asked_when_the_section_already_shows_every_stored_fact() -> None:
    model = panel_model([take("HISTORIAN", said(FOUR_HUNDRED))])
    every = (FOUR_HUNDRED, SEVENTH_CENTURY, DHAMADKA, CLIENTS, BHARMALJI)
    assert await built(("HISTORIAN",), model, shown=every) == []
    assert model.calls == []


async def test_two_views_resting_on_one_claim_agree() -> None:
    model = panel_model([take("HISTORIAN", said(BHARMALJI)), take("DESIGN_HISTORIAN", said(BHARMALJI))])
    historian, design = await built(("HISTORIAN", "DESIGN_HISTORIAN"), model)
    assert (historian.agrees_with, design.agrees_with) == (["DESIGN_HISTORIAN"], ["HISTORIAN"])


async def test_the_artisan_seat_is_never_composed_by_the_model() -> None:
    artisan_only = panel_model([take("ARTISAN", said(SEVENTH_CENTURY))])
    assert await built(("ARTISAN",), artisan_only) == []
    assert artisan_only.calls == []
    model = panel_model([take("ARTISAN", said(SEVENTH_CENTURY)), take("HISTORIAN", said(FOUR_HUNDRED))])
    views = await built(("ARTISAN", "HISTORIAN"), model)
    assert [view.seat for view in views] == ["HISTORIAN"]
    (call,) = model.calls
    assert "ARTISAN" not in call["user"] and "ARTISAN" not in json.dumps(call["schema"])


def test_the_panel_hears_the_stored_facts_its_section_has_not_shown_first() -> None:
    ask = build_ask(("HISTORIAN",))
    candidates = panel_candidates(ask.cited, ask.blocks)
    assert [c.id for c in candidates] == [
        str(v.id) for v in (FOUR_HUNDRED, CLIENTS, BHARMALJI, SEVENTH_CENTURY, DHAMADKA)
    ]
    assert candidates[0].quotes == [
        "came to Kutch from Sindh some 400 years ago at the behest of the King of Kutch"
    ]


def test_the_panel_call_keeps_statements_and_the_question_inside_untrusted_blocks() -> None:
    ask = build_ask(("HISTORIAN", "ANTHROPOLOGIST"))
    focus = ComposeFocus(discipline="HISTORY", title="History")
    candidates = tuple(panel_candidates(ask.cited, ask.blocks))
    seat = SeatAsk(QUESTION, ask.request.craft, focus, EXPERT_PANEL["HISTORIAN"], candidates)
    briefs = (EXPERT_PANEL["HISTORIAN"], EXPERT_PANEL["ANTHROPOLOGIST"])
    compared = DifferenceAsk(QUESTION, ask.request.craft, focus, briefs, candidates)
    for message in (seat_message(seat), difference_message(compared)):
        assert untrusted_block("question", "learner question", QUESTION) in message
        assert f'ref="{FOUR_HUNDRED.id}"' in message
        assert f"Expert HISTORIAN: Historian. {EXPERT_PANEL['HISTORIAN'].brief}" in message
    assert "Expert ANTHROPOLOGIST" not in seat_message(seat)
    assert schema_problems(seat_schema()) == []
    assert schema_problems(difference_schema(compared)) == []


async def test_an_off_schema_reply_drops_only_that_seat_s_view() -> None:
    model = panel_model(
        [{"seat": "HISTORIAN", "take": [], "mood": "sure"}, take("ANTHROPOLOGIST", said(CLIENTS))]
    )
    views = await built(("HISTORIAN", "ANTHROPOLOGIST"), model)
    assert [view.seat for view in views] == ["ANTHROPOLOGIST"]
    assert len(model.seat_calls) == 2


async def test_a_refused_spend_adds_no_view_and_fails_nothing() -> None:
    (entry,) = [entry for entry in BLOCK_BUILDERS if entry.kind == "expert_view"]
    spent = SpentModel()
    added = await BlockBuilders([(entry, ExpertPanelBuilder(tools(spent)))]).added(build_ask(("HISTORIAN",)))
    assert (added.blocks, spent.calls) == ((), 1)


def test_the_panel_builder_listens_in_every_field_within_the_model_wait() -> None:
    (entry,) = [entry for entry in BLOCK_BUILDERS if entry.kind == "expert_view"]
    assert entry.disciplines == set(DISCIPLINES)
    assert 0 < entry.wait_seconds <= BUILDER_WAIT_MAX_SECONDS
