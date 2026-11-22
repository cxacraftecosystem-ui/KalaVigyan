import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Claim, ClaimSource, Concept, Craft, CraftGiRecord

from .open_data_seed import IDS

__all__ = [
    "CATEGORY_CLAIM",
    "FAMILY_CLAIM",
    "OTHER_CLAIM",
    "OTHER_SLUG",
    "OTHER_TEXT",
    "seed_neighbours",
]


def _id(n: int) -> uuid.UUID:
    return uuid.UUID(f"0da7a000-0000-4000-8000-{n:012d}")


OTHER_SLUG = "Open-Data-Neighbour-Craft"
OTHER_TEXT = "Iron darkens the neighbour's cloth."
CATEGORY_NAME = "Open data test category"
OTHER_CRAFT, OTHER_CONCEPT, FAMILY_CONCEPT, CATEGORY_CONCEPT = _id(501), _id(502), _id(503), _id(504)
OTHER_CLAIM, FAMILY_CLAIM, CATEGORY_CLAIM = _id(511), _id(512), _id(513)


async def seed_neighbours(session: AsyncSession) -> None:
    session.add(
        Craft(id=OTHER_CRAFT, name="Open Data Neighbour Craft", slug=OTHER_SLUG, subCategoryId=IDS["family"])
    )
    await session.flush()
    session.add(Concept(id=OTHER_CONCEPT, craftId=OTHER_CRAFT, type="MATERIAL", name="Iron"))
    session.add(Concept(id=FAMILY_CONCEPT, subCategoryId=IDS["family"], type="MATERIAL", name="Madder"))
    session.add(Concept(id=CATEGORY_CONCEPT, type="MECHANISM", name=CATEGORY_NAME))
    await session.flush()
    await _claim(session, OTHER_CLAIM, OTHER_CONCEPT, OTHER_TEXT)
    await _claim(session, FAMILY_CLAIM, FAMILY_CONCEPT, "Madder gives the family's reds.")
    await _claim(session, CATEGORY_CLAIM, CATEGORY_CONCEPT, "Mordants bind dyes to fibres.")
    session.add(
        CraftGiRecord(craftId=OTHER_CRAFT, applicationNumber="998", claimIds=[OTHER_CLAIM, FAMILY_CLAIM])
    )
    await session.flush()


async def _claim(session: AsyncSession, claim_id: uuid.UUID, concept_id: uuid.UUID, text: str) -> None:
    session.add(
        Claim(
            id=claim_id,
            subjectType="CONCEPT",
            subjectId=concept_id,
            predicate="states",
            text=text,
            evidenceLevel="PROVISIONAL",
            origin="IMPORT",
            field="CHEMISTRY",
        )
    )
    await session.flush()
    session.add(ClaimSource(claimId=claim_id, sourceId=IDS["paper"], quoteCheck="NA", relation="DIRECT"))
    await session.flush()
