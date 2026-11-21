from typing import Any

from app.research.coverage_chapters import field_chapter
from app.research.monograph_document import MonographDocument

SLUG = "Test-Craft"
PICTURE = "test-craft/pictures/i01"
SECOND = "test-craft/pictures/i02"
FIGURE = "test-craft/chemistry/alum-table"
STATEMENT = "Alum fixes the madder red at 70 degrees."
SIGNATURE_CLAIM = "0e000000-0000-4000-8000-0000000000c2"
SRC = "https://upload.wikimedia.org/a.jpg"
CREDIT = "Photo: Jane Doe, CC BY-SA 4.0, via Wikimedia Commons"
OPENING = "opening"
CHEM = "chem"


def sentence(field: str, text: str, claim: str, chapter: str | None = None) -> dict[str, Any]:
    placed = chapter or field_chapter(field)
    return {"chapter": placed, "tag": "p", "field": field, "nodes": [text], "claimIds": [claim]}


def plain(chapter: str, tag: str, text: str, field: str | None = None) -> dict[str, Any]:
    return {"chapter": chapter, "tag": tag, "field": field, "nodes": [text], "claimIds": []}


def page_document(
    *,
    extra: dict[str, dict[str, Any]] | None = None,
    chapter: dict[str, str] | None = None,
    title: str = "Test craft",
    second_picture: bool = False,
    subject_kind: str = "craft",
    coverage: dict[str, Any] | None = None,
) -> MonographDocument:
    added = extra or {}
    placed = {**(chapter or {})}
    units = {**_units(), **added}
    if second_picture:
        units |= {"u9003": plain(OPENING, "span", "A second view"), "u9004": plain(OPENING, "span", CREDIT)}
    content = {
        "craftSlug": SLUG,
        "sources": _sources(),
        "citations": _citations(),
        "citationClaims": {},
        "data": {},
        "units": units,
        "components": _components(second_picture),
        "layout": _layout(added, placed, second_picture),
    }
    body: dict[str, Any] = {
        "subjectKind": subject_kind,
        "subjectSlug": SLUG,
        "title": title,
        "version": 1,
        "content": content,
        "specs": _specs(second_picture),
        "pageUrl": f"https://kalavigyan.example/crafts/{SLUG}",
    }
    if coverage is not None:
        body["coverage"] = coverage
    return MonographDocument.model_validate(body)


def _units() -> dict[str, dict[str, Any]]:
    return {
        "masthead-title": plain(OPENING, "h1", "Test craft"),
        "overview-1": sentence(
            "OVERVIEW", "Test craft is printed with alum and madder in Kachchh.", "c1", OPENING
        ),
        "chapter-chem": plain(CHEM, "h2", "The chemistry"),
        "h-chemistry": plain(CHEM, "h3", "Chemistry", "CHEMISTRY"),
        "chemistry-1": sentence("CHEMISTRY", STATEMENT, SIGNATURE_CLAIM),
        "chemistry-2": sentence("CHEMISTRY", "The madder bath turns the alum print red.", "c3"),
        "chemistry-3": sentence("CHEMISTRY", "Madder holds alizarin, which binds to the alum.", "c4"),
        "process-1": sentence("PROCESS", "The cloth is dipped in the vat four times.", "c5", CHEM),
        "u9001": plain(OPENING, "span", "The printer at work"),
        "u9002": plain(OPENING, "span", CREDIT),
        "u5001": sentence("CHEMISTRY", "Alum", SIGNATURE_CLAIM),
    }


def _layout(
    extra: dict[str, dict[str, Any]], chapter: dict[str, str], second_picture: bool
) -> list[dict[str, Any]]:
    entries = [
        _entry(OPENING, "component", PICTURE),
        _entry(OPENING, "unit", "u9001", PICTURE),
        _entry(OPENING, "unit", "u9002", PICTURE),
    ]
    if second_picture:
        entries += [
            _entry(OPENING, "component", SECOND),
            _entry(OPENING, "unit", "u9003", SECOND),
            _entry(OPENING, "unit", "u9004", SECOND),
        ]
    opening = ["masthead-title", "overview-1"]
    chem = ["chapter-chem", "h-chemistry", "chemistry-1", "chemistry-2", "chemistry-3", "process-1"]
    entries += [_entry(OPENING, "unit", ref) for ref in opening]
    entries += [_entry(chapter.get(ref, CHEM), "unit", ref) for ref in [*chem, *extra]]
    entries += [_entry(CHEM, "component", FIGURE), _entry(CHEM, "unit", "u5001", FIGURE)]
    return entries


def _entry(chapter: str, kind: str, ref: str, within: str | None = None) -> dict[str, Any]:
    return {"chapter": chapter, "kind": kind, "ref": ref, "within": within}


def _components(second_picture: bool) -> list[dict[str, Any]]:
    pictures = [PICTURE, SECOND] if second_picture else [PICTURE]
    plates = [
        _component(label, OPENING, "picture_plate", "OVERVIEW", "The printer at work") for label in pictures
    ]
    return [*plates, _component(FIGURE, CHEM, "fact_table", "CHEMISTRY", "Alum on cotton")]


def _component(label: str, chapter: str, kind: str, field: str, title: str) -> dict[str, Any]:
    return {
        "label": label,
        "chapter": chapter,
        "anchor": "#" + label.replace("/", "--"),
        "kind": kind,
        "title": title,
        "description": f"{title}, drawn for the test.",
        "field": field,
        "fields": [],
        "subjects": [],
    }


def _specs(second_picture: bool) -> dict[str, dict[str, Any]]:
    specs = {PICTURE: _plate("u9001", "u9002"), FIGURE: {"head": {"title": "u5001"}}}
    if second_picture:
        specs[SECOND] = _plate("u9003", "u9004")
    return specs


def _plate(caption: str, credit: str) -> dict[str, Any]:
    return {
        "setting": "figure",
        "picture": {"src": SRC, "width": 1280, "height": 960, "alt": "A printer at the table"},
        "figure": {"classes": ["plate"], "captions": [{"unit": caption}], "credit": credit},
    }


def _sources() -> dict[str, dict[str, Any]]:
    return {
        "g1": _source(1, "Alum", "A", "https://doi.org/10.1000/kv.42"),
        "g2": _source(2, "Madder", None, "https://example.org/madder"),
    }


def _source(number: int, title: str, grade: str | None, url: str) -> dict[str, Any]:
    return {
        "number": number,
        "title": title,
        "fullTitle": None,
        "publisher": None,
        "year": None,
        "grade": grade,
        "url": url,
        "extra": None,
        "dossierSourceId": None,
    }


def _citations() -> dict[str, list[dict[str, Any]]]:
    return {
        "overview-1": [_quote("g1", "printed with alum and madder in Kachchh", "p. 1")],
        "chemistry-1": [_quote("g1", "alum fixes the red at 60 degrees", "p. 2")],
        "chemistry-2": [_quote("g2", "the madder bath turns the alum print red")],
        "chemistry-3": [_quote("g2", None)],
        "process-1": [_quote("g2", "dipped in the vat four times")],
        "u5001": [_quote("g1", "alum fixes the red", "p. 2")],
    }


def _quote(source: str, quote: str | None, locator: str | None = None) -> dict[str, Any]:
    return {"source": source, "locator": locator, "quote": quote}
