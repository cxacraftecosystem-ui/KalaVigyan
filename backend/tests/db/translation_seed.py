import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.models import Craft, TranslationReader, User
from app.research.monograph_document import MonographDocument
from app.research.page_proposals import PageBundle
from app.research.translation_passages import unit_hash
from app.services.monograph_document import store_document

__all__ = [
    "CRAFT",
    "HINDI_LEDE",
    "HINDI_PLANT",
    "LEDE",
    "NOW",
    "PLANT",
    "SITE",
    "SLUG",
    "bundle",
    "document",
    "hindi",
    "lede_nodes",
    "opened_session",
    "person",
    "units",
]

NOW = datetime(2026, 11, 21, 9, 0, tzinfo=UTC)
SITE = "https://kalavigyan.example"
SLUG = "Translation-Test-Craft"
CRAFT = uuid.UUID("7a000000-0000-4000-8000-000000000001")
LEDE, PLANT, TITLE, YEAR = "u-lede", "u-plant", "masthead-title", "u-year"
HINDI_LEDE = ["कपड़े को नील के घोल में 3 बार ", "रंगा जाता है।"]
HINDI_PLANT = ["रंग ", "Indigofera tinctoria", " से आता है, जो एक ", "झाड़ी है।"]


def lede_nodes(times: str = "3") -> list[Any]:
    cite = {"m": "cite", "key": "c1", "g": ["g1"], "c": ["vat."]}
    return [{"m": "s", "c": [f"The cloth is dyed {times} times in an indigo ", cite]}]


def _plant_nodes() -> list[Any]:
    plant = {"m": "i", "role": "bot", "c": ["Indigofera tinctoria"]}
    cite = {"m": "cite", "key": "c2", "g": ["g1"], "c": ["shrub."]}
    return [{"m": "s", "c": ["The dye comes from ", plant, ", a ", cite]}]


def units(times: str = "3") -> dict[str, dict[str, Any]]:
    return {
        TITLE: {
            "chapter": "opening",
            "tag": "h1",
            "field": None,
            "nodes": ["Translation Test Craft"],
            "claimIds": [],
        },
        LEDE: {
            "chapter": "opening",
            "tag": "p",
            "field": "OVERVIEW",
            "nodes": lede_nodes(times),
            "claimIds": ["c-1"],
        },
        PLANT: {
            "chapter": "made",
            "tag": "p",
            "field": "MATERIALS",
            "nodes": _plant_nodes(),
            "claimIds": ["c-2"],
        },
        YEAR: {"chapter": "history", "tag": "dd", "field": "HISTORY", "nodes": ["1998"], "claimIds": []},
    }


def document(times: str = "3") -> MonographDocument:
    source = {
        "number": 1,
        "title": "A dyer's handbook",
        "fullTitle": None,
        "publisher": None,
        "year": 2020,
        "grade": "A",
        "url": "https://example.org/handbook",
        "extra": None,
        "dossierSourceId": None,
    }
    laid = units(times)
    content = {
        "craftSlug": SLUG,
        "sources": {"g1": source},
        "citations": {"c1": [{"source": "g1", "locator": "p. 4", "quote": "dyed three times"}]},
        "citationClaims": {"c1": ["c-1"], "c2": ["c-2"]},
        "data": {},
        "units": laid,
        "components": [],
        "layout": [{"chapter": unit["chapter"], "kind": "unit", "ref": key} for key, unit in laid.items()],
    }
    return MonographDocument.model_validate(
        {
            "subjectKind": "craft",
            "subjectSlug": SLUG,
            "title": "Translation Test Craft",
            "version": 1,
            "content": content,
            "pageUrl": f"{SITE}/crafts/{SLUG}",
        }
    )


def hindi(key: str, texts: list[str], times: str = "3") -> dict[str, Any]:
    unit = units(times)[key]
    return {"key": key, "source_hash": unit_hash(unit["nodes"], unit["claimIds"]), "texts": texts}


def bundle(*passages: dict[str, Any], task_key: str | None = None) -> PageBundle:
    translation: dict[str, Any] = {"language": "hi", "passages": list(passages)}
    if task_key is not None:
        translation["task_key"] = task_key
    return PageBundle.model_validate({"subject": {"kind": "craft", "slug": SLUG}, "translation": translation})


async def person(session: AsyncSession, role: str, *, reads: tuple[str, ...] = ()) -> User:
    token = uuid.uuid4()
    user = User(
        id=token, name=f"{role.title()} {token.hex[:4]}", email=f"{token.hex[:12]}@example.org", role=role
    )
    session.add(user)
    await session.flush()
    session.add_all([TranslationReader(userId=user.id, language=language) for language in reads])
    await session.flush()
    return user


async def opened_session() -> AsyncIterator[AsyncSession]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            session = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)
            session.add(
                Craft(
                    id=CRAFT,
                    name="Translation Test Craft",
                    slug=SLUG,
                    stateOfOrigin=["Gujarat"],
                    stateOfPractice=["Gujarat"],
                )
            )
            await session.flush()
            await store_document(session, document())
            yield session
            await session.close()
        finally:
            await transaction.rollback()
