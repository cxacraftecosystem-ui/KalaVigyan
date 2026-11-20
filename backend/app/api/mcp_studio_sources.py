from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import Field

from app.core.errors import InvalidInput
from app.core.mcp_scopes import CONTRIBUTE_SCOPE
from app.core.rate_limit import FACT_PROPOSALS
from app.research.supplied_sources import SuppliedSourceReply
from app.services import page_drafts, supplied_sources
from app.services.supplied_sources_identity import scholarly_lookup
from app.services.supplied_sources_views import slot_path, supplied_reply

from .mcp_studio_arguments import STUDIO_DOES, SupplySourceArguments
from .mcp_tool_base import SOURCES, WRITES, Tool, ToolContext, contributor
from .oauth_hosts import endpoints_or_none
from .proposal_limits import refuse_tool_when_spent

__all__ = ["STUDIO_SOURCE_TOOLS", "SUPPLY_SOURCE", "SuppliedReply"]

NO_UPLOADS = "Files cannot be uploaded to this server; give the source's passages or its whole text instead."
DESCRIPTION = (
    "Give KalaVigyan a source your own reach opened and its fetcher cannot: a paywalled paper read through your "
    "subscription or library, a book or PDF you hold, an archive, or a site that refuses automated reading. Give "
    "its identity (DOI, ISBN or url, title, authors, year, publisher), how and when you read it, and its words: "
    "the passages you will quote with their locators, the whole text, or upload pdf (or text) for a private slot "
    "to PUT the file to. The identity is looked up in Crossref, OpenAlex and Semantic Scholar and the source is "
    "graded by the rubric (a confirmed paper or book A, a work found nowhere C at most). The text is kept "
    "privately for reviewers, hashed, and never shown or republished: pages show only short cited quotes. Cite it "
    "in a fact's sources as cite_as gives it: the QUOTES gate checks each quote verbatim against your text (test "
    "them first with read_source's quotes), and the review queue shows that the fact rests on text you supplied. "
    "Counts against the hour's fact proposals, like a source proposal."
)


class SuppliedReply(SuppliedSourceReply):
    draft_id: uuid.UUID | None = None
    notices: list[str] = Field(default_factory=list)


async def _supply_source(context: ToolContext, arguments: SupplySourceArguments) -> SuppliedReply:
    user = contributor(context, "supply_source", STUDIO_DOES)
    endpoints = endpoints_or_none()
    if arguments.upload is not None and endpoints is None:
        raise InvalidInput(NO_UPLOADS)
    refuse_tool_when_spent(FACT_PROPOSALS, user)
    now = datetime.now(UTC)
    async with scholarly_lookup(context.session) as lookup:
        supplied = await supplied_sources.supply_source(
            context.session, user, arguments.supplied(), lookup=lookup, now=now
        )
    if arguments.draft_id is not None:
        await page_drafts.attach_supplied(context.session, user, arguments.draft_id, supplied.row.id, now=now)
    upload_url = None
    if supplied.slot_token is not None and endpoints is not None:
        upload_url = f"{endpoints.issuer.rstrip('/')}{slot_path(supplied.slot_token)}"
    reply = supplied_reply(supplied.row, upload_url)
    return SuppliedReply.model_validate(
        {**reply.model_dump(), "draftId": arguments.draft_id, "notices": arguments.notices()}
    )


SUPPLY_SOURCE = Tool(
    "supply_source",
    "Supply a source you can read",
    DESCRIPTION,
    SupplySourceArguments,
    SuppliedReply,
    _supply_source,
    scope=CONTRIBUTE_SCOPE,
    annotations=WRITES,
    group=SOURCES,
)

STUDIO_SOURCE_TOOLS = (SUPPLY_SOURCE,)
