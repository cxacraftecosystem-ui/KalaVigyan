import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from app.core.errors import InvalidInput
from app.models import Craft, ImageContribution, UploadLink, User
from app.research.image_screens import ScreenTools
from app.research.upload_links import (
    SlotDeclaration,
    UploadSlot,
    declared,
    link_state,
    slot_upload_url,
    upload_page_url,
)
from app.services import image_contributions as images, knowledge_view, upload_links as links

NOW = datetime(2026, 11, 19, 12, tzinfo=UTC)
CRAFT = Craft(id=uuid.UUID(int=7), name="Kutch Ajrakh", slug="Kutch-Ajrakh")
FACT = uuid.UUID(int=21)
OTHER_FACT = uuid.UUID(int=22)
LINK = "kvup_pg_" + "a" * 43
SLOT = "kvup_sl_" + "b" * 43
PHOTO = {
    "origin": "PHOTOGRAPH",
    "caption": "A printer lifts the block",
    "altText": "Hands lifting a carved block from red cloth",
    "rightsConfirmed": True,
    "termsVersion": "2026-11-19",
}
AI_IMAGE = PHOTO | {"origin": "AI_GENERATED", "generator": "ChatGPT, gpt-image-1", "prompt": "An indigo vat"}
FILLING = links.Filling(objects=None, tools=ScreenTools(vision=None), now=NOW)  # type: ignore[arg-type]


def person(role: str = "RESEARCHER", key: int = 41, **fields: Any) -> User:
    return User(id=uuid.UUID(int=key), name="Meera Rao", email="meera@example.org", role=role, **fields)


def slot(*claims: uuid.UUID) -> UploadSlot:
    return UploadSlot(craft_slug=CRAFT.slug, claim_ids=list(claims or (FACT,)))


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def link_row(owner: User, **fields: Any) -> UploadLink:
    values: dict[str, Any] = {
        "id": uuid.UUID(int=99),
        "userId": owner.id,
        "userTokenVersion": 0,
        "craftId": CRAFT.id,
        "stageId": None,
        "claimIds": [FACT],
        "linkHash": "x" * 64,
        "slotHash": None,
        "declaration": None,
        "expiresAt": NOW + timedelta(minutes=30),
        "usedAt": None,
        "contributionId": None,
        "createdAt": NOW,
    }
    return UploadLink(**(values | fields))


@dataclass
class FakeSession:
    answers: list[Any] = field(default_factory=list)
    rows: dict[tuple[type, Any], Any] = field(default_factory=dict)
    added: list[Any] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)

    async def scalar(self, query: Any) -> Any:
        self.queries.append(str(query))
        return self.answers.pop(0) if self.answers else None

    async def get(self, model: type, key: Any) -> Any:
        return self.rows.get((model, key))

    def add(self, row: Any) -> None:
        self.added.append(row)

    async def flush(self) -> None:
        return None


def test_a_used_link_stays_used_and_an_open_link_expires_at_its_thirtieth_minute() -> None:
    expires = NOW + timedelta(minutes=30)
    assert link_state(used_at=None, expires_at=expires, now=NOW + timedelta(minutes=29, seconds=59)) == "OPEN"
    assert link_state(used_at=None, expires_at=expires, now=expires) == "EXPIRED"
    assert link_state(used_at=NOW, expires_at=expires, now=NOW) == "USED"
    assert link_state(used_at=NOW, expires_at=expires, now=expires + timedelta(days=1)) == "USED"


def test_a_slot_names_one_to_twenty_facts_each_once() -> None:
    with pytest.raises(ValidationError):
        UploadSlot(craft_slug=CRAFT.slug, claim_ids=[])
    with pytest.raises(ValidationError):
        UploadSlot(craft_slug=CRAFT.slug, claim_ids=[uuid.UUID(int=n) for n in range(21)])
    with pytest.raises(ValidationError, match="Each fact is named once"):
        UploadSlot(craft_slug=CRAFT.slug, claim_ids=[FACT, FACT])


def test_the_declaration_takes_its_craft_stage_and_facts_from_the_slot() -> None:
    stage = uuid.UUID(int=5)
    made = declared(
        UploadSlot(craft_slug=CRAFT.slug, stage_id=stage, claim_ids=[FACT, OTHER_FACT]),
        SlotDeclaration.model_validate(AI_IMAGE),
    )
    assert (made.craft_slug, made.stage_id, made.claim_ids) == (CRAFT.slug, stage, [FACT, OTHER_FACT])
    assert (made.origin, made.generator, made.prompt) == (
        "AI_GENERATED",
        "ChatGPT, gpt-image-1",
        "An indigo vat",
    )
    with pytest.raises(ValidationError, match="names its tool and model"):
        declared(slot(), SlotDeclaration.model_validate(AI_IMAGE | {"generator": None}))
    with pytest.raises(ValidationError, match="Only an AI-made image"):
        declared(slot(), SlotDeclaration.model_validate(PHOTO | {"prompt": "A vat"}))


