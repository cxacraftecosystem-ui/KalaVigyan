import json

from app.sources.reference.commons import file_metadata
from app.sources.reference.commons_dates import original_date
from app.sources.reference.mediawiki import pages_in_order

from .recorded import recorded

READ_IN_ENGLISH = {
    "1850": "1850",
    "1967": "1967",
    "1893": "1893",
    "1902[3]": "1902",
    "circa 1904": "1904",
    "Circa 1850": "1850",
    "January 1889": "1889-01",
    "Taken on 20 July 2013": "2013-07-20",
    "27 December 2017 (according to Exif data)": "2017-12-27",
    "2015-03-13 14:50:19": "2015-03-13",
}
LEFT_EMPTY_IN_ENGLISH = {
    "Unknown date",
    "early 20th century",
    "1890s",
    "between 1610 and 1640",
    "circa 1640–50",
    "Circa 1888 -1890",
    "1/2/1934",
    "2 March 2008 (original upload date)",
}
READ_IN_HINDI = {
    "१८५०": "1850",
    "जनवरी १८८९": "1889-01",
    "circa १९०४": None,
    "Taken on २० जुलाई २०१३": None,
}


def published_by_shown_date(fixture: str) -> dict[str | None, str | None]:
    pages = pages_in_order(json.loads(recorded(fixture)))
    return {meta["date"]: meta["published"] for meta in (file_metadata(page) for page in pages)}


def test_commons_reads_the_original_date_in_the_forms_its_english_metadata_writes() -> None:
    expected = READ_IN_ENGLISH | dict.fromkeys(LEFT_EMPTY_IN_ENGLISH)
    assert published_by_shown_date("commons_dates.json") == expected


def test_other_languages_fall_back_to_the_stated_wikidata_date_without_qualifiers() -> None:
    assert published_by_shown_date("commons_dates_hi.json") == READ_IN_HINDI


def test_no_date_value_reads_as_no_date() -> None:
    assert original_date(None) is None
    assert original_date("") is None
