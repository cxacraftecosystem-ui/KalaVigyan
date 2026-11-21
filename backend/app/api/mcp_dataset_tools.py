from __future__ import annotations

from datetime import UTC, datetime

from pydantic import Field

from app.core.errors import ExternalFailure, InvalidInput
from app.core.mcp_scopes import CONTRIBUTE_SCOPE
from app.core.rate_limit import COMPONENT_PROPOSALS
from app.research.dataset_proposals import DatasetProposal, DatasetReply, DatasetUploadStart, upload_url
from app.services.candidate_sources import proposal_fetcher
from app.services.dataset_proposals import issue_dataset_slot, proposal_problems

from .mcp_argument_names import SnakeBodyArguments
from .mcp_tool_base import OPEN_WRITES, PROPOSING, Tool, ToolContext, contributor
from .oauth_hosts import endpoints_or_none
from .proposal_limits import refuse_tool_when_spent

__all__ = ["DATASET_TOOLS", "PROPOSE_DATASET", "ProposeDataset"]

DESCRIPTION = (
    "Propose an open dataset whose rows a component draws: its record (code, title, publisher, edition, version, "
    "period, native_resolution, crs, licence with licence_url, attribution, redistributable, citation with doi, "
    "landing_url, url of the file, and the file's sha256). The gates check the licence is open and redistributable, "
    "the code is new and the landing page is reachable, then return a single-use upload slot: PUT the CSV file "
    "(UTF-8, a header row, at most 20000 rows) to upload_url within 30 minutes and its SHA-256 is checked before "
    "the table is stored. A chart, fact_table or map_layer then names the dataset's code as dataset and each "
    "value's row and column as its cell, and the gates check every value against its stored row."
)
UPLOADS_OFF = "Dataset uploads are not open on this server right now."
CHECKS_UNAVAILABLE = (
    "The checks could not run just now and nothing was stored; call propose_dataset again later."
)
UPLOAD_STEP = "PUT the CSV file to upload_url (curl -T file.csv <upload_url>) before the slot expires."
REFUSED = "The dataset was not taken: {problems}."


class ProposeDataset(SnakeBodyArguments):
    proposal: DatasetProposal = Field(description="The dataset's record, as the datasets guide lists it")


async def _propose(context: ToolContext, arguments: ProposeDataset) -> DatasetReply:
    user = contributor(context, "propose_dataset", "propose datasets")
    refuse_tool_when_spent(COMPONENT_PROPOSALS, user)
    proposal = arguments.proposal
    endpoints = endpoints_or_none()
    if endpoints is None:
        raise InvalidInput(UPLOADS_OFF)
    try:
        async with proposal_fetcher() as fetcher:
            problems = await proposal_problems(context.session, fetcher, proposal)
    except ExternalFailure:
        raise InvalidInput(CHECKS_UNAVAILABLE) from None
    if problems:
        return DatasetReply(
            code=proposal.code, outcome="REFUSED", message=REFUSED.format(problems="; ".join(problems))
        )
    issued = await issue_dataset_slot(context.session, user, proposal, now=datetime.now(UTC))
    upload = DatasetUploadStart(
        upload_url=upload_url(endpoints.issuer, issued.token), expires_at=issued.expires_at
    )
    return DatasetReply(code=proposal.code, outcome="UPLOAD", message=UPLOAD_STEP, upload=upload)


PROPOSE_DATASET = Tool(
    name="propose_dataset",
    title="Propose a dataset",
    description=DESCRIPTION,
    arguments=ProposeDataset,
    output=DatasetReply,
    run=_propose,
    scope=CONTRIBUTE_SCOPE,
    annotations=OPEN_WRITES,
    group=PROPOSING,
)

DATASET_TOOLS = (PROPOSE_DATASET,)
