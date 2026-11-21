import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AdminDistrict,
    AdminState,
    ArticleSection,
    Claim,
    ClaimSource,
    Concept,
    Craft,
    CraftCategory,
    CraftLocation,
    CraftSubCategory,
    KnowledgePiece,
    KnowledgePieceSubject,
    Source,
)

__all__ = [
    "AZAMGARH",
    "CLAY_COLOURS",
    "GUJARAT",
    "KACHCHH",
    "KACHCHH_RIVER",
    "KUTCH_CATEGORY_SLUG",
    "KUTCH_SLUG",
    "MONOGRAPH",
    "RAINFALL",
    "SHARED_PLAYER",
    "UP_CATEGORY_SLUG",
    "UP_SLUG",
    "UTTAR_PRADESH",
    "delivered_pieces",
    "seed",
]

GUJARAT, UTTAR_PRADESH = 24, 9
KACHCHH, AZAMGARH = 449, 123
KUTCH_CRAFT = uuid.UUID("9e1a0000-0000-4000-8000-000000000001")
UP_CRAFT = uuid.UUID("9e1a0000-0000-4000-8000-000000000002")
KUTCH_CATEGORY = uuid.UUID("9e1a0000-0000-4000-8000-000000000003")
UP_CATEGORY = uuid.UUID("9e1a0000-0000-4000-8000-000000000004")
KUTCH_SHELF = uuid.UUID("9e1a0000-0000-4000-8000-000000000005")
UP_SHELF = uuid.UUID("9e1a0000-0000-4000-8000-000000000006")
CLAY = uuid.UUID("9e1a0000-0000-4000-8000-000000000007")
PAPER = uuid.UUID("9e1a0000-0000-4000-8000-000000000008")
CLAIM = uuid.UUID("9e1a0000-0000-4000-8000-000000000009")
KUTCH_SLUG = "Places-Test-Kutch-Print"
UP_SLUG = "Places-Test-Azamgarh-Pottery"
KUTCH_CATEGORY_SLUG = "Places-Test-Kutch-Category"
UP_CATEGORY_SLUG = "Places-Test-Azamgarh-Category"
MONOGRAPH = "Places-Test-Monograph"
RAINFALL = "shared/climate/places-test-kachchh-rainfall"
SHARED_PLAYER = "shared/chemistry/places-test-clay-firing"
KACHCHH_RIVER = "shared/chemistry/places-test-a-river-water"
CLAY_COLOURS = "shared/chemistry/places-test-clay-colours"
SECTION_FIELDS = ("CHEMISTRY", "PROCESS", "MATERIALS")
CLAIM_TEXT = "The clay darkens as it is fired in a closed kiln."


async def seed(session: AsyncSession) -> None:
    await _places(session)
    await _subjects(session)
    await _facts(session)
    await _pieces(session)


async def _places(session: AsyncSession) -> None:
    await session.merge(AdminState(lgd=GUJARAT, name="Gujarat"))
    await session.merge(AdminState(lgd=UTTAR_PRADESH, name="Uttar Pradesh"))
    await session.flush()
    await session.merge(AdminDistrict(lgd=KACHCHH, stateLgd=GUJARAT, name="Kachchh"))
    await session.merge(AdminDistrict(lgd=AZAMGARH, stateLgd=UTTAR_PRADESH, name="Azamgarh"))
    await session.flush()


async def _subjects(session: AsyncSession) -> None:
    await _shelves(session)
    session.add_all(
        [
            Craft(
                id=KUTCH_CRAFT,
                slug=KUTCH_SLUG,
                name="Places Test Kutch Print",
                subCategoryId=KUTCH_SHELF,
                stateOfPractice=["Gujarat"],
            ),
            Craft(
                id=UP_CRAFT,
                slug=UP_SLUG,
                name="Places Test Azamgarh Pottery",
                subCategoryId=UP_SHELF,
                stateOfPractice=["Uttar Pradesh"],
            ),
        ]
    )
    await session.flush()
    session.add_all(
        [
            _located(KUTCH_CRAFT, KACHCHH),
            _located(UP_CRAFT, AZAMGARH),
            _located(UP_CRAFT, KACHCHH),
        ]
    )
    await session.flush()


