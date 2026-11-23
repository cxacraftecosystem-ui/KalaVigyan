from datetime import UTC, datetime

from app.research.images import ImageQuery
from app.sources.images.europe_pmc_figures import EuropePmcFiguresAdapter

from .recorded import Recorder, Reply, source_http

REST = "www.ebi.ac.uk/europepmc/webservices/rest"
SEARCH = f"{REST}/search"
POLYMERS = f"{REST}/PMC8037842/fullTextXML"
DIGITAL_FIBRES = f"{REST}/PMC8175338/fullTextXML"
OPEN_ONLY = f"{REST}/PMC13721911/fullTextXML"
RETRIEVED = datetime(2026, 11, 23, 17, 5, tzinfo=UTC)
CC_BY_4 = "https://creativecommons.org/licenses/by/4.0/"


def figures(routes: dict[str, Reply]) -> tuple[EuropePmcFiguresAdapter, Recorder]:
    recorder = Recorder(routes)
    return EuropePmcFiguresAdapter(
        source_http(recorder, "europe_pmc_figures"), clock=lambda: RETRIEVED
    ), recorder


async def test_a_figure_search_offers_the_own_figures_of_the_first_two_open_articles() -> None:
    adapter, recorder = figures(
        {
            SEARCH: Reply("europe_pmc_figures_search.json"),
            POLYMERS: Reply("europe_pmc_figures_polymers.xml"),
            DIGITAL_FIBRES: Reply("europe_pmc_figures_digital_fibres.xml"),
        }
    )
    found = await adapter.images(ImageQuery(text="cotton fibre micrograph"), 10)
    assert [image.title for image in found] == [
        "Figure 2: Adsorption and photocatalysis of dye removal using a waste cotton cloth fibre composite.",
        "Figure 6: Production of antimicrobial film from antimicrobial raw material.",
        "Figure 13: A summary of extraction methods of CNC derived from cotton wastes.",
        "Figure 14: Issue challenges of extraction methods for the production of CNC.",
        "Fig. 1: Fabrication approach of digital fibres.",
        "Fig. 2: Digital addressing in fibre and textile integration.",
        "Fig. 3: Storage of information in fibres.",
        "Fig. 4: Hybrid digital fibres for physiological monitoring.",
        "Fig. 5: Fabric with incorporated neural network capabilities.",
    ]
    assert [f"{request.url.host}{request.url.path}" for request in recorder.requests] == [
        SEARCH,
        POLYMERS,
        DIGITAL_FIBRES,
    ]
    assert (
        recorder.requests[0].url.params["query"]
        == "FIG:(cotton fibre micrograph) AND OPEN_ACCESS:y AND HAS_FT:y"
    )


async def test_each_figure_is_credited_to_its_article_s_authors_under_its_article_s_licence() -> None:
    adapter, _ = figures(
        {
            SEARCH: Reply("europe_pmc_figures_search.json"),
            POLYMERS: Reply("europe_pmc_figures_polymers.xml"),
            DIGITAL_FIBRES: Reply("europe_pmc_figures_digital_fibres.xml"),
        }
    )
    first, *_ = await adapter.images(ImageQuery(text="cotton fibre micrograph"), 2)
    assert (first.provider, first.site, first.author) == (
        "europe_pmc_figures",
        "Europe PMC",
        "Rizal S et al.",
    )
    assert first.image_url == (
        "https://cdn.ncbi.nlm.nih.gov/pmc/blobs/bf46/8037842/57ca33af7953/polymers-13-01006-g002.jpg"
    )
    assert (first.width, first.height, first.page_url) == (756, 675, "https://doi.org/10.3390/polym13071006")
    assert (first.licence, first.licence_url) == ("CC BY 4.0", CC_BY_4)
    assert first.description == first.title.removeprefix("Figure 2: ")


async def test_a_figure_another_work_is_cited_for_is_left_out_as_third_party_material() -> None:
    adapter, _ = figures(
        {
            SEARCH: Reply("europe_pmc_figures_search.json"),
            POLYMERS: Reply("europe_pmc_figures_polymers.xml"),
            DIGITAL_FIBRES: Reply("europe_pmc_figures_digital_fibres.xml"),
        }
    )
    found = await adapter.images(ImageQuery(text="cotton fibre micrograph"), 10)
    assert not any("SEM Micrograph" in image.title for image in found)
    assert not any(image.image_url.endswith("polymers-13-01006-g012.jpg") for image in found)


async def test_an_article_under_a_non_commercial_licence_is_never_read_and_one_without_full_text_offers_none() -> (
    None
):
    adapter, recorder = figures(
        {
            SEARCH: Reply("europe_pmc_figures_licences.json"),
            OPEN_ONLY: Reply("europe_pmc_full_text_missing.json", status=404),
        }
    )
    assert await adapter.images(ImageQuery(text="cotton fiber micrograph"), 10) == []
    assert [f"{request.url.host}{request.url.path}" for request in recorder.requests] == [SEARCH, OPEN_ONLY]
