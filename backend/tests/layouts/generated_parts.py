import dataclasses
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.research.media_refs import MediaRef
from app.research.monograph_page import CitedSource
from app.research.page_layout import PageLayout
from app.services.knowledge_view import ClaimView
from app.services.monograph_generated_assembly import GeneratedParts
from app.services.monograph_generated_parts import RegisteredComponent, StoredSection
from app.services.monograph_generated_pictures import PlateSource, curated_plate
from app.services.monograph_generated_units import SubjectRecord

from .pictures import picture

__all__ = [
    "ALUM",
    "BAGH",
    "GI_JOURNAL",
    "HIDDEN",
    "PLAYER",
    "RECORD",
    "SURVEY",
    "TEXT_ALUM",
    "TEXT_BAGH",
    "VAT_DIP",
    "fragment_monograph",
    "generated",
    "hero_layout",
    "media",
]

ALUM = uuid.UUID("9a1e0000-0000-4000-8000-0000000000a1")
BAGH = uuid.UUID("9a1e0000-0000-4000-8000-0000000000b1")
HIDDEN = uuid.UUID("9a1e0000-0000-4000-8000-0000000000d1")
ALUM_PAPER = uuid.UUID("9a1e0000-0000-4000-8000-000000000501")
SURVEY_PAPER = uuid.UUID("9a1e0000-0000-4000-8000-000000000502")
TEXT_ALUM = "Alum fixes the madder red."
TEXT_BAGH = "Bagh print is block printed on the Baghini river."
PLAYER = "shared/chemistry/alum-player"
VAT_DIP = "shared/chemistry/indigo-vat-dip"
NO_DRAWING = "shared/chemistry/no-drawing"
UNREGISTERED = "shared/chemistry/proposed-player"
SURVEY = "Bagh survey"
GI_JOURNAL = "GI Journal"
FOCAL = {"x": 0.0, "y": 0.1, "width": 1.0, "height": 0.8}


def source(title: str, url: str) -> CitedSource:
    return CitedSource(
        number=1,
        title=title,
        full_title=None,
        publisher=None,
        year=2020,
        grade="A",
        url=url,
        extra=None,
        dossier_source_id=None,
    )


def view(claim_id: uuid.UUID, text: str, *papers: uuid.UUID) -> ClaimView:
    citations = [
        {"sourceId": str(paper), "quote": f"quote {n}", "locator": f"p. {n}"}
        for n, paper in enumerate(papers, 1)
    ]
    return ClaimView(claim_id, text, "PROVISIONAL", "MATERIAL", None, citations=citations)


def media(key: str) -> MediaRef:
    return MediaRef(
        id=uuid.uuid5(uuid.NAMESPACE_URL, f"https://example.org/{key}"),
        display="INLINE",
        provider="curation",
        page_url=f"https://commons.wikimedia.org/wiki/File:{key}.jpg",
        image_url=f"https://upload.wikimedia.org/wikipedia/commons/a/ab/{key}.jpg",
        width=1600,
        height=1200,
        title=f"Picture {key}",
        alt=f"Picture {key}",
        author="A. Printer",
        site="Wikimedia Commons",
        credit="A. Printer",
        licence="CC BY-SA 4.0",
        licence_url="https://creativecommons.org/licenses/by-sa/4.0/",
        source_id=None,
        retrieved_at=datetime(2026, 11, 19, tzinfo=UTC),
    )


def component(label: str, monograph: str | None = "Kutch-Ajrakh") -> RegisteredComponent:
    return RegisteredComponent(
        label=label,
        kind="reaction_player",
        title=f"Title of {label}",
        description="A player.",
        field="CHEMISTRY",
        fields=("PROCESS",),
        subjects=("compound:23035",),
        monograph=monograph,
        anchor="#fig1" if label == VAT_DIP else None,
    )


