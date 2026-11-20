from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ExternalFailure, InvalidInput
from app.models import Compound
from app.research.evidence import SearchQuery, SourceAdapter, SourceDocument
from app.research.licences import open_licence
from app.sources.reference.pubchem import PUBCHEM_LICENCE, PubChemCompound

from .source_lookup_models import CompoundLookup, CompoundRecord, EntityLookup, EntityRecord, Hazards
from .source_lookup_sources import CompoundSource

__all__ = [
    "COMPOUNDS_MAX",
    "ENTITIES_MAX",
    "PUBCHEM_GRADE",
    "TAXON_NAME",
    "compound_lookup",
    "entity_lookup",
]

COMPOUNDS_MAX = 3
ENTITIES_MAX = 3
PUBCHEM_GRADE = "A"
TAXON_NAME = "taxon name: "
NOT_FOUND = "not_found"
NO_COMPOUND = "PubChem holds no compound for {query}; try its IUPAC name, a synonym or its formula."
NO_ENTITY = "Wikidata holds no item for {query}; try another name or the item's Q number."
HAZARDS_UNREAD = "PubChem's hazards for CID {cid} could not be read just now; ask again later."


async def compound_lookup(
    session: AsyncSession, source: CompoundSource, *, name: str | None, cid: int | None
) -> CompoundLookup:
    query = str(cid) if cid is not None else name or ""
    if cid is not None:
        one = await source.compound(cid)
        found = [one] if one is not None else []
    else:
        found = await source.compounds(query, COMPOUNDS_MAX)
    if not found:
        raise InvalidInput(NO_COMPOUND.format(query=query))
    notices: list[str] = []
    records = [await _record(session, source, compound, notices) for compound in found[:COMPOUNDS_MAX]]
    return CompoundLookup(query=query, compounds=records, notices=notices)


async def entity_lookup(source: SourceAdapter, *, name: str | None, qid: str | None) -> EntityLookup:
    query = qid or name or ""
    if qid is not None:
        ids = [f"{source.name}:{qid}"]
    else:
        ids = [item.id for item in await source.search(SearchQuery(text=query), ENTITIES_MAX)]
    entities = [
        record for record in [await _entity(source, item_id) for item_id in ids] if record is not None
    ]
    if not entities:
        raise InvalidInput(NO_ENTITY.format(query=query))
    return EntityLookup(query=query, entities=entities)


async def _record(
    session: AsyncSession, source: CompoundSource, compound: PubChemCompound, notices: list[str]
) -> CompoundRecord:
    held = await session.scalar(select(Compound).where(Compound.pubchemCid == compound.cid))
    return CompoundRecord(
        cid=compound.cid,
        title=compound.title,
        formula=compound.formula,
        molecular_weight=compound.molecular_weight,
        iupac_name=compound.iupac_name,
        inchikey=compound.inchikey,
        smiles=compound.smiles,
        url=compound.url,
        licence=PUBCHEM_LICENCE,
        grade=PUBCHEM_GRADE,
        held=held is not None,
        held_name=held.name if held is not None else None,
        synonyms=list(held.synonyms) if held is not None else [],
        hazards=await _hazards(source, compound.cid, notices),
    )


async def _hazards(source: CompoundSource, cid: int, notices: list[str]) -> Hazards | None:
    try:
        document = await source.fetch(f"{source.name}:{cid}:ghs")
    except ExternalFailure as failure:
        if failure.kind != NOT_FOUND:
            notices.append(HAZARDS_UNREAD.format(cid=cid))
        return None
    item = document.item
    return Hazards(
        title=item.title,
        url=item.url,
        publisher=item.publisher,
        licence=item.licence,
        open_licence=open_licence(item.licence),
        attribution=item.attribution,
        lines=document.text.splitlines(),
    )


async def _entity(source: SourceAdapter, item_id: str) -> EntityRecord | None:
    try:
        document = await source.fetch(item_id)
    except ExternalFailure as failure:
        if failure.kind == NOT_FOUND:
            return None
        raise
    return _entity_record(document)


def _entity_record(document: SourceDocument) -> EntityRecord:
    item = document.item
    lines = document.text.splitlines()
    taxon = next((line.removeprefix(TAXON_NAME) for line in lines if line.startswith(TAXON_NAME)), None)
    return EntityRecord(
        qid=item.external_ids.get("wikidata") or item.id.split(":")[-1],
        label=item.title,
        url=item.url,
        licence=item.licence,
        open_licence=open_licence(item.licence),
        grade=item.trust,
        taxon_name=taxon,
        pubchem_cid=item.external_ids.get("pubchem_cid"),
        lines=lines,
    )
