import pytest

from app.planner.failures import FailureLog
from app.planner.reading import DocumentReader, LiveSources
from app.research.evidence import EvidenceItem
from app.research.licences import open_licence
from app.services.live_source_store import chunk_acl
from app.sources.adapter import build_document

from ..planner.fakes import FakeFetcher, FakeLocator, scholarly, web_page

ELSEVIER_TDM = "https://www.elsevier.com/tdm/userlicense/1.0/"
OPEN_COPY = "https://repo.example.org/b.pdf"
TEXT = "Alum binds alizarin to cotton as an insoluble red lake."


def full_text(item: EvidenceItem) -> str:
    return chunk_acl(build_document(item, TEXT, "FULL_TEXT"))


@pytest.mark.parametrize(
    "licence",
    [
        "CC BY 4.0",
        "cc-by",
        "CC BY-SA 3.0 IGO",
        "cc-by-sa",
        "CC0",
        "CC0 1.0",
        "cc0 1.0 universal",
        "PDDL",
        "Public domain",
        "public-domain",
        "Creative Commons Attribution-Share Alike 4.0",
        "Creative Commons Attribution-ShareAlike License",
        "http://creativecommons.org/licenses/by/4.0/",
        "https://creativecommons.org/licenses/by-sa/4.0/legalcode",
        "https://creativecommons.org/publicdomain/zero/1.0/",
        "https://opendatacommons.org/licenses/pddl/1-0/",
    ],
)
def test_open_licences_are_recognised_by_name_or_canonical_url(licence: str) -> None:
    assert open_licence(licence)


@pytest.mark.parametrize(
    "licence",
    [
        None,
        "",
        ELSEVIER_TDM,
        "https://www.springer.com/tdm",
        "publisher-specific-oa",
        "implied-oa",
        "other-oa",
        "acs-specific: authorchoice/editors choice usage agreement",
        "cc-by-nc",
        "CC BY-NC-SA 4.0",
        "cc-by-nd",
        "https://creativecommons.org/licenses/by-nc/4.0/",
        "https://www.ncbi.nlm.nih.gov/home/about/policies/",
        "All rights reserved",
    ],
)
def test_every_other_licence_is_closed(licence: str | None) -> None:
    assert not open_licence(licence)


@pytest.mark.parametrize(
    "licence",
    [
        "CC BY 2.5 IN",
        "cc by-sa 2.5 in",
        "CC BY-SA 3.0 DE",
        "CC-BY-SA-2.0-UK",
        "Creative Commons Attribution 2.5 India",
        "Creative Commons Attribution-Share Alike 3.0 Germany",
        "https://creativecommons.org/licenses/by/2.5/in/",
    ],
)
def test_national_ports_of_open_cc_licences_are_open(licence: str) -> None:
    assert open_licence(licence)


@pytest.mark.parametrize(
    "licence",
    [
        "This is an open access article under the CC BY license (http://creativecommons.org/licenses/by/4.0/).",
        "This article is licensed under a Creative Commons Attribution 4.0 International License.",
        "This is an open access article distributed under the terms of the Creative Commons Attribution "
        "License, which permits unrestricted use, distribution, and reproduction in any medium.",
        "Attribution 4.0 International (CC BY 4.0)",
        "Text is available under the Creative Commons Attribution-ShareAlike 4.0 License; additional terms may apply.",
        "This file is made available under the Creative Commons CC0 1.0 Universal Public Domain Dedication.",
        "This work is in the public domain.",
        "Open Data Commons Public Domain Dedication and License",
        "Licensed under CC BY-SA 2.5 IN.",
    ],
)
def test_common_prose_naming_an_open_licence_is_open(licence: str) -> None:
    assert open_licence(licence)


@pytest.mark.parametrize(
    "licence",
    [
        "CC BY-NC 2.5 IN",
        "Creative Commons Attribution-NonCommercial 4.0 International License",
        "Creative Commons Attribution-NoDerivatives 4.0 International License",
        "This is an open access article under the CC BY-NC-ND license.",
        "Text under CC BY 4.0; figures copyright the publisher, all rights reserved.",
        "Licensed under a Creative Commons licence.",
        "This work is in the public domain in India because its term of copyright has expired.",
        "This is an open access article under the CC BY license (https://www.elsevier.com/tdm/userlicense/1.0/).",
        "PD Dr. Meier holds the rights.",
    ],
)
def test_prose_with_a_restriction_a_place_or_no_named_open_licence_is_closed(licence: str) -> None:
    assert not open_licence(licence)


def test_full_text_under_an_open_licence_is_public() -> None:
    item = scholarly("W7", doi="10.1000/w7").model_copy(update={"licence": "CC BY 4.0"})
    assert full_text(item) == "PUBLIC"


@pytest.mark.parametrize("licence", [ELSEVIER_TDM, "publisher-specific-oa", "implied-oa", None])
def test_full_text_under_a_publisher_or_missing_licence_is_for_researchers(licence: str | None) -> None:
    item = scholarly("W8", doi="10.1000/w8").model_copy(update={"licence": licence})
    assert full_text(item) == "RESEARCHER"


def test_a_web_page_declaring_its_own_open_licence_is_for_researchers() -> None:
    page = web_page("declared").model_copy(update={"licence": "CC-BY"})
    assert full_text(page) == "RESEARCHER"


def test_abstracts_stay_public_whatever_the_licence() -> None:
    item = scholarly("W9", doi="10.1000/w9").model_copy(update={"licence": ELSEVIER_TDM})
    assert chunk_acl(build_document(item, TEXT, "ABSTRACT")) == "PUBLIC"


async def test_an_open_copy_without_its_own_licence_does_not_inherit_the_crossref_one() -> None:
    item = scholarly("10.1000/b", doi="10.1000/b", adapter="crossref").model_copy(
        update={"licence": ELSEVIER_TDM}
    )
    sources = LiveSources(
        searchers=(),
        fetcher=FakeFetcher({OPEN_COPY: TEXT}),
        locator=FakeLocator({"10.1000/b": OPEN_COPY}, licence=None),
    )
    reader = DocumentReader(sources, mode="DEEP", log=FailureLog())
    opened = await reader.open_access_document(item)
    assert opened is not None
    assert (opened.content, opened.item.licence) == ("FULL_TEXT", None)
    assert chunk_acl(opened) == "RESEARCHER"
