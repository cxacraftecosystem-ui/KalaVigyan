import uuid

import pytest

from app.core.errors import InvalidInput
from app.research.composition import ComposedAnswer, ComposedSection, ComposedSentence, QuotedSpan
from app.research.evidence_pack import EvidencePack, PackedEvidence
from app.research.planning import Facet, FacetCoverage
from app.research.sections import DISCIPLINE_TITLES
from app.services.write_back_crafts import SKIP_ABROAD, SKIP_SEVERAL_CRAFTS
from app.services.write_back_names import CraftNames
from app.services.write_back_plan import section_discipline, write_back_plan
from app.sources.adapter import build_document

from ..composer.fixtures import ABSTRACT, ABSTRACT_ITEM, PLAN, pack
from ..research.fixtures import AJRAKH, evidence_item
from .names import AJRAKH_NAMES, BAGH, KHURJA, MUD_FAMILY, TEXTILE_FAMILY, names_for

ANSWER_ID = uuid.UUID("5e1d2c3b-4a5e-4f60-8b71-2c3d4e5f6a71")
FIGURE_QUOTE = "Mordanting baths of 8 g/L alum were heated to 60 °C"
FIGURE_TEXT = "Ajrakh mordant baths held 8 g/L alum and were heated to 60 °C."
BAGH_PAGE = "https://crafts.example.org/bagh/dhawdi"
BAGH_TEXT = (
    "In Bagh, printers boil the cloth with dhawdi flowers to brighten the red. "
    "Both Ajrakh and Bagh printers mordant the cloth with alum before the madder bath."
)
BAGH_ITEM = evidence_item(
    id=f"searxng:{BAGH_PAGE}",
    adapter="searxng",
    tier="T4",
    sourceType="WEB_PAGE",
    url=BAGH_PAGE,
    title="Dhawdi in Bagh printing",
    doi=None,
    trust="C",
    quotes=[],
)


def two_facet_pack() -> EvidencePack:
    facets = [Facet(type="MATERIAL", target="alum"), Facet(type="MECHANISM", target="alum binding")]
    found = PackedEvidence(
        item=ABSTRACT_ITEM, facet_indexes=(0, 1), found_by=("crossref",), hits=2, best_rank=1
    )
    return pack(
        plan=PLAN.model_copy(update={"facets": facets}),
        coverage=(FacetCoverage(facet_index=0), FacetCoverage(facet_index=1)),
        evidence=(found,),
        documents=(build_document(ABSTRACT_ITEM, ABSTRACT, "ABSTRACT"),),
    )


def bagh_pack() -> EvidencePack:
    found = PackedEvidence(item=BAGH_ITEM, facet_indexes=(0,), found_by=("web",), hits=1, best_rank=1)
    return pack(evidence=(found,), documents=(build_document(BAGH_ITEM, BAGH_TEXT, "FULL_TEXT"),))


def under(heading: str, *sentences: ComposedSentence) -> ComposedAnswer:
    return ComposedAnswer(sections=[ComposedSection(heading=heading, sentences=list(sentences))])


def said(text: str, ref: str, span: str) -> ComposedSentence:
    return ComposedSentence(text=text, evidence_ids=[ref], spans=[QuotedSpan(ref=ref, text=span)])


def written(evidence: EvidencePack, composed: ComposedAnswer, names: CraftNames = AJRAKH_NAMES):
    return write_back_plan(evidence, composed, found_by="ANSWER", answer_id=ANSWER_ID, names=names)


def test_a_section_heading_names_its_discipline() -> None:
    assert section_discipline("The chemistry") == "CHEMISTRY"
    assert section_discipline(DISCIPLINE_TITLES["BOTANY"]) == "BOTANY"
    assert section_discipline("Mordant") is None
    assert section_discipline(None) is None


@pytest.mark.parametrize(
    ("heading", "subject", "field"),
    [
        ("The chemistry", ("MECHANISM", "alum binding"), "CHEMISTRY"),
        ("Materials", ("MATERIAL", "alum"), "MATERIALS"),
        ("Mordant", ("MATERIAL", "alum"), "MATERIALS"),
    ],
)
def test_a_sentence_is_filed_under_the_cited_facet_of_its_section_s_field(
    heading: str, subject: tuple[str, str], field: str
) -> None:
    (claim,) = written(
        two_facet_pack(), under(heading, said(FIGURE_TEXT, ABSTRACT_ITEM.id, FIGURE_QUOTE))
    ).claims
    assert ((claim.subject.concept_type, claim.subject.concept_name), claim.field) == (subject, field)


def test_a_section_s_field_is_kept_when_no_cited_facet_is_of_it() -> None:
    (claim,) = written(
        pack(), under("The chemistry", said(FIGURE_TEXT, ABSTRACT_ITEM.id, FIGURE_QUOTE))
    ).claims
    assert ((claim.subject.concept_type, claim.subject.concept_name), claim.field) == (
        ("MATERIAL", "alum"),
        "CHEMISTRY",
    )
    assert claim.stored_field == "CHEMISTRY"


