from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from app.curation.checks import content_problems, default_context, dossier_problems
from app.curation.coverage import coverage_problems, full_shortfalls, thin_shortfalls
from app.curation.dossier import Dossier

from .builders import changed_dossier, check_for, failing_dossier, passing_dossier, passing_plain


def found(problems: list[Any]) -> list[tuple[str, str]]:
    return [(problem.where, problem.message) for problem in problems]


def test_the_passing_dossier_has_no_problem() -> None:
    dossier = passing_dossier()
    assert dossier_problems(dossier, default_context(), check_for(dossier)) == []


def test_the_failing_dossier_reports_each_planted_fault_once() -> None:
    expected = [
        ("C002", "2002 in the text appears in none of its quotes"),
        ("C003", "the text is a relationship sentence"),
        ("C004.quotes.0", "the quote has 10 characters; a quote has 25 to 300"),
        ("C008", "near-identical to C001"),
        ("C009", "is a hypothesis, which shows only under an open question"),
        ("S03", "no claim quotes it"),
        ("overview.lede.1", "only 12% of its content words are in its claims"),
        ("sources.1.title", "carries personal data (phone-like number)"),
        ("L01", "district 'Kutch' is not in Gujarat in the LGD register"),
    ]
    problems = found(content_problems(failing_dossier(), default_context()))
    assert len(problems) == len(expected)
    for (where, message), (want_where, want_start) in zip(problems, expected, strict=True):
        assert where == want_where
        assert message.startswith(want_start)


@pytest.mark.parametrize(
    "change",
    [
        lambda plain: plain["sources"][0].update(subKind="THESIS"),
        lambda plain: plain["claims"][0].update(subject={"type": "STAGE", "ref": "M01"}),
        lambda plain: plain["claims"][0].update(subject={"type": "CRAFT", "ref": "P01"}),
        lambda plain: plain["sources"][0].update(archivedUrl="https://example.org/copy"),
        lambda plain: plain["sources"][0].update(kind="FIELD_TESTIMONY"),
        lambda plain: plain["stages"][0].update(order=1),
        lambda plain: plain["materials"][0].update(role="TOOL"),
        lambda plain: plain["places"][0].update(role="WORKSHOP"),
        lambda plain: plain["claims"][0].update(discipline="ART"),
        lambda plain: plain["sources"][0].update(url="http://example.org/test/block-printing"),
        lambda plain: plain.update(curator="someone"),
        lambda plain: plain["overview"].update(lede=plain["overview"]["lede"][:1]),
        lambda plain: plain["communities"][0].update(honours=["Award"]),
    ],
)
def test_the_schema_refuses_shapes_off_the_contract(change: Any) -> None:
    plain = passing_plain()
    change(plain)
    with pytest.raises(ValidationError):
        Dossier.model_validate(plain)


def test_an_unresolved_reference_stops_the_content_rules() -> None:
    def break_references(plain: dict[str, Any]) -> None:
        plain["places"][0]["claimIds"] = ["C099"]
        plain["claims"][1]["quotes"][0]["sourceId"] = "S09"
        plain["stages"].append(dict(plain["stages"][0]))

    problems = found(content_problems(changed_dossier(break_references), default_context()))
    assert problems == [
        ("stages", "P01 is used more than once"),
        ("C002", "S09 names no source in the dossier"),
        ("L01", "C099 names no claim in the dossier"),
    ]


def test_an_unknown_craft_slug_is_reported() -> None:
    dossier = changed_dossier(lambda plain: plain.update(craftSlug="Not-A-Craft"))
    assert ("craftSlug", "Not-A-Craft is not on the master list or the portal craft register") in found(
        content_problems(dossier, default_context())
    )


def test_a_craft_the_portals_added_is_curated_like_a_master_craft() -> None:
    portal = changed_dossier(lambda plain: plain.update(craftSlug="Krishnanagar-Terracotta"))
    assert not [
        where for where, _ in found(content_problems(portal, default_context())) if where == "craftSlug"
    ]
    merged = changed_dossier(lambda plain: plain.update(craftSlug="Cane-And-Bamboo"))
    assert found(content_problems(merged, default_context()))[0] == (
        "craftSlug",
        "Cane-And-Bamboo is merged into Cane-Bamboo-Craft; curate Cane-Bamboo-Craft",
    )


