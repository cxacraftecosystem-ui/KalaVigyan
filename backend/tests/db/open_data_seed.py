import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Chunk,
    Claim,
    ClaimSource,
    Concept,
    Craft,
    CraftCategory,
    CraftGiRecord,
    CraftSubCategory,
    CuratedCraft,
    Process,
    ProcessStage,
    Source,
    User,
)

__all__ = [
    "ALUM_QUOTE",
    "CATEGORY",
    "CONTRIBUTOR",
    "FAMILY",
    "HELD",
    "HELD_QUOTE",
    "IDS",
    "RESEARCHER_ONLY",
    "RESTRICTED_ONLY",
    "RETRACTED",
    "SECRET_TITLE",
    "SHOWN",
    "SLUG",
    "TESTIMONY_ONLY",
    "add_claim",
    "seed_open_data",
]


def _id(n: int) -> uuid.UUID:
    return uuid.UUID(f"0da7a000-0000-4000-8000-{n:012d}")


SLUG = "Open-Data-Test-Craft"
FAMILY = "Open-Data-Test-Family"
CATEGORY = "Open-Data-Test-Category"
CONTRIBUTOR = "Zebediah Quillfeather"
SECRET_TITLE = "A letter kept from the public"
ALUM_QUOTE = "alum fixes the madder red on cotton in the second bath"
HELD_QUOTE = "a quote the page no longer holds anywhere"
IDS = {
    name: _id(n)
    for n, name in enumerate(
        (
            "craft",
            "family",
            "category",
            "concept",
            "paper",
            "secret",
            "testimony",
            "chunk",
            "user",
            "process",
            "stage",
            "shown",
            "restricted",
            "testimony_claim",
            "held",
            "retracted",
            "researcher",
            "public_chunk",
        ),
        start=1,
    )
}
SHOWN, RESTRICTED_ONLY, TESTIMONY_ONLY = IDS["shown"], IDS["restricted"], IDS["testimony_claim"]
HELD, RETRACTED, RESEARCHER_ONLY = IDS["held"], IDS["retracted"], IDS["researcher"]
CURATED_AT = datetime(2026, 11, 17, 9, 30, tzinfo=UTC)


async def seed_open_data(session: AsyncSession) -> None:
    await _catalogue(session)
    session.add(
        Source(id=IDS["paper"], kind="PAPER", title="Alum mordants on cotton", licence="CC-BY-4.0", year=2019)
    )
    session.add(Source(id=IDS["secret"], kind="PAPER", title=SECRET_TITLE, sensitivity="RESTRICTED"))
    session.add(Source(id=IDS["testimony"], kind="FIELD_TESTIMONY", title="A printer's own account"))
    await session.flush()
    session.add(Concept(id=IDS["concept"], craftId=IDS["craft"], type="MATERIAL", name="Alum"))
    session.add(
        Chunk(
            id=IDS["chunk"], sourceId=IDS["paper"], ordinal=0, text="For researchers only.", acl="RESEARCHER"
        )
    )
    session.add(
        Chunk(
            id=IDS["public_chunk"], sourceId=IDS["paper"], ordinal=1, text=f"In the dye house {ALUM_QUOTE}."
        )
    )
    session.add(Process(id=IDS["process"], craftId=IDS["craft"], name="Printing"))
    await session.flush()
    session.add(
        ProcessStage(
            id=IDS["stage"], processId=IDS["process"], ordinal=1, name="Mordanting", stageType="MORDANT"
        )
    )
    await _claims(session)
    session.add(_curated_page())
    session.add(CraftGiRecord(craftId=IDS["craft"], applicationNumber="999", claimIds=[SHOWN, RETRACTED]))
    await session.flush()


async def _catalogue(session: AsyncSession) -> None:
    session.add(
        CraftCategory(id=IDS["category"], slug=CATEGORY, name="Open data test category", sortOrder=990)
    )
    session.add(
        User(id=IDS["user"], email="open-data-contributor@example.com", name=CONTRIBUTOR, role="RESEARCHER")
    )
    await session.flush()
    session.add(
        CraftSubCategory(
            id=IDS["family"],
            slug=FAMILY,
            name="Open data test family",
            categoryId=IDS["category"],
            sortOrder=1,
        )
    )
    await session.flush()
    session.add(Craft(id=IDS["craft"], name="Open Data Test Craft", slug=SLUG, subCategoryId=IDS["family"]))


