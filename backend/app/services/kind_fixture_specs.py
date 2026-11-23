from __future__ import annotations

from typing import Any

from app.data.kind_fixture_files import kind_fixtures

from .drawing_themes import themed_spec

__all__ = ["served_kind_fixtures"]

KIND_KEY = "kind"
SPEC_KEY = "spec"


def served_kind_fixtures() -> list[dict[str, Any]]:
    return [
        {**fixture, SPEC_KEY: themed_spec(fixture[KIND_KEY], fixture[SPEC_KEY])}
        for fixture in kind_fixtures()
    ]
