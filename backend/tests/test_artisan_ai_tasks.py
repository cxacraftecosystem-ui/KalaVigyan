from app.providers.catalogue import (
    DEFAULT_ROUTES,
    PUBLIC_TEXT_TASKS,
    ROUTABLE_TASKS,
    TASK_LABELS,
    AiProvider,
    AiTask,
    allows_data,
)


def test_artisan_tasks_are_routable_with_their_contract_defaults() -> None:
    assert AiTask.INTERVIEW in ROUTABLE_TASKS and AiTask.TESTIMONY in ROUTABLE_TASKS
    assert DEFAULT_ROUTES[AiTask.INTERVIEW] == DEFAULT_ROUTES[AiTask.VOICE_TURN]
    assert DEFAULT_ROUTES[AiTask.TESTIMONY] == DEFAULT_ROUTES[AiTask.COMPOSE]
    assert TASK_LABELS[AiTask.INTERVIEW] == "Artisan conversations"
    assert TASK_LABELS[AiTask.TESTIMONY] == "Artisan testimony"


def test_a_conversation_never_reaches_a_public_text_provider() -> None:
    for task in (AiTask.INTERVIEW, AiTask.TESTIMONY):
        assert task not in PUBLIC_TEXT_TASKS
        assert not allows_data(AiProvider.DEEPSEEK, task)
