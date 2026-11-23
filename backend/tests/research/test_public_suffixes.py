from __future__ import annotations

import pytest

from app.research.images import same_site, site_of
from app.research.public_suffixes import load_public_suffixes, parse_public_suffixes

LISTED = parse_public_suffixes(
    [
        "// a comment line is skipped",
        "",
        "uk",
        "ac.uk",
        "ck",
        "*.ck",
        "!www.ck",
        "jp",
        "kawasaki.jp",
        "*.kawasaki.jp",
        "!city.kawasaki.jp",
    ]
)


@pytest.mark.parametrize(
    ("host", "registrable"),
    [
        ("www.vam.ac.uk", "vam.ac.uk"),
        ("vam.ac.uk", "vam.ac.uk"),
        ("ac.uk", None),
        ("example.uk", "example.uk"),
        ("shop.example.ck", "shop.example.ck"),
        ("example.ck", None),
        ("www.ck", "www.ck"),
        ("a.www.ck", "www.ck"),
        ("city.kawasaki.jp", "city.kawasaki.jp"),
        ("ward.kawasaki.jp", None),
        ("one.ward.kawasaki.jp", "one.ward.kawasaki.jp"),
        ("example.unlisted", "example.unlisted"),
        ("unlisted", None),
        ("a..uk", None),
    ],
)
def test_the_registrable_name_is_one_label_more_than_the_longest_rule(
    host: str, registrable: str | None
) -> None:
    assert LISTED.registrable(host) == registrable


def test_a_file_without_rules_is_refused() -> None:
    with pytest.raises(ValueError, match="holds no rules"):
        parse_public_suffixes(["// only a comment", ""])


def test_the_vendored_list_holds_both_sections_and_its_rule_kinds() -> None:
    listed = load_public_suffixes()
    assert {"gov.in", "res.in", "ac.uk", "ltd.uk", "blogspot.com", "cloudfront.net"} <= listed.rules
    assert {"ck", "kawasaki.jp"} <= listed.wildcards
    assert {"www.ck", "city.kawasaki.jp"} <= listed.exceptions


@pytest.mark.parametrize(
    ("host", "site"),
    [
        ("collections.vam.ac.uk", "vam.ac.uk"),
        ("www.dsource.in", "dsource.in"),
        ("a.gov.in", "a.gov.in"),
        ("craftsofindia.res.in", "craftsofindia.res.in"),
        ("shop.ltd.uk", "shop.ltd.uk"),
        ("one.blogspot.com", "one.blogspot.com"),
        ("www.example.XN--H2BRJ9C", "example.भारत"),
        ("XN--H2BRJ9C", None),
        ("10.0.0.1", None),
        ("[::1]", None),
        ("localhost", None),
    ],
)
def test_a_site_is_named_by_the_public_suffix_list(host: str, site: str | None) -> None:
    assert site_of(host) == site


@pytest.mark.parametrize(
    ("page", "image"),
    [
        ("https://alpha.blogspot.com/p", "https://beta.blogspot.com/a.jpg"),
        ("https://one.ltd.uk/page", "https://two.ltd.uk/a.jpg"),
        ("https://d1.cloudfront.net/page", "https://d2.cloudfront.net/a.jpg"),
    ],
)
def test_two_sites_under_a_suffix_the_old_label_list_missed_are_not_paired(page: str, image: str) -> None:
    assert not same_site(page, image)
