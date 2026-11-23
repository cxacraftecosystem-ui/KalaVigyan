from typing import Any

from fastapi import APIRouter, Depends, Request, Response

from app.api.public_deps import cached_read, public_reader
from app.models import User
from app.services.kind_fixture_specs import served_kind_fixtures

router = APIRouter(prefix="/design", tags=["design"])


@router.get("/kind-fixtures")
async def get_kind_fixtures(
    request: Request, response: Response, reader: User | None = Depends(public_reader)
) -> Any:
    return cached_read(request, response, reader, {"fixtures": served_kind_fixtures()})
