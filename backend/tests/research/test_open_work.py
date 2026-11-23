import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.errors import InvalidInput
from app.models.component_kinds import PIECE_KINDS
from app.research.open_work import (
    COMPONENT_NEEDS,
    OWNER_ORDER,
    CoverageTargets,
    FieldStanding,
    Hold,
    Items,
    QueueStanding,
    SubjectStanding,
    TaskSubject,
    Viewer,
    WorkFilters,
    parse_task_key,
)
from app.research.open_work_links import SourceLink, link_state, sources_in_state
from app.research.open_work_tasks import (
    chosen_tasks,
    open_tasks,
    review_tasks,
    reviewed_queues,
    subject_priority,
    subject_tasks,
)

CURATION = Path(__file__).resolve().parents[2] / "app" / "data" / "curation"
NOW = datetime(2026, 11, 19, 12, 0, tzinfo=UTC)
ME = uuid.UUID("0e000000-0000-4000-8000-000000000001")
OTHER = uuid.UUID("0e000000-0000-4000-8000-000000000002")
FACT_A = "0e000000-0000-4000-8000-0000000000a1"
FACT_B = "0e000000-0000-4000-8000-0000000000a2"
CRAFT_TARGETS = CoverageTargets(
    core_fields=("OVERVIEW", "HISTORY", "PROCESS", "MATERIALS"),
    facts_min=3,
    section_sentences_min=3,
    quote_chars_min=25,
    quote_chars_max=300,
    components=True,
)
CATEGORY_TARGETS = replace(CRAFT_TARGETS, core_fields=("OVERVIEW", "HISTORY", "MATERIALS"), components=False)
EVERY_COMPONENT = frozenset({"what_if", "molecule_3d", "map_layer", "reaction_player", "picture_plate"})


def subject(slug: str = "Test-Craft", kind: str = "craft") -> TaskSubject:
    return TaskSubject(
        kind=kind, slug=slug, name=slug.replace("-", " "), page_url=f"https://kv.example/crafts/{slug}"
    )


def standing(**changes: object) -> SubjectStanding:
    base = SubjectStanding(
        subject=subject(),
        targets=CRAFT_TARGETS,
        fields={field: FieldStanding(facts=3, section_sentences=3) for field in CRAFT_TARGETS.core_fields},
        component_kinds=EVERY_COMPONENT,
        new_form=True,
        layout=True,
    )
    return replace(base, **changes)


def keys(standing_: SubjectStanding) -> list[str]:
    return [task.key for task in subject_tasks(standing_)]


def test_a_complete_craft_has_no_open_work() -> None:
    assert keys(standing()) == []


def test_a_craft_with_no_facts_lacks_its_four_core_fields_and_every_component() -> None:
    bare = standing(fields={}, component_kinds=frozenset(), new_form=False, layout=False)
    assert keys(bare) == [
        "MISSING_FIELD:craft:Test-Craft:OVERVIEW",
        "MISSING_FIELD:craft:Test-Craft:PROCESS",
        "MISSING_FIELD:craft:Test-Craft:MATERIALS",
        "MISSING_FIELD:craft:Test-Craft:HISTORY",
        "MISSING_COMPONENT:craft:Test-Craft:what-if",
        "MISSING_COMPONENT:craft:Test-Craft:molecules",
        "MISSING_COMPONENT:craft:Test-Craft:map",
        "MISSING_COMPONENT:craft:Test-Craft:reaction-player",
        "MISSING_COMPONENT:craft:Test-Craft:pictures",
        "PAGE_FORM:craft:Test-Craft",
    ]
    missing = subject_tasks(bare)[0]
    assert (missing.field, missing.count, missing.prompt) == ("OVERVIEW", 3, "research_field")
    assert "At least 3 more facts filed under OVERVIEW" in missing.acceptance
    assert "25 to 300 characters" in missing.acceptance


