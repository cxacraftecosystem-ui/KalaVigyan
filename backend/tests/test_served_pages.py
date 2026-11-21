import json

import pytest
from pydantic import ValidationError

from app.research.page_revalidation import PageOwners
from app.services.page_revalidation import BatchedRefresh
from app.services.served_pages import (
    ServedPages,
    changed_owners,
    kept_digests,
    parsed_record,
    record_text,
    refresh_report,
)

BEFORE = {
    "page:craft:Kutch-Ajrakh": "e1",
    "document:craft:Kutch-Ajrakh": "v3-aa",
    "page:craft:Bagh-Print": "e2",
    "document:category:textiles": "v1-cc",
    "document:category:stone": "v1-dd",
}


def test_nothing_changed_refreshes_nothing() -> None:
    assert changed_owners(BEFORE, dict(BEFORE)) == PageOwners()


def test_a_changed_new_or_vanished_page_or_document_names_its_owner() -> None:
    now = dict(BEFORE)
    now["document:craft:Kutch-Ajrakh"] = "v4-ab"
    now["page:craft:Bidriware"] = "e9"
    del now["document:category:stone"]
    assert changed_owners(BEFORE, now) == PageOwners(
        crafts=("Bidriware", "Kutch-Ajrakh"), categories=("stone",)
    )


def test_a_document_not_read_in_time_is_refreshed_anyway() -> None:
    owners = changed_owners(BEFORE, dict(BEFORE), unmeasured={"category:textiles", "craft:Bagh-Print"})
    assert owners == PageOwners(crafts=("Bagh-Print",), categories=("textiles",))


def test_without_a_record_every_page_is_new() -> None:
    assert changed_owners({}, BEFORE) == PageOwners(
        crafts=("Bagh-Print", "Kutch-Ajrakh"), categories=("stone", "textiles")
    )


def test_a_page_the_web_did_not_refresh_keeps_its_old_digest_so_the_next_release_tries_again() -> None:
    now = {**BEFORE, "document:craft:Kutch-Ajrakh": "v4-ab", "page:craft:Bagh-Print": "e3"}
    kept = kept_digests(BEFORE, now, unsettled=PageOwners(crafts=("Kutch-Ajrakh",)))
    assert kept["document:craft:Kutch-Ajrakh"] == "v3-aa"
    assert kept["page:craft:Bagh-Print"] == "e3"
    assert list(kept) == sorted(BEFORE)


def test_the_record_is_versioned_and_read_back() -> None:
    text = record_text({"page:craft:B": "2", "page:craft:A": "1"})
    assert json.loads(text) == {"schemaVersion": 1, "digests": {"page:craft:A": "1", "page:craft:B": "2"}}
    assert parsed_record(text) == {"page:craft:A": "1", "page:craft:B": "2"}


@pytest.mark.parametrize(
    "text",
    [
        '{"schemaVersion": 2, "digests": {}}',
        '{"schemaVersion": 1, "digests": {"craft:A": "1"}}',
        '{"schemaVersion": 1, "digests": {"page:category:A": "1"}}',
        "not json",
    ],
)
def test_a_record_of_another_shape_is_refused(text: str) -> None:
    with pytest.raises(ValidationError):
        parsed_record(text)


def test_the_report_counts_what_changed_and_names_the_slowest_document() -> None:
    served = ServedPages(
        digests=dict(BEFORE), measured={"craft:Kutch-Ajrakh": 2.5, "category:textiles": 31.0}
    )
    changed = PageOwners(crafts=("Kutch-Ajrakh",), categories=("textiles",))
    sent = BatchedRefresh(PageOwners(crafts=("Kutch-Ajrakh",)), PageOwners(categories=("textiles",)), 1, 1)
    report = refresh_report(served, changed, sent)
    assert (report["pages"], report["documents"]) == (2, 2)
    assert report["slowestDocument"] == {"page": "category:textiles", "seconds": 31.0}
    assert report["slowerThanBuildReads"] == ["category:textiles"]
    assert report["refreshed"] == {"crafts": 1, "categories": 0}
    assert report["notRefreshed"] == {"crafts": 0, "categories": 1}
