import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    text as sql_text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at, one_of, updated_at, uuid_pk
from app.models.enums import ENGLISH_SOURCES

FIELD_VOICE_PORTALS = ("DESIGNER", "FIELD_REPOSITORY")
FIELD_VOICE_STREAMS = ("TRANSCRIPTS", "IMAGES")
FIELD_MEDIA_TYPES = ("AUDIO", "VIDEO")
FIELD_TRANSCRIPT_SOURCES = ("TURNS", "TEXT", "TYPED")
FIELD_TEXT_SOURCES = ("MACHINE", "EDITED", "TYPED")
FIELD_SEGMENT_ROLES = ("ARTISAN", "DESIGNER", "RESEARCHER", "OTHER")
FIELD_IMAGE_TYPES = ("image/jpeg", "image/png")
EMPTY_LIST = sql_text("'[]'::jsonb")
EMPTY_OBJECT = sql_text("'{}'::jsonb")
SHA256_CHECK = "~ '^[0-9a-f]{64}$'"
FIELD_CHANGE_ID_CHARS = 64


class FieldVoiceStream(Base):
    __tablename__ = "FieldVoiceStream"

    portal: Mapped[str] = mapped_column(String(20), nullable=False)
    stream: Mapped[str] = mapped_column(String(12), nullable=False)
    cursor: Mapped[str | None] = mapped_column(Text)
    goneCursor: Mapped[str | None] = mapped_column(Text)
    lastAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lastId: Mapped[str | None] = mapped_column(String(FIELD_CHANGE_ID_CHARS))
    goneLastAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    goneLastId: Mapped[str | None] = mapped_column(String(FIELD_CHANGE_ID_CHARS))
    rereadFrom: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lastContactAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lastCaughtUpAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lastReconciledAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    live: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sql_text("0"))
    digest: Mapped[str | None] = mapped_column(String(64))
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        PrimaryKeyConstraint("portal", "stream"),
        CheckConstraint(one_of("portal", FIELD_VOICE_PORTALS), name="portal"),
        CheckConstraint(one_of("stream", FIELD_VOICE_STREAMS), name="stream"),
        CheckConstraint('num_nonnulls("lastAt", "lastId") <> 1', name="last"),
        CheckConstraint('num_nonnulls("goneLastAt", "goneLastId") <> 1', name="gone_last"),
    )


class FieldRecording(Base):
    __tablename__ = "FieldRecording"

    id: Mapped[uuid.UUID] = uuid_pk()
    portal: Mapped[str] = mapped_column(String(20), nullable=False)
    portalMediaId: Mapped[str] = mapped_column(String(64), nullable=False)
    portalRecordingId: Mapped[str | None] = mapped_column(String(64))
    revision: Mapped[str] = mapped_column(String(32), nullable=False)
    portalUpdatedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    seenAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    mediaType: Mapped[str] = mapped_column(String(8), nullable=False)
    recordedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    durationMs: Mapped[int | None] = mapped_column(Integer)
    context: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=EMPTY_OBJECT)
    people: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default=EMPTY_LIST)
    speakers: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default=EMPTY_LIST)
    transcriptSource: Mapped[str] = mapped_column(String(8), nullable=False)
    languages: Mapped[list[str]] = mapped_column(
        ARRAY(String(16)), nullable=False, server_default=sql_text("ARRAY[]::varchar[]")
    )
    english: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    scrubbing: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=EMPTY_OBJECT)
    unresolvedCrafts: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default=EMPTY_LIST)
    sourceId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Source.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    hiddenAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        UniqueConstraint("portal", "portalMediaId"),
        CheckConstraint(one_of("portal", FIELD_VOICE_PORTALS), name="portal"),
        CheckConstraint(one_of("mediaType", FIELD_MEDIA_TYPES), name="mediaType"),
        CheckConstraint(one_of("transcriptSource", FIELD_TRANSCRIPT_SOURCES), name="transcriptSource"),
        CheckConstraint('"durationMs" IS NULL OR "durationMs" >= 1', name="durationMs"),
        Index(None, "portal", "hiddenAt"),
        Index(None, "recordedAt"),
    )


