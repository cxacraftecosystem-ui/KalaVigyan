import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from io import BytesIO

from PIL import Image

from app.research.citation_formats import citation_entries
from app.research.explainer import Explainer, explainer_blocks
from app.research.explainer_versions import ExplainerVersionDocument
from app.research.export_text import References
from app.research.lessons import LessonPack, LessonRequest
from app.services.apa_references import apa_references
from app.services.explainer_payload import first_version_mark, version_document
from app.services.export_pictures import Picture, normalised
from app.services.object_store import PresignedGet

from ..contracts.explainer_golden import DOCUMENT, golden_json
from ..contracts.learning_golden import LESSON, learning

__all__ = [
    "BUCKET_HOST",
    "BUILT_AT",
    "PICTURE_SIDE",
    "FakeBucket",
    "first_version",
    "golden_pack",
    "golden_request",
    "lede_version",
    "pack_references",
    "picture_bytes",
    "pictures_of",
    "visible_claims",
]

BUILT_AT = datetime(2026, 11, 18, 10, 0, tzinfo=UTC)
SEED_RETRIEVED = date(2026, 10, 14)
PICTURE_SIDE = (800, 600)
BUCKET_HOST = "https://kalavigyan-media-example.s3.ap-south-1.amazonaws.com"
LEDE_DOCUMENT = "explainer.lede.golden.json"


def first_version() -> ExplainerVersionDocument:
    explainer = Explainer.model_validate(golden_json(DOCUMENT))
    mark = first_version_mark(
        answer_id=explainer.answer_id, question=explainer.question, created_at=explainer.created_at
    )
    return version_document(mark, explainer)


def lede_version() -> ExplainerVersionDocument:
    explainer = Explainer.model_validate(golden_json(LEDE_DOCUMENT))
    mark = first_version_mark(
        answer_id=explainer.answer_id, question=explainer.question, created_at=explainer.created_at
    )
    return version_document(mark, explainer)


def visible_claims(document: ExplainerVersionDocument) -> frozenset[str]:
    return frozenset(c.claim_id for block in explainer_blocks(document.explainer) for c in block.citations())


def golden_request() -> LessonRequest:
    return LessonRequest.model_validate(learning(LESSON)["request"])


def golden_pack() -> LessonPack:
    return LessonPack.model_validate(learning(LESSON)["pack"])


def pack_references(pack: LessonPack) -> References:
    accessed = {source.id: SEED_RETRIEVED for source in pack.sources}
    return References(tuple(citation_entries(pack.sources, accessed=accessed, apa=apa_references)))


def picture_bytes(fmt: str = "PNG", size: tuple[int, int] = PICTURE_SIDE) -> bytes:
    image = Image.new("RGBA", size, (200, 120, 60, 255))
    out = BytesIO()
    image.save(out, format=fmt)
    return out.getvalue()


def pictures_of(pack: LessonPack) -> dict[uuid.UUID, Picture]:
    picture = normalised(picture_bytes())
    assert picture is not None
    return {slide.image.id: picture for slide in pack.slides if slide.image is not None}


@dataclass
class FakeBucket:
    stored: dict[str, tuple[bytes, str]] = field(default_factory=dict)
    signed: list[tuple[str, str, int]] = field(default_factory=list)

    async def exists(self, key: str) -> bool:
        return key in self.stored

    async def put(self, key: str, body: bytes, *, content_type: str) -> None:
        self.stored[key] = (body, content_type)

    async def delete(self, key: str) -> None:
        self.stored.pop(key, None)

    def presigned_get(self, key: str, *, disposition: str, seconds: int, now: datetime) -> PresignedGet:
        self.signed.append((key, disposition, seconds))
        return PresignedGet(url=f"{BUCKET_HOST}/{key}?signed", expires_at=now + timedelta(seconds=seconds))