async def _shelves(session: AsyncSession) -> None:
    session.add_all(
        [
            CraftCategory(
                id=KUTCH_CATEGORY, slug=KUTCH_CATEGORY_SLUG, name="Places Test Kutch", sortOrder=991
            ),
            CraftCategory(id=UP_CATEGORY, slug=UP_CATEGORY_SLUG, name="Places Test Azamgarh", sortOrder=992),
        ]
    )
    await session.flush()
    session.add_all(
        [
            CraftSubCategory(
                id=KUTCH_SHELF, slug="places-test-kutch", name="Kutch", categoryId=KUTCH_CATEGORY, sortOrder=1
            ),
            CraftSubCategory(
                id=UP_SHELF, slug="places-test-up", name="Azamgarh", categoryId=UP_CATEGORY, sortOrder=1
            ),
        ]
    )
    await session.flush()


def _located(craft_id: uuid.UUID, district: int) -> CraftLocation:
    return CraftLocation(
        id=uuid.uuid4(),
        craftId=craft_id,
        precision="DISTRICT",
        districtLgd=district,
        evidenceLevel="PROVISIONAL",
    )


async def _facts(session: AsyncSession) -> None:
    session.add(Concept(id=CLAY, craftId=UP_CRAFT, type="MATERIAL", name="Places test clay"))
    session.add(Source(id=PAPER, kind="PAPER", title="Fired clay", url="https://example.org/clay", year=2020))
    await session.flush()
    session.add(
        Claim(
            id=CLAIM,
            subjectType="CONCEPT",
            subjectId=CLAY,
            predicate="states",
            text=CLAIM_TEXT,
            evidenceLevel="PROVISIONAL",
            origin="IMPORT",
            field="CHEMISTRY",
        )
    )
    await session.flush()
    session.add(
        ClaimSource(claimId=CLAIM, sourceId=PAPER, quote="clay darkens", locator="p. 2", quoteCheck="PASS")
    )
    await session.flush()
    sections = [
        _section(field, craftId=craft) for craft in (KUTCH_CRAFT, UP_CRAFT) for field in SECTION_FIELDS
    ]
    sections += [_section("OVERVIEW", categoryId=category) for category in (KUTCH_CATEGORY, UP_CATEGORY)]
    session.add_all(sections)
    await session.flush()


def _section(field: str, **subject: Any) -> ArticleSection:
    sentences = [{"text": CLAIM_TEXT, "claimIds": [str(CLAIM)]}]
    return ArticleSection(field=field, version=1, status="PUBLISHED", sentences=sentences, **subject)


def _piece(label: str, kind: str, facet: str, title: str) -> KnowledgePiece:
    return KnowledgePiece(
        craftId=None,
        kind=kind,
        facet=facet,
        topicKey=f"monograph:{label}",
        language="en",
        depth="EXPERT",
        payload={"monograph": MONOGRAPH, "anchor": None, "chapter": "why", "units": []},
        claimIds=[CLAIM],
        sourceIds=[str(PAPER)],
        contentHash=uuid.uuid4().hex + uuid.uuid4().hex,
        label=label,
        title=title,
        description=f"{title}, drawn from the cited records.",
        fields=[],
    )


def _delivered(label: str, title: str, unit: str) -> KnowledgePiece:
    piece = _piece(label, "fact_table", "CHEMISTRY", title)
    piece.payload = {"delivered": {"spec": {}, "units": {"u5001": {"text": unit, "claimIds": []}}}}
    return piece


async def delivered_pieces(session: AsyncSession) -> None:
    river = _delivered(
        KACHCHH_RIVER, "Water hardness by month", "Well water at Ajrakhpur in Kachchh, by month."
    )
    colours = _delivered(CLAY_COLOURS, "Clay colours by firing", "The colour of the clay after each firing.")
    session.add_all([river, colours])
    await session.flush()
    session.add_all(
        KnowledgePieceSubject(pieceId=piece.id, kind="CONCEPT", conceptId=CLAY) for piece in (river, colours)
    )
    await session.flush()


async def _pieces(session: AsyncSession) -> None:
    rainfall = _piece(RAINFALL, "chart", "CLIMATE", "Kachchh annual rainfall")
    player = _piece(SHARED_PLAYER, "reaction_player", "CHEMISTRY", "Clay firing player")
    session.add_all([rainfall, player])
    await session.flush()
    session.add_all(
        [
            KnowledgePieceSubject(pieceId=rainfall.id, kind="PLACE", placeKey=f"lgd:{KACHCHH}"),
            KnowledgePieceSubject(pieceId=rainfall.id, kind="CONCEPT", conceptId=CLAY),
            KnowledgePieceSubject(pieceId=player.id, kind="CONCEPT", conceptId=CLAY),
        ]
    )
    await session.flush()
