from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.core.roles import ROLE_RANK
from app.models.enums import EXPLAINER_DEPTHS
from app.providers import budget
from app.providers.catalogue import model_for
from app.services import app_settings

from .ai_caps import ceilings, unlimited

FAR_PAST_ANY_EARLIER_CAP = budget.SpendState(Decimal(1_000_000), Decimal(1_000_000), Decimal(1_000_000))


@pytest.mark.parametrize("is_media", [False, True])
@pytest.mark.parametrize("depth", EXPLAINER_DEPTHS)
@pytest.mark.parametrize("role", [*ROLE_RANK, None, "GUEST"])
def test_no_role_or_depth_is_refused_or_degraded_by_default(
    role: str | None, depth: str, is_media: bool
) -> None:
    answer = budget.AnswerSpend(depth=depth)
    answer.hold(Decimal(500))
    for left in (answer.left(unlimited()), answer.headroom().left(unlimited())):
        decision = budget.evaluate(
            unlimited(),
            FAR_PAST_ANY_EARLIER_CAP,
            estimate_usd=Decimal(250),
            is_media=is_media,
            role=role,
            answer_left_usd=left,
        )
        assert (decision.allowed, decision.reason, decision.degrade, decision.month_fraction) == (
            True,
            None,
            False,
            None,
        )
    assert not budget.degrades(unlimited(), FAR_PAST_ANY_EARLIER_CAP, role=role)
    assert not budget.past_degrade_mark(unlimited(), FAR_PAST_ANY_EARLIER_CAP)


@pytest.mark.parametrize("depth", EXPLAINER_DEPTHS)
def test_an_uncapped_answer_still_counts_what_it_holds_and_spends(depth: str) -> None:
    answer = budget.AnswerSpend(depth=depth)
    optional = answer.headroom()
    answer.hold(Decimal("3"))
    optional.hold(Decimal("2"))
    answer.settle(Decimal("3"), Decimal("1.25"))
    optional.release(Decimal("2"))
    assert (answer.left(unlimited()), optional.left(unlimited())) == (None, None)
    assert (answer.held_usd, answer.spent_usd) == (Decimal(0), Decimal("1.25"))


def test_allows_inside_every_cap() -> None:
    decision = budget.evaluate(
        ceilings(),
        budget.SpendState(Decimal("100"), Decimal("10"), Decimal("0.1")),
        estimate_usd=Decimal("0.05"),
        is_media=False,
        role="STUDENT",
    )
    assert decision.allowed
    assert not decision.degrade


def test_monthly_ceiling_refuses() -> None:
    decision = budget.evaluate(
        ceilings(),
        budget.SpendState(Decimal("799.99"), Decimal(0), Decimal(0)),
        estimate_usd=Decimal("0.02"),
        is_media=False,
        role="ADMIN",
    )
    assert not decision.allowed
    assert decision.reason == budget.MONTHLY_CEILING
    assert decision.degrade
    assert decision.message


def test_exactly_at_ceiling_is_allowed() -> None:
    decision = budget.evaluate(
        ceilings(),
        budget.SpendState(Decimal("799.98"), Decimal(0), Decimal(0)),
        estimate_usd=Decimal("0.02"),
        is_media=False,
        role="ADMIN",
    )
    assert decision.allowed


def test_media_sub_cap_refuses_media_only() -> None:
    spend = budget.SpendState(Decimal("300"), Decimal("149.95"), Decimal(0))
    media = budget.evaluate(ceilings(), spend, estimate_usd=Decimal("0.067"), is_media=True, role="ADMIN")
    text = budget.evaluate(ceilings(), spend, estimate_usd=Decimal("0.067"), is_media=False, role="ADMIN")
    assert not media.allowed
    assert media.reason == budget.MEDIA_CAP
    assert text.allowed


