import json
from collections.abc import Mapping
from typing import Any

import pytest

from app.core.errors import ExternalFailure
from app.models.enums import DISCIPLINES
from app.planner.understanding import ModelUnderstander
from app.planner.understanding_prompt import UNDERSTAND_SYSTEM_PROMPT, understand_schema
from app.providers.router import RouterError
from app.research.blocks_people import EXPERT_SEATS
from app.research.crafts import CraftCandidate, CraftQuery, CraftRef, CraftResolution, MatchReason
from app.research.planning import PlanRequest
from app.research.understanding import UnderstandAsk, UnknownCraft

from ..research.fixtures import AJRAKH, BAGRU
from .fakes import FakeModel

QUESTION = "Why does the red of the printed cloth last?"
BARMER = CraftRef(slug="Barmer-Ajrakh-Print", name="Barmer Ajrakh Print", path="/crafts/Barmer-Ajrakh-Print")
READ = {"craft": "", "craftNames": [], "disciplines": ["CHEMISTRY", "HISTORY"], "seats": ["CHEMIST"]}
SCHEMA_KEYWORDS = {"type", "enum", "items", "properties", "required", "additionalProperties"}


def candidate(craft: CraftRef, score: float) -> CraftCandidate:
    return CraftCandidate(
        craft=craft, score=score, reasons=[MatchReason(kind="FUZZY", matched=craft.name, score=score)]
    )


def resolution(status: str, *ranked: tuple[CraftRef, float]) -> CraftResolution:
    craft = ranked[0][0] if status == "RESOLVED" else None
    candidates = [candidate(craft_ref, score) for craft_ref, score in ranked]
    return CraftResolution(status=status, craft=craft, candidates=candidates, normalised="x", script="Latn")


NONE = resolution("NONE")
AMBIGUOUS = resolution("AMBIGUOUS", (AJRAKH, 0.7), (BAGRU, 0.6))
RESOLVED = resolution("RESOLVED", (AJRAKH, 1.0), (BARMER, 0.5))


class Resolver:
    def __init__(self, first: CraftResolution, named: Mapping[str, CraftResolution] | None = None) -> None:
        self.first = first
        self.named = dict(named or {})
        self.queries: list[CraftQuery] = []

    async def __call__(self, query: CraftQuery) -> CraftResolution:
        self.queries.append(query)
        if len(self.queries) == 1:
            return self.first
        return self.named.get(query.text, NONE)


def ask(**changes: Any) -> UnderstandAsk:
    return UnderstandAsk.model_validate({"question": QUESTION, "depth": "DETAILED", **changes})


async def understood(
    first: CraftResolution,
    reply: Mapping[str, Any] | None = READ,
    *,
    named: Mapping[str, CraftResolution] | None = None,
    degraded: bool = False,
    **changes: Any,
) -> Any:
    model = FakeModel([json.dumps(reply)], degraded=degraded)
    understander = ModelUnderstander(model=model, resolve=Resolver(first, named))
    return await understander.understand(ask(**changes)), model


async def test_an_unknown_craft_does_not_block_and_answers_for_any_craft() -> None:
    found, _ = await understood(NONE)
    assert (found.craft, found.candidates, found.basis) == (None, [], "MODEL")
    assert found.understood().model_dump(by_alias=True) == {
        "crafts": [],
        "candidates": [],
        "depth": "DETAILED",
        "language": "en",
    }


async def test_an_ambiguous_question_the_model_finds_about_no_single_craft_offers_every_candidate() -> None:
    found, _ = await understood(AMBIGUOUS)
    assert (found.craft, found.candidates, found.basis) == (None, [AJRAKH, BAGRU], "MODEL")
    assert found.understood().crafts == []


async def test_without_a_reply_an_ambiguous_craft_proceeds_with_the_best_and_lists_the_others() -> None:
    model = FakeModel(["not json"])
    found = await ModelUnderstander(model=model, resolve=Resolver(AMBIGUOUS)).understand(ask())
    assert (found.craft, found.candidates, found.basis) == (AJRAKH, [BAGRU], "RESOLVER")
    assert found.understood().crafts == [AJRAKH]