def test_a_field_below_three_facts_is_thin_and_one_with_facts_but_no_full_section_needs_writing() -> None:
    fields = {
        "OVERVIEW": FieldStanding(facts=3, section_sentences=3),
        "HISTORY": FieldStanding(facts=2, section_sentences=3),
        "PROCESS": FieldStanding(facts=4, section_sentences=0),
        "MATERIALS": FieldStanding(facts=3, section_sentences=2),
        "CHEMISTRY": FieldStanding(facts=1),
        "BOTANY": FieldStanding(facts=3, section_sentences=3),
    }
    tasks = {task.key: task for task in subject_tasks(standing(fields=fields))}
    assert sorted(tasks) == [
        "SECTION:craft:Test-Craft:MATERIALS",
        "SECTION:craft:Test-Craft:PROCESS",
        "THIN_FIELD:craft:Test-Craft:CHEMISTRY",
        "THIN_FIELD:craft:Test-Craft:HISTORY",
    ]
    history = tasks["THIN_FIELD:craft:Test-Craft:HISTORY"]
    assert history.count == 1 and "At least 1 more fact filed under HISTORY" in history.acceptance
    assert "holds 2 facts under HISTORY (history); the target is 3" in history.needed
    process = tasks["SECTION:craft:Test-Craft:PROCESS"]
    assert (process.count, process.prompt) == (4, "write_section")
    assert "no section is published" in process.needed
    assert "the published section has 2 sentences" in tasks["SECTION:craft:Test-Craft:MATERIALS"].needed


def test_a_category_has_three_core_fields_and_no_component_tasks() -> None:
    category = standing(
        subject=subject("Test-Category", "category"),
        targets=CATEGORY_TARGETS,
        fields={},
        component_kinds=frozenset(),
    )
    assert keys(category) == [
        "MISSING_FIELD:category:Test-Category:OVERVIEW",
        "MISSING_FIELD:category:Test-Category:MATERIALS",
        "MISSING_FIELD:category:Test-Category:HISTORY",
    ]


def test_a_component_need_is_met_by_any_kind_that_shows_it() -> None:
    held = frozenset({"indigo_vat", "images", "region_story"})
    assert keys(standing(component_kinds=held)) == [
        "MISSING_COMPONENT:craft:Test-Craft:what-if",
        "MISSING_COMPONENT:craft:Test-Craft:molecules",
    ]
    task = subject_tasks(standing(component_kinds=held))[0]
    assert (task.need, task.prompt) == ("what-if", "propose_component")


def test_every_component_need_names_registered_component_kinds() -> None:
    assert set(COMPONENT_NEEDS) == {"what-if", "molecules", "map", "reaction-player", "pictures"}
    assert {kind for kinds in COMPONENT_NEEDS.values() for kind in kinds} <= set(PIECE_KINDS)


def test_a_page_in_the_new_form_without_a_layout_needs_one() -> None:
    assert keys(standing(layout=False)) == ["PAGE_LAYOUT:craft:Test-Craft"]
    assert keys(standing(new_form=False, layout=False)) == ["PAGE_FORM:craft:Test-Craft"]


def test_single_source_and_differing_facts_become_tasks_per_field_with_their_ids() -> None:
    fields = {
        **standing().fields,
        "HISTORY": FieldStanding(
            facts=3, section_sentences=3, one_source=Items(count=2, ids=(FACT_A, FACT_B))
        ),
        None: FieldStanding(differing=Items(count=1, ids=(FACT_A,))),
    }
    tasks = subject_tasks(standing(fields=fields))
    assert [task.key for task in tasks] == [
        "SECOND_SOURCE:craft:Test-Craft:HISTORY",
        "SOURCES_DIFFER:craft:Test-Craft",
    ]
    assert [str(fact) for fact in tasks[0].fact_ids] == [FACT_A, FACT_B]
    assert tasks[0].needed == "2 facts of Test Craft under HISTORY rest on one source."
    assert tasks[1].needed == "1 fact of Test Craft is marked sources differ, waiting for a deciding source."
    assert tasks[1].field is None and tasks[1].source_ids == []


