import json

import pytest

from app.core.errors import InvalidInput
from app.models.component_kinds import COMPONENT_KINDS, DOCUMENT_KINDS, PIECE_KINDS
from app.research.component_specs import SPEC_MODELS, checked_spec
from app.research.monograph_document import spec_file_name
from app.services.monograph_document import MONOGRAPHS_DIR, monograph_content

AJRAKH = "Kutch-Ajrakh"


def test_every_component_kind_has_a_spec_model_and_every_model_is_a_piece_or_document_kind() -> None:
    assert set(COMPONENT_KINDS) <= set(SPEC_MODELS) <= set(PIECE_KINDS) | set(DOCUMENT_KINDS)
    assert set(DOCUMENT_KINDS) <= set(SPEC_MODELS)
    assert set(DOCUMENT_KINDS).isdisjoint(PIECE_KINDS)


def test_every_ajrakh_component_has_a_spec_its_kind_validates() -> None:
    content = monograph_content(AJRAKH)
    folder = MONOGRAPHS_DIR / AJRAKH / "specs"
    assert sorted(path.name for path in folder.glob("*.json")) == sorted(
        spec_file_name(component.label) for component in content.components
    )
    for component in content.components:
        spec = json.loads((folder / spec_file_name(component.label)).read_text(encoding="utf-8"))
        checked_spec(component.kind, spec)


def test_a_kind_without_a_model_is_refused() -> None:
    with pytest.raises(InvalidInput, match="no_such_kind"):
        checked_spec("no_such_kind", {})
