from typing import Any

from app.services.source_merge import SourceMerge, source_keys

from .indigo_claims import (
    EDWARDS,
    EDWARDS_JOURNAL,
    FRATER_BOOK,
    FRATER_WEB,
    GI_COPY,
    GI_JOURNAL,
    IMPART,
    KHAMIR_ART,
    KHAMIR_PART,
    source,
)

FAO_RATTAN = "https://www.fao.org/3/y2783e/y2783e.pdf"
RATTAN_BOOK = (
    "in Rattan: current research issues and prospects for conservation and sustainable development "
    "(Non-Wood Forest Products 14)"
)
RENUKA = source(
    "cane-s04",
    "BOOK_CHAPTER",
    f"Status of Rattan Resources and Use in South Asia, {RATTAN_BOOK}",
    url=FAO_RATTAN,
    year=2002,
    authors=("C. Renuka",),
)
LIESE = source(
    "cane-s39",
    "BOOK_CHAPTER",
    f"Challenges and Constraints in Rattan Processing and Utilization, {RATTAN_BOOK}",
    url=FAO_RATTAN,
    year=2002,
    authors=("Walter Liese",),
)
SUNDERLAND = source(
    "cane-s40",
    "BOOK_CHAPTER",
    f"Species Profiles Rattan, {RATTAN_BOOK}",
    url=FAO_RATTAN,
    year=2002,
    authors=("Terry C.H. Sunderland", "John Dransfield"),
)
LIESE_AGAIN = source(
    "fibre-s05",
    "BOOK_CHAPTER",
    f"Challenges and constraints in rattan processing and utilization, {RATTAN_BOOK}",
    url=FAO_RATTAN,
    year=2002,
    authors=("W. Liese",),
)
GI_SUPPLEMENT = "https://ipindia.nic.in/girindia/journal/Supplementary_Journal_1.pdf"
AGATES_GI = source(
    "agates-s01",
    "GI_JOURNAL",
    "Geographical Indications Journal (Supplementary - 1): Agates of Cambay, G.I. Application Number 101",
    url=GI_SUPPLEMENT,
    year=2008,
)
KONARK_GI = source(
    "konark-s02",
    "GI_JOURNAL",
    "Geographical Indications Journal (Supplementary - 1), 24 March 2008: G.I. Application Number 87, "
    "Konark Stone Carving",
    url=GI_SUPPLEMENT,
    year=2008,
)


def merged(*refs: dict[str, Any]) -> SourceMerge:
    merge = SourceMerge()
    for ref in refs:
        merge.register(ref["id"], ref)
    return merge


def test_a_doi_in_its_field_and_in_a_doi_link_name_one_work() -> None:
    linked = source("linked", "PAPER", "Ajrakh dress", url="https://doi.org/10.1080/00404969.2016.1211436")
    merge = merged(EDWARDS, EDWARDS_JOURNAL, linked)
    assert {merge.canonical(ref["id"]) for ref in (EDWARDS, EDWARDS_JOURNAL, linked)} == {EDWARDS["id"]}


def test_one_address_with_or_without_www_and_a_closing_slash_is_one_source() -> None:
    merge = merged(KHAMIR_PART, KHAMIR_ART)
    assert merge.canonical(KHAMIR_ART["id"]) == KHAMIR_PART["id"]


def test_a_title_in_other_words_order_with_asides_is_one_source() -> None:
    merge = merged(GI_COPY, GI_JOURNAL)
    assert merge.canonical(GI_JOURNAL["id"]) == GI_COPY["id"]
    assert list(merge.refs()) == [GI_COPY["id"]]


def test_a_merged_source_keeps_the_first_title_the_earliest_year_and_fills_what_it_lacked() -> None:
    merge = merged(FRATER_WEB, FRATER_BOOK)
    (ref,) = merge.refs().values()
    assert (ref["id"], ref["title"], ref["kind"]) == (FRATER_WEB["id"], FRATER_WEB["title"], "WEB_PAGE")
    assert (ref["year"], ref["authors"]) == (2024, ["Judy Frater"])


def test_a_short_title_alone_never_merges_two_works() -> None:
    wikipedia = source("wikipedia", "ENCYCLOPEDIA", "Ajrakh", url="https://en.wikipedia.org/wiki/Ajrakh")
    merge = merged(IMPART, wikipedia)
    assert merge.canonical(wikipedia["id"]) == wikipedia["id"]
    assert source_keys(wikipedia) == ["url:en.wikipedia.org/wiki/Ajrakh"]


