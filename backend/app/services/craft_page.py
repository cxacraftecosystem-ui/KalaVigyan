from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Any

from app.models.enums import DISCIPLINES
from app.research.blocks import ProseBlock
from app.research.citations import Citation, SourceRef
from app.research.craft_page import (
    CRAFT_PAGE_SCHEMA_VERSION,
    CraftPage,
    CurationHeader,
    KeyFact,
    OverviewSection,
    PageClaim,
    PageCraft,
    PageOverview,
    PageSentence,
    SearchedFor,
    SubjectRef,
)
from app.research.craft_page_context import LocalName
from app.research.knowledge_pieces import KnowledgePiece
from app.research.sections import DISCIPLINE_TITLES
from app.research.vocabulary import CONCEPT_TYPE_DISCIPLINES, LEVEL_ORDER, weakest_level

from .chapter_assembly import page_chapters
from .chapter_context import ChapterContext, ChapterRows
from .craft_page_context import (
    page_depth,
    page_environment,
    page_events,
    page_gi,
    page_tabs,
)
from .craft_page_evidence import page_evidence, stored_overview_sections
from .craft_page_family import family_place, suggested_questions
from .craft_page_parts import (
    Visible,
    page_communities,
    page_differ,
    page_glossary,
    page_pictures,
    page_places,
    page_process,
    page_questions,
)
from .craft_page_records import ClaimFacts, CraftPageRecords
from .curated_index import CuratedPage
from .knowledge_view import ClaimView

__all__ = [
    "CONCEPT_SUBJECT_KINDS",
    "ORIGIN_PROVENANCES",
    "chapter_context",
    "craft_page",
    "page_claims",
]

CURATED = "CURATED"
HYPOTHESIS = "HYPOTHESIS"
FALLBACK_DISCIPLINE = "OVERVIEW"
CONCEPT_SUBJECT_KINDS: Mapping[str, str] = MappingProxyType(
    {"PROCESS_STAGE": "STAGE", "MATERIAL": "MATERIAL", "TOOL": "TOOL", "TRADITION": "CRAFT"}
)
ORIGIN_PROVENANCES: Mapping[str, str] = MappingProxyType(
    {
        "IMPORT": "SEED",
        "RESEARCHER": "RESEARCHER",
        "ENRICHMENT": "FROM_ANSWERS",
        "MODEL": "FROM_ANSWERS",
        "LIVE_RESEARCH": "FROM_ANSWERS",
        "CONTRIBUTION": "RESEARCHER",
    }
)


def chapter_context(records: CraftPageRecords, rows: ChapterRows | None = None) -> ChapterContext:
    claims = page_claims(records)
    visible = _visible(claims)
    found = rows or ChapterRows()
    known = {claim.id: claim for claim in [*(found.family.claims if found.family else ()), *claims]}
    return ChapterContext(records, found, known, visible, frozenset(claim.id for claim in claims))


def craft_page(records: CraftPageRecords, rows: ChapterRows | None = None) -> CraftPage:
    claims = page_claims(records)
    visible = _visible(claims)
    curated = records.curated
    craft = _named_in_its_scripts(records.craft, curated, visible)
    parts = _parts(records, claims, visible)
    process, pictures = parts["process"], parts["pictures"]
    sources = _sources(claims, records.sources)
    place = family_place(craft.category_name, craft.sub_category_name)
    depth = page_depth(curated, claims, (len(sources), len(process.stages), len(pictures)))
    questions = suggested_questions(place, craft.display_name, catch_all=records.catch_all)
    ctx = chapter_context(records, rows)
    built = page_chapters(ctx, parts, depth, questions)
    return CraftPage(
        schema_version=CRAFT_PAGE_SCHEMA_VERSION,
        craft=craft,
        curated=curated is not None,
        curation=_header(curated),
        depth=depth,
        suggested_questions=questions,
        masthead=built.masthead,
        lede=built.lede,
        chapters=built.chapters,
        cite=built.cite,
        evidence=page_evidence(built.claims),
        claims=built.claims,
        sources=built.sources,
        field_voices_total=records.field_voices.totals,
        tabs=page_tabs(process, records.offers, sources=bool(sources), evidence=bool(claims)),
        same_family=list(records.relatives),
        voices=list(records.field_voices.voices),
        field_photos=list(records.field_voices.photos),
        **parts,
    )


def _named_in_its_scripts(craft: PageCraft, curated: CuratedPage | None, visible: Visible) -> PageCraft:
    names = [
        LocalName(name=name.text, language=name.language, script=name.script, claim_ids=[name.claim_id])
        for name in (curated.native_names if curated else [])
        if visible.all_shown([name.claim_id])
    ]
    return craft.model_copy(update={"local_names": names}) if names else craft


