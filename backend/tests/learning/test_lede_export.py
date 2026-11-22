from io import BytesIO

from pypdf import PdfReader

from app.research.export_text import References
from app.services.apa_references import apa_references
from app.services.export_files import explainer_citations, explainer_cited
from app.services.export_pdfs import explainer_pdf

from .lesson_fixtures import lede_version


def test_the_report_opens_with_the_lede_whose_sources_it_lists() -> None:
    document = lede_version()
    lede = document.explainer.lede
    assert lede is not None
    export = explainer_citations(document, {}, apa_references)
    refs = References(tuple(export.entries))
    reader = PdfReader(BytesIO(explainer_pdf(document, refs, {})))
    text = " ".join(" ".join(page.extract_text() for page in reader.pages).split())
    body = text.split(document.explainer.sections[0].title)[0]
    for sentence in lede.sentences:
        assert f"{sentence.text} {refs.sentence_marker(sentence)}" in body
    listed = {source.id for source in explainer_cited(document)}
    assert set(lede.cited_source_ids()) <= listed