def test_a_d_source_alone_supports_only_a_dated_price() -> None:
    def weaken(plain: dict[str, Any]) -> None:
        plain["sources"][1]["reliability"] = "D"

    problems = found(content_problems(changed_dossier(weaken), default_context()))
    assert [where for where, message in problems if "D sources" in message] == ["C006", "C007"]

    def price(plain: dict[str, Any]) -> None:
        weaken(plain)
        plain["claims"][5]["text"] = (
            "About 40 families of Khatri printers sell a stole for Rs 40 to urban buyers."
        )

    priced = found(content_problems(changed_dossier(price), default_context()))
    assert [where for where, message in priced if "D sources" in message] == ["C007"]


def test_a_claim_keeps_the_hedge_of_its_only_quote() -> None:
    def hedge_the_quote(plain: dict[str, Any]) -> None:
        plain["claims"][1]["quotes"][0]["quote"] = (
            "It is believed that the printers of Ajrakhpur in Kachchh moved there from Dhamadka after the "
            "earthquake of 2001."
        )

    problems = found(content_problems(changed_dossier(hedge_the_quote), default_context()))
    assert [(where, message) for where, message in problems if "hedge" in message] == [
        (
            "C002",
            "every quote hedges (believed) and the text does not; keep the hedge (probably, believed, about, ...) "
            "or cite words that state it plainly",
        )
    ]

    def hedge_the_claim(plain: dict[str, Any]) -> None:
        hedge_the_quote(plain)
        plain["claims"][1]["text"] = (
            "The printers of Ajrakhpur in Kachchh are believed to have moved there from Dhamadka after the "
            "earthquake of 2001."
        )

    hedged = found(content_problems(changed_dossier(hedge_the_claim), default_context()))
    assert not [where for where, message in hedged if "hedge" in message]


def test_hypotheses_show_only_under_open_questions() -> None:
    def hypothesise(plain: dict[str, Any]) -> None:
        plain["claims"][1]["hypothesis"] = True
        plain["openQuestions"] = [
            {"id": "O01", "question": "When did the printers first reach Ajrakhpur?", "claimIds": ["C002"]}
        ]

    problems = found(content_problems(changed_dossier(hypothesise), default_context()))
    assert ("L01", "cites hypothesis C002 as a fact") in problems
    assert ("overview.lede.0", "cites hypothesis C002 as a fact") in problems
    assert not [where for where, _ in problems if where in ("O01", "C002")]


def test_place_names_follow_the_lgd_register() -> None:
    def misname(plain: dict[str, Any]) -> None:
        plain["places"][0]["state"] = "Gujrat"
        plain["places"].append(
            {
                "id": "L02",
                "name": "Dhamadka",
                "kind": "VILLAGE",
                "state": "Gujarat",
                "country": "India",
                "role": "HISTORIC_CENTRE",
                "claimIds": ["C002"],
            }
        )
        plain["places"].append(
            {
                "id": "L03",
                "name": "Sindh",
                "kind": "REGION",
                "country": "Pakistan",
                "role": "ORIGIN",
                "claimIds": ["C002"],
            }
        )

    problems = found(content_problems(changed_dossier(misname), default_context()))
    places = [(where, message) for where, message in problems if where.startswith("L0")]
    assert places == [
        ("L01", "state 'Gujrat' is not in the LGD register; did you mean Gujarat?"),
        ("L02", "a VILLAGE in India names its district and state as the LGD register does"),
    ]


def test_stage_timings_and_orders_rest_on_their_claims() -> None:
    def time_stages(plain: dict[str, Any]) -> None:
        plain["stages"][0].update(
            order=1, orderClaimId="C003", duration={"text": "three days", "claimId": "C003"}
        )
        plain["stages"][1].update(
            order=1, orderClaimId="C007", season={"text": "the open sun", "claimId": "C007"}
        )

    problems = found(content_problems(changed_dossier(time_stages), default_context()))
    assert ("stages", "order 1 is given to more than one stage") in problems
    assert ("P01", "the duration 'three days' is not stated by C003 or its quotes") in problems
    assert not [where for where, _ in problems if where == "P02"]