def test_a_media_cap_without_a_monthly_ceiling_still_refuses_media() -> None:
    c = unlimited(**{app_settings.MEDIA_CAP_USD: 1.0})
    spend = budget.SpendState(Decimal(5000), Decimal("0.99"), Decimal(0))
    media = budget.evaluate(c, spend, estimate_usd=Decimal("0.02"), is_media=True, role="ADMIN")
    text = budget.evaluate(c, spend, estimate_usd=Decimal("0.02"), is_media=False, role="ADMIN")
    assert (media.allowed, media.reason, text.allowed) == (False, budget.MEDIA_CAP, True)


def test_role_daily_cap() -> None:
    spend = budget.SpendState(Decimal("10"), Decimal(0), Decimal("0.49"))
    student = budget.evaluate(ceilings(), spend, estimate_usd=Decimal("0.02"), is_media=False, role="STUDENT")
    researcher = budget.evaluate(
        ceilings(), spend, estimate_usd=Decimal("0.02"), is_media=False, role="RESEARCHER"
    )
    master = budget.evaluate(
        ceilings(),
        budget.SpendState(Decimal(10), Decimal(0), Decimal(500)),
        estimate_usd=Decimal("1"),
        is_media=False,
        role="MASTER_ADMIN",
    )
    assert not student.allowed
    assert student.reason == budget.ROLE_DAILY_CAP
    assert researcher.allowed
    assert master.allowed


def test_admin_daily_cap_is_ten_dollars_when_set() -> None:
    def admin_spending(today: str) -> budget.BudgetDecision:
        spend = budget.SpendState(Decimal(10), Decimal(0), Decimal(today))
        return budget.evaluate(ceilings(), spend, estimate_usd=Decimal("0.5"), is_media=False, role="ADMIN")

    assert admin_spending("9.5").allowed
    assert admin_spending("9.51").reason == budget.ROLE_DAILY_CAP


def test_unknown_role_falls_back_to_student_cap() -> None:
    spend = budget.SpendState(Decimal(0), Decimal(0), Decimal("0.5"))
    decision = budget.evaluate(ceilings(), spend, estimate_usd=Decimal("0.01"), is_media=False, role="GUEST")
    assert decision.reason == budget.ROLE_DAILY_CAP


def test_degrade_at_eighty_percent() -> None:
    below = budget.evaluate(
        ceilings(),
        budget.SpendState(Decimal("639.99")),
        estimate_usd=Decimal("0.01"),
        is_media=False,
        role=None,
    )
    above = budget.evaluate(
        ceilings(), budget.SpendState(Decimal("640")), estimate_usd=Decimal("0.01"), is_media=False, role=None
    )
    assert not below.degrade
    assert above.degrade
    assert above.allowed


def test_a_ceiling_without_a_degrade_mark_never_degrades() -> None:
    c = ceilings(**{app_settings.DEGRADE_AT_FRACTION: None})
    decision = budget.evaluate(
        c, budget.SpendState(Decimal("799")), estimate_usd=Decimal("0.01"), is_media=False, role="STUDENT"
    )
    assert (decision.allowed, decision.degrade) == (True, False)
    assert decision.month_fraction == Decimal("799") / Decimal("800")


def test_zero_ceiling_refuses_paid_but_not_free() -> None:
    c = ceilings(**{app_settings.MONTHLY_CEILING_USD: 0})
    paid = budget.evaluate(
        c, budget.SpendState(), estimate_usd=Decimal("0.000001"), is_media=False, role=None
    )
    free = budget.evaluate(c, budget.SpendState(), estimate_usd=Decimal(0), is_media=False, role=None)
    assert not paid.allowed
    assert free.allowed


def test_request_budget() -> None:
    decision = budget.evaluate(
        unlimited(),
        budget.SpendState(),
        estimate_usd=Decimal("2.5"),
        is_media=False,
        role="ADMIN",
        request_budget_usd=Decimal("2"),
    )
    assert decision.reason == budget.REQUEST_BUDGET


def test_token_cost_sonnet() -> None:
    model = model_for("ANTHROPIC", "claude-sonnet-5-5")
    cost = budget.token_cost(model, input_tokens=12_000, output_tokens=1_200, day=date(2026, 11, 16))
    assert cost == Decimal("0.036000")


