from app.research.explainer import SectionDoneEvent
from app.research.research_summary import (
    SEARCHED_MAX_CHARS,
    ResearchSummary,
    SearchedQuery,
    not_enough_evidence_message,
    searched_note,
)

from .fixtures import AJRAKH

LONG_QUERY = "q" * 290
LISTED = f'T3 "{LONG_QUERY}"'
STORED = "Searched 0 stored claims and 0 stored source passages."
FOUND = "Found 0 items, read 0 documents and recorded 0 failed requests."
SIX_OF_TEN_LENGTH = 1942


def summary(*texts: str) -> ResearchSummary:
    return ResearchSummary(
        craft=AJRAKH,
        mode="DEEP",
        storedClaims=0,
        storedPassages=0,
        queries=tuple(SearchedQuery(tier="T3", text=text) for text in texts),
        evidenceFound=0,
        documentsRead=0,
        failures=0,
    )


def test_a_note_that_fits_lists_every_query() -> None:
    assert searched_note(summary("Kutch Ajrakh alum", "Kutch Ajrakh lime")) == (
        f'{STORED} Live research ran 2 queries: T3 "Kutch Ajrakh alum"; T3 "Kutch Ajrakh lime". {FOUND}'
    )


def test_a_note_lists_the_queries_that_fit_the_limit_and_counts_the_rest() -> None:
    note = searched_note(summary(*[LONG_QUERY] * 10))
    listed = "; ".join([LISTED] * 6)
    assert note == f"{STORED} Live research ran 10 queries: {listed}; and 4 more. {FOUND}"
    assert len(note) == SIX_OF_TEN_LENGTH <= SEARCHED_MAX_CHARS
    SectionDoneEvent.model_validate({"sectionId": "s4", "state": "EMPTY", "searched": note})


def test_a_note_of_queries_none_of_which_fits_only_counts_them() -> None:
    note = searched_note(summary(*[LONG_QUERY] * 30).model_copy(update={"services": ("x" * 1900,)}))
    assert note.startswith(f"{STORED} Live research ran 30 queries. Sources searched: ")
    assert note.endswith(FOUND)


def test_the_not_enough_evidence_message_still_lists_every_query() -> None:
    message = not_enough_evidence_message(summary(*[LONG_QUERY] * 10))
    assert message.count(LISTED) == 10
