from __future__ import annotations

import uuid
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.research.blocks import ExplainerSentence
from app.research.citations import AnswerSentence, SourceRef
from app.research.craft_chapters import Borrowed, Chapter, ChapterItem
from app.research.craft_masthead import CiteThis, Masthead, PageSource
from app.research.craft_page import PageClaim, PageDepth
from app.research.craft_parts import SourceListPart
from app.research.datasets import DatasetRef
from app.research.media_refs import MediaRef

from .chapter_ai_media import with_ai_media
from .chapter_chem import chem_chapter
from .chapter_context import ChapterContext
from .chapter_contributed import with_contributed
from .chapter_draft import ChapterDraft
from .chapter_glance import glance_chapter
from .chapter_history import history_chapter
from .chapter_ledger import PageLedger
from .chapter_made import made_chapter, with_loose_differ
from .chapter_market import market_chapter
from .chapter_people import kin_chapter, people_chapter
from .chapter_plates import PicturePlan, picture_plan
from .chapter_prose import piece_sentences
from .chapter_sources import SourceOrigins, page_sources, source_list, sources_chapter
from .chapter_why import why_chapter
from .craft_chapters import admitted_chapters, chapter_title
from .craft_page_answer_assets import with_answer_pieces
from .craft_page_masthead import cite_this, masthead, masthead_place

__all__ = ["PageChapters", "page_chapters"]

SEED = "SEED"
SOURCES = "sources"


@dataclass(frozen=True)
class PageChapters:
    masthead: Masthead
    lede: list[ExplainerSentence]
    chapters: list[Chapter]
    cite: CiteThis | None
    sources: list[PageSource]
    claims: list[PageClaim]


def page_chapters(
    ctx: ChapterContext, parts: Mapping[str, Any], depth: PageDepth, questions: Sequence[str]
) -> PageChapters:
    plan = picture_plan(ctx, parts["pictures"])
    place = masthead_place(ctx, parts["places"])
    head = masthead(ctx, plan.masthead, (depth, parts["events"], parts["places"]))
    curated = ctx.records.curated
    lede = (
        piece_sentences(ctx, curated.overview.lede_piece_id)
        if curated and curated.overview.lede_piece_id
        else []
    )
    refs = _refs(ctx)
    ledger = PageLedger({sid: ref.model_dump(mode="json", by_alias=True) for sid, ref in refs.items()})
    ledger.note([*(head.picture.sentences if head.picture else []), *lede])
    drafts = _drafts(ctx, parts, plan, questions)
    chapters = admitted_chapters(drafts, ledger, place=_district(place), gi=head.gi is not None)
    claims = _listed_claims(ctx, chapters)
    shown = [*_head_sentences(head), *lede, *(s for chapter in chapters for s in chapter.sentences())]
    voiced = [voice.source_id for voice in ctx.records.field_voices.voices]
    origins = _origins(ctx)
    cited = _reading_sources(head, lede, chapters)
    sources = page_sources((shown, cited), (claims, voiced), refs, origins)
    listing = source_list(
        ctx.records.craft.family_label, (sources, _datasets(chapters), list(_pictures(head, chapters)))
    )
    chapters = _with_source_list(chapters, listing)
    cite = (
        cite_this(ctx, place) if any(isinstance(s, AnswerSentence) and s.citations for s in shown) else None
    )
    return PageChapters(head, lede, chapters, cite, sources, claims)


def _drafts(
    ctx: ChapterContext, parts: Mapping[str, Any], plan: PicturePlan, questions: Sequence[str]
) -> list[ChapterDraft]:
    sections = parts["overview"].sections
    drafts: list[ChapterDraft] = [
        glance_chapter(ctx, sections, plan, questions),
        made_chapter(ctx, sections, plan, (parts["process"], parts["sources_differ"])),
        chem_chapter(ctx, sections, plan),
        why_chapter(ctx, sections, plan, (parts["environment"], parts["places"])),
        history_chapter(ctx, sections, plan, (parts["events"], parts["places"])),
        market_chapter(ctx, sections, plan, parts["events"]),
        people_chapter(ctx, plan, parts["communities"]),
        kin_chapter(ctx, plan),
    ]
    drafts = with_loose_differ(ctx, drafts, (parts["process"], parts["sources_differ"]))
    drafts = with_contributed(ctx, drafts)
    drafts = with_ai_media(ctx, drafts)
    drafts = with_answer_pieces(drafts, ctx.rows.answers.pieces, ctx.claims)
    return [*drafts, sources_chapter(ctx, parts["open_questions"])]


