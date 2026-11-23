import uuid
from typing import Any

from app.research.blocks import ExplainerSentence
from app.research.blocks_learning import CONCEPT_CRAFTS_MAX
from app.research.citations import SourceRef
from app.research.crafts import CraftRef
from app.research.offered_facts import STORED_CLAIM, OfferedFact
from app.research.shared_science import (
    SHARED_SCIENCE_NODES_MAX,
    TermCraftOffer,
    TermOffer,
    concept_crafts_page,
    concept_node,
    shared_concept,
    shared_science,
)

AJRAKH = CraftRef(slug="Kutch-Ajrakh", name="Kutch Ajrakh", path="/crafts/Kutch-Ajrakh")
BAGRU = CraftRef(slug="Bagru-Print", name="Bagru Print", path="/crafts/Bagru-Print")
SANGANER = CraftRef(slug="Sanganeri-Print", name="Sanganeri Print", path="/crafts/Sanganeri-Print")
AKOLA = CraftRef(slug="Akola-Print", name="Akola Print", path="/crafts/Akola-Print")


def source(source_id: str) -> SourceRef:
    return SourceRef(
        id=source_id,
        kind="GI_JOURNAL",
        title=f"Source {source_id}",
        authors=[],
        year=None,
        doi=None,
        url=None,
        publisher=None,
        licence=None,
        attribution=None,
        reliability="A",
    )


def fact(claim: str, text: str, concept: uuid.UUID, *, rank: int = 0, source_id: str = "s1") -> OfferedFact:
    sentence = ExplainerSentence.model_validate(
        {
            "id": f"offered.{claim}",
            "text": text,
            "level": "PROVISIONAL",
            "citations": [
                {
                    "id": f"cite-{claim}",
                    "claimId": claim,
                    "sourceId": source_id,
                    "quote": text,
                    "locator": None,
                    "context": None,
                    "evidence": "QUOTED",
                    "level": "PROVISIONAL",
                }
            ],
            "translated": False,
            "terms": [],
        }
    )
    return OfferedFact(
        sentence=sentence, rank=(STORED_CLAIM, 2, 0, -1, f"{rank:03d}", claim), concept_id=concept
    )


def concept(number: int) -> uuid.UUID:
    return uuid.UUID(int=number)


def entry(craft: CraftRef, number: int, *facts: OfferedFact) -> TermCraftOffer:
    return TermCraftOffer(craft=craft, concept_ids=(concept(number),), facts=facts)


def alum(*entries: TermCraftOffer) -> TermOffer:
    return TermOffer(key="alum", label="Alum", surfaces=("Alum", "fitkari"), crafts=entries)


AJRAKH_ALUM = entry(AJRAKH, 1, fact("a1", "Alum is used as a mordant.", concept(1)))
BAGRU_ALUM = entry(BAGRU, 2, fact("b1", "Alum solution fixes colour.", concept(2), source_id="s2"))
SANGANER_SILENT = entry(SANGANER, 3, fact("g1", "Turmeric gives the yellow.", concept(3)))


def crafts_of(node: Any) -> list[str]:
    return [item.craft.slug for item in node.crafts]


def test_a_craft_whose_claims_never_name_the_term_has_no_edge() -> None:
    node = concept_node(alum(SANGANER_SILENT, BAGRU_ALUM, AJRAKH_ALUM), focus=None)
    assert node is not None
    assert crafts_of(node) == [BAGRU.slug, AJRAKH.slug]


def test_a_claim_about_another_concept_backs_no_edge() -> None:
    elsewhere = entry(SANGANER, 3, fact("g2", "Alum is sold in the market.", concept(30)))
    node = concept_node(alum(AJRAKH_ALUM, BAGRU_ALUM, elsewhere), focus=None)
    assert node is not None and SANGANER.slug not in crafts_of(node)


def test_a_term_fewer_than_two_crafts_name_is_no_concept() -> None:
    assert concept_node(alum(AJRAKH_ALUM, SANGANER_SILENT), focus=None) is None
    assert concept_node(alum(AJRAKH_ALUM), focus=None) is None


def test_the_focus_craft_comes_first_and_the_others_follow_by_name() -> None:
    sanganer = entry(SANGANER, 3, fact("g3", "Diluted alum fixes the yellow.", concept(3)))
    node = concept_node(alum(sanganer, BAGRU_ALUM, AJRAKH_ALUM), focus=AJRAKH.slug, id_prefix="s2.shared.")
    assert node is not None
    assert crafts_of(node) == [AJRAKH.slug, BAGRU.slug, SANGANER.slug]
    assert [item.sentence.id for item in node.crafts] == [f"s2.shared.alum.{n}" for n in (1, 2, 3)]
    assert [[span.text for span in item.sentence.terms] for item in node.crafts] == [
        ["Alum"],
        ["Alum"],
        ["alum"],
    ]
    assert concept_node(alum(sanganer, BAGRU_ALUM), focus=AJRAKH.slug) is None