def test_a_source_is_dead_or_unarchived_only_when_no_archive_is_held() -> None:
    links = [
        SourceLink("s-archived", archived=True, last_status=404),
        SourceLink("s-gone", archived=False, last_status=410),
        SourceLink("s-missing", archived=False, last_status=404),
        SourceLink("s-live", archived=False, last_status=200),
        SourceLink("s-unread", archived=False, last_status=None),
    ]
    assert [link_state(link) for link in links] == [
        None,
        "DEAD_SOURCE",
        "DEAD_SOURCE",
        "UNARCHIVED_SOURCE",
        "UNARCHIVED_SOURCE",
    ]
    dead = sources_in_state(links, "DEAD_SOURCE")
    task = subject_tasks(standing(dead_sources=dead))[0]
    assert (task.key, task.count, task.source_ids, task.fact_ids) == (
        "DEAD_SOURCE:craft:Test-Craft",
        2,
        ["s-gone", "s-missing"],
        [],
    )
    assert task.needed == "2 sources cited by Test Craft no longer answer at their address."


def test_items_count_every_id_but_carry_at_most_twenty() -> None:
    items = Items.of(f"s{number:02d}" for number in range(25))
    assert (items.count, len(items.ids), items.ids[-1]) == (25, 20, "s19")


@pytest.mark.parametrize(
    ("changes", "priority"),
    [
        ({"subject": subject("Bidriware")}, "HIGH"),
        ({"demand": 25}, "HIGH"),
        ({"demand": 24}, "MEDIUM"),
        ({"gi": True}, "MEDIUM"),
        ({"demand": 5}, "MEDIUM"),
        ({"demand": 4}, "LOW"),
        ({}, "LOW"),
        ({"subject": subject("Bidriware", "category"), "demand": 100, "gi": True}, "LOW"),
    ],
)
def test_priority_follows_the_owner_s_order_reader_demand_and_gi(
    changes: dict[str, object], priority: str
) -> None:
    assert subject_priority(standing(**changes)) == priority


def test_the_owner_s_first_crafts_are_curated_dossiers() -> None:
    assert len(OWNER_ORDER) == 8
    assert all((CURATION / f"{slug}.json").is_file() for slug in OWNER_ORDER)


def test_subjects_are_ordered_by_priority_then_owner_order_then_demand() -> None:
    bare = {"fields": {}, "component_kinds": EVERY_COMPONENT}
    standings = [
        standing(subject=subject("Plain-Craft"), **bare),
        standing(subject=subject("Channapatna-Toys-Dolls"), **bare),
        standing(subject=subject("Popular-Craft"), demand=40, **bare),
        standing(subject=subject("Bidriware"), **bare),
        standing(subject=subject("Gi-Craft"), gi=True, **bare),
    ]
    tasks = open_tasks(standings, {}, Viewer())
    firsts = list(dict.fromkeys(task.subject.slug for task in tasks if task.subject is not None))
    assert firsts == ["Bidriware", "Channapatna-Toys-Dolls", "Popular-Craft", "Gi-Craft", "Plain-Craft"]


def test_review_queues_are_shown_only_to_the_roles_that_review_them() -> None:
    queues = {
        "FACTS": QueueStanding(count=4, oldest=datetime(2026, 11, 1, tzinfo=UTC)),
        "TESTIMONY": QueueStanding(count=2, oldest=None),
        "IMAGES": QueueStanding(count=1, oldest=None),
        "COMPONENTS": QueueStanding(count=0, oldest=None),
    }
    assert review_tasks(queues, Viewer(user_id=ME)) == []
    assert review_tasks(queues, Viewer(user_id=ME, review_role="RESEARCHER")) == []
    professor = review_tasks(queues, Viewer(user_id=ME, review_role="PROFESSOR"))
    assert [task.key for task in professor] == ["REVIEW:FACTS", "REVIEW:TESTIMONY"]
    assert professor[0].needed == "4 proposed facts wait for review, the oldest since 2026-11-01."
    admin = review_tasks(queues, Viewer(user_id=ME, review_role="ADMIN"))
    assert [task.key for task in admin] == ["REVIEW:FACTS", "REVIEW:TESTIMONY", "REVIEW:IMAGES"]
    assert {task.priority for task in admin} == {"HIGH"}


