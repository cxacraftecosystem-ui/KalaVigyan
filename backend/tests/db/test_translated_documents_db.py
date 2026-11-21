import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.document_reads import generated_in_language
from app.models import PageTranslation, StoredDocument
from app.research.page_translations import APPROVED_STATUS
from app.research.translation_passages import is_translatable, passage_leaves, unit_hash
from app.services import stored_documents
from app.services.page_english import english_page
from app.services.page_text_index import indexed_tag
from app.services.stored_documents import generated_read

from .page_documents_seed import CATEGORY_SLUG, CRAFT_SLUG, seed
from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

CATEGORY_PAGE = ("category", CATEGORY_SLUG)
HINDI = "हिन्दी"


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        await seed(opened)
        yield opened


def first_passage(body: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    units: dict[str, dict[str, Any]] = body["content"]["units"]
    return next((key, unit) for key, unit in units.items() if is_translatable(key, unit["nodes"]))


def hindi_texts(nodes: list[Any]) -> list[str]:
    return [leaf.text if leaf.fixed else f"{HINDI} {at}" for at, leaf in enumerate(passage_leaves(nodes))]


async def approved(session: AsyncSession, key: str, unit: dict[str, Any]) -> list[str]:
    texts = hindi_texts(unit["nodes"])
    session.add(
        PageTranslation(
            batchId=uuid.uuid4(),
            subjectKind=CATEGORY_PAGE[0],
            subjectSlug=CATEGORY_PAGE[1],
            language="hi",
            unitKey=key,
            sourceHash=unit_hash(unit["nodes"], unit["claimIds"]),
            english="The English passage.",
            texts=texts,
            status=APPROVED_STATUS,
            origin="CONTRIBUTION",
        )
    )
    await session.flush()
    return texts


def never_assembled(monkeypatch: pytest.MonkeyPatch) -> None:
    async def refused(session: Any, subject: Any) -> None:
        raise AssertionError(f"{subject.slug} was assembled to serve a translation of its stored copy")

    monkeypatch.setattr(stored_documents, "generated_document_of", refused)


async def stored_languages(session: AsyncSession, slug: str) -> list[str]:
    rows = await session.scalars(select(StoredDocument.language).where(StoredDocument.subjectSlug == slug))
    return list(rows.all())


async def test_a_translation_is_drawn_from_the_stored_english_copy_on_read_and_never_stored(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    read = await generated_read(session, *CATEGORY_PAGE)
    assert read.copy is not None
    english = await generated_in_language(session, read, language="en")
    assert english is not None and english.text == read.copy.text
    assert await indexed_tag(session, CATEGORY_PAGE) == f"v{read.copy.version}-{read.copy.content_hash}"
    key, unit = first_passage(read.copy.body())
    texts = await approved(session, key, unit)
    never_assembled(monkeypatch)
    hindi = await generated_in_language(session, await generated_read(session, *CATEGORY_PAGE), language="hi")
    assert hindi is not None
    assert (hindi.language, hindi.version) == ("hi", read.copy.version)
    assert hindi.etag.startswith(f"{read.copy.etag}-hi-")
    shown = json.loads(hindi.text)
    assert shown["language"] == "hi"
    assert shown["content"]["units"][key]["lang"] == "hi"
    assert [leaf.text for leaf in passage_leaves(shown["content"]["units"][key]["nodes"])] == texts
    assert shown["translation"]["translated"] == 1
    assert await stored_languages(session, CATEGORY_SLUG) == ["en"]
    again = await generated_read(session, *CATEGORY_PAGE)
    assert again.copy is not None and again.copy.text == read.copy.text


async def test_a_new_approval_moves_the_translated_tag_while_the_stored_english_stays_as_built(
    session: AsyncSession,
) -> None:
    read = await generated_read(session, *CATEGORY_PAGE)
    assert read.copy is not None
    key, unit = first_passage(read.copy.body())
    await approved(session, key, unit)
    first = await generated_in_language(session, read, language="hi")
    built = await stored_documents.stored_row(session, read.subject)
    assert first is not None and built is not None
    held_at = (built.version, built.builtAt, built.contentHash)
    await approved(session, key, unit)
    second = await generated_in_language(session, read, language="hi")
    assert second is not None and second.etag != first.etag
    assert second.etag.startswith(f"{read.copy.etag}-hi-")
    after = await stored_documents.stored_row(session, read.subject)
    assert after is not None and (after.version, after.builtAt, after.contentHash) == held_at


async def test_a_contributor_works_on_the_english_readers_are_served_so_both_index_one_tag(
    session: AsyncSession,
) -> None:
    first = await generated_read(session, "craft", CRAFT_SLUG)
    assert first.copy is not None
    moved = first.copy.version + 4
    await session.execute(
        update(StoredDocument)
        .where(StoredDocument.subjectKind == "craft", StoredDocument.subjectSlug == CRAFT_SLUG)
        .values(version=moved)
    )
    read = await generated_read(session, "craft", CRAFT_SLUG)
    assert read.copy is not None and read.copy.version == moved
    await generated_in_language(session, read, language="en")
    english = await english_page(session, ("craft", CRAFT_SLUG))
    assert english is not None
    assert english.tag == f"v{moved}-{first.copy.content_hash}"
    assert await indexed_tag(session, ("craft", CRAFT_SLUG)) == english.tag