async def test_a_craft_the_model_names_beside_the_candidates_is_looked_up_and_a_listed_one_is_not() -> None:
    named = {BARMER.name: resolution("RESOLVED", (BARMER, 1.0))}
    reply = {**READ, "craftNames": [AJRAKH.name, BARMER.name]}
    resolver = Resolver(AMBIGUOUS, named)
    found = await ModelUnderstander(model=FakeModel([json.dumps(reply)]), resolve=resolver).understand(ask())
    assert (found.craft, found.candidates) == (BARMER, [AJRAKH, BAGRU])
    assert [query.text for query in resolver.queries] == [QUESTION, BARMER.name]


async def test_the_model_chooses_among_ambiguous_candidates() -> None:
    found, model = await understood(AMBIGUOUS, {**READ, "craft": BAGRU.slug})
    assert (found.craft, found.candidates) == (BAGRU, [AJRAKH])
    assert model.calls[0]["schema"]["properties"]["craft"]["enum"] == [AJRAKH.slug, BAGRU.slug, ""]


async def test_a_clear_winner_stands_whatever_the_model_says() -> None:
    found, _ = await understood(RESOLVED, {**READ, "craft": BARMER.slug})
    assert (found.craft, found.candidates) == (AJRAKH, [BARMER])


async def test_a_craft_the_model_names_is_chosen_only_when_the_resolver_confirms_it() -> None:
    named = {"Kutch Ajrakh": RESOLVED, "Bagru block print": AMBIGUOUS}
    reply = {**READ, "craftNames": ["Bagru block print", "Kutch Ajrakh"]}
    found, _ = await understood(NONE, reply, named=named)
    assert found.craft == AJRAKH
    assert found.candidates == [BAGRU, BARMER]


async def test_names_the_resolver_cannot_place_leave_any_craft_with_the_offers() -> None:
    found, _ = await understood(
        NONE, {**READ, "craftNames": ["Bagru block print"]}, named={"Bagru block print": AMBIGUOUS}
    )
    assert (found.craft, found.candidates) == (None, [AJRAKH, BAGRU])


async def test_any_craft_on_request_keeps_the_detected_crafts_as_offers() -> None:
    found, _ = await understood(RESOLVED, any_craft=True)
    assert (found.craft, found.candidates) == (None, [AJRAKH, BARMER])


THREE = resolution("AMBIGUOUS", (AJRAKH, 0.7), (BAGRU, 0.6), (BARMER, 0.5))


async def test_a_comparison_leads_with_the_first_compared_craft_and_sets_the_others_beside_it() -> None:
    found, _ = await understood(THREE, {**READ, "compare": [BAGRU.slug, BARMER.slug]})
    assert (found.craft, found.compared, found.candidates) == (BAGRU, [BARMER], [AJRAKH])
    assert found.understood().crafts == [BAGRU, BARMER]
    assert found.understood().candidates == [AJRAKH]


async def test_the_first_compared_craft_leads_even_past_a_clear_winner() -> None:
    found, _ = await understood(RESOLVED, {**READ, "compare": [BARMER.slug, AJRAKH.slug]})
    assert (found.craft, found.compared, found.candidates) == (BARMER, [AJRAKH], [])


@pytest.mark.parametrize(
    ("compare", "changes"),
    [
        ([AJRAKH.slug], {}),
        ([AJRAKH.slug, "Not-Listed"], {}),
        ([AJRAKH.slug, BAGRU.slug], {"any_craft": True}),
    ],
)
async def test_one_listed_craft_or_any_craft_is_no_comparison(compare: list[str], changes: Any) -> None:
    found, _ = await understood(THREE, {**READ, "compare": compare}, **changes)
    assert found.compared == []
    assert len(found.understood().crafts) <= 1


async def test_a_picked_craft_is_compared_only_with_crafts_the_resolver_listed_beside_it() -> None:
    picked = resolution("RESOLVED", (BAGRU, 1.0), (AJRAKH, 0.4))
    found, _ = await understood(picked, {**READ, "compare": [AJRAKH.slug, BAGRU.slug]}, craft_slug=BAGRU.slug)
    assert (found.craft, found.compared) == (BAGRU, [AJRAKH])
    alone = resolution("RESOLVED", (BAGRU, 1.0))
    found, _ = await understood(alone, {**READ, "compare": [AJRAKH.slug, BAGRU.slug]}, craft_slug=BAGRU.slug)
    assert (found.craft, found.compared) == (BAGRU, [])


