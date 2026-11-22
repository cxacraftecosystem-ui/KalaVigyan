from typing import Any

import pytest
from pydantic import ValidationError

from app.research.web_trust import load_web_trust, parse_web_trust, web_trust

REASON = "A registry that admits only government bodies, so every page in it is official."
ABOUT = "Domains this test ranks above the general web."


def row(domain: str, trust: str = "B", **changes: str) -> dict[str, str]:
    return {"domain": domain, "trust": trust, "kind": "government", "reason": REASON} | changes


def listed(*rows: dict[str, str], version: int = 1) -> dict[str, Any]:
    return {"schemaVersion": version, "about": ABOUT, "domains": list(rows)}


@pytest.mark.parametrize(
    ("url", "trust"),
    [
        ("https://search.ipindia.gov.in/GIRPublic/Application", "A"),
        ("https://IPINDIA.gov.in./journal", "A"),
        ("https://www.incredibleindia.gov.in/en/gujarat", "B"),
        ("https://gov.in/", "B"),
        ("https://evilgov.in/", "C"),
        ("https://gov.in.example.com/", "C"),
        ("https://ipindia.gov.in.example.com/", "C"),
        ("https://93.184.215.14/", "C"),
    ],
)
def test_a_host_takes_the_trust_of_the_longest_listed_domain_it_ends_in(url: str, trust: str) -> None:
    ranked = parse_web_trust(listed(row("gov.in"), row("ipindia.gov.in", "A")))
    assert ranked.trust_of(url) == trust


@pytest.mark.parametrize(
    "broken",
    [
        listed(row("gov.in"), row("gov.in", "A")),
        listed(row("gov.in", "C")),
        listed(row("gov.in", "D")),
        listed(row("Gov.In")),
        listed(row(".gov.in")),
        listed(row("https://gov.in")),
        listed(row("gov.in", reason="official")),
        listed(row("gov.in", kind="blog")),
        listed(row("gov.in"), version=2),
        listed(),
        {"schemaVersion": 1, "domains": [row("gov.in")]},
    ],
)
def test_a_list_that_breaks_a_rule_is_refused_on_load(broken: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        parse_web_trust(broken)


@pytest.mark.parametrize(
    ("url", "trust"),
    [
        ("https://search.ipindia.gov.in/GIRPublic/Application/Details/646", "A"),
        ("https://www.bis.gov.in/standards/", "A"),
        ("https://nopr.niscpr.res.in/handle/123456789/1", "A"),
        ("https://handicrafts.nic.in/", "B"),
        ("https://www.ncl.res.in/", "B"),
        ("https://textiles.example.ac.in/natural-dyes", "B"),
        ("https://collections.vam.ac.uk/item/O1/", "B"),
        ("https://www.metmuseum.org/art/collection/search/1", "B"),
        ("https://ich.unesco.org/en/lists", "B"),
        ("https://crafts.example.org/ajrakh", "C"),
    ],
)
def test_the_shipped_list_ranks_records_standards_and_journals_a_and_institutions_b(
    url: str, trust: str
) -> None:
    assert web_trust(url) == trust


def test_the_shipped_list_loads_once() -> None:
    assert load_web_trust() is load_web_trust()
