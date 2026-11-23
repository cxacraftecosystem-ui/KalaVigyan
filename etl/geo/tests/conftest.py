import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def sleeps(monkeypatch) -> list[float]:
    from geo_etl import remote

    waited: list[float] = []
    monkeypatch.setattr(remote.time, "sleep", waited.append)
    return waited
