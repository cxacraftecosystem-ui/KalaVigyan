import uuid

from app.research.image_relevance import ClaimText
from app.services.zoom_pictures import LevelTerm, PicturesAsk, ZoomPictures, fibre_tagged, picture_level

from ..images.fakes import FakeMediaStore, FakeSource, candidate

EMBROIDERY = LevelTerm(level="CLOTH", label="Kutch Embroidery", surfaces=("Kutch Embroidery", "કચ્છ ભરતકામ"))
MULMUL = LevelTerm(level="CLOTH", label="Cotton cloth", surfaces=("Cotton cloth", "latha", "mulmul"))
NETTLE = LevelTerm(level="FIBRE", label="Nettle Fibre", surfaces=("Nettle Fibre",))


def test_a_picture_naming_a_tagged_term_in_any_of_its_names_takes_the_term_s_level() -> None:
    assert picture_level("કચ્છ ભરતકામ, ભુજ", None, (EMBROIDERY,)) == "CLOTH"
    assert picture_level("Mulmul drying in the sun", None, (MULMUL,)) == "CLOTH"
    assert picture_level("Mulmul drying in the sun", None) is None
    assert picture_level("Artisans at work on કચ્છ ભરતકામ", None, (EMBROIDERY,)) == "WORKSHOP"
    assert picture_level("Bhuj market at dusk", None, (EMBROIDERY, MULMUL)) is None


def test_a_fibre_level_still_needs_a_micrograph_and_a_tagged_fibre_names_the_craft_s_fibre() -> None:
    assert fibre_tagged((MULMUL, NETTLE)) == "Nettle"
    assert fibre_tagged((MULMUL,)) is None
    assert picture_level("Nettle fibres under the microscope", "Nettle") == "FIBRE"
    assert picture_level("Nettle fibre spun by hand", "Nettle", (NETTLE,)) is None
    assert picture_level("Cotton fibres under the microscope", "Nettle") is None


async def test_a_craft_whose_fibre_only_its_glossary_tags_name_searches_that_fibre_s_micrographs() -> None:
    naming = ClaimText(uuid.UUID(int=31), "Nettle fibre is stripped from the stems of Himalayan nettle.")
    micrograph = candidate(
        "wikimedia_commons", 4, "Nettle fibres under the microscope", licence="CC BY 4.0", author="C"
    )
    source = FakeSource("wikimedia_commons", [micrograph])
    store = FakeMediaStore({})
    ask = PicturesAsk("Nettle Fibre", (naming,), None, (), terms=(NETTLE,))
    found = await ZoomPictures(sources=(source,), keeper=store).pictures(ask)
    assert "Nettle fibre micrograph" in source.queries
    assert found["FIBRE"].claim_ids == (naming.claim_id,)
    assert [image.candidate.title for image in store.kept] == [micrograph.title]
