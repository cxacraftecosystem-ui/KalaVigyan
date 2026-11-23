import uuid

from app.research.image_relevance import ClaimText
from app.research.images import ImageCandidate
from app.services.zoom_pictures import PicturesAsk, ZoomPictures

from ..images.fakes import FakeMediaStore, FakeSource, candidate

COTTON = ClaimText(uuid.UUID(int=41), "Ajrakh is printed on cotton cloth spun from local cotton.")


def figure() -> ImageCandidate:
    return candidate(
        "europe_pmc_figures",
        1,
        "Figure 3: SEM micrograph of raw cotton fibres",
        licence="CC BY 4.0",
        author="R",
    )


async def test_the_fibre_level_asks_paper_figures_when_commons_and_openverse_find_no_micrograph() -> None:
    commons = FakeSource("wikimedia_commons", [])
    figures = FakeSource("europe_pmc_figures", [figure()])
    store = FakeMediaStore({})
    ask = PicturesAsk("Kutch Ajrakh", (COTTON,), "cotton", ())
    found = await ZoomPictures(sources=(commons,), keeper=store, figures=figures).pictures(ask)
    assert figures.queries == ["cotton fibre micrograph"]
    assert found["FIBRE"].media.provider == "europe_pmc_figures"
    assert found["FIBRE"].claim_ids == (COTTON.claim_id,)


async def test_open_paper_figures_are_not_asked_when_commons_holds_the_fibre_micrograph() -> None:
    micrograph = candidate(
        "wikimedia_commons", 2, "Cotton fibres, SEM micrograph", licence="CC BY 4.0", author="B"
    )
    commons = FakeSource("wikimedia_commons", [micrograph])
    figures = FakeSource("europe_pmc_figures", [figure()])
    ask = PicturesAsk("Kutch Ajrakh", (COTTON,), "cotton", ())
    found = await ZoomPictures(sources=(commons,), keeper=FakeMediaStore({}), figures=figures).pictures(ask)
    assert found["FIBRE"].media.provider == "wikimedia_commons"
    assert figures.queries == []


async def test_a_craft_with_no_fibre_never_asks_for_figures() -> None:
    figures = FakeSource("europe_pmc_figures", [figure()])
    ask = PicturesAsk("Kutch Ajrakh", (COTTON,), None, ())
    found = await ZoomPictures(sources=(), keeper=FakeMediaStore({}), figures=figures).pictures(ask)
    assert "FIBRE" not in found
    assert figures.queries == []
