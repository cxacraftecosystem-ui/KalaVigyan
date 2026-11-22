from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType

from pydantic import ValidationError

from app.core.errors import InvalidInput
from app.research.composition import ComposedAnswer, ComposedSentence
from app.research.evidence import Quote, SourceDocument
from app.research.evidence_pack import EvidencePack, PackedEvidence
from app.research.quotes import QUOTE_OVERLAP_MIN, quote_occurs, quote_overlap, trivial_quote
from app.research.sections import DISCIPLINE_TITLES
from app.research.vocabulary import CONCEPT_TYPE_DISCIPLINES
from app.research.write_back import ClaimWriteBack, FoundBy, WriteBackCitation, WriteBackSubject

from .curation_keys import DISCIPLINE_CONCEPT_TYPES
from .write_back_crafts import CraftFiling, FilingTexts, craft_filing, researched_craft
from .write_back_names import CraftNames
from .write_back_passages import passage_around

__all__ = [
    "INFERRED_REASON",
    "QUOTED_REASON",
    "SECTION_DISCIPLINES",
    "SKIP_BESIDE_STORED",
    "SKIP_UNKEPT",
    "WRITE_BACK_PREDICATE",
    "SkippedSentence",
    "WriteBackPlan",
    "composed_sentences",
    "quote_carries",
    "section_discipline",
    "write_back_plan",
]

WRITE_BACK_PREDICATE = "states"
QUOTED_REASON = "Live research: the sentence rests on verbatim passages that passed the quote check"
INFERRED_REASON = "Live research: model inference from the cited sources without a passing quote"
SKIP_NO_EVIDENCE = "cites stored claims only"
SKIP_UNKEPT = "cites only evidence the write-back could not keep"
SKIP_BESIDE_STORED = "cites a stored fact beside live research, and a new fact would not carry its citations"
SKIP_INVALID = "breaks the write-back contract"
SKIP_FIELD_ONLY = "a field interview alone supports only the speaker's own practice"
SKIP_FIELD_BESIDE = "a field interview supports another discipline only beside an A or B source"
FIELD_ONLY_DISCIPLINES = frozenset({"PROCESS", "MATERIALS", "DESIGN", "ECONOMICS", "SOCIETY"})
FIELD_FOUND_BY = ("field_voices",)
STORED_FOUND_BY = ("stored_passages",)
BESIDE_FIELD_TRUST = frozenset({"A", "B"})
SECTION_DISCIPLINES: Mapping[str, str] = MappingProxyType(
    {title: discipline for discipline, title in DISCIPLINE_TITLES.items()}
)


@dataclass(frozen=True)
class SkippedSentence:
    text: str
    reason: str


@dataclass(frozen=True)
class WriteBackPlan:
    claims: tuple[ClaimWriteBack, ...]
    skipped: tuple[SkippedSentence, ...]
    sentence_keys: tuple[str | None, ...] = ()
    held: tuple[ClaimWriteBack, ...] = ()


@dataclass(frozen=True)
class _Context:
    pack: EvidencePack
    found_by: FoundBy
    answer_id: uuid.UUID | None
    documents: Mapping[str, SourceDocument]
    packed: Mapping[str, PackedEvidence]
    names: CraftNames
    field_ids: frozenset[str] = frozenset()


@dataclass(frozen=True)
class _Filing:
    subject: WriteBackSubject
    field: str | None
    section: str | None
    craft_slug: str | None = None
    category_slug: str | None = None
    held: str | None = None


def write_back_plan(
    pack: EvidencePack,
    answer: ComposedAnswer,
    *,
    found_by: FoundBy,
    answer_id: uuid.UUID | None,
    names: CraftNames,
    field_documents: Mapping[str, SourceDocument] | None = None,
    stored_documents: Mapping[str, SourceDocument] | None = None,
) -> WriteBackPlan:
    lead = pack.plan.craft.slug if pack.plan.craft is not None else None
    if names.lead_slug != lead:
        raise InvalidInput(f"The craft names are for {names.lead_slug!r}, but the research was for {lead!r}")
    context = _context(
        pack,
        names,
        found_by=found_by,
        answer_id=answer_id,
        fields=dict(field_documents or {}),
        stored=dict(stored_documents or {}),
    )
    claims: list[ClaimWriteBack] = []
    skipped: list[SkippedSentence] = []
    keys: list[str | None] = []
    for sentence, heading in composed_sentences(answer):
        planned = _planned(sentence, heading, context)
        if isinstance(planned, SkippedSentence):
            skipped.append(planned)
            keys.append(None)
        else:
            claims.append(planned)
            keys.append(planned.dedupe_key)
    return _plan(_distinct(claims), tuple(skipped), keys)