def test_a_gi_or_price_date_is_checked_at_its_own_precision() -> None:
    def date_the_market(plain: dict[str, Any]) -> None:
        plain["market"] = {
            "gi": {"filedOn": "2001-05-11", "registeredOn": "2001", "claimIds": ["C002"]},
            "prices": [
                {"claimId": "C006", "date": "2001-03", "placeId": "L01"},
                {"claimId": "C002", "date": "2001", "placeId": "L01"},
            ],
        }

    problems = found(content_problems(changed_dossier(date_the_market), default_context()))
    assert [(where, message) for where, message in problems if "precision" in message] == [
        ("market.gi", "the filedOn 2001-05-11 is not stated to that precision by any quote of its claims"),
        ("market.prices.0", "the date 2001-03 is not stated to that precision by any quote of C006"),
    ]


def test_coverage_targets_of_the_thin_fixture() -> None:
    dossier = passing_dossier()
    assert thin_shortfalls(dossier) == []
    assert full_shortfalls(dossier) == [
        "at least 8 sources (has 2)",
        "at least 3 sources rated A or B (has 1)",
        "at least 40 claims (has 7)",
        "3 or more OVERVIEW claims",
        "3 or more HISTORY claims",
        "3 or more PROCESS claims",
        "3 or more MATERIALS claims",
        "2 more disciplines with 3 or more claims (has 0)",
        "at least 3 overview sections (has 0)",
    ]
    full = changed_dossier(lambda plain: plain.update(coverage="FULL"))
    messages = [problem.message for problem in coverage_problems(full)]
    assert messages[:2] == [
        "FULL needs at least 8 sources (has 2)",
        "FULL needs at least 3 sources rated A or B (has 1)",
    ]


def test_a_thin_dossier_that_meets_every_full_target_is_marked_full() -> None:
    plain = passing_plain()
    plain["sources"] = [dict(plain["sources"][0], id=f"S{n:02d}") for n in range(1, 9)]
    disciplines = ["OVERVIEW", "HISTORY", "PROCESS", "MATERIALS", "CHEMISTRY", "DESIGN"]
    template = plain["claims"][0]
    plain["claims"] = [
        dict(template, id=f"C{n:03d}", discipline=disciplines[n % len(disciplines)]) for n in range(1, 43)
    ]
    sentence = plain["overview"]["lede"][0]
    plain["overview"]["sections"] = [
        {"discipline": discipline, "sentences": [sentence] * 3} for discipline in disciplines[:3]
    ]
    dossier = Dossier.model_validate(plain)
    assert full_shortfalls(dossier) == []
    assert [problem.message for problem in coverage_problems(dossier)] == [
        "the dossier meets every FULL target; mark it FULL"
    ]


FAMILIES = ("Cane-Bamboo-Craft", "Other-Stone-Carving", "Stone-Others")


def full_plain(craft_slug: str, scope: str = "FAMILY") -> dict[str, Any]:
    plain = passing_plain()
    plain["craftSlug"] = craft_slug
    plain["scope"] = scope
    plain["sources"] = [dict(plain["sources"][0], id=f"S{n:02d}") for n in range(1, 9)]
    disciplines = ["OVERVIEW", "HISTORY", "PROCESS", "MATERIALS", "CHEMISTRY", "DESIGN"]
    template = plain["claims"][0]
    plain["claims"] = [
        dict(template, id=f"C{n:03d}", discipline=disciplines[n % len(disciplines)]) for n in range(1, 43)
    ]
    sentence = plain["overview"]["lede"][0]
    plain["overview"]["sections"] = [
        {"discipline": discipline, "sentences": [sentence] * 3} for discipline in disciplines
    ]
    plain["coverage"] = "FULL"
    plain["places"] = [
        dict(place, claimIds=["C001"], role="PRACTISED")
        for place in (
            {"id": "L01", "name": "Assam", "kind": "STATE", "state": "Assam", "country": "India"},
            {"id": "L02", "name": "Northeast India", "kind": "REGION", "country": "India"},
            {"id": "L03", "name": "Tripura", "kind": "STATE", "state": "Tripura", "country": "India"},
        )
    ]
    return plain


