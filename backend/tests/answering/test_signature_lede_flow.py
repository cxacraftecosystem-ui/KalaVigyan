import dataclasses
from typing import Any

from app.composer.composer import ModelComposer
from app.services.answer_events import CitedClaims, cited_claims
from app.services.answer_lede import LedeTools
from app.services.answering import AnswerAsk
from app.services.curation_keys import curated_id
from app.services.signature_blocks import CraftCompounds, SignatureFigures

from ..planner.fakes import FakeModel
from .fakes import SOURCES, FakeEnrichment, FakeStore, pipeline, streamed
from .lede_search import LedeStore, StoredSearch
from .signature_evidence import AJRAKH, GLOSSARY, MORDANT_CLAIMS, evidence
from .test_answer_flow import events
from .test_lede_flow import ALUM_RED, HARDE, MORDANT, MORDANT_LEDE, sections_model, understood_as


async def no_compounds(craft: Any) -> CraftCompounds:
    return CraftCompounds()


def stored() -> CitedClaims:
    known = cited_claims([ALUM_RED, HARDE], SOURCES)
    curated = evidence(AJRAKH, MORDANT_CLAIMS)
    return CitedClaims(views={**known.views, **curated.views}, sources={**known.sources, **curated.sources})


async def mordant_answer(*, figures: SignatureFigures | None) -> tuple[list[tuple[str, dict]], FakeStore]:
    store = LedeStore(stored=stored())
    built = pipeline(
        store=store,
        compose_model=sections_model(),
        understand_model=understood_as("PROCESS", "CHEMISTRY"),
        enrichment=FakeEnrichment(entries=GLOSSARY),
    )
    composer = ModelComposer(model=FakeModel([MORDANT_LEDE]))
    lede = LedeTools(compose=composer.lede, figures=figures, retriever=StoredSearch(store))
    built = dataclasses.replace(built, lede=lede)
    found = events(await streamed(AnswerAsk(question=MORDANT, depth="DETAILED"), built))
    return found, store


def lede_of(found: list[tuple[str, dict]]) -> dict:
    (lede,) = [data["block"] for name, data in found if name == "lede"]
    return lede


async def test_without_the_setting_the_lede_streams_and_is_kept_with_no_figure() -> None:
    found, store = await mordant_answer(figures=None)
    assert lede_of(found)["figure"] is None
    (finished,) = store.finished
    assert finished["explainer"].lede.figure is None


async def test_with_the_setting_the_lede_carries_the_mordant_bath_its_terms_call_for() -> None:
    found, store = await mordant_answer(figures=SignatureFigures(compounds=no_compounds))
    names = [name for name, _ in found]
    figure = lede_of(found)["figure"]
    assert figure["kind"] == "mordant_bath"
    assert (figure["dye"], figure["fibre"]) == ("madder", "cotton")
    assert [(s["mordant"], s["colour"]) for s in figure["swatches"]] == [("alum", "red"), ("iron", "black")]
    cited = [{c["claimId"] for c in s["sentence"]["citations"]} for s in figure["swatches"]]
    assert cited == [{str(curated_id(AJRAKH, "C093"))}, {str(curated_id(AJRAKH, "C078"))}]
    sent = [data["id"] for name, data in found[: names.index("lede")] if name == "source"]
    assert {c["sourceId"] for s in figure["swatches"] for c in s["sentence"]["citations"]} <= set(sent)
    (finished,) = store.finished
    kept = finished["explainer"]
    assert kept.lede.figure is not None and kept.lede.figure.kind == "mordant_bath"
    assert set(kept.lede.figure.cited_source_ids()) <= {source.id for source in kept.sources}
