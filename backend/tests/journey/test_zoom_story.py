import uuid
from typing import Any

import pytest

from app.research.explainer import BLOCK_MODELS
from app.research.image_relevance import ClaimText
from app.research.images import ImageCandidate
from app.services import craft_matter as craft_matter_module, journey_builders
from app.services.block_builders import BLOCK_BUILDERS
from app.services.journey_builders import ZoomStoryBuilder
from app.services.ledger_payloads import sentence_keys
from app.services.matter_builders import molecule_candidates
from app.services.media_ref_store import StoredPicture
from app.services.zoom_pictures import (
    LevelPicture,
    PicturesAsk,
    ZoomPictures,
    chosen_level_images,
    fibre_named,
    picture_level,
    stored_level_pictures,
)
from app.services.zoom_story import (
    Captions,
    district_level,
    figure_texts,
    molecule_level,
    picture_level_of,
    zoom_story_block,
)
from app.sources.reference.pubchem import PubChemAdapter

from ..images.fakes import RETRIEVED, FakeMediaStore, FakeSource, candidate
from ..ledger.indigo_blocks import card
from ..ledger.indigo_claims import AJRAKH_INDIGO
from ..matter.fixtures import alizarin_record_source
from ..place.season_supply_fixtures import written_claim
from ..sources.recorded import Recorder, Reply, fixed_clock, source_http
from ..voice.listen_fakes import MemoryObjects
from .fixtures import (
    ZOOM,
    boundary_dataset,
    cloth_link_card,
    golden_zoom,
    journey_tools,
    phase_c_ask,
    renamed,
    workshop_media,
    zoom_claims,
    zoom_ground_of,
    zoom_matter,
)

PUG = "pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid"
ALIZARIN_SDF = Reply("pubchem_conformer.sdf")
NO_CONFORMER = Reply("pubchem_conformer_missing.txt", status=404)
WASHED = "The printed cloth is washed in running water after each resist stage."


def materials_ask() -> Any:
    _, workshop, molecule = zoom_claims()
    return phase_c_ask([workshop, molecule], discipline="MATERIALS", section_id="s3")


def pubchem(reply: Reply) -> Any:
    adapter = PubChemAdapter(
        source_http(Recorder({f"{PUG}/6293/record/SDF": reply}), "pubchem"), clock=fixed_clock()
    )

    async def source() -> PubChemAdapter:
        return adapter

    return source


def unlicensed_cloth() -> ImageCandidate:
    card = cloth_link_card()
    return ImageCandidate(
        provider="openverse",
        page_url=card["pageUrl"],
        image_url=card["imageUrl"],
        original_url=card["imageUrl"],
        title=card["title"],
        description=card["alt"],
        author=card["author"],
        site=card["site"],
        licence=card["licence"],
        retrieved_at=RETRIEVED,
    )


def pictures_of(*found: ImageCandidate, store: FakeMediaStore | None = None) -> tuple[Any, FakeSource]:
    source = FakeSource("openverse", list(found))
    keeper = store or FakeMediaStore({})

    async def made() -> ZoomPictures:
        return ZoomPictures(sources=(source,), keeper=keeper)

    return made, source


def stored_workshop() -> LevelPicture:
    _, workshop, _ = zoom_claims()
    ask = PicturesAsk("Kutch Ajrakh", (), None, (StoredPicture(workshop_media(), workshop.id, "TEXT"),))
    return stored_level_pictures(ask)["WORKSHOP"]


def zoom_builder(pictures: tuple[Any, FakeSource], *, sdf: Reply = ALIZARIN_SDF) -> ZoomStoryBuilder:
    bucket = MemoryObjects()
    return ZoomStoryBuilder(
        journey_tools(), bucket=lambda: bucket, pubchem=pubchem(sdf), pictures=pictures[0]
    )


