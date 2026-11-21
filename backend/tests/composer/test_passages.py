from app.composer.candidates import WHOLE_TEXT_MAX_CHARS, compose_request
from app.composer.passages import best_passages, passage_terms, passages_of
from app.research.quotes import quote_occurs
from app.sources.adapter import build_document

from ..research.fixtures import evidence_item
from .fixtures import PLAN, QUESTION, pack, packed

PADDING = "talks " * 110


def long_sentence(opening: str) -> str:
    return f"{opening} {PADDING}end."


BINDS = long_sentence("Alum is the mordant that binds alizarin")
CHEAP = long_sentence("Alum is cheap")
LAKE = long_sentence("A red lake forms with alum")
FILLER = long_sentence("The workshop")
MADDER = long_sentence("The madder bath")
ARTICLE = " ".join([FILLER, BINDS, CHEAP, FILLER, LAKE, MADDER])
TERMS = frozenset({"alum", "mord", "aliz", "lake"})
PAGE_ITEM = evidence_item(
    id="searxng:https://crafts.example.org/ajrakh/mordants",
    adapter="searxng",
    tier="T4",
    sourceType="WEB_PAGE",
    url="https://crafts.example.org/ajrakh/mordants",
    title="Ajrakh mordants",
    doi=None,
    trust="C",
    quotes=[],
)


def test_a_text_is_cut_into_passages_of_whole_sentences() -> None:
    text = "One sentence here. Two sentence here.\n\nA line\nbroken here."
    assert passages_of(text, max_chars=20) == [
        "One sentence here.",
        "Two sentence here.",
        "A line broken here.",
    ]
    assert passages_of(text, max_chars=40) == ["One sentence here. Two sentence here.", "A line broken here."]


def test_the_facet_words_of_a_plan_leave_out_the_craft_s_own_name() -> None:
    assert passage_terms(PLAN) == TERMS


def test_the_passages_that_best_match_the_facets_by_rarity_are_picked_within_the_budget() -> None:
    assert [len(passage) <= 1200 for passage in passages_of(ARTICLE)] == [True] * 6
    assert best_passages(ARTICLE, TERMS, budget=4000) == [BINDS, LAKE, CHEAP]
    assert best_passages(ARTICLE, TERMS, budget=2 * len(BINDS) + 10) == [BINDS, LAKE]
    assert best_passages(ARTICLE, frozenset({"indi"}), budget=4000) == []


def test_a_long_document_without_reader_quotes_offers_its_best_passages_to_the_composer() -> None:
    assert len(ARTICLE) > WHOLE_TEXT_MAX_CHARS
    document = build_document(PAGE_ITEM, ARTICLE, "FULL_TEXT")
    evidence = pack(evidence=(packed(PAGE_ITEM, "web"),), documents=(document,))
    (candidate,) = [c for c in compose_request(evidence, QUESTION).candidates if c.id == PAGE_ITEM.id]
    assert (candidate.text, candidate.quotes) == (BINDS, [LAKE, CHEAP])
    assert all(
        quote_occurs("Alum is the mordant that binds alizarin", text) for text in (candidate.text, ARTICLE)
    )
