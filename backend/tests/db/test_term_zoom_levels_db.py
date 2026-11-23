import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Craft, Term, TermCraft
from app.services.term_scales import fill_zoom_levels
from app.services.zoom_pictures import LevelTerm
from app.services.zoom_story import level_terms

from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db


def key(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-term-zoom-levels/{name}")


CRAFT = key("craft")


def term(name: str, label: str, level: str | None, *local: str) -> Term:
    return Term(
        id=key(f"term/{name}"),
        key=f"test-zoom-{name}",
        label=label,
        zoomLevel=level,
        localNames=list(local),
        aliases=[],
    )


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        opened.add_all(
            [
                Craft(id=CRAFT, slug="Zoom-Levels-Test-Print", name="Zoom Levels Test Print"),
                term("cloth", "Cotton cloth", "CLOTH", "mulmul"),
                term("molecule", "Alizarin", "MOLECULE"),
                term("plain", "Kut", None),
                term("elsewhere", "Base fabric", "CLOTH"),
            ]
        )
        await opened.flush()
        opened.add_all(
            [TermCraft(termId=key(f"term/{name}"), craftId=CRAFT) for name in ("cloth", "molecule", "plain")]
        )
        await opened.flush()
        yield opened


async def test_the_zoom_reads_the_picture_level_tags_of_its_craft_s_glossary_terms(
    session: AsyncSession,
) -> None:
    assert await level_terms(session, CRAFT) == (
        LevelTerm(level="CLOTH", label="Cotton cloth", surfaces=("Cotton cloth", "mulmul")),
    )


async def test_an_untagged_term_whose_stored_definition_states_its_scale_is_filled(
    session: AsyncSession,
) -> None:
    lace = term("lace", "Lace", None)
    lace.meaning = "openwork fabric, patterned with open holes in the work"
    session.add(lace)
    await session.flush()
    assert await fill_zoom_levels(session) >= 1
    rows = await session.execute(
        select(Term.key, Term.zoomLevel).where(
            Term.id.in_([key("term/lace"), key("term/plain"), key("term/molecule")])
        )
    )
    assert dict(rows.tuples().all()) == {
        "test-zoom-lace": "CLOTH",
        "test-zoom-plain": None,
        "test-zoom-molecule": "MOLECULE",
    }


async def test_a_tag_outside_the_zoom_s_term_levels_is_refused(session: AsyncSession) -> None:
    session.add(term("district", "Kachchh", "DISTRICT"))
    with pytest.raises(IntegrityError):
        await session.flush()