def _with_source_list(chapters: list[Chapter], listing: SourceListPart | None) -> list[Chapter]:
    if listing is None:
        return chapters
    item = ChapterItem(block=None, part=listing, figure=None, origin=None, piece_id=None)
    if chapters and chapters[-1].key == SOURCES:
        closing = chapters[-1]
        return [*chapters[:-1], closing.model_copy(update={"items": [item, *closing.items]})]
    return [
        *chapters,
        Chapter(key=SOURCES, title=chapter_title(SOURCES, place=None, gi=False), opener=None, items=[item]),
    ]


def _reading_sources(
    head: Masthead, lede: Sequence[ExplainerSentence], chapters: Sequence[Chapter]
) -> list[str]:
    order = [citation.source_id for citation in (head.gi.citations if head.gi else [])]
    order += [c.source_id for s in [*_head_sentences(head), *lede] for c in s.citations]
    for chapter in chapters:
        order += [c.source_id for plate in chapter.plates() for s in plate.sentences for c in s.citations]
        for item in chapter.items:
            order += item.cited_source_ids()
    return list(dict.fromkeys(order))


def _district(place: str | None) -> str | None:
    return place.split(",")[0].strip() if place else None


def _head_sentences(head: Masthead) -> list[AnswerSentence]:
    return list(head.picture.sentences) if head.picture else []


def _refs(ctx: ChapterContext) -> dict[str, SourceRef]:
    refs: dict[str, SourceRef] = dict(ctx.records.sources)
    if ctx.rows.family is not None:
        refs.update({sid: ref for sid, ref in ctx.rows.family.sources.items() if sid not in refs})
    refs.update({sid: ref for sid, ref in ctx.rows.record_sources.items() if sid not in refs})
    refs.update({sid: ref for sid, ref in ctx.records.field_voices.sources.items() if sid not in refs})
    for stored in ctx.rows.explainers:
        refs.update({sid: ref for sid, ref in stored.sources.items() if sid not in refs})
    refs.update({sid: ref for sid, ref in ctx.rows.answers.sources.items() if sid not in refs})
    for relative in ctx.records.relatives:
        if relative.lede is not None:
            refs.update({ref.id: ref for ref in relative.lede.sources if ref.id not in refs})
    return refs


def _listed_claims(ctx: ChapterContext, chapters: Sequence[Chapter]) -> list[PageClaim]:
    own = [claim for claim in ctx.claims.values() if claim.id in ctx.own]
    family = ctx.rows.family
    if family is None:
        return own
    cited = {
        uuid.UUID(c.claim_id) for chapter in chapters for item in chapter.items for c in item.citations()
    }
    return [*own, *(claim for claim in family.claims if claim.id in cited and claim.id not in ctx.own)]


def _origins(ctx: ChapterContext) -> SourceOrigins:
    family = ctx.rows.family
    borrowed = {}
    if family is not None:
        mark = Borrowed(scope="FAMILY", slug=family.slug, label=family.label)
        borrowed = {sid: mark for sid in family.sources if sid not in ctx.records.sources}
    seeded = {
        c.source_id for claim in ctx.claims.values() if claim.provenance == SEED for c in claim.citations
    }
    kin = {
        ref.id: Borrowed(scope="KIN", slug=relative.craft.slug, label=relative.display_name)
        for relative in ctx.records.relatives
        if relative.lede is not None
        for ref in relative.lede.sources
        if ref.id not in ctx.records.sources
    }
    return SourceOrigins(
        family=borrowed, kin=kin, library=frozenset(seeded), records=frozenset(ctx.rows.record_sources)
    )


def _datasets(chapters: Sequence[Chapter]) -> list[DatasetRef]:
    found: dict[str, DatasetRef] = {}
    for chapter in chapters:
        for item in chapter.items:
            for dataset in getattr(item.block, "datasets", None) or []:
                found.setdefault(dataset.code, dataset)
    return list(found.values())


def _pictures(head: Masthead, chapters: Sequence[Chapter]) -> Iterator[MediaRef]:
    if head.picture is not None:
        yield head.picture.media
    for chapter in chapters:
        for plate in chapter.plates():
            yield plate.media
        for item in chapter.items:
            yield from item.shown_media()
