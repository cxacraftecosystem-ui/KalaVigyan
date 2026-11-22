from app.models.enums import AI_TASKS
from app.providers.catalogue import (
    DEFAULT_ROUTES,
    RESEARCH_TEXT_TASKS,
    ROUTABLE_TASKS,
    TASK_LABELS,
    AiTask,
    supports,
)
from app.providers.router import DEGRADABLE_TASKS


def test_the_understanding_call_is_a_task_of_its_own_routed_like_planning_until_reordered() -> None:
    assert AiTask.UNDERSTAND in ROUTABLE_TASKS and AiTask.UNDERSTAND in RESEARCH_TEXT_TASKS
    assert DEFAULT_ROUTES[AiTask.UNDERSTAND] == DEFAULT_ROUTES[AiTask.PLAN]
    assert DEFAULT_ROUTES[AiTask.UNDERSTAND][0] == ("GEMINI", "gemini-3.5-flash-lite")
    assert all(
        supports(provider, model, AiTask.UNDERSTAND) for provider, model in DEFAULT_ROUTES[AiTask.UNDERSTAND]
    )
    assert AiTask.UNDERSTAND in DEGRADABLE_TASKS
    assert AI_TASKS[-1] == "UNDERSTAND"


def test_usage_names_the_understanding_apart_from_planning() -> None:
    assert (TASK_LABELS[AiTask.UNDERSTAND], TASK_LABELS[AiTask.PLAN]) == (
        "Understand the question",
        "Plan research",
    )