def _context(
    pack: EvidencePack,
    names: CraftNames,
    *,
    found_by: FoundBy,
    answer_id: uuid.UUID | None,
    fields: dict[str, SourceDocument],
    stored: dict[str, SourceDocument],
) -> _Context:
    packed = {entry.item.id: entry for entry in pack.evidence}
    packed |= _passages_packed(fields, _field_facets(pack) or (0,), FIELD_FOUND_BY)
    packed |= _passages_packed(stored, tuple(range(len(pack.plan.facets))), STORED_FOUND_BY)
    return _Context(
        pack=pack,
        found_by=found_by,
        answer_id=answer_id,
        documents={document.item.id: document for document in pack.documents} | fields | stored,
        packed=packed,
        names=names,
        field_ids=frozenset(fields),
    )


def _plan(
    claims: tuple[ClaimWriteBack, ...], skipped: tuple[SkippedSentence, ...], keys: list[str | None]
) -> WriteBackPlan:
    filed = tuple(claim for claim in claims if claim.held_because is None)
    shown = {claim.dedupe_key for claim in filed}
    return WriteBackPlan(
        claims=filed,
        skipped=skipped,
        sentence_keys=tuple(key if key in shown else None for key in keys),
        held=tuple(claim for claim in claims if claim.held_because is not None),
    )


def composed_sentences(answer: ComposedAnswer) -> Iterable[tuple[ComposedSentence, str | None]]:
    for section in answer.sections:
        for sentence in section.sentences:
            yield sentence, section.heading
    for sentence in answer.open_questions:
        yield sentence, None


def section_discipline(heading: str | None) -> str | None:
    return SECTION_DISCIPLINES.get(heading) if heading else None


def _planned(
    sentence: ComposedSentence, heading: str | None, context: _Context
) -> ClaimWriteBack | SkippedSentence:
    cited = [ref for ref in sentence.evidence_ids if ref in context.documents and ref in context.packed]
    if not cited:
        return SkippedSentence(sentence.text, SKIP_UNKEPT if sentence.evidence_ids else SKIP_NO_EVIDENCE)
    if sentence.claim_ids:
        return SkippedSentence(sentence.text, SKIP_BESIDE_STORED)
    filing = _filing(context, cited, section_discipline(heading))
    craft = _craft(sentence, cited, context, filing)
    refused = craft.refused or _field_refusal(context, cited, filing)
    if refused is not None:
        return SkippedSentence(sentence.text, refused)
    try:
        return _claim(sentence, cited, context, _filed(filing, craft), inferred=heading is None)
    except ValidationError as error:
        return SkippedSentence(sentence.text, f"{SKIP_INVALID}: {_first_error(error)}")


def _craft(sentence: ComposedSentence, cited: list[str], context: _Context, filing: _Filing) -> CraftFiling:
    if all(ref in context.field_ids for ref in cited):
        return researched_craft(context.names)
    return craft_filing(_filing_texts(sentence, cited, context), field=filing.field, names=context.names)


def _filing_texts(sentence: ComposedSentence, cited: list[str], context: _Context) -> FilingTexts:
    quoted = [
        (ref, quote.text) for ref in cited for quote in _passing_quotes(sentence, context.documents[ref])
    ]
    read = [ref for ref in cited if ref not in context.field_ids]
    passages = (passage_around(context.documents[ref].text, quote) for ref, quote in quoted if ref in read)
    return FilingTexts(
        text=sentence.text,
        quotes=tuple(quote for _, quote in quoted),
        passages=tuple(dict.fromkeys(passage for passage in passages if passage)),
        titles=tuple(dict.fromkeys(context.documents[ref].item.title for ref in read)),
    )


def _filed(filing: _Filing, craft: CraftFiling) -> _Filing:
    if craft.family is None or filing.field is None:
        return replace(filing, craft_slug=craft.slug, held=craft.held)
    subject = WriteBackSubject(
        concept_type=DISCIPLINE_CONCEPT_TYPES[filing.field], concept_name=craft.family.name
    )
    return replace(filing, craft_slug=None, category_slug=craft.family.slug, subject=subject)


def _claim(
    sentence: ComposedSentence, cited: list[str], context: _Context, filing: _Filing, *, inferred: bool
) -> ClaimWriteBack:
    citations = [
        citation
        for ref in cited
        for citation in _citations(sentence, context.documents[ref], inferred=inferred)
    ]
    passing = [citation.quote.text for citation in citations if citation.quote is not None]
    quoted = not inferred and quote_overlap(sentence.text, passing) >= QUOTE_OVERLAP_MIN
    return ClaimWriteBack(
        craft_slug=filing.craft_slug,
        category_slug=filing.category_slug,
        held_because=filing.held,
        subject=filing.subject,
        field=filing.field,
        predicate=WRITE_BACK_PREDICATE,
        text=sentence.text,
        label="QUOTED" if quoted else "INFERRED",
        level_reason=QUOTED_REASON if quoted else INFERRED_REASON,
        citations=citations,
        found_by=context.found_by,
        answer_id=context.answer_id,
    )