async def test_the_compared_crafts_reach_the_builders_through_the_plan_request() -> None:
    found, _ = await understood(THREE, {**READ, "compare": [BAGRU.slug, AJRAKH.slug]})
    request = PlanRequest(question=QUESTION, mode="HYBRID", craft=found.craft, compared=tuple(found.compared))
    again = PlanRequest.model_validate(request.model_dump() | {"focus": "MATERIALS"})
    assert (again.craft, again.compared) == (BAGRU, (AJRAKH,))
    assert "compared" not in PlanRequest(question=QUESTION, mode="HYBRID", craft=BAGRU).model_dump()


async def test_a_chosen_craft_is_kept_and_an_unknown_one_is_refused() -> None:
    chosen = resolution("RESOLVED", (BAGRU, 1.0))
    found, _ = await understood(chosen, craft_slug=BAGRU.slug)
    assert (found.craft, found.candidates) == (BAGRU, [])
    with pytest.raises(UnknownCraft):
        await understood(NONE, craft_slug="No-Such-Craft")


async def test_the_fields_and_expert_seats_are_kept_for_later() -> None:
    reply = {
        **READ,
        "disciplines": ["GEOGRAPHY", "CHEMISTRY", "GEOGRAPHY"],
        "seats": ["HYDROLOGIST", "CHEMIST", "HYDROLOGIST", "GEOLOGIST"],
    }
    found, _ = await understood(RESOLVED, reply, depth="BASIC")
    assert found.disciplines == ["GEOGRAPHY", "CHEMISTRY"]
    assert found.seats == ["HYDROLOGIST", "CHEMIST"]


@pytest.mark.parametrize(
    ("role", "degraded", "depth"),
    [
        ("ADMIN", True, "DETAILED"),
        ("STUDENT", True, "DETAILED"),
        ("MASTER_ADMIN", True, "EXPERT"),
        ("ADMIN", False, "EXPERT"),
    ],
)
async def test_past_the_degrade_mark_expert_becomes_detailed_except_for_master_admins(
    role: str, degraded: bool, depth: str
) -> None:
    found, _ = await understood(RESOLVED, degraded=degraded, depth="EXPERT", role=role)
    assert found.depth == depth


BOTH = [AJRAKH, BAGRU]
TWO_FIELDS = ["CHEMISTRY", "HISTORY"]


@pytest.mark.parametrize(
    ("reply", "craft", "candidates", "fields", "seats"),
    [
        ({**READ, "craft": "Some-Other-Craft"}, AJRAKH, [BAGRU], TWO_FIELDS, ["CHEMIST", "HISTORIAN"]),
        ({**READ, "disciplines": []}, None, BOTH, ["CHEMISTRY"], ["CHEMIST"]),
        (
            {**READ, "disciplines": ["ASTROLOGY", "HISTORY"]},
            None,
            BOTH,
            ["HISTORY"],
            ["HISTORIAN", "CHEMIST"],
        ),
        ({**READ, "seats": ["ORACLE"]}, None, BOTH, TWO_FIELDS, ["CHEMIST", "HISTORIAN"]),
        ({"craft": ""}, None, BOTH, ["CHEMISTRY"], ["CHEMIST"]),
    ],
)
async def test_a_reply_keeps_its_usable_fields_and_leaves_out_only_the_unusable_ones(
    reply: Mapping[str, Any],
    craft: CraftRef | None,
    candidates: list[CraftRef],
    fields: list[str],
    seats: list[str],
) -> None:
    found, _ = await understood(AMBIGUOUS, reply)
    assert (found.craft, found.candidates, found.basis) == (craft, candidates, "MODEL")
    assert (found.disciplines, found.seats, found.refusal) == (fields, seats, None)


@pytest.mark.parametrize("reply", [{}, {"craftNames": [""], "disciplines": ["ASTROLOGY"], "notes": "x"}])
async def test_a_reply_that_holds_nothing_usable_falls_back_to_the_resolver(reply: Mapping[str, Any]) -> None:
    found, _ = await understood(AMBIGUOUS, reply)
    assert (found.craft, found.candidates, found.basis) == (AJRAKH, [BAGRU], "RESOLVER")
    assert (found.disciplines, found.seats, found.refusal) == (["CHEMISTRY"], ["CHEMIST"], None)


class Failing:
    def __init__(self, error: Exception) -> None:
        self.error = error

    async def __call__(self, **_: Any) -> Any:
        raise self.error