def test_chosen_tasks_hide_others_reservations_mark_mine_and_return_expired_ones() -> None:
    tasks = subject_tasks(standing(fields={}, component_kinds=EVERY_COMPONENT))
    overview, process, materials, history = (task.key for task in tasks)
    holds = {
        overview: Hold(user_id=OTHER, expires_at=NOW + timedelta(minutes=30)),
        process: Hold(user_id=ME, expires_at=NOW + timedelta(minutes=90)),
        materials: Hold(user_id=OTHER, expires_at=NOW - timedelta(minutes=1)),
    }
    kept = chosen_tasks(
        tasks, WorkFilters(), holds=holds, closed=frozenset({history}), viewer=Viewer(user_id=ME), now=NOW
    )
    assert [task.key for task in kept] == [process, materials]
    assert kept[0].reserved_until == NOW + timedelta(minutes=90)
    assert kept[1].reserved_until is None
    anonymous = chosen_tasks(tasks, WorkFilters(), holds=holds, closed=frozenset(), viewer=Viewer(), now=NOW)
    assert [task.key for task in anonymous] == [materials, history]


def test_filters_narrow_by_kind_priority_and_field_and_put_high_priority_first() -> None:
    low = subject_tasks(standing(subject=subject("Plain-Craft"), fields={}, layout=False))
    high = subject_tasks(standing(subject=subject("Bidriware"), layout=False))
    every = [*low, *high]
    chosen = chosen_tasks(every, WorkFilters(), holds={}, closed=frozenset(), viewer=Viewer(), now=NOW)
    assert chosen[0].key == "PAGE_LAYOUT:craft:Bidriware"
    by_kind = chosen_tasks(
        every,
        WorkFilters(kind="PAGE_LAYOUT", priority="LOW"),
        holds={},
        closed=frozenset(),
        viewer=Viewer(),
        now=NOW,
    )
    assert [task.key for task in by_kind] == ["PAGE_LAYOUT:craft:Plain-Craft"]
    by_field = chosen_tasks(
        every, WorkFilters(field="HISTORY"), holds={}, closed=frozenset(), viewer=Viewer(), now=NOW
    )
    assert [task.key for task in by_field] == ["MISSING_FIELD:craft:Plain-Craft:HISTORY"]


def test_work_is_filtered_by_one_subject_at_most() -> None:
    assert WorkFilters(family_slug="Cane-Bamboo-Craft").subject_filter() == ("family", "Cane-Bamboo-Craft")
    assert WorkFilters().subject_filter() is None
    with pytest.raises(ValidationError, match="not several"):
        WorkFilters(craft_slug="Kutch-Ajrakh", category_slug="Textiles-Based-Craft-Category")


def test_a_task_key_names_its_kind_subject_and_detail() -> None:
    key = parse_task_key("THIN_FIELD:craft:Kutch-Ajrakh:HISTORY")
    assert (key.kind, key.subject_kind, key.slug, key.detail) == (
        "THIN_FIELD",
        "craft",
        "Kutch-Ajrakh",
        "HISTORY",
    )
    assert key.text() == "THIN_FIELD:craft:Kutch-Ajrakh:HISTORY"
    assert parse_task_key("PAGE_FORM:family:Cane-Bamboo-Craft").detail is None
    assert parse_task_key("REVIEW:IMAGES").detail == "IMAGES"


@pytest.mark.parametrize(
    "key",
    [
        "GUESS:craft:Kutch-Ajrakh",
        "THIN_FIELD:shop:Kutch-Ajrakh:HISTORY",
        "THIN_FIELD:craft:Kutch Ajrakh:HISTORY",
        "THIN_FIELD:craft:Kutch-Ajrakh:ASTROLOGY",
        "THIN_FIELD:craft",
        "REVIEW:EVERYTHING",
    ],
)
def test_a_malformed_task_key_is_refused(key: str) -> None:
    with pytest.raises(InvalidInput):
        parse_task_key(key)


ALL_QUEUES = ("FACTS", "TESTIMONY", "IMAGES", "COMPONENTS", "LAYOUTS", "STRUCTURE", "STAGES")


@pytest.mark.parametrize(
    ("role", "queues"),
    [
        (None, ()),
        ("STUDENT", ()),
        ("ARTISAN", ()),
        ("RESEARCHER", ()),
        ("PROFESSOR", ("FACTS", "TESTIMONY", "STRUCTURE", "STAGES")),
        ("ADMIN", ALL_QUEUES),
        ("MASTER_ADMIN", ALL_QUEUES),
    ],
)
def test_each_role_reviews_the_queues_its_capabilities_allow(
    role: str | None, queues: tuple[str, ...]
) -> None:
    assert reviewed_queues(role) == queues