def scope_messages(plain: dict[str, Any], change: Any = None) -> list[tuple[str, str]]:
    if change is not None:
        change(plain)
    problems = found(content_problems(Dossier.model_validate(plain), default_context()))
    kept = ("coverage", "scope", "market.gi", "craftSlug", "categorySlug", "overview")
    return [
        (where, message) for where, message in problems if where in kept or where.startswith(("L0", "O0"))
    ]


def test_a_family_craft_names_its_centres_by_state_or_region() -> None:
    assert scope_messages(full_plain("Kutch-Ajrakh", "CRAFT")) == [
        ("coverage", "FULL needs the district of every centre (L01, L02, L03 names none)")
    ]
    for family in FAMILIES:
        assert scope_messages(full_plain(family)) == []
    family = Dossier.model_validate(full_plain("Cane-Bamboo-Craft"))
    assert full_shortfalls(family) == []
    as_craft = family.model_copy(update={"scope": "CRAFT"})
    assert full_shortfalls(as_craft) == ["the district of every centre (L01, L02, L03 names none)"]


def test_the_scope_is_declared_and_must_match_the_register() -> None:
    assert scope_messages(full_plain("Cane-Bamboo-Craft", "CRAFT"))[0] == (
        "scope",
        "Cane-Bamboo-Craft is a family craft (catch-all or practised across India); its scope is FAMILY",
    )
    assert scope_messages(full_plain("Kutch-Ajrakh"))[0] == (
        "scope",
        "Kutch-Ajrakh is a single named craft; its scope is CRAFT",
    )
    with pytest.raises(ValidationError, match="names its categorySlug"):
        Dossier.model_validate(full_plain("Cane-Bamboo-Craft", "CATEGORY"))
    assert Dossier.model_validate(passing_plain()).scope == "CRAFT"


def test_a_family_craft_still_places_its_villages_in_their_districts() -> None:
    def add_village(plain: dict[str, Any]) -> None:
        plain["places"].append(
            {
                "id": "L04",
                "name": "Ajrakhpur",
                "kind": "VILLAGE",
                "state": "Gujarat",
                "country": "India",
                "role": "PRACTISED",
                "claimIds": ["C001"],
            }
        )

    assert scope_messages(full_plain("Cane-Bamboo-Craft"), add_village) == [
        ("coverage", "FULL needs the district of every centre (L04 names none)"),
        ("L04", "a VILLAGE in India names its district and state as the LGD register does"),
    ]


def test_a_family_craft_has_no_gi_record_and_may_be_thin() -> None:
    def thin(plain: dict[str, Any]) -> None:
        plain["coverage"] = "THIN"
        plain["claims"] = plain["claims"][:5]
        plain["overview"]["sections"] = []

    assert scope_messages(full_plain("Other-Stone-Carving"), thin) == []

    def with_gi(plain: dict[str, Any]) -> None:
        plain["market"] = {"gi": {"applicationNumber": "151", "claimIds": ["C001"]}}

    assert ("market.gi", "a family craft has no GI record; a GI names one craft") in scope_messages(
        full_plain("Other-Stone-Carving"), with_gi
    )


def test_only_a_category_names_sub_categories_or_member_crafts() -> None:
    plain = full_plain("Other-Stone-Carving")
    lede = plain["overview"]["lede"]
    lede[0] = dict(lede[0], subCategories=["Stone-Carving"])
    lede[1] = dict(lede[1], crafts=["Mysuru-Stone-Carving"])
    problems = found(content_problems(Dossier.model_validate(plain), default_context()))
    assert [(where, message) for where, message in problems if message.startswith("only a category")] == [
        ("overview.lede.0", "only a category dossier names sub-categories or member crafts"),
        ("overview.lede.1", "only a category dossier names sub-categories or member crafts"),
    ]
