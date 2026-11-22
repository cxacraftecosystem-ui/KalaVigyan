from typing import Any

from app.services.explainer_events import ExplainerStream


class Lines:
    def __init__(self) -> None:
        self.shown: list[str] = []

    async def __call__(self, name: str, data: Any) -> None:
        if name == "status":
            self.shown.append(data["message"])


async def test_the_status_line_sums_what_each_section_searches() -> None:
    lines = Lines()
    stream = ExplainerStream(lines, language="en")
    await stream.status("RESEARCHING", 2)
    await stream.status("RESEARCHING", 3)
    assert lines.shown == ["Searching 2 live queries", "Searching 5 live queries"]


async def test_a_step_already_passed_adds_to_its_total_without_going_back() -> None:
    lines = Lines()
    stream = ExplainerStream(lines, language="en")
    await stream.status("RESEARCHING", 2)
    await stream.status("READING", 4)
    await stream.status("RESEARCHING", 1)
    await stream.status("READING", 6)
    await stream.status("COMPOSING", 7)
    await stream.status("COMPOSING", 0)
    assert lines.shown == [
        "Searching 2 live queries",
        "Reading the best of 4 sources found",
        "Reading the best of 10 sources found",
        "Writing a cited answer from 7 passages",
    ]


async def test_planning_is_shown_each_time_it_is_asked() -> None:
    lines = Lines()
    stream = ExplainerStream(lines, language="en")
    await stream.status("PLANNING", craft="Kutch Ajrakh")
    await stream.status("SEARCHING_STORED", 3)
    await stream.status("SEARCHING_STORED", 2)
    assert lines.shown == ["Planning the research on Kutch Ajrakh", "Searching stored findings"]