async def _claims(session: AsyncSession) -> None:
    await add_claim(
        session,
        SHOWN,
        "Alum fixes the madder red.",
        cite=(IDS["paper"], ALUM_QUOTE, "PASS", IDS["public_chunk"]),
        createdById=IDS["user"],
    )
    await add_claim(
        session,
        RESTRICTED_ONLY,
        "A restricted measure.",
        cite=(IDS["secret"], "kept from view", "PASS", None),
    )
    await add_claim(
        session, TESTIMONY_ONLY, "A printer said so.", cite=(IDS["testimony"], "my own words", "PASS", None)
    )
    await add_claim(session, HELD, "A held reading of alum.", cite=(IDS["paper"], HELD_QUOTE, "FAIL", None))
    await add_claim(
        session, RETRACTED, "A withdrawn reading.", cite=(IDS["paper"], None, "NA", None), status="RETRACTED"
    )
    await add_claim(
        session, RESEARCHER_ONLY, "A reading for researchers.", cite=(IDS["paper"], None, "NA", IDS["chunk"])
    )


async def add_claim(
    session: AsyncSession, claim_id: uuid.UUID, text: str, *, cite: tuple[Any, ...], **changes: Any
) -> None:
    source_id, quote, check, chunk_id = cite
    session.add(
        Claim(
            id=claim_id,
            subjectType="CONCEPT",
            subjectId=IDS["concept"],
            predicate="states",
            text=text,
            evidenceLevel="PROVISIONAL",
            origin="IMPORT",
            field="CHEMISTRY",
            **changes,
        )
    )
    await session.flush()
    session.add(
        ClaimSource(
            claimId=claim_id,
            sourceId=source_id,
            chunkId=chunk_id,
            quote=quote,
            locator="p. 4" if quote else None,
            quoteCheck=check,
            relation="DIRECT",
        )
    )
    await session.flush()


def _curated_page() -> CuratedCraft:
    page = {
        "craft_slug": SLUG,
        "version": 3,
        "curated_at": CURATED_AT.isoformat(),
        "coverage": "THIN",
        "searched": [],
        "process_id": str(IDS["process"]),
        "craft_concepts": {},
        "overview": {},
        "conflicts": [],
        "open_questions": [],
        "places": [],
        "communities": [],
        "stages": [_stage()],
        "materials": [_material("M01", "Alum", [SHOWN]), _material("M02", "Lime", [RETRACTED])],
        "tools": [],
        "reactions": [_reaction()],
        "glossary": [],
        "pictures": [],
        "environment": [],
        "native_names": [
            {"text": "ફટકડી", "language": "gu", "script": "Gujr", "claim_id": str(SHOWN)},
            {"text": "हटाया", "language": "hi", "script": "Deva", "claim_id": str(HELD)},
        ],
    }
    return CuratedCraft(
        craftId=IDS["craft"], version=3, curatedAt=CURATED_AT, coverage="THIN", digest="a" * 64, page=page
    )


def _stage() -> dict[str, Any]:
    return {
        "key": "P01",
        "stage_id": str(IDS["stage"]),
        "concept_id": str(IDS["concept"]),
        "local_name": None,
        "order": 1,
        "order_claim_id": None,
        "duration": {"text": "a day", "claim_id": str(RETRACTED)},
        "season": None,
        "claim_ids": [str(SHOWN), str(HELD)],
    }


def _material(key: str, name: str, claims: list[uuid.UUID]) -> dict[str, Any]:
    return {
        "key": key,
        "material_id": str(_id(900 + int(key[1:]))),
        "concept_id": str(IDS["concept"]),
        "name": name,
        "kind": "MORDANT",
        "role": "MORDANT",
        "local_names": [],
        "botanical_name": None,
        "pubchem_cid": 24856 if key == "M01" else None,
        "claim_ids": [str(claim) for claim in claims],
    }


def _reaction() -> dict[str, Any]:
    return {
        "key": "R01",
        "reaction_id": None,
        "stage_key": "P01",
        "kind": "COMPLEXATION",
        "reactants": [{"name": "alum", "formula": "KAl(SO4)2"}],
        "products": [],
        "claim_ids": [str(SHOWN)],
    }
