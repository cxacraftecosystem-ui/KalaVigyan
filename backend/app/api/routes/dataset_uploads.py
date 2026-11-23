from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.multipart_form import BodyTooLarge, limited_body
from app.api.public_deps import counted_anonymous_read
from app.core.db import get_session
from app.core.errors import InvalidInput
from app.research.dataset_proposals import TABLE_BYTES_MAX, DatasetReply
from app.services import dataset_proposals as proposals

router = APIRouter(prefix="/dataset-uploads", tags=["contributions"])

SlotToken = Annotated[str, Path(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9_-]+$")]
NOT_FOUND_DETAIL = "No upload slot has this address."
TOO_LARGE_DETAIL = f"A table or a layer is at most {TABLE_BYTES_MAX // (1024 * 1024)} MB."
STORED = "The dataset and its table are stored; cite its rows from a component's spec by the dataset's code."
LAYER_STORED = (
    "The dataset and its layer are stored for a reviewer: once approved, an engineer adds it to the site's maps "
    "through tools/maplayers. It is drawn nowhere until then."
)


@router.put("/{token}")
async def fill_dataset_upload(
    token: SlotToken, request: Request, session: AsyncSession = Depends(get_session)
) -> DatasetReply:
    await counted_anonymous_read(request)
    data = await _body(request)
    try:
        stored = await proposals.fill_dataset_slot(session, token, data, now=datetime.now(UTC))
    except proposals.UnknownSlot as missing:
        await session.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND_DETAIL) from missing
    except proposals.SlotGone as gone:
        await session.rollback()
        raise HTTPException(status.HTTP_410_GONE, gone.detail) from gone
    except InvalidInput as invalid:
        await session.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(invalid)) from invalid
    await session.commit()
    return _stored_reply(stored)


def _stored_reply(stored: proposals.StoredDataset) -> DatasetReply:
    code = stored.dataset.code
    if stored.layer is not None:
        return DatasetReply(code=code, outcome="STORED", message=LAYER_STORED, features=stored.layer.features)
    columns = list(stored.table.columns) if stored.table is not None else []
    rows = len(stored.table.rows) if stored.table is not None else 0
    return DatasetReply(code=code, outcome="STORED", message=STORED, columns=columns, rows=rows)


async def _body(request: Request) -> bytes:
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > TABLE_BYTES_MAX:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, TOO_LARGE_DETAIL)
    try:
        return await limited_body(request, TABLE_BYTES_MAX)
    except BodyTooLarge as too_large:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, TOO_LARGE_DETAIL) from too_large