def _visible(claims: Sequence[PageClaim]) -> Visible:
    return Visible(
        levels={claim.id: claim.level for claim in claims},
        order={claim.id: index for index, claim in enumerate(claims)},
        disciplines={claim.id: claim.discipline for claim in claims},
    )


def _parts(records: CraftPageRecords, claims: Sequence[PageClaim], visible: Visible) -> dict[str, Any]:
    curated = records.curated
    differ = page_differ(curated, visible)
    places = page_places(curated, visible)
    return {
        "overview": _overview(records, claims, visible),
        "gi_card": page_gi(records.craft.gi_status, records.market.gi, visible),
        "events": page_events(records.market, claims, visible, curated=curated is not None),
        "environment": page_environment(curated, visible, places),
        "sources_differ": differ,
        "places": places,
        "communities": page_communities(curated, visible, places),
        "process": page_process(records, visible, differ),
        "glossary": page_glossary(records, visible),
        "pictures": page_pictures(records, visible),
        "open_questions": page_questions(curated, visible),
    }


def page_claims(records: CraftPageRecords) -> list[PageClaim]:
    kinds = records.curated.concept_kinds() if records.curated else {}
    claims = [_claim(view, records.facts[view.id], kinds, records.craft.name) for view in records.views]
    return sorted(
        claims, key=lambda c: (DISCIPLINES.index(c.discipline), LEVEL_ORDER[c.level], c.text, str(c.id))
    )


def _claim(view: ClaimView, facts: ClaimFacts, kinds: Mapping[uuid.UUID, str], craft_name: str) -> PageClaim:
    concept_type = facts.concept_type or ""
    discipline = facts.discipline or CONCEPT_TYPE_DISCIPLINES.get(concept_type, FALLBACK_DISCIPLINE)
    if facts.concept_name is None:
        subject = SubjectRef(id=None, name=craft_name, kind="CRAFT")
    else:
        kind = kinds.get(view.concept_id) or CONCEPT_SUBJECT_KINDS.get(concept_type, "CONCEPT")
        subject = SubjectRef(id=view.concept_id, name=facts.concept_name, kind=kind)
    return PageClaim(
        id=view.id,
        text=view.text,
        level=view.level,
        discipline=discipline,
        subject=subject,
        provenance=CURATED if facts.discipline else ORIGIN_PROVENANCES[facts.origin],
        sources_differ=facts.sources_differ,
        citations=[Citation.model_validate(citation) for citation in view.citations],
    )


def _header(curated: CuratedPage | None) -> CurationHeader | None:
    if curated is None:
        return None
    return CurationHeader(
        version=curated.version,
        curated_at=curated.curated_at,
        coverage=curated.coverage,
        searched=[SearchedFor(query=item.query, site=item.site) for item in curated.searched],
    )


def _overview(records: CraftPageRecords, claims: Sequence[PageClaim], visible: Visible) -> PageOverview:
    curated = records.curated
    if curated is None:
        return PageOverview(lede=[], key_facts=[], sections=stored_overview_sections(claims))
    lede = records.pieces.get(curated.overview.lede_piece_id) if curated.overview.lede_piece_id else None
    sections = []
    for section in curated.overview.sections:
        sentences = _piece_sentences(records.pieces.get(section.piece_id), visible)
        if sentences:
            sections.append(
                OverviewSection(
                    discipline=section.discipline,
                    title=DISCIPLINE_TITLES[section.discipline],
                    basis=CURATED,
                    sentences=sentences,
                )
            )
    facts = [
        KeyFact(label=fact.label, value=fact.value, claim_ids=fact.claim_ids)
        for fact in curated.overview.key_facts
        if visible.all_shown(fact.claim_ids)
    ]
    return PageOverview(lede=_piece_sentences(lede, visible), key_facts=facts, sections=sections)


def _piece_sentences(piece: KnowledgePiece | None, visible: Visible) -> list[PageSentence]:
    if piece is None or not isinstance(piece.payload, ProseBlock):
        return []
    shown = []
    for sentence in piece.payload.sentences:
        claim_ids = list(dict.fromkeys(uuid.UUID(citation.claim_id) for citation in sentence.citations))
        if not visible.all_shown(claim_ids):
            continue
        level = weakest_level(visible.levels[claim_id] for claim_id in claim_ids)
        if level != HYPOTHESIS:
            shown.append(
                PageSentence(
                    id=sentence.id, text=sentence.text, level=level, claim_ids=claim_ids, terms=sentence.terms
                )
            )
    return shown


def _sources(claims: Sequence[PageClaim], known: Mapping[str, SourceRef]) -> list[SourceRef]:
    ordered = dict.fromkeys(citation.source_id for claim in claims for citation in claim.citations)
    return [known[source_id] for source_id in ordered if source_id in known]
