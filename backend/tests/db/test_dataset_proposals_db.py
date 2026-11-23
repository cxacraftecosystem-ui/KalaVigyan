import hashlib
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import DatasetTable, EnvDataset, User
from app.research.component_specs import checked_spec
from app.research.dataset_proposals import DatasetProposal
from app.research.fetcher import FetchRefused
from app.services import dataset_proposals as proposals
from app.services.dataset_cells import checked_cells
from app.services.dataset_registry import dataset_record, sync_registry

from ..knowledge_writes.fakes import FakeFetcher, page
from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 21, 9, tzinfo=UTC)
LANDING = "https://example.org/artisans"
CSV = b"district,artisans\nKachchh,1200\nBidar,640\n"
CODE = "KV_TEST_ARTISANS_DB"
CHELSA = "CHELSA_2_1_1981_2010"


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        yield opened


async def person(session: AsyncSession, role: str = "RESEARCHER") -> User:
    token = uuid.uuid4()
    user = User(
        id=token, name=f"{role.title()} {token.hex[:4]}", email=f"{token.hex[:12]}@example.org", role=role
    )
    session.add(user)
    await session.flush()
    return user


def record(**changes: Any) -> DatasetProposal:
    body = {
        "code": CODE,
        "title": "Artisans by district",
        "publisher": "A state handicrafts department",
        "edition": "2024",
        "version": "1",
        "period": "2024",
        "native_resolution": "district",
        "crs": "none, a table by district",
        "licence": "CC BY 4.0",
        "licence_url": "https://creativecommons.org/licenses/by/4.0/",
        "attribution": "A state handicrafts department",
        "redistributable": True,
        "citation": "A state handicrafts department (2024). Artisans by district.",
        "landing_url": LANDING,
        "url": "https://example.org/artisans.csv",
        "sha256": hashlib.sha256(CSV).hexdigest(),
    }
    return DatasetProposal.model_validate(body | changes)


async def stored(session: AsyncSession) -> proposals.StoredDataset:
    issued = await proposals.issue_dataset_slot(session, await person(session), record(), now=NOW)
    return await proposals.fill_dataset_slot(session, issued.token, CSV, now=NOW + timedelta(minutes=5))


def chart(first: float, second: float) -> dict[str, Any]:
    points = [
        {"label": "u0002", "value": first, "reading": "u0003", "cell": {"row": 1, "column": "artisans"}},
        {"label": "u0004", "value": second, "reading": "u0005", "cell": {"row": 2, "column": "artisans"}},
    ]
    return {
        "head": {"title": "u0001", "caption": None},
        "form": "bars",
        "valueLabel": "u0006",
        "series": [{"name": "u0007", "points": points}],
        "emphasis": None,
        "dataset": {"code": CODE},
    }


async def test_a_reachable_open_record_with_a_new_code_passes_and_a_registry_code_is_taken(
    session: AsyncSession,
) -> None:
    fetcher = FakeFetcher({LANDING: page()})
    assert await proposals.proposal_problems(session, fetcher, record()) == []
    assert fetcher.asked == [LANDING]
    taken = await proposals.proposal_problems(session, fetcher, record(code=CHELSA))
    assert taken == [f"the code {CHELSA} names a dataset the site already holds; give a code of its own"]


async def test_an_unreadable_landing_page_is_a_problem(session: AsyncSession) -> None:
    fetcher = FakeFetcher({LANDING: FetchRefused(LANDING, "BAD_URL")})
    assert await proposals.proposal_problems(session, fetcher, record()) == [
        f"the landing page {LANDING} could not be read: give the dataset's own public page"
    ]