@pytest.fixture
def stored(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    found: dict[str, Any] = {"matter": zoom_matter(), "ground": zoom_ground_of(), "asked": [], "read": []}

    async def load(sessions: Any, craft: Any) -> Any:
        found["read"].append(craft.slug)
        return found["matter"]

    async def ground(session: Any, slug: str, *, mode: str, offered: Any) -> Any:
        found["asked"].append((slug, mode, list(offered)))
        return found["ground"]

    monkeypatch.setattr(craft_matter_module, "craft_matter", load)
    monkeypatch.setattr(journey_builders, "zoom_ground", ground)
    return found


async def test_the_zoom_is_the_fixture_s_from_stored_rows_a_kept_picture_and_a_conformer(
    stored: dict[str, Any],
) -> None:
    pictures = pictures_of(unlicensed_cloth())
    built = await zoom_builder(pictures).build(materials_ask())
    (block,) = built.blocks
    assert block.model_dump(mode="json", by_alias=True) == renamed(golden_zoom(), ZOOM, "s3.zoom")
    assert built.sources == {alizarin_record_source()["id"]: alizarin_record_source()}
    (slug, mode, offered) = stored["asked"][0]
    assert (slug, mode) == ("Kutch-Ajrakh", "HYBRID")
    assert offered[:2] == [claim.id for claim in zoom_claims()[1:]]


async def test_a_level_without_a_licensed_image_is_left_out(stored: dict[str, Any]) -> None:
    store = FakeMediaStore({})
    pictures = pictures_of(unlicensed_cloth(), store=store)
    (block,) = (await zoom_builder(pictures).build(materials_ask())).blocks
    assert [level.level for level in block.levels] == ["DISTRICT", "WORKSHOP", "MOLECULE"]
    assert store.kept == []
    assert pictures[1].queries[0].startswith("Kutch Ajrakh")
    assert picture_level(f"{unlicensed_cloth().title}\n{unlicensed_cloth().description}", "cotton") == "CLOTH"


async def test_a_licensed_cloth_photograph_becomes_the_cloth_level_and_is_kept(
    stored: dict[str, Any],
) -> None:
    _, workshop, molecule = zoom_claims()
    washed = written_claim("washed", WASHED, WASHED)
    licensed = candidate(
        "wikimedia_commons", 7, "Ajrakh printed cloth washed in running water", licence="CC0", author="A"
    )
    store = FakeMediaStore({})
    ask = phase_c_ask([workshop, molecule, washed], discipline="MATERIALS", section_id="s3")
    (block,) = (await zoom_builder(pictures_of(licensed, store=store)).build(ask)).blocks
    assert [level.level for level in block.levels] == ["DISTRICT", "WORKSHOP", "CLOTH", "MOLECULE"]
    cloth = block.levels[2]
    assert (cloth.media.display, cloth.media.licence, cloth.relevance, cloth.sentence.text) == (
        "INLINE",
        "CC0",
        "TEXT",
        WASHED,
    )
    assert [(image.candidate.title, image.illustration.claim_ids) for image in store.kept] == [
        (licensed.title, (washed.id,))
    ]


async def test_a_picture_whose_only_caption_is_taken_is_left_out(stored: dict[str, Any]) -> None:
    resist = candidate(
        "wikimedia_commons",
        8,
        "Cotton cloth printed with a carved block and resist paste",
        licence="CC0",
        author="A",
    )
    (block,) = (await zoom_builder(pictures_of(resist)).build(materials_ask())).blocks
    assert [level.level for level in block.levels] == ["DISTRICT", "WORKSHOP", "MOLECULE"]


async def test_without_a_conformer_the_molecule_level_is_left_out(stored: dict[str, Any]) -> None:
    (block,) = (await zoom_builder(pictures_of(), sdf=NO_CONFORMER).build(materials_ask())).blocks
    assert [level.level for level in block.levels] == ["DISTRICT", "WORKSHOP"]


async def test_one_level_is_no_zoom(stored: dict[str, Any]) -> None:
    stored["ground"] = zoom_ground_of(boundary=False)
    built = await zoom_builder(pictures_of(), sdf=NO_CONFORMER).build(materials_ask())
    assert built.blocks == ()


async def test_an_answer_for_any_craft_or_without_a_bucket_gets_what_it_can(stored: dict[str, Any]) -> None:
    ask = materials_ask()
    blank = ask.request.model_copy(update={"craft": None})
    no_craft = type(ask)(ask.answer_id, ask.section, blank, ask.blocks, ask.cited)
    assert (await zoom_builder(pictures_of()).build(no_craft)).blocks == ()
    builder = ZoomStoryBuilder(journey_tools(), bucket=lambda: None, pictures=pictures_of()[0])
    (block,) = (await builder.build(materials_ask())).blocks
    assert [level.level for level in block.levels] == ["DISTRICT", "WORKSHOP"]


async def test_the_zoom_shares_the_answer_s_one_read_of_the_craft_s_matter(stored: dict[str, Any]) -> None:
    ask = materials_ask()
    shared = await ask.matter.read(None, ask.request.craft)
    (block,) = (await zoom_builder(pictures_of()).build(ask)).blocks
    assert [level.level for level in block.levels][-1] == "MOLECULE"
    assert stored["read"] == ["Kutch-Ajrakh"]
    assert shared is stored["matter"]


def test_each_level_carries_its_own_caption_named_by_its_matter() -> None:
    district, workshop, molecule = zoom_claims()
    captions = Captions.of([workshop, molecule], [district])
    ground = zoom_ground_of()
    found = district_level(ground, captions)
    assert (found.district.name, found.sentence.text) == ("Kachchh", district.text)
    assert district_level(ground, captions) is None
    shown = picture_level_of(stored_workshop(), captions)
    assert shown.sentence.text == workshop.text
    linked = molecule_candidates(zoom_matter(), materials_ask().blocks)[0]
    assert molecule_level(linked, Captions.of([workshop])) is None
    assert molecule_level(linked, captions).compound.pubchem_cid == 6293


def test_a_zoom_cites_the_boundary_exactly_when_it_maps_a_district() -> None:
    district, workshop, molecule = zoom_claims()
    captions = Captions.of([workshop, molecule], [district])
    levels = [district_level(zoom_ground_of(), captions), picture_level_of(stored_workshop(), captions)]
    mapped = zoom_story_block(levels, boundary_dataset(), block_id=ZOOM)
    assert (mapped.datasets, mapped.boundary_caption) == (
        [boundary_dataset()],
        golden_zoom()["boundaryCaption"],
    )
    unmapped = zoom_story_block([*levels[1:], None], boundary_dataset(), block_id=ZOOM)
    assert unmapped is None


@pytest.mark.parametrize(
    ("text", "fibre", "level"),
    [
        ("Cotton fibres under a scanning electron microscope", "cotton", "FIBRE"),
        ("Silk fibres, SEM micrograph", "cotton", None),
        ("Artisan printing in his workshop", "cotton", "WORKSHOP"),
        ("Block printed cotton cloth drying", "cotton", "CLOTH"),
        ("Kutch landscape at dusk", "cotton", None),
    ],
)
def test_a_picture_s_level_is_read_from_its_own_words(text: str, fibre: str, level: str | None) -> None:
    assert picture_level(text, fibre) == level


def test_the_fibre_is_a_named_fibre_of_the_craft_s_fibre_material() -> None:
    assert fibre_named(["Cotton cloth"]) == "cotton"
    assert fibre_named(["base fabric", "Tussar silk saree"]) == "silk"
    assert fibre_named(["base fabric"]) is None


def test_a_fibre_micrograph_is_captioned_only_by_a_claim_naming_the_fibre() -> None:
    micrograph = candidate(
        "wikimedia_commons", 3, "Cotton fibres, SEM micrograph", licence="CC BY 4.0", author="B"
    )
    naming = ClaimText(uuid.UUID(int=21), "Ajrakh is printed on cotton cloth.")
    other = ClaimText(uuid.UUID(int=22), "The block is carved from teak.")
    ask = PicturesAsk(craft_name="Kutch Ajrakh", claims=(other, naming), fibre="cotton", stored=())
    chosen = chosen_level_images([micrograph], ask, ["FIBRE"])
    assert chosen["FIBRE"].illustration.claim_ids == (naming.claim_id,)
    alone = PicturesAsk(craft_name="Kutch Ajrakh", claims=(other,), fibre="cotton", stored=())
    assert chosen_level_images([micrograph], alone, ["FIBRE"]) == {}


def test_the_zoom_joins_materials_chemistry_and_process_sections() -> None:
    (entry,) = [entry for entry in BLOCK_BUILDERS if entry.kind == "zoom_story"]
    assert (entry.disciplines, entry.wait_seconds) == ({"MATERIALS", "CHEMISTRY", "PROCESS"}, 20.0)


def test_the_zoom_is_rebuilt_on_reuse_in_place_of_a_stored_story() -> None:
    (entry,) = [entry for entry in BLOCK_BUILDERS if entry.kind == "zoom_story"]
    assert (entry.rebuilt_on_reuse, entry.replaces_stored) == (True, True)


def test_a_level_is_not_captioned_by_a_claim_a_figure_of_its_section_already_states() -> None:
    _, workshop, molecule = zoom_claims()
    captions = Captions.of([workshop, molecule]).without_said(sentence_keys(workshop.text))
    assert captions.first([workshop.id, molecule.id]) == molecule
    figure = BLOCK_MODELS["material_card"].model_validate(card("s3.b2", "Indigo", "indigo", AJRAKH_INDIGO))
    prose = materials_ask().blocks
    assert figure_texts(prose) == set()
    assert figure_texts([*prose, figure]) == sentence_keys(AJRAKH_INDIGO.text)
