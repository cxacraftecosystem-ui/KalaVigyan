from typing import Any

from app.research.monograph_document import MonographDocument
from app.research.monograph_page import CitedSource
from app.research.page_report_rules import ReportInput, checked_rules
from app.research.page_report_sources import counted_apart, source_split
from app.services.monograph_generated_units import stored_source

SLUG = "Bagh-Print"
KIN = "bagh-print/kin/related-crafts"
BLOCK = "bagh-print/blocks/chem-card-1"


def _cited(text: str, key: str, sources: list[str]) -> list[dict[str, Any]]:
    return [{"m": "s", "c": [f"{text} ", {"m": "cite", "key": key, "g": sources, "c": ["here."]}]}]


def _unit(chapter: str, key: str, sources: list[str]) -> dict[str, Any]:
    return {
        "chapter": chapter,
        "tag": "p",
        "field": "OVERVIEW",
        "nodes": _cited("Printed", key, sources),
        "claimIds": [],
    }


def _source(number: int, kind: str | None) -> dict[str, Any]:
    found = {
        "number": number,
        "title": f"Source {number}",
        "fullTitle": None,
        "publisher": None,
        "year": None,
    }
    return {**found, "grade": "A", "url": None, "extra": None, "dossierSourceId": None, "kind": kind}


def _component(label: str, chapter: str, kind: str) -> dict[str, Any]:
    return {
        "label": label,
        "chapter": chapter,
        "anchor": "#" + label.replace("/", "--"),
        "kind": kind,
        "title": "A part",
        "description": "A part of the test page.",
        "field": "OVERVIEW",
        "fields": [],
        "subjects": [],
    }


UNITS = {
    "overview-1": _unit("opening", "overview-1", ["g1"]),
    "chem-1": _unit("chem", "chem-1", ["g2", "g1"]),
    "kin-1": _unit("kin", "kin-1", ["g3"]),
    "kin-2": _unit("kin", "kin-2", ["g1", "g4"]),
}
KINDS = ["GI_JOURNAL", "PAPER", "WEB_PAGE", "BOOK", "COMPOUND_RECORD"]


def _layout(kin: bool) -> list[dict[str, Any]]:
    owner = KIN if kin else None
    return [
        {"chapter": "opening", "kind": "unit", "ref": "overview-1", "within": None},
        {"chapter": "chem", "kind": "unit", "ref": "chem-1", "within": None},
        {"chapter": "chem", "kind": "component", "ref": BLOCK, "within": None},
        *([{"chapter": "kin", "kind": "component", "ref": KIN, "within": None}] if kin else []),
        {"chapter": "kin", "kind": "unit", "ref": "kin-1", "within": owner},
        {"chapter": "kin", "kind": "unit", "ref": "kin-2", "within": owner},
    ]


def _document(kin: bool) -> MonographDocument:
    components = [
        _component(BLOCK, "chem", "answer_block"),
        *([_component(KIN, "kin", "related_crafts")] if kin else []),
    ]
    content = {
        "craftSlug": SLUG,
        "sources": {f"g{n}": _source(n, kind) for n, kind in enumerate(KINDS, start=1)},
        "citations": {},
        "citationClaims": {},
        "data": {},
        "units": UNITS,
        "components": components,
        "layout": _layout(kin),
    }
    body = {
        "subjectKind": "craft",
        "subjectSlug": SLUG,
        "title": "Bagh Print",
        "version": 1,
        "content": content,
    }
    specs = {BLOCK: {"sources": [{"key": "g5"}]}}
    return MonographDocument.model_validate(
        {**body, "specs": specs, "pageUrl": f"https://kalavigyan.example/crafts/{SLUG}"}
    )


def test_a_source_only_the_kin_crafts_sentences_cite_is_counted_apart() -> None:
    split = source_split(_document(kin=True))
    assert split.kin == ("g3", "g4")
    assert split.own == ("g1", "g2", "g5")


def test_without_a_kin_component_every_source_is_the_page_s_own() -> None:
    split = source_split(_document(kin=False))
    assert split.kin == ()
    assert split.own == ("g1", "g2", "g3", "g4", "g5")


def test_rule_5_gives_the_count_the_masthead_draws() -> None:
    verdict, evidence = checked_rules(ReportInput(document=_document(kin=True)))[5]
    assert verdict == "JUDGE"
    assert evidence == [
        "the masthead counts 3 sources for this page's own sentences and, apart, 2 sources for the kin "
        "crafts' sentences alone; check that no family fact is filed as the craft's own"
    ]
    assert counted_apart(_document(kin=False)).startswith(
        "the masthead counts 5 sources for this page's own sentences and, apart, no source for"
    )


def test_a_generated_source_keeps_its_stored_kind_and_an_authored_one_writes_none() -> None:
    ref = {"title": "GI Journal No. 37", "publisher": "GI Registry", "year": 2011, "reliability": "A"}
    assert stored_source({**ref, "kind": "GI_JOURNAL"}).kind == "GI_JOURNAL"
    assert "kind" not in stored_source(ref).model_dump(by_alias=True)
    authored = CitedSource.model_validate(_source(1, None) | {"kind": None})
    assert "kind" not in authored.model_dump(mode="json", by_alias=True)
    assert CitedSource.model_validate(_source(2, "PAPER")).model_dump(by_alias=True)["kind"] == "PAPER"