def hero_layout() -> PageLayout:
    return PageLayout.model_validate(
        {
            "subjectKind": "craft",
            "subjectSlug": "Bagh-Print",
            "version": 2,
            "entries": [
                {
                    "ref": "bagh-print/pictures/i02",
                    "chapter": "glance",
                    "order": 1,
                    "role": "HERO",
                    "crop": {"x": 0.2, "y": 0.2, "width": 0.6, "height": 0.6},
                    "size": "BLEED",
                    "caption": "Override caption",
                }
            ],
        }
    )


SECTIONS = (
    StoredSection("OVERVIEW", 2, ({"text": TEXT_BAGH, "claimIds": [str(BAGH)]},)),
    StoredSection(
        "CHEMISTRY",
        3,
        (
            {"text": TEXT_ALUM, "claimIds": [str(ALUM)]},
            {"text": "A hidden measure.", "claimIds": [str(ALUM), str(HIDDEN)]},
        ),
    ),
)
RECORD = SubjectRecord(
    name="Bagh Print", kicker="Textiles · Hand block printing", place="Madhya Pradesh", gi=True
)


def pictures() -> tuple[PlateSource, ...]:
    return tuple(
        curated_plate(built, media(built.key))
        for built in (
            picture("I01", role="PLATE", chapter="glance"),
            picture("I02", role="MASTHEAD", chapter="glance", focal=FOCAL),
            picture("I03", role="MATERIAL", chapter="chem", placed={"materialKey": "M01"}),
            picture("I04", role="OPENER", chapter="chem", focal=FOCAL),
        )
    )


def generated(layout: PageLayout | None = None, **changes: Any) -> GeneratedParts:
    parts = GeneratedParts(
        subject_kind="craft",
        subject_slug="Bagh-Print",
        page_url="https://kalavigyan.example/crafts/Bagh-Print",
        record=RECORD,
        sections=SECTIONS,
        visible={
            ALUM: view(ALUM, TEXT_ALUM, ALUM_PAPER, SURVEY_PAPER),
            BAGH: view(BAGH, TEXT_BAGH, SURVEY_PAPER),
        },
        sources={
            str(ALUM_PAPER): source("Alum on cotton", "https://example.org/alum"),
            str(SURVEY_PAPER): source(SURVEY, "https://example.org/bagh"),
        },
        components=(
            component(VAT_DIP),
            component(PLAYER),
            component(NO_DRAWING),
            component(UNREGISTERED, monograph=None),
        ),
        pictures=pictures(),
        layout=layout,
    )
    return dataclasses.replace(parts, **changes)


def fragment_monograph(root: Path, *, gi_url: str = "https://example.org/gi") -> Path:
    folder = root / "Kutch-Ajrakh"
    (folder / "fragments").mkdir(parents=True)
    (folder / "specs").mkdir()
    content = {
        "craftSlug": "Kutch-Ajrakh",
        "sources": {"g1": {**source(GI_JOURNAL, gi_url).model_dump(by_alias=True), "number": 1}},
        "citations": {"chem:q6": [{"source": "g1", "locator": "p. 8", "quote": "bright green"}]},
        "citationClaims": {"chem:q6": ["C086"]},
        "data": {},
        "units": {
            "u9": {
                "chapter": "chemistry",
                "tag": "p",
                "field": "CHEMISTRY",
                "nodes": [
                    {
                        "m": "s",
                        "c": ["Green at ", {"m": "cite", "key": "chem:q6", "g": ["g1"], "c": ["first."]}],
                    }
                ],
                "claimIds": ["C086"],
            }
        },
        "components": [],
        "layout": [],
    }
    (folder / "content.json").write_text(json.dumps(content), encoding="utf-8")
    markup = '<figure id="fig1"><figcaption><kv-slot unit="u9"></kv-slot></figcaption></figure>'
    (folder / "fragments" / "shared__chemistry__indigo-vat-dip.html").write_text(markup, encoding="utf-8")
    (folder / "specs" / "shared__chemistry__alum-player.json").write_text(
        '{"steps": [1, 2]}', encoding="utf-8"
    )
    return root
