from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OAuthClient
from app.research.oauth_client_documents import (
    MetadataClient,
    client_id_problem,
    is_client_id_url,
    is_metadata_client_key,
    metadata_client_key,
)
from app.research.oauth_contract import (
    GRANT_TYPES,
    RESPONSE_TYPES,
    ClientRegistration,
    RegisteredClient,
    client_host,
    registered_client,
)
from app.research.oauth_metadata import PUBLIC_CLIENT_AUTH

from . import oauth_client_documents

__all__ = [
    "AskingClient",
    "asking_client",
    "find_client",
    "keep_metadata_client",
    "register_client",
    "shown_host",
    "stored_client_id",
]


@dataclass(frozen=True)
class AskingClient:
    name: str
    redirect_uris: tuple[str, ...]
    registered_id: uuid.UUID | None = None
    metadata: MetadataClient | None = None

    @property
    def client_id_host(self) -> str | None:
        return self.metadata.host if self.metadata is not None else None


async def register_client(
    session: AsyncSession, registration: ClientRegistration, *, now: datetime
) -> RegisteredClient:
    row = OAuthClient(**registered_client(registration), createdAt=now)
    session.add(row)
    await session.flush()
    return RegisteredClient(
        client_id=str(row.id),
        client_id_issued_at=int(now.timestamp()),
        client_name=row.name,
        redirect_uris=list(row.redirectUris),
        grant_types=list(GRANT_TYPES),
        response_types=list(RESPONSE_TYPES),
        token_endpoint_auth_method=PUBLIC_CLIENT_AUTH,
        client_uri=row.clientUri,
    )


async def find_client(session: AsyncSession, client_id: str | None) -> OAuthClient | None:
    key = _client_key(client_id or "")
    return None if key is None else await session.get(OAuthClient, key)


async def asking_client(session: AsyncSession, client_id: str) -> AskingClient | None:
    if is_client_id_url(client_id):
        made = await oauth_client_documents.client_document(client_id)
        return AskingClient(name=made.name, redirect_uris=made.redirect_uris, metadata=made)
    row = await find_client(session, client_id)
    if row is None:
        return None
    return AskingClient(name=row.name, redirect_uris=tuple(row.redirectUris), registered_id=row.id)


async def stored_client_id(session: AsyncSession, asking: AskingClient, *, now: datetime) -> uuid.UUID:
    if asking.metadata is not None:
        return await keep_metadata_client(session, asking.metadata, now=now)
    if asking.registered_id is None:
        raise ValueError("A registered client carries its id")
    return asking.registered_id


async def keep_metadata_client(session: AsyncSession, made: MetadataClient, *, now: datetime) -> uuid.UUID:
    kept = {"name": made.name, "redirectUris": list(made.redirect_uris), "clientUri": made.client_id}
    await session.execute(
        insert(OAuthClient)
        .values(id=made.key, createdAt=now, **kept)
        .on_conflict_do_update(index_elements=["id"], set_={**kept, "createdAt": now})
    )
    return made.key


def shown_host(row: OAuthClient) -> str:
    if row.clientUri is not None and row.id == metadata_client_key(row.clientUri):
        return client_host(row.clientUri)
    return client_host(row.redirectUris[0])


def _client_key(client_id: str) -> uuid.UUID | None:
    if not client_id:
        return None
    if is_client_id_url(client_id):
        return None if client_id_problem(client_id) else metadata_client_key(client_id)
    try:
        key = uuid.UUID(client_id)
    except ValueError:
        return None
    return None if is_metadata_client_key(key) else key