def test_the_page_link_and_the_slot_address_carry_the_token_escaped() -> None:
    assert upload_page_url("https://kalavigyan.example/", "kvup_pg_x-y") == (
        "https://kalavigyan.example/contributions/pictures/upload?link=kvup_pg_x-y"
    )
    assert slot_upload_url("https://api.kalavigyan.example", "kvup_sl_a/b") == (
        "https://api.kalavigyan.example/api/upload-links/slots/kvup_sl_a%2Fb"
    )


async def test_a_link_is_issued_for_thirty_minutes_and_only_its_hash_is_kept(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shown(monkeypatch, {FACT: "Alum binds alizarin to cotton."})
    session = FakeSession(answers=[0])
    issued = await links.start_upload(session, person(), slot(), None, now=NOW)  # type: ignore[arg-type]
    (row,) = session.added
    assert issued.link_token.startswith("kvup_pg_") and issued.slot_token is None
    assert (row.linkHash, row.slotHash, row.declaration) == (sha256(issued.link_token), None, None)
    assert (row.expiresAt, issued.expires_at) == (NOW + timedelta(minutes=30), NOW + timedelta(minutes=30))
    assert (row.userId, row.craftId, row.claimIds) == (uuid.UUID(int=41), CRAFT.id, [FACT])
    assert [(fact.id, fact.text) for fact in issued.facts] == [(FACT, "Alum binds alizarin to cotton.")]


async def test_a_declared_slot_gets_its_own_token_and_keeps_the_declaration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shown(monkeypatch, {FACT: "Alum binds alizarin to cotton."})
    session = FakeSession(answers=[0])
    declaration = SlotDeclaration.model_validate(AI_IMAGE)
    issued = await links.start_upload(session, person(), slot(), declaration, now=NOW)  # type: ignore[arg-type]
    (row,) = session.added
    assert issued.slot_token is not None and issued.slot_token.startswith("kvup_sl_")
    assert row.slotHash == sha256(issued.slot_token) and issued.slot_token not in str(row.declaration)
    assert row.declaration == AI_IMAGE | {"prompt": "An indigo vat"}


@pytest.mark.parametrize(
    ("user", "held", "facts", "says"),
    [
        (person("STUDENT"), 0, {FACT: "x"}, "Researcher or above"),
        (person(), 10, {FACT: "x"}, "holds 10 open upload links"),
        (person(), 0, {}, f"No shown fact has the id {FACT}"),
    ],
)
async def test_a_link_is_refused_to_a_student_past_ten_open_links_or_for_a_fact_not_shown(
    monkeypatch: pytest.MonkeyPatch, user: User, held: int, facts: dict[uuid.UUID, str], says: str
) -> None:
    shown(monkeypatch, facts)
    session = FakeSession(answers=[held])
    with pytest.raises(InvalidInput, match=says):
        await links.start_upload(session, user, slot(), None, now=NOW)  # type: ignore[arg-type]
    assert session.added == []


async def test_an_ai_declaration_without_its_tool_is_refused_before_anything_is_read() -> None:
    session = FakeSession()
    declaration = SlotDeclaration.model_validate(PHOTO | {"origin": "AI_GENERATED"})
    with pytest.raises(InvalidInput, match="names its tool and model"):
        await links.start_upload(session, person(), slot(), declaration, now=NOW)  # type: ignore[arg-type]
    assert session.queries == []


@pytest.mark.parametrize(
    ("fields", "refusal", "says"),
    [
        ({"usedAt": NOW - timedelta(minutes=1)}, links.LinkGone, "used already"),
        ({"expiresAt": NOW}, links.LinkGone, "expired"),
    ],
)
async def test_a_used_or_expired_link_takes_no_picture(
    fields: dict[str, Any], refusal: type, says: str
) -> None:
    owner = person()
    session = FakeSession(answers=[link_row(owner, **fields)])
    with pytest.raises(refusal, match=says):
        await links.fill_by_link(session, owner, LINK, picture(), filling=FILLING)  # type: ignore[arg-type]


async def test_another_person_s_link_or_a_token_of_the_wrong_kind_is_unknown() -> None:
    owner, stranger = person(), person(key=42)
    with pytest.raises(links.UnknownLink):
        await links.fill_by_link(
            FakeSession(answers=[link_row(owner)]), stranger, LINK, picture(), filling=FILLING
        )  # type: ignore[arg-type]
    with pytest.raises(links.UnknownLink):
        await links.link_view(FakeSession(), owner, SLOT, now=NOW)  # type: ignore[arg-type]
    with pytest.raises(links.UnknownLink):
        await links.fill_slot(FakeSession(), LINK, b"png", filling=FILLING)  # type: ignore[arg-type]


async def test_an_open_link_is_not_renewed() -> None:
    owner = person()
    with pytest.raises(links.LinkRefused, match="still works"):
        await links.renew_link(FakeSession(answers=[link_row(owner)]), owner, LINK, now=NOW)  # type: ignore[arg-type]


async def test_a_slot_stops_working_when_its_account_signs_out_everywhere() -> None:
    owner = person(tokenVersion=1)
    row = link_row(owner, slotHash="y" * 64, declaration=PHOTO)
    session = FakeSession(answers=[row], rows={(User, owner.id): owner})
    with pytest.raises(links.LinkGone, match="signed out or changed"):
        await links.fill_slot(session, SLOT, b"png", filling=FILLING)  # type: ignore[arg-type]


async def test_a_picture_through_the_link_is_declared_for_the_slot_and_closes_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = person()
    row = link_row(owner, claimIds=[FACT, OTHER_FACT])
    sent = received(monkeypatch)
    session = FakeSession(answers=[row, row], rows={(Craft, CRAFT.id): CRAFT})
    made = await links.fill_by_link(session, owner, LINK, picture(AI_IMAGE), filling=FILLING)  # type: ignore[arg-type]
    (declaration,) = sent.declarations
    assert (declaration.craft_slug, declaration.claim_ids, declaration.generator) == (
        CRAFT.slug,
        [FACT, OTHER_FACT],
        "ChatGPT, gpt-image-1",
    )
    assert sent.files == [(made.id, owner.id, b"png")]
    assert (row.usedAt, row.contributionId) == (NOW, made.id)


async def test_a_slot_upload_uses_the_declaration_stored_with_it(monkeypatch: pytest.MonkeyPatch) -> None:
    owner = person()
    row = link_row(owner, slotHash="y" * 64, declaration=PHOTO)
    sent = received(monkeypatch)
    session = FakeSession(answers=[row, row], rows={(User, owner.id): owner, (Craft, CRAFT.id): CRAFT})
    made = await links.fill_slot(session, SLOT, b"png", filling=FILLING)  # type: ignore[arg-type]
    (declaration,) = sent.declarations
    assert (declaration.origin, declaration.caption) == ("PHOTOGRAPH", "A printer lifts the block")
    assert (row.usedAt, row.contributionId) == (NOW, made.id)


def picture(values: dict[str, Any] = PHOTO) -> links.Picture:
    return links.Picture(declaration=SlotDeclaration.model_validate(values), data=b"png")


def shown(monkeypatch: pytest.MonkeyPatch, facts: dict[uuid.UUID, str]) -> None:
    async def resolve(session: Any, slug: str) -> Craft | None:
        return CRAFT if slug == CRAFT.slug else None

    async def claims(
        session: Any, claim_ids: list[uuid.UUID], *, acls: Any
    ) -> tuple[dict[Any, Any], dict[Any, Any]]:
        return {key: SimpleNamespace(text=facts[key]) for key in claim_ids if key in facts}, {}

    monkeypatch.setattr(knowledge_view, "resolve_craft", resolve)
    monkeypatch.setattr(knowledge_view, "claims_by_id", claims)


@dataclass
class Received:
    declarations: list[Any] = field(default_factory=list)
    files: list[tuple[uuid.UUID, uuid.UUID, bytes]] = field(default_factory=list)


def received(monkeypatch: pytest.MonkeyPatch) -> Received:
    sent = Received()
    made = ImageContribution(id=uuid.UUID(int=77))

    async def declare(session: Any, user: User, declaration: Any, *, now: datetime) -> ImageContribution:
        sent.declarations.append(declaration)
        return made

    async def screened(session: Any, data: bytes, *, origin: str, user: User, tools: Any) -> Any:
        return SimpleNamespace(data=data, origin=origin)

    async def store_screened(
        session: Any, contribution_id: uuid.UUID, user: User, screen: Any, *, objects: Any, now: datetime
    ) -> ImageContribution:
        sent.files.append((contribution_id, user.id, screen.data))
        return made

    monkeypatch.setattr(images, "declare", declare)
    monkeypatch.setattr(links, "screened", screened)
    monkeypatch.setattr(images, "store_screened", store_screened)
    return sent