def _citations(
    sentence: ComposedSentence, document: SourceDocument, *, inferred: bool
) -> list[WriteBackCitation]:
    item = document.item
    quotes = _passing_quotes(sentence, document)
    if not quotes:
        return [WriteBackCitation(evidence=item, quote=None, quote_check="NA", relation="CONTEXTUAL")]
    evidence = item.model_copy(
        update={"quotes": [*item.quotes, *(q for q in quotes if q not in item.quotes)]}
    )
    return [
        WriteBackCitation(
            evidence=evidence,
            quote=quote,
            quote_check="PASS",
            relation="DIRECT" if not inferred and quote_carries(sentence.text, quote) else "CONTEXTUAL",
        )
        for quote in quotes
    ]


def quote_carries(text: str, quote: Quote) -> bool:
    return quote_overlap(text, [quote.text]) >= QUOTE_OVERLAP_MIN


def _passing_quotes(sentence: ComposedSentence, document: SourceDocument) -> list[Quote]:
    item = document.item
    found: list[Quote] = []
    for span in sentence.spans:
        if span.ref != item.id or trivial_quote(span.text) or not quote_occurs(span.text, document.text):
            continue
        quote = next((known for known in item.quotes if known.text == span.text), None) or Quote(
            text=span.text
        )
        if quote not in found:
            found.append(quote)
    return found


def _filing(context: _Context, cited: list[str], section: str | None) -> _Filing:
    facets = context.pack.plan.facets
    order = [ref for ref in cited if ref not in context.field_ids] or cited
    indexes = [index for ref in order for index in context.packed[ref].facet_indexes]
    matching = [i for i in indexes if section and CONCEPT_TYPE_DISCIPLINES.get(facets[i].type) == section]
    facet = facets[(matching or indexes)[0]]
    return _Filing(
        subject=WriteBackSubject(concept_type=facet.type, concept_name=facet.target),
        field=section or CONCEPT_TYPE_DISCIPLINES.get(facet.type),
        section=section,
    )


def _passages_packed(
    passages: Mapping[str, SourceDocument], facets: tuple[int, ...], found_by: tuple[str, ...]
) -> dict[str, PackedEvidence]:
    return {
        key: PackedEvidence(item=document.item, facet_indexes=facets, found_by=found_by, hits=1, best_rank=1)
        for key, document in passages.items()
    }


def _field_facets(pack: EvidencePack) -> tuple[int, ...]:
    return tuple(
        index
        for index, facet in enumerate(pack.plan.facets)
        if CONCEPT_TYPE_DISCIPLINES.get(facet.type) in FIELD_ONLY_DISCIPLINES
    )


def _field_refusal(context: _Context, cited: list[str], filing: _Filing) -> str | None:
    others = [ref for ref in cited if ref not in context.field_ids]
    if len(others) == len(cited):
        return None
    if not others:
        return None if _speakers_practice(context, filing.section) else SKIP_FIELD_ONLY
    if filing.field in FIELD_ONLY_DISCIPLINES:
        return None
    if any(context.documents[ref].item.trust in BESIDE_FIELD_TRUST for ref in others):
        return None
    return SKIP_FIELD_BESIDE


def _speakers_practice(context: _Context, section: str | None) -> bool:
    if section is not None:
        return section in FIELD_ONLY_DISCIPLINES
    return len(_field_facets(context.pack)) == len(context.pack.plan.facets)


def _distinct(claims: list[ClaimWriteBack]) -> tuple[ClaimWriteBack, ...]:
    by_key: dict[str, ClaimWriteBack] = {}
    for claim in claims:
        kept = by_key.get(claim.dedupe_key)
        by_key[claim.dedupe_key] = claim if kept is None else _merged(kept, claim)
    return tuple(by_key.values())


def _merged(kept: ClaimWriteBack, claim: ClaimWriteBack) -> ClaimWriteBack:
    held = kept.held_because if claim.held_because is not None else None
    if kept.label == "INFERRED" and claim.label == "QUOTED":
        return claim.model_copy(
            update={"citations": [*claim.citations, *kept.citations], "held_because": held}
        )
    return kept.model_copy(update={"citations": [*kept.citations, *claim.citations], "held_because": held})


def _first_error(error: ValidationError) -> str:
    details = error.errors()
    return str(details[0]["msg"]) if details else str(error)
