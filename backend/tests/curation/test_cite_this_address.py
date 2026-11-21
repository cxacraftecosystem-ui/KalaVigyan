import pytest
from pydantic import ValidationError

from app.research.craft_masthead import CiteThis

TEXT = "KalaVigyan. A craft: a monograph of the craft and its science."
BIBTEX = "@misc{kalavigyan-a-craft}"


def cite(url: str, version: int | None, day: str | None) -> CiteThis:
    return CiteThis(url=url, version=version, curated_on=day, text=TEXT, bibtex=BIBTEX)


def test_an_uncurated_craft_whose_slug_begins_with_v_cites_its_plain_address() -> None:
    assert cite("/crafts/villianur-terracotta-works", None, None).url == "/crafts/villianur-terracotta-works"
    assert cite("/crafts/v2-craft", None, None).version is None


def test_a_curated_craft_cites_its_versioned_address_and_only_that() -> None:
    assert cite("/crafts/villianur-terracotta-works/v3", 3, "2026-11-21").version == 3
    with pytest.raises(ValidationError):
        cite("/crafts/villianur-terracotta-works", 3, "2026-11-21")
    with pytest.raises(ValidationError):
        cite("/crafts/kutch-ajrakh/v3", None, None)
