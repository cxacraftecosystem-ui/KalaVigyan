from __future__ import annotations

from datetime import UTC, datetime
from functools import partial

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.mcp_scopes import CONTRIBUTE_SCOPE
from app.models import User
from app.research.page_proposals import PageBundle, PageProposalResult
from app.research.upload_links import SlotDeclaration, UploadSlot, UploadStart
from app.services.candidate_sources import proposal_fetcher
from app.services.craft_resolver import CraftIndexStore
from app.services.page_proposals import PageTools, propose_page

from .mcp_picture_tools import START_IMAGE_UPLOAD, StartImageUpload
from .mcp_tool_base import ToolContext
from .proposal_deps import gate_adapters
from .proposal_limits import refuse_tool_when_spent

__all__ = ["page_proposed"]


async def page_proposed(
    session: AsyncSession, bundle: PageBundle, user: User, *, origin: str, site: str
) -> PageProposalResult:
    context = ToolContext(
        session=session, index=CraftIndexStore(), site=site, user=user, scopes=frozenset({CONTRIBUTE_SCOPE})
    )
    async with proposal_fetcher() as fetcher:
        tools = PageTools(
            gates=gate_adapters(user, fetcher),
            fetcher=fetcher,
            start_picture=partial(_started_picture, context),
            spend=partial(_spend, user),
            origin=origin,
            site=site,
        )
        return await propose_page(session, user, bundle, tools=tools, now=datetime.now(UTC))


async def _started_picture(
    context: ToolContext, slot: UploadSlot, declaration: SlotDeclaration | None
) -> UploadStart:
    arguments = StartImageUpload(
        craft_slug=slot.craft_slug, stage_id=slot.stage_id, claim_ids=slot.claim_ids, declaration=declaration
    )
    started = await START_IMAGE_UPLOAD.run(context, arguments)
    return UploadStart.model_validate(started.model_dump())


def _spend(user: User, kind: str) -> None:
    refuse_tool_when_spent(kind, user)
