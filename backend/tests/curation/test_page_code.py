from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.models import Craft
from app.research.craft_page import CRAFT_PAGE_SCHEMA_VERSION
from app.services import craft_page_stamp
from app.services.craft_page_stamp import page_stamp, stamp_text
from app.services.page_code import PAGE_CODE, CodeSpec, code_files, code_fingerprint

TREE = {
    "app/__init__.py": "",
    "app/services/__init__.py": "",
    "app/services/builder.py": "from . import parts\nfrom app.models import Row\nfrom app.data.loader import load\n",
    "app/services/parts.py": "WIDTH = 1\n",
    "app/services/unread.py": "HEIGHT = 2\n",
    "app/models/__init__.py": "Row = 1\n",
    "app/data/__init__.py": "",
    "app/data/loader.py": 'NAMES = "names.json"\n\n\ndef load() -> None:\n    return None\n',
    "app/data/names.json": "{}",
    "app/data/other.json": "[]",
    "app/data/monographs/kit/monograph.css": "a{}",
}
READ_IN_ORDER = [
    "app/data/__init__.py",
    "app/data/loader.py",
    "app/data/monographs/kit/monograph.css",
    "app/data/names.json",
    "app/services/__init__.py",
    "app/services/builder.py",
    "app/services/parts.py",
]


def planted(root: Path) -> CodeSpec:
    for name, text in TREE.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
    return CodeSpec(app_dir=root / "app", roots=("app.services.builder",))


def by_hand(root: Path, names: list[str]) -> str:
    lines = "".join(f"{name}\n{hashlib.sha256((root / name).read_bytes()).hexdigest()}\n" for name in names)
    return hashlib.sha256(lines.encode("utf-8")).hexdigest()


def test_the_page_code_is_the_builders_what_they_import_the_files_they_name_and_the_kit(
    tmp_path: Path,
) -> None:
    spec = planted(tmp_path)
    assert [path.relative_to(tmp_path).as_posix() for path in code_files(spec)] == READ_IN_ORDER
    assert code_fingerprint(spec) == by_hand(tmp_path, READ_IN_ORDER)


@pytest.mark.parametrize(
    ("changed", "moves"),
    [
        ("app/services/parts.py", True),
        ("app/data/names.json", True),
        ("app/data/monographs/kit/monograph.css", True),
        ("app/services/unread.py", False),
        ("app/models/__init__.py", False),
        ("app/data/other.json", False),
    ],
)
def test_only_a_change_to_the_page_code_moves_the_fingerprint(
    tmp_path: Path, changed: str, moves: bool
) -> None:
    spec = planted(tmp_path)
    before = code_fingerprint(spec)
    (tmp_path / changed).write_bytes((tmp_path / changed).read_bytes() + b"\n")
    assert (code_fingerprint(spec) != before) is moves


def test_a_builder_that_does_not_exist_is_refused(tmp_path: Path) -> None:
    spec = planted(tmp_path)
    with pytest.raises(ValueError, match=r"app\.services\.missing"):
        code_files(CodeSpec(app_dir=spec.app_dir, roots=("app.services.missing",)))


def test_the_real_page_code_holds_the_page_and_document_builders_and_the_kit() -> None:
    named = {path.relative_to(PAGE_CODE.app_dir.parent).as_posix() for path in code_files(PAGE_CODE)}
    assert {
        "app/services/craft_page.py",
        "app/services/craft_page_records.py",
        "app/services/chapter_records.py",
        "app/services/craft_page_stamp.py",
        "app/services/monograph_generated_assembly.py",
        "app/services/document_components.py",
        "app/research/craft_page.py",
        "app/data/monographs/kit/monograph.css",
        "app/data/monographs/kit/monograph.js",
    } <= named
    assert not any(name.startswith(("app/models/", "app/core/", "app/api/")) for name in named)


def test_the_stamp_is_the_hash_of_its_terms_code_site_and_variant() -> None:
    record = (
        f'{{"code":"c1","schemaVersion":{CRAFT_PAGE_SCHEMA_VERSION},"site":"https://a.example",'
        '"terms":{"claimsCount":3},"variant":"OPEN"}'
    )
    expected = hashlib.sha256(record.encode("utf-8")).hexdigest()
    assert stamp_text({"claimsCount": 3}, code="c1", site="https://a.example", variant="OPEN") == expected


class OneRow:
    def __init__(self, terms: dict[str, Any]) -> None:
        self._mapping = terms

    def one(self) -> OneRow:
        return self


class TermsSession:
    def __init__(self, terms: dict[str, Any]) -> None:
        self.terms = terms

    async def execute(self, statement: Any) -> OneRow:
        return OneRow(self.terms)


async def stamped(monkeypatch: pytest.MonkeyPatch, *, release: str, code: str, claims: int) -> str:
    settings = SimpleNamespace(release=release, public_web_url="https://a.example")
    monkeypatch.setattr(craft_page_stamp, "get_settings", lambda: settings)
    monkeypatch.setattr(craft_page_stamp, "page_code_fingerprint", lambda: code)
    session: Any = TermsSession({"claimsCount": claims})
    craft = Craft(id=uuid.UUID(int=7), name="Kutch Ajrakh", slug="Kutch-Ajrakh")
    return await page_stamp(session, craft, "OPEN")


async def test_a_new_release_with_the_same_terms_and_code_keeps_the_stamp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = await stamped(monkeypatch, release="r1", code="c1", claims=3)
    assert await stamped(monkeypatch, release="r2", code="c1", claims=3) == first
    assert first == stamp_text({"claimsCount": 3}, code="c1", site="https://a.example", variant="OPEN")


async def test_a_changed_term_or_changed_page_code_moves_the_stamp(monkeypatch: pytest.MonkeyPatch) -> None:
    first = await stamped(monkeypatch, release="r1", code="c1", claims=3)
    assert await stamped(monkeypatch, release="r1", code="c1", claims=4) != first
    assert await stamped(monkeypatch, release="r1", code="c2", claims=3) != first
