import asyncio
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.core.errors import ExternalFailure
from app.research.image_relevance import ChosenImage, ClaimText
from app.research.images import ImageCandidate, ImageQuery, media_ref_of
from app.research.media_refs import MediaRef
from app.services.media_ref_store import StoredPicture, media_ref_id, media_url_key

RETRIEVED = datetime(2026, 11, 17, 10, 20, tzinfo=UTC)


def candidate(
    provider: str,
    n: int,
    title: str,
    *,
    licence: str | None,
    author: str | None,
    credit: str | None = None,
) -> ImageCandidate:
    return ImageCandidate(
        provider=provider,
        page_url=f"https://pictures.example.org/{provider}/{n}",
        image_url=f"https://pictures.example.org/{provider}/{n}.jpg",
        original_url=f"https://pictures.example.org/original/{provider}/{n}.jpg",
        title=title,
        author=author,
        site="pictures.example.org",
        credit=credit,
        licence=licence,
        retrieved_at=RETRIEVED,
    )


@dataclass
class FakeSource:
    name: str
    found: list[ImageCandidate]
    queries: list[str] = field(default_factory=list)
    failing: bool = False
    hanging: bool = False

    async def images(self, query: ImageQuery, k: int) -> list[ImageCandidate]:
        self.queries.append(query.text)
        if self.failing:
            raise ExternalFailure(f"{self.name} answered 503", kind="unavailable", service=self.name)
        if self.hanging:
            await asyncio.Event().wait()
        return self.found


@dataclass
class FakeMediaStore:
    claims: dict[uuid.UUID, ClaimText]
    kept: list[ChosenImage] = field(default_factory=list)
    pictures: list[StoredPicture] = field(default_factory=list)
    asked: list[list[uuid.UUID]] = field(default_factory=list)

    async def claim_texts(self, claim_ids: Sequence[uuid.UUID]) -> list[ClaimText]:
        return [self.claims[claim_id] for claim_id in claim_ids if claim_id in self.claims]

    async def stored(self, claim_ids: Sequence[uuid.UUID]) -> list[StoredPicture]:
        self.asked.append(list(claim_ids))
        return [picture for picture in self.pictures if picture.claim_id in claim_ids]

    async def keep(self, chosen: Sequence[ChosenImage]) -> list[MediaRef]:
        self.kept.extend(chosen)
        return [media_ref_of(image.candidate, media_id=_media_id(image), source_id=None) for image in chosen]


def stored_picture(found: ImageCandidate, claim_id: uuid.UUID, relevance: str = "TEXT") -> StoredPicture:
    media = media_ref_of(
        found,
        media_id=media_ref_id(media_url_key(found.provider, found.page_url, found.image_url)),
        source_id=None,
    )
    return StoredPicture(media, claim_id, relevance)


def _media_id(image: ChosenImage) -> uuid.UUID:
    found = image.candidate
    return media_ref_id(media_url_key(found.provider, found.page_url, found.image_url))
