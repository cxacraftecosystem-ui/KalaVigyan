import re
from pathlib import Path

import pytest

from app.scripts.build_monograph import PUBLIC_KIT_DIR
from app.services.document_kit_defs import KIT_STYLE_FILE
from app.services.monograph_document import KIT_DIR

RULE = re.compile(r"(?P<selector>[^{}]+)\{(?P<body>[^{}]*)\}")
EQUATION_LABEL = ".bx-{scope} .eq .sp small"
SCOPES_DRAWING_EQUATIONS = ("chem", "mb", "pt", "rm")


def declarations(css: str, selector: str) -> str:
    return " ".join(
        rule.group("body") for rule in RULE.finditer(css) if rule.group("selector").strip() == selector
    )


@pytest.mark.parametrize("folder", [KIT_DIR, PUBLIC_KIT_DIR], ids=["source", "served"])
@pytest.mark.parametrize("scope", SCOPES_DRAWING_EQUATIONS)
def test_an_equation_label_wraps_inside_its_box_in_every_scope_that_draws_equations(
    folder: Path, scope: str
) -> None:
    css = (folder / KIT_STYLE_FILE).read_bytes().decode("utf-8")
    held = declarations(css, EQUATION_LABEL.format(scope=scope))
    assert "max-width: 15ch" in held
    assert "white-space: normal" in held