async def test_a_failed_model_call_still_understands_the_craft() -> None:
    failure = ExternalFailure("route timed out", kind="unavailable", service="model")
    understander = ModelUnderstander(model=Failing(failure), resolve=Resolver(RESOLVED))
    found = await understander.understand(ask())
    assert (found.craft, found.basis, found.refusal) == (AJRAKH, "RESOLVER", None)


class FailingResolver:
    def __init__(self, error: Exception) -> None:
        self.error = error
        self.queries: list[CraftQuery] = []

    async def __call__(self, query: CraftQuery) -> CraftResolution:
        self.queries.append(query)
        raise self.error


EMBEDDINGS_DOWN = ExternalFailure("embedding route timed out", kind="unavailable", service="embeddings")


@pytest.mark.parametrize("any_craft", [False, True])
async def test_a_failed_craft_lookup_never_blocks_the_question(any_craft: bool) -> None:
    resolver = FailingResolver(EMBEDDINGS_DOWN)
    model = FakeModel([json.dumps({**READ, "craftNames": ["Kutch Ajrakh"]})])
    understander = ModelUnderstander(model=model, resolve=resolver)
    found = await understander.understand(ask(any_craft=any_craft))
    assert (found.craft, found.candidates, found.basis) == (None, [], "MODEL")
    assert (found.disciplines, found.seats) == (["CHEMISTRY", "HISTORY"], ["CHEMIST", "HISTORIAN"])
    assert model.calls[0]["schema"]["properties"]["craft"]["enum"] == [""]
    assert [query.text for query in resolver.queries] == [QUESTION, *([] if any_craft else ["Kutch Ajrakh"])]


async def test_a_failed_lookup_of_a_chosen_craft_or_a_spend_refusal_still_stops() -> None:
    with pytest.raises(ExternalFailure):
        await ModelUnderstander(model=FakeModel([]), resolve=FailingResolver(EMBEDDINGS_DOWN)).understand(
            ask(craft_slug=BAGRU.slug)
        )
    refusal = RouterError("ceiling", "The monthly AI budget has been reached.", reason="MONTHLY_CEILING")
    with pytest.raises(RouterError):
        await ModelUnderstander(model=FakeModel([]), resolve=FailingResolver(refusal)).understand(ask())


async def test_a_spend_refusal_is_kept_in_its_own_words() -> None:
    refusal = RouterError("ceiling", "The monthly AI budget has been reached.", reason="MONTHLY_CEILING")
    understander = ModelUnderstander(model=Failing(refusal), resolve=Resolver(RESOLVED))
    found = await understander.understand(ask())
    assert (found.craft, found.basis, found.refusal) == (
        AJRAKH,
        "RESOLVER",
        "The monthly AI budget has been reached.",
    )


async def test_the_question_and_crafts_reach_the_model_only_as_untrusted_data() -> None:
    _, model = await understood(AMBIGUOUS, depth="EXPERT")
    (call,) = model.calls
    assert call["system"] == UNDERSTAND_SYSTEM_PROMPT
    lines = call["user"].split("\n")
    assert lines[:4] == ["Answer depth: Expert", "Experts: 6 to 12", "Sections: 1 to 16", "Listed crafts: 2"]
    assert (
        f'<untrusted_source ref="question" label="learner question">\n{QUESTION}\n</untrusted_source>'
        in call["user"]
    )
    assert call["user"].count('<untrusted_source ref="craft"') == 2


def keywords(schema: Any) -> set[str]:
    if isinstance(schema, dict):
        found = set(schema) - {"properties"}
        nested = list(schema.get("properties", {}).values()) + [v for k, v in schema.items() if k == "items"]
        return found.union(*(keywords(child) for child in nested))
    return set()


def test_the_schema_uses_only_widely_supported_keywords_and_the_registered_vocabulary() -> None:
    schema = understand_schema([AJRAKH])
    assert keywords(schema) <= SCHEMA_KEYWORDS
    assert schema["required"] == ["craft", "craftNames", "compare", "disciplines", "seats", "englishQuestion"]
    assert schema["properties"]["englishQuestion"] == {"type": "string"}
    assert schema["properties"]["compare"]["items"]["enum"] == [AJRAKH.slug, ""]
    assert schema["additionalProperties"] is False
    assert schema["properties"]["disciplines"]["items"]["enum"] == list(DISCIPLINES)
    assert schema["properties"]["seats"]["items"]["enum"] == list(EXPERT_SEATS)
    assert understand_schema([])["properties"]["craft"]["enum"] == [""]
