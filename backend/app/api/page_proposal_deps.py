from __future__ import annotations

import uuid
from datetime import UTC, datetime
from functools import partial

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.mcp_scopes import CONTRIBUTE_SCOPE
from app.models import User
from app.research.page_proposals import ACCEPTED, STRUCTURE, PageBundle, PageProposalResult, PartReport
from app.services.candidate_sources import proposal_fetcher
from app.services.craft_resolver import CraftIndexStore
from app.services.page_proposals import PageTools, propose_page
from app.services.written_vectors import embed_structure_claims

from .mcp_picture_tools import start_picture
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
            start_picture=partial(start_picture, context),
            spend=partial(_spend, user),
            origin=origin,
            site=site,
        )
        result = await propose_page(session, user, bundle, tools=tools, now=datetime.now(UTC))
    await embed_structure_claims(session, tools.gates.embed, _written_structures(result.parts))
    return result


def _written_structures(parts: list[PartReport]) -> list[uuid.UUID]:
    kept = (part for part in parts if part.part == STRUCTURE and part.outcome == ACCEPTED)
    return [uuid.UUID(part.id) for part in kept if part.id]


async def _spend(user: User, kind: str) -> None:
    await refuse_tool_when_spent(kind, user)