def test_the_best_ranked_claim_naming_the_term_speaks_for_a_craft() -> None:
    ajrakh = entry(
        AJRAKH,
        1,
        fact("a2", "Red comes from alum as mordant.", concept(1), rank=2),
        fact("a3", "Madder gives the red.", concept(1), rank=0),
        fact("a1", "Alum is used as a mordant.", concept(1), rank=1),
    )
    node = concept_node(alum(ajrakh, BAGRU_ALUM), focus=AJRAKH.slug)
    assert node is not None
    assert node.crafts[0].sentence.citations[0].claim_id == "a1"


def many_crafts(count: int) -> list[TermCraftOffer]:
    return [
        entry(
            CraftRef(slug=f"craft-{n:03d}", name=f"Craft {n:03d}", path=f"/crafts/craft-{n:03d}"),
            100 + n,
            fact(f"c{n}", f"Alum is used by craft {n}.", concept(100 + n), source_id=f"s{n % 3}"),
        )
        for n in range(count)
    ]


def test_the_limits_hold() -> None:
    node = concept_node(alum(*many_crafts(CONCEPT_CRAFTS_MAX + 20)), focus="craft-119")
    assert node is not None
    assert len(node.crafts) == CONCEPT_CRAFTS_MAX and node.crafts[0].craft.slug == "craft-119"
    assert node.craft_count == 120
    offers = [
        TermOffer(
            key=f"term{n:02d}",
            label=f"Term{n:02d}",
            surfaces=(f"Term{n:02d}",),
            crafts=(
                entry(AJRAKH, 1, fact(f"a{n}", f"Term{n:02d} is used in Ajrakh.", concept(1))),
                entry(BAGRU, 2, fact(f"b{n}", f"Term{n:02d} is used in Bagru.", concept(2))),
            ),
        )
        for n in reversed(range(SHARED_SCIENCE_NODES_MAX + 6))
    ]
    sources = {"s1": source("s1")}
    explored = shared_science(AJRAKH, offers, sources)
    assert len(explored.nodes) == SHARED_SCIENCE_NODES_MAX
    assert [node.term_key for node in explored.nodes][:2] == ["term00", "term01"]
    assert [s.id for s in explored.sources] == ["s1"]


def test_one_shared_concept_cites_every_craft_s_source_in_order() -> None:
    sources = {"s1": source("s1"), "s2": source("s2")}
    found = shared_concept(alum(BAGRU_ALUM, AJRAKH_ALUM), sources)
    assert found is not None
    assert crafts_of(found.node) == [BAGRU.slug, AJRAKH.slug]
    assert [s.id for s in found.sources] == ["s2", "s1"]
    focused = shared_concept(alum(BAGRU_ALUM, AJRAKH_ALUM), sources, focus=AJRAKH.slug)
    assert focused is not None and [s.id for s in focused.sources] == ["s1", "s2"]
    assert shared_concept(alum(AJRAKH_ALUM), sources) is None


def test_a_node_counts_every_craft_whose_own_claims_name_the_term() -> None:
    node = concept_node(alum(SANGANER_SILENT, BAGRU_ALUM, AJRAKH_ALUM), focus=None)
    assert node is not None and node.craft_count == 2


def test_the_pages_of_a_node_continue_its_order_and_its_sentence_numbers() -> None:
    offer = alum(*many_crafts(CONCEPT_CRAFTS_MAX + 20))
    sources = {f"s{n}": source(f"s{n}") for n in range(3)}
    page = concept_crafts_page(offer, sources, focus="craft-119", offset=CONCEPT_CRAFTS_MAX)
    assert page is not None
    assert (page.craft_count, page.offset, len(page.crafts)) == (120, 100, 20)
    assert page.crafts[0].craft.slug == "craft-099" and page.crafts[-1].craft.slug == "craft-118"
    assert [entry.sentence.id for entry in page.crafts][:2] == ["alum.101", "alum.102"]
    assert [s.id for s in page.sources] == ["s0", "s1", "s2"]
    first = concept_crafts_page(offer, sources, focus="craft-119", offset=0)
    assert first is not None and len(first.crafts) == CONCEPT_CRAFTS_MAX
    assert first.crafts[0].craft.slug == "craft-119" and first.crafts[0].sentence.id == "alum.1"
    assert concept_crafts_page(offer, sources, focus="craft-119", offset=120) is None
    assert concept_crafts_page(offer, sources, focus="no-such-craft", offset=0) is None
    assert concept_crafts_page(alum(AJRAKH_ALUM), sources, focus=None, offset=0) is None
