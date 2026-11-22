from collections.abc import Callable, Sequence
from io import BytesIO
from typing import Any

from pydantic import TypeAdapter
from pypdf import PdfReader

from app.research.blocks import BlockBase
from app.research.blocks_place import DistrictRef, MonthlyRain
from app.research.citations import SourceRef
from app.research.explainer import Block, ExplainerSection
from app.research.explainer_versions import ExplainerVersionDocument
from app.research.export_text import References
from app.services.apa_references import apa_references
from app.services.explainer_payload import first_version_mark, version_document
from app.services.export_files import explainer_citations
from app.services.pdf_writer import PdfWriter

from ..contracts.golden import golden_json
from .lesson_fixtures import first_version

__all__ = [
    "KACHCHH_RAIN_MM",
    "drawn",
    "golden_block",
    "kachchh",
    "kachchh_rain",
    "pdf_text",
    "report_of",
]

KACHCHH_RAIN_MM = (1.0, 0.4, 0.0, 0.0, 2.0, 60.0, 150.0, 120.0, 50.0, 8.0, 2.0, 1.0)
BLOCKS: TypeAdapter[Any] = TypeAdapter(Block)


def kachchh() -> DistrictRef:
    return DistrictRef(district_lgd=449, name="Kachchh", state_name="Gujarat")


def kachchh_rain() -> MonthlyRain:
    return MonthlyRain(
        district=kachchh(), dataset_code="CHIRPS_3_0", period="1991-2020", millimetres=list(KACHCHH_RAIN_MM)
    )


def golden_block(name: str, block_id: str) -> Any:
    blocks = {block["id"]: block for section in golden_json(name)["sections"] for block in section["blocks"]}
    return BLOCKS.validate_python(blocks[block_id])


def pdf_text(data: bytes) -> str:
    reader = PdfReader(BytesIO(data))
    return " ".join(" ".join(page.extract_text() for page in reader.pages).split())


def drawn(draw: Callable[[PdfWriter], None]) -> tuple[str, bytes]:
    writer = PdfWriter("en", orientation="portrait", title="Figures")
    writer.new_page()
    draw(writer)
    data = writer.output()
    return pdf_text(data), data


def report_of(name: str, section_ids: Sequence[str]) -> tuple[ExplainerVersionDocument, References]:
    golden = golden_json(name)
    chosen = [section for section in golden["sections"] if section["id"] in section_ids]
    sections = [
        ExplainerSection.model_validate(
            {**section, "title": f"Section {order}", "order": order, "state": "READY", "searched": None}
        )
        for order, section in enumerate(chosen, 1)
    ]
    blocks: list[BlockBase] = [block for section in sections for block in section.blocks]
    by_id = {source["id"]: source for source in golden["sources"]}
    cited = dict.fromkeys(source_id for block in blocks for source_id in block.cited_source_ids())
    base = first_version().explainer
    explainer = base.model_copy(
        update={"sections": sections, "sources": [SourceRef.model_validate(by_id[sid]) for sid in cited]}
    )
    mark = first_version_mark(answer_id=base.answer_id, question=base.question, created_at=base.created_at)
    document = version_document(mark, explainer)
    return document, References(tuple(explainer_citations(document, {}, apa_references).entries))