def test_the_same_sentence_in_two_fields_is_two_facts() -> None:
    chemistry = written(pack(), under("The chemistry", said(FIGURE_TEXT, ABSTRACT_ITEM.id, FIGURE_QUOTE)))
    materials = written(pack(), under("Materials", said(FIGURE_TEXT, ABSTRACT_ITEM.id, FIGURE_QUOTE)))
    assert chemistry.claims[0].dedupe_key != materials.claims[0].dedupe_key


def test_a_sentence_naming_a_compared_craft_is_filed_under_that_craft() -> None:
    sentence = said(
        "Bagh printers boil the cloth with dhawdi flowers.",
        BAGH_ITEM.id,
        "printers boil the cloth with dhawdi flowers",
    )
    (claim,) = written(bagh_pack(), under("Materials", sentence), names_for(AJRAKH, (BAGH,))).claims
    assert claim.craft_slug == BAGH.slug
    by_name = said(
        "Bagh print makers boil the cloth with dhawdi flowers.",
        BAGH_ITEM.id,
        "printers boil the cloth with dhawdi flowers",
    )
    (alone,) = written(bagh_pack(), under("Materials", by_name)).claims
    assert alone.craft_slug == BAGH.slug


def test_a_sentence_naming_two_compared_crafts_or_whose_passage_names_both_is_skipped() -> None:
    both = said(
        "Ajrakh and Bagh printers both mordant the cloth with alum.",
        BAGH_ITEM.id,
        "Both Ajrakh and Bagh printers mordant the cloth with alum",
    )
    plain = said(
        "Printers mordant the cloth with alum before the madder bath.",
        BAGH_ITEM.id,
        "printers mordant the cloth with alum before the madder bath",
    )
    plan = written(bagh_pack(), under("Materials", both, plain), names_for(AJRAKH, (BAGH,)))
    assert [skipped.reason for skipped in plan.skipped] == [SKIP_SEVERAL_CRAFTS, SKIP_SEVERAL_CRAFTS]
    assert (plan.claims, plan.held) == ((), ())


def test_in_a_comparison_material_science_naming_nothing_goes_to_the_shared_family() -> None:
    sentence = said("Mordant baths held 8 g/L alum and were heated to 60 °C.", ABSTRACT_ITEM.id, FIGURE_QUOTE)
    (claim,) = written(pack(), under("Materials", sentence), names_for(AJRAKH, (BAGH,))).claims
    assert (claim.craft_slug, claim.category_slug, claim.field) == (None, TEXTILE_FAMILY.slug, "MATERIALS")
    assert (claim.subject.concept_type, claim.subject.concept_name) == ("PROPERTY", TEXTILE_FAMILY.name)


def test_family_science_is_filed_under_the_family_concept_of_its_field() -> None:
    sentence = said("Mordant baths held 8 g/L alum and were heated to 60 °C.", ABSTRACT_ITEM.id, FIGURE_QUOTE)
    (claim,) = written(pack(), under("The chemistry", sentence)).claims
    assert (claim.craft_slug, claim.category_slug, claim.stored_field) == (
        None,
        TEXTILE_FAMILY.slug,
        "CHEMISTRY",
    )
    assert (claim.subject.concept_type, claim.subject.concept_name) == ("MECHANISM", TEXTILE_FAMILY.name)


def test_the_same_general_sentence_is_one_fact_per_family() -> None:
    sentence = said("Mordant baths held 8 g/L alum and were heated to 60 °C.", ABSTRACT_ITEM.id, FIGURE_QUOTE)
    textiles = written(pack(), under("The chemistry", sentence)).claims[0]
    clay = written(pack(), under("The chemistry", sentence), names_for(AJRAKH, family=MUD_FAMILY)).claims[0]
    assert (textiles.category_slug, clay.category_slug) == (TEXTILE_FAMILY.slug, MUD_FAMILY.slug)
    assert textiles.dedupe_key != clay.dedupe_key


def test_a_sentence_about_a_place_abroad_is_skipped_with_the_reason() -> None:
    sentence = said(
        "In Persian practice, mordant baths held 8 g/L alum and were heated to 60 °C.",
        ABSTRACT_ITEM.id,
        FIGURE_QUOTE,
    )
    plan = written(pack(), under("Materials", sentence))
    assert plan.claims == ()
    assert [skipped.reason for skipped in plan.skipped] == [SKIP_ABROAD.format(places="Persian")]


def test_names_for_another_craft_than_the_research_s_are_refused() -> None:
    with pytest.raises(InvalidInput, match="Khurja-Pottery"):
        written(
            pack(), under("Materials", said(FIGURE_TEXT, ABSTRACT_ITEM.id, FIGURE_QUOTE)), names_for(KHURJA)
        )
