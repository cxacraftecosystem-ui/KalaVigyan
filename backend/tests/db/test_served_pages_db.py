from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.craft_monograph import DocumentAsk, served_document
from app.models import Craft, CraftPageSnapshot
from app.services.served_pages import ServedPages, measure_served

from .page_documents_seed import BARE_SLUG, CATEGORY_SLUG, CRAFT, CRAFT_SLUG, FAMILY_SLUG, seed
from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

BUILT = datetime(2026, 11, 21, 6, tzinfo=UTC)


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        await seed(opened)
        for variant, etag in (("OPEN", "open-etag"), ("RESEARCHER", "researcher-etag")):
            opened.add(
                CraftPageSnapshot(
                    craftId=CRAFT,
                    variant=variant,
                    stamp="s",
                    schemaVersion=1,
                    body={},
                    etag=etag,
                    builtAt=BUILT,
                )
            )
        await opened.flush()
        yield opened


async def test_the_release_records_the_open_page_and_every_document_a_signed_out_reader_is_served(
    session: AsyncSession,
) -> None:
    served = ServedPages()
    await measure_served(session, served, clock=iter(range(100)).__next__)
    assert served.digests[f"page:craft:{CRAFT_SLUG}"] == "open-etag"
    craft = await session.get(Craft, CRAFT)
    assert craft is not None
    route = await served_document(session, craft, DocumentAsk(language="en"))
    assert route is not None and served.digests[f"document:craft:{CRAFT_SLUG}"] == route.etag
    assert f"document:craft:{FAMILY_SLUG}" in served.digests
    assert f"document:category:{CATEGORY_SLUG}" in served.digests
    assert f"document:craft:{BARE_SLUG}" not in served.digests
    owners = {f"craft:{CRAFT_SLUG}", f"craft:{FAMILY_SLUG}", f"category:{CATEGORY_SLUG}"}
    assert owners <= set(served.measured) and not owners & served.unmeasured
    assert all(took == 1 for took in served.measured.values())