class FieldSegment(Base):
    __tablename__ = "FieldSegment"

    id: Mapped[uuid.UUID] = uuid_pk()
    recordingId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("FieldRecording.id", ondelete="CASCADE"), nullable=False
    )
    portalSegmentId: Mapped[str] = mapped_column(String(96), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    speakerKey: Mapped[str | None] = mapped_column(String(40))
    personId: Mapped[str | None] = mapped_column(String(64))
    role: Mapped[str | None] = mapped_column(String(12))
    startMs: Mapped[int | None] = mapped_column(Integer)
    endMs: Mapped[int | None] = mapped_column(Integer)
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    textSource: Mapped[str] = mapped_column(String(8), nullable=False)
    english: Mapped[str | None] = mapped_column(Text)
    englishSource: Mapped[str | None] = mapped_column(String(8))
    quotable: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sql_text("false"))

    __table_args__ = (
        UniqueConstraint("recordingId", "portalSegmentId"),
        CheckConstraint(one_of("textSource", FIELD_TEXT_SOURCES), name="textSource"),
        CheckConstraint(
            '"englishSource" IS NULL OR ' + one_of("englishSource", ENGLISH_SOURCES), name="englishSource"
        ),
        CheckConstraint('"role" IS NULL OR ' + one_of("role", FIELD_SEGMENT_ROLES), name="role"),
        CheckConstraint('num_nonnulls("startMs", "endMs") <> 1', name="timed"),
        CheckConstraint('"startMs" IS NULL OR "endMs" > "startMs"', name="span"),
        Index(None, "recordingId", "position"),
        Index(None, "recordingId", "quotable"),
    )


class FieldRecordingCraft(Base):
    __tablename__ = "FieldRecordingCraft"

    recordingId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("FieldRecording.id", ondelete="CASCADE"), primary_key=True
    )
    craftId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Craft.id", ondelete="CASCADE"), primary_key=True
    )

    __table_args__ = (Index(None, "craftId"),)


class FieldImage(Base):
    __tablename__ = "FieldImage"

    id: Mapped[uuid.UUID] = uuid_pk()
    portal: Mapped[str] = mapped_column(String(20), nullable=False)
    portalMediaId: Mapped[str] = mapped_column(String(64), nullable=False)
    revision: Mapped[str] = mapped_column(String(32), nullable=False)
    portalUpdatedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    seenAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    takenAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    caption: Mapped[str | None] = mapped_column(Text)
    belongsTo: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default=EMPTY_LIST)
    context: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=EMPTY_OBJECT)
    people: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default=EMPTY_LIST)
    credits: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default=EMPTY_LIST)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    rightsHolder: Mapped[str] = mapped_column(String(200), nullable=False)
    licence: Mapped[str | None] = mapped_column(String(200))
    portalSha256: Mapped[str] = mapped_column(String(64), nullable=False)
    objectKey: Mapped[str] = mapped_column(Text, nullable=False)
    mimeType: Mapped[str] = mapped_column(String(16), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    unresolvedCrafts: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default=EMPTY_LIST)
    mediaRefId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("MediaRef.id", ondelete="SET NULL")
    )
    artisanLinked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sql_text("false"))
    hiddenAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    createdAt: Mapped[datetime] = created_at()
    updatedAt: Mapped[datetime] = updated_at()

    __table_args__ = (
        UniqueConstraint("portal", "portalMediaId"),
        CheckConstraint(one_of("portal", FIELD_VOICE_PORTALS), name="portal"),
        CheckConstraint(one_of("mimeType", FIELD_IMAGE_TYPES), name="mimeType"),
        CheckConstraint(f'"sha256" {SHA256_CHECK}', name="sha256"),
        CheckConstraint(f'"portalSha256" {SHA256_CHECK}', name="portalSha256"),
        CheckConstraint('"width" >= 1 AND "height" >= 1 AND "bytes" >= 1', name="size"),
        Index(None, "objectKey"),
        Index(None, "portal", "hiddenAt"),
        Index(None, "mediaRefId"),
        Index(None, "artisanLinked"),
    )


class FieldImageCraft(Base):
    __tablename__ = "FieldImageCraft"

    imageId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("FieldImage.id", ondelete="CASCADE"), primary_key=True
    )
    craftId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("Craft.id", ondelete="CASCADE"), primary_key=True
    )

    __table_args__ = (Index(None, "craftId"),)
