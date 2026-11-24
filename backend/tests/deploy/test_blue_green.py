import sys
from pathlib import Path

import pytest

from .fake_box import LIVE, NEW, PREVIOUS, WORKERS, FakeBox

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="the box's scripts run under Linux bash")

SEEDED = (
    "app.scripts.seed_crafts",
    "app.scripts.import_curation",
    "app.scripts.embed_knowledge",
    "app.scripts.rebuild_stale_pages",
    "app.scripts.eval_retrieval",
)
BELOW_FLOOR = "3"
REBUILD = "app.scripts.rebuild_stale_pages"
REFRESH = "app.scripts.refresh_served_pages"


@pytest.fixture
def box(tmp_path: Path) -> FakeBox:
    return FakeBox(tmp_path)


def serves_as_before(box: FakeBox) -> bool:
    return (
        box.proxied() == "8000"
        and box.active("kv-api@8000")
        and not box.active("kv-api@8001")
        and box.slot("slot-8000") == LIVE
        and box.slot("slot-8001") == PREVIOUS
        and all(box.active(worker) for worker in WORKERS)
    )


def test_a_release_whose_migration_was_retried_serves_from_the_old_colour_while_it_seeds(
    box: FakeBox,
) -> None:
    box.mark("migration-failures", "3")
    run = box.run("release", NEW)
    assert run.code == 0, run.said
    events = box.events()
    assert events.index("stop kv-api@8000") < events.index("alembic unserved")
    assert events.index("alembic unserved") < events.index("start kv-api@8000")
    assert events.index("start kv-api@8000") < events.index("app.scripts.seed_crafts served")
    assert [event for event in events if event.startswith("alembic")] == ["alembic served"] * 3 + [
        "alembic unserved"
    ]
    for module in SEEDED:
        assert f"{module} served" in events and f"{module} unserved" not in events, module
    assert (box.proxied(), box.slot("current"), box.slot("slot-8000")) == ("8001", NEW, LIVE)


def test_a_release_stopped_by_its_retrieval_check_leaves_the_release_before_for_a_rollback(
    box: FakeBox,
) -> None:
    box.mark("check-exit", BELOW_FLOOR)
    run = box.run("release", NEW)
    assert run.code == 1 and "retrieval fell below its floor" in run.said
    assert serves_as_before(box)
    rollback = box.run("rollback")
    assert rollback.code == 0, rollback.said
    assert (box.proxied(), box.slot("current")) == ("8001", PREVIOUS)
    assert not box.active("kv-api@8000")


def test_a_release_rebuilds_the_stored_pages_only_once_its_own_colour_serves(box: FakeBox) -> None:
    run = box.run("release", NEW)
    assert run.code == 0, run.said
    assert box.runs("app.scripts.import_curation") == [(NEW, LIVE)]
    assert box.runs(REBUILD) == [(NEW, NEW)]
    events = box.events()
    assert events.index("stop kv-api@8000") < events.index(f"{REBUILD} served")
    assert events.index(f"{REBUILD} served") < events.index(f"{REFRESH} served")


def test_a_release_stopped_by_its_retrieval_check_rebuilds_no_stored_page(box: FakeBox) -> None:
    box.mark("check-exit", BELOW_FLOOR)
    run = box.run("release", NEW)
    assert run.code == 1, run.said
    assert box.runs("app.scripts.eval_retrieval") == [(NEW, LIVE)]
    assert box.runs(REBUILD) == []


def test_a_rollback_rebuilds_the_stored_pages_in_its_own_shape_once_it_serves(box: FakeBox) -> None:
    run = box.run("rollback")
    assert run.code == 0, run.said
    assert box.runs(REBUILD) == [(PREVIOUS, PREVIOUS)]
    events = box.events()
    assert events.index("stop kv-api@8000") < events.index(f"{REBUILD} served")
    assert events.index(f"{REBUILD} served") < events.index(f"{REFRESH} served")


def test_a_plain_rollback_refuses_a_release_that_never_served(box: FakeBox) -> None:
    box.link("slot-8001", NEW)
    run = box.run("rollback")
    assert run.code == 1 and "which has never served" in run.said
    assert (box.proxied(), box.slot("slot-8001")) == ("8000", NEW)
    assert box.active("kv-api@8000") and not box.active("kv-api@8001")
    named = box.run("rollback", PREVIOUS)
    assert named.code == 0, named.said
    assert (box.proxied(), box.slot("current")) == ("8001", PREVIOUS)


def test_a_new_colour_that_cannot_reach_its_database_is_not_promoted(box: FakeBox) -> None:
    box.mark("unreachable-database")
    run = box.run("release", NEW)
    assert run.code == 1 and "did not become ready" in run.said
    assert "start kv-api@8001" in box.events()
    assert serves_as_before(box)


def test_a_restart_on_an_environment_that_cannot_reach_the_database_keeps_the_serving_colour(
    box: FakeBox,
) -> None:
    box.mark("unreachable-database")
    run = box.run("restart")
    assert run.code == 1 and "did not become ready" in run.said
    assert serves_as_before(box)
    assert not [event for event in box.events() if event.endswith("kv-api@8000") or "restart kv-" in event]


def test_a_restart_moves_the_live_release_to_the_other_colour_and_keeps_the_one_before(box: FakeBox) -> None:
    run = box.run("restart")
    assert run.code == 0, run.said
    assert (box.proxied(), box.slot("slot-8001"), box.slot("slot-8000"), box.slot("current")) == (
        "8001",
        LIVE,
        PREVIOUS,
        LIVE,
    )
    assert not box.active("kv-api@8000")
    assert all(f"restart {worker}" in box.events() for worker in WORKERS)


def test_a_release_that_runs_out_of_its_time_stops_and_puts_the_box_back(box: FakeBox) -> None:
    box.mark("slow-step", "app.scripts.embed_knowledge")
    run = box.run("release", NEW, "--within", "3")
    assert run.code == 124, run.said
    assert run.seconds < 15
    assert serves_as_before(box)
    events = box.events()
    assert events.index("stop kv-worker") < events.index("start kv-worker")


def test_a_release_that_runs_out_of_time_while_it_rebuilds_pages_keeps_its_own_colour_serving(
    box: FakeBox,
) -> None:
    box.mark("slow-step", REBUILD)
    run = box.run("release", NEW, "--within", "8")
    assert run.code == 124, run.said
    assert (box.proxied(), box.slot("current")) == ("8001", NEW)
    assert box.active("kv-api@8001") and not box.active("kv-api@8000")
    assert all(box.active(worker) for worker in WORKERS)
