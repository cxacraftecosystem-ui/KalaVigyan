from app.composer.candidates import WHOLE_TEXT_MAX_CHARS, ClaimSupport, compose_request, research_summary
from app.research.research_summary import SearchedQuery
from app.research.retrieval import KnowledgeHits

from ..research.fixtures import AJRAKH
from .fixtures import (
    ABSTRACT,
    ALUM_CLAIM_ID,
    ALUM_CLAIM_TEXT,
    GUESS_CLAIM_ID,
    LONG_QUOTES,
    LONG_TEXT,
    QUESTION,
    pack,
)


def test_stored_claims_and_read_documents_become_candidates() -> None:
    request = compose_request(pack(), QUESTION)
    assert (request.question, request.language, request.craft) == (QUESTION, "en", AJRAKH)
    assert [(c.id, c.kind, c.level) for c in request.candidates] == [
        (str(ALUM_CLAIM_ID), "CLAIM", "REVIEWED"),
        (str(GUESS_CLAIM_ID), "CLAIM", "HYPOTHESIS"),
        ("crossref:10.1000/lake", "EVIDENCE", "PROVISIONAL"),
        ("searxng:https://crafts.example.org/ajrakh", "EVIDENCE", "PROVISIONAL"),
    ]
    claim, _, abstract, page = request.candidates
    assert (claim.text, claim.quotes, claim.source_label) == (ALUM_CLAIM_TEXT, [], "stored claim, reviewed")
    assert (abstract.text, abstract.quotes) == (ABSTRACT, [])
    assert abstract.source_label == "Alizarin lakes on cotton (Journal of Dye Chemistry, 2019, abstract)"
    assert (page.text, page.quotes) == (LONG_QUOTES[0], [LONG_QUOTES[1]])
    assert page.source_label == "Ajrakh fastness notes (searxng, undated, full text)"


def test_a_long_document_without_reader_quotes_and_unread_evidence_are_left_out() -> None:
    assert len(LONG_TEXT) > WHOLE_TEXT_MAX_CHARS
    ids = set(compose_request(pack(), QUESTION).allowed)
    assert "searxng:https://crafts.example.org/workshops" not in ids
    assert "openalex:W9" not in ids


def test_the_summary_lists_what_was_searched() -> None:
    summary = research_summary(pack())
    assert summary.craft == AJRAKH
    assert summary.mode == "HYBRID"
    assert (summary.stored_claims, summary.stored_passages) == (2, 1)
    assert summary.queries == (
        SearchedQuery(tier="T3", text="Kutch Ajrakh alum mordant"),
        SearchedQuery(tier="T4", text="Kutch Ajrakh alizarin lake"),
    )
    assert summary.services == ("crossref", "openalex", "semantic_scholar", "web")
    assert (summary.evidence_found, summary.documents_read, summary.failures) == (4, 3, 1)


def test_a_stored_claim_is_offered_with_its_sources_quotes_and_names() -> None:
    source_quote = "Alum is the mordant that fixes the red on Ajrakh cloth"
    support = {
        ALUM_CLAIM_ID: ClaimSupport(
            quotes=(source_quote, source_quote, ALUM_CLAIM_TEXT), sources=("Ajrakh (Khamir, 2019)",)
        )
    }
    claim = compose_request(pack(), QUESTION, support=support).candidates[0]
    assert claim.quotes == [source_quote]
    assert claim.source_label == "stored claim, reviewed; Ajrakh (Khamir, 2019)"
    assert claim.cited_texts == [ALUM_CLAIM_TEXT, source_quote]


def test_the_summary_names_every_searcher_asked_even_one_that_found_nothing() -> None:
    summary = research_summary(pack(searched=("searxng", "openalex", "wikipedia")))
    assert summary.services == ("crossref", "openalex", "searxng", "semantic_scholar", "web", "wikipedia")


def test_an_empty_pack_gives_a_request_with_no_candidates() -> None:
    empty = pack(stored=KnowledgeHits(craft_slug=AJRAKH.slug), evidence=(), documents=(), failures=())
    request = compose_request(empty, QUESTION)
    assert request.candidates == []
    assert request.searched.services == ()