def test_cached_tokens_are_cheaper() -> None:
    model = model_for("ANTHROPIC", "claude-sonnet-5-5")
    full = budget.token_cost(model, input_tokens=10_000, output_tokens=0, day=date(2026, 11, 16))
    cached = budget.token_cost(
        model, input_tokens=10_000, output_tokens=0, cached_tokens=8_000, day=date(2026, 11, 16)
    )
    assert cached < full
    assert cached == Decimal("0.008000")


def test_gemini_flash_price_doubles_in_2027() -> None:
    model = model_for("GEMINI", "gemini-3.8-flash")
    before = budget.token_cost(model, input_tokens=1_000_000, output_tokens=0, day=date(2026, 12, 31))
    after = budget.token_cost(model, input_tokens=1_000_000, output_tokens=0, day=date(2027, 1, 1))
    assert before == Decimal("0.750000")
    assert after == Decimal("1.500000")


def test_unknown_price_is_conservative() -> None:
    unverified = model_for("DEEPSEEK", "deepseek-flash")
    cost = budget.token_cost(unverified, input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost == Decimal("35.000000")


def test_override_price_wins() -> None:
    model = model_for("DEEPSEEK", "deepseek-flash")
    cost = budget.token_cost(
        model, input_tokens=1_000_000, output_tokens=0, overrides={"deepseek-flash": {"in": 0.07, "out": 1.1}}
    )
    assert cost == Decimal("0.070000")


def test_unit_costs() -> None:
    image = model_for("GEMINI", "gemini-3.1-flash-image")
    video = model_for("GEMINI", "gemini-omni-1.2-flash")
    assert budget.unit_cost(image, 1) == Decimal("0.067000")
    assert budget.unit_cost(video, 8) == Decimal("0.560000")


@pytest.mark.parametrize(
    ("moment", "expected"),
    [
        (datetime(2026, 11, 30, 18, 29, tzinfo=UTC), datetime(2026, 10, 31, 18, 30, tzinfo=UTC)),
        (datetime(2026, 11, 30, 18, 31, tzinfo=UTC), datetime(2026, 11, 30, 18, 30, tzinfo=UTC)),
    ],
)
def test_month_starts_at_ist_midnight(moment: datetime, expected: datetime) -> None:
    assert budget.month_start(moment) == expected


def test_day_starts_at_ist_midnight() -> None:
    assert budget.day_start(datetime(2026, 11, 16, 3, 0, tzinfo=UTC)) == datetime(
        2026, 11, 15, 18, 30, tzinfo=UTC
    )


AT_THE_CEILING = budget.SpendState(Decimal("800"), Decimal("150"), Decimal("500"))


@pytest.mark.parametrize("is_media", [False, True])
def test_a_master_admin_is_never_refused_or_degraded_at_the_ceiling(is_media: bool) -> None:
    decision = budget.evaluate(
        ceilings(), AT_THE_CEILING, estimate_usd=Decimal("3"), is_media=is_media, role="MASTER_ADMIN"
    )
    assert (decision.allowed, decision.reason, decision.degrade) == (True, None, False)
    assert decision.month_fraction == Decimal(1)
    assert not budget.degrades(ceilings(), AT_THE_CEILING, role="MASTER_ADMIN")


@pytest.mark.parametrize("role", ["STUDENT", "ADMIN", None])
def test_everyone_else_is_refused_and_degraded_at_a_set_ceiling(role: str | None) -> None:
    decision = budget.evaluate(
        ceilings(), AT_THE_CEILING, estimate_usd=Decimal("0.01"), is_media=False, role=role
    )
    assert (decision.allowed, decision.reason, decision.degrade) == (False, budget.MONTHLY_CEILING, True)
    assert budget.degrades(ceilings(), AT_THE_CEILING, role=role)


def test_a_master_admin_daily_cap_in_settings_is_ignored() -> None:
    capped = ceilings(**{app_settings.ROLE_DAILY_USD: {"MASTER_ADMIN": 1.0, "STUDENT": 0.5}})
    spend = budget.SpendState(Decimal(10), Decimal(0), Decimal(5))
    master = budget.evaluate(capped, spend, estimate_usd=Decimal("2"), is_media=False, role="MASTER_ADMIN")
    assert master.allowed


def test_a_master_admin_answer_has_no_cap() -> None:
    decision = budget.evaluate(
        ceilings(),
        budget.SpendState(),
        estimate_usd=Decimal("40"),
        is_media=False,
        role="MASTER_ADMIN",
        answer_left_usd=Decimal(0),
        request_budget_usd=Decimal(1),
    )
    assert decision.allowed


def test_an_answer_is_refused_past_its_depth_cap() -> None:
    spent = budget.AnswerSpend(depth="EXPERT")
    spent.hold(Decimal("0.3"))
    spent.settle(Decimal("0.3"), Decimal("0.25"))
    spent.hold(Decimal("2.0"))
    assert spent.left(ceilings()) == Decimal("0.25")
    inside = budget.evaluate(
        ceilings(),
        budget.SpendState(),
        estimate_usd=Decimal("0.25"),
        is_media=False,
        role="ADMIN",
        answer_left_usd=spent.left(ceilings()),
    )
    past = budget.evaluate(
        ceilings(),
        budget.SpendState(),
        estimate_usd=Decimal("0.26"),
        is_media=False,
        role="ADMIN",
        answer_left_usd=spent.left(ceilings()),
    )
    assert inside.allowed
    assert (past.allowed, past.reason) == (False, budget.ANSWER_CAP)
    assert past.message == "This answer reached the cost limit for its depth."


def test_a_released_hold_frees_the_answer_cap() -> None:
    spent = budget.AnswerSpend(depth="BASIC")
    spent.hold(Decimal("0.2"))
    assert spent.left(ceilings()) == Decimal("0.05")
    spent.release(Decimal("0.2"))
    assert spent.left(ceilings()) == Decimal("0.25")


def test_optional_work_spends_only_while_the_answer_keeps_half_its_cap() -> None:
    answer = budget.AnswerSpend(depth="DETAILED")
    optional = answer.headroom()
    assert optional.left(ceilings()) == Decimal("0.5")
    optional.hold(Decimal("0.1"))
    answer.hold(Decimal("0.1"))
    assert (answer.held_usd, answer.left(ceilings()), optional.left(ceilings())) == (
        Decimal("0.2"),
        Decimal("0.8"),
        Decimal("0.3"),
    )
    optional.settle(Decimal("0.1"), Decimal("0.04"))
    answer.release(Decimal("0.1"))
    assert (answer.spent_usd, answer.held_usd, optional.left(ceilings())) == (
        Decimal("0.04"),
        Decimal(0),
        Decimal("0.46"),
    )
    refused = budget.evaluate(
        ceilings(),
        budget.SpendState(),
        estimate_usd=Decimal("0.47"),
        is_media=False,
        role="ADMIN",
        answer_left_usd=optional.left(ceilings()),
    )
    assert (refused.allowed, refused.reason) == (False, budget.ANSWER_CAP)
    uncapped = budget.evaluate(
        ceilings(),
        budget.SpendState(),
        estimate_usd=Decimal("5"),
        is_media=False,
        role="MASTER_ADMIN",
        answer_left_usd=optional.left(ceilings()),
    )
    assert uncapped.allowed


def test_a_depth_missing_from_a_stored_cap_row_leaves_nothing_to_spend() -> None:
    capped = ceilings(**{app_settings.ANSWER_CAP_USD: {"BASIC": 0.25}})
    assert budget.AnswerSpend(depth="EXPERT").left(capped) == Decimal(0)
    assert budget.AnswerSpend(depth="EXPERT").headroom().left(capped) == Decimal(0)


def test_a_depth_with_a_null_cap_is_unlimited_beside_a_capped_one() -> None:
    mixed = ceilings(**{app_settings.ANSWER_CAP_USD: {"BASIC": 0.25, "DETAILED": None, "EXPERT": None}})
    assert budget.AnswerSpend(depth="BASIC").left(mixed) == Decimal("0.25")
    assert budget.AnswerSpend(depth="EXPERT").left(mixed) is None
    assert budget.AnswerSpend(depth="EXPERT").headroom().left(mixed) is None