async def test_a_filled_slot_stores_the_record_and_its_table_once(session: AsyncSession) -> None:
    made = await stored(session)
    assert (made.dataset.code, made.dataset.origin, made.dataset.licence) == (
        CODE,
        "CONTRIBUTED",
        "CC BY 4.0",
    )
    assert made.table is not None and made.layer is None
    assert made.table.rows == (("Kachchh", "1200"), ("Bidar", "640"))
    table = await session.scalar(select(DatasetTable).where(DatasetTable.datasetId == made.dataset.id))
    assert table is not None and (table.rowCount, table.columns) == (2, ["district", "artisans"])
    assert table.sha256 == hashlib.sha256(CSV).hexdigest()


async def test_a_slot_takes_only_its_declared_file_once_and_before_it_expires(session: AsyncSession) -> None:
    researcher = await person(session)
    issued = await proposals.issue_dataset_slot(session, researcher, record(), now=NOW)
    with pytest.raises(InvalidInput, match="SHA-256"):
        await proposals.fill_dataset_slot(session, issued.token, CSV + b"Purnia,10\n", now=NOW)
    late = await proposals.issue_dataset_slot(session, researcher, record(), now=NOW)
    with pytest.raises(proposals.SlotGone, match="expired"):
        await proposals.fill_dataset_slot(session, late.token, CSV, now=NOW + timedelta(hours=1))
    await proposals.fill_dataset_slot(session, issued.token, CSV, now=NOW)
    with pytest.raises(proposals.SlotGone, match="used already"):
        await proposals.fill_dataset_slot(session, issued.token, CSV, now=NOW)
    with pytest.raises(proposals.UnknownSlot):
        await proposals.fill_dataset_slot(session, "kvds_unknown", CSV, now=NOW)


async def test_each_value_is_read_from_its_cell_of_the_stored_table(session: AsyncSession) -> None:
    await stored(session)
    check = await checked_cells(session, checked_spec("chart", chart(1200, 640)))
    assert check.problems == []
    assert check.rows == {"u0003": ["1200"], "u0005": ["640"]}
    assert check.dataset is not None and check.dataset["code"] == CODE and check.dataset["url"] == LANDING
    wrong = await checked_cells(session, checked_spec("chart", chart(1300, 640)))
    assert wrong.problems == [
        f"the value 1300 of the unit u0003 is not the '1200' that row 1 of {CODE} states"
    ]


async def test_a_dataset_without_a_stored_table_is_refused(session: AsyncSession) -> None:
    check = await checked_cells(session, checked_spec("chart", chart(1200, 640)))
    assert check.problems == [
        f"the dataset {CODE} holds no stored table: propose it with propose_dataset first"
    ]


async def test_the_registry_sync_gives_a_site_dataset_its_whole_record(session: AsyncSession) -> None:
    row = await session.scalar(select(EnvDataset).where(EnvDataset.code == CHELSA))
    if row is None:
        row = EnvDataset(code=CHELSA, title="CHELSA", licence="Karger et al. 2017")
        session.add(row)
    row.licence, row.retrievedAt = "Karger et al. 2017", NOW
    await session.flush()
    assert CHELSA in await sync_registry(session)
    full = dataset_record(row)
    assert (full.licence, full.licence_url) == (
        "CC0 1.0",
        "https://creativecommons.org/publicdomain/zero/1.0/",
    )
    assert (full.version, full.doi, full.read_on) == ("2.1", "10.16904/envidat.228", NOW.date())
    assert (full.crs, full.redistributable, full.landing_url) == (
        "EPSG:4326",
        True,
        "https://www.envidat.ch/dataset/chelsa-climatologies",
    )


async def test_the_registry_sync_keeps_the_period_the_load_stored(session: AsyncSession) -> None:
    row = await session.scalar(select(EnvDataset).where(EnvDataset.code == "CHIRPS_3_0"))
    if row is None:
        row = EnvDataset(code="CHIRPS_3_0", title="CHIRPS", licence="CC BY 4.0")
        session.add(row)
    row.period, row.edition = "1981-2025", "old"
    await session.flush()
    assert "CHIRPS_3_0" in await sync_registry(session)
    assert (row.period, row.edition) == ("1981-2025", "3.0")