def test_two_papers_with_one_title_but_different_dois_stay_apart() -> None:
    title = "A survey of natural dyes used in Indian textile printing"
    first = source("first", "PAPER", title, doi="10.1000/one")
    second = source("second", "PAPER", title, doi="10.1000/two")
    merge = merged(first, second)
    assert merge.canonical(second["id"]) == second["id"]


def test_two_works_sharing_a_title_but_stating_different_years_stay_apart() -> None:
    title = "Annual Report of the Archaeological Survey of India"
    early = source("asi-1905", "GOVERNMENT_REPORT", title, url="https://example.org/asi-1905.pdf", year=1905)
    late = source("asi-1930", "GOVERNMENT_REPORT", title, url="https://example.org/asi-1930.pdf", year=1930)
    merge = merged(early, late)
    assert merge.canonical(late["id"]) == late["id"]
    assert {ref["year"] for ref in merge.refs().values()} == {1905, 1930}


def test_one_address_still_merges_two_records_that_state_different_years() -> None:
    merge = merged(FRATER_WEB, FRATER_BOOK)
    assert (FRATER_WEB["year"], FRATER_BOOK["year"]) == (2025, 2024)
    assert merge.canonical(FRATER_BOOK["id"]) == FRATER_WEB["id"]


def test_a_source_known_only_by_its_id_maps_to_itself() -> None:
    merge = SourceMerge()
    assert merge.register("unknown", None) == "unknown"
    assert merge.refs() == {}


def test_every_source_id_in_a_payload_is_remapped() -> None:
    merge = merged(GI_COPY, GI_JOURNAL)
    payload = {
        "citations": [{"sourceId": GI_JOURNAL["id"]}],
        "media": {"sourceId": None},
        "x": [GI_JOURNAL["id"]],
    }
    assert merge.remapped(payload) == {
        "citations": [{"sourceId": GI_COPY["id"]}],
        "media": {"sourceId": None},
        "x": [GI_JOURNAL["id"]],
    }


def test_chapters_of_one_book_behind_one_address_stay_their_own_works() -> None:
    merge = merged(RENUKA, LIESE, SUNDERLAND)
    assert [merge.canonical(ref["id"]) for ref in (RENUKA, LIESE, SUNDERLAND)] == [
        RENUKA["id"],
        LIESE["id"],
        SUNDERLAND["id"],
    ]
    kept = merge.refs()
    assert [(kept[ref["id"]]["title"], kept[ref["id"]]["authors"]) for ref in (LIESE, SUNDERLAND)] == [
        (LIESE["title"], ["Walter Liese"]),
        (SUNDERLAND["title"], ["Terry C.H. Sunderland", "John Dransfield"]),
    ]
    payload = {"citations": [{"sourceId": LIESE["id"]}, {"sourceId": SUNDERLAND["id"]}]}
    assert merge.remapped(payload) == payload


def test_a_second_record_of_one_chapter_joins_that_chapter_behind_a_shared_address() -> None:
    merge = merged(RENUKA, LIESE, SUNDERLAND, LIESE_AGAIN)
    assert merge.canonical(LIESE_AGAIN["id"]) == LIESE["id"]
    assert len(merge.refs()) == 3


def test_two_applications_in_one_gi_journal_issue_stay_apart() -> None:
    merge = merged(AGATES_GI, KONARK_GI)
    assert merge.canonical(KONARK_GI["id"]) == KONARK_GI["id"]
    assert [ref["title"] for ref in merge.refs().values()] == [AGATES_GI["title"], KONARK_GI["title"]]


def test_two_records_at_one_address_whose_authors_share_no_surname_stay_apart() -> None:
    proceedings = "https://example.org/proceedings-2019.pdf"
    first = source("first", "PAPER", "Natural dyes", url=proceedings, authors=("Anita Rao",))
    second = source("second", "PAPER", "Lac", url=proceedings, authors=("Rao Anita", "M. Iyer"))
    third = source("third", "PAPER", "Resists", url=proceedings, authors=("Sunil Mehta",))
    merge = merged(first, second, third)
    assert [merge.canonical(ref["id"]) for ref in (first, second, third)] == [
        first["id"],
        first["id"],
        third["id"],
    ]
