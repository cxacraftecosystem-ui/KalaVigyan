import uuid
from datetime import UTC, date, datetime

import rispy

from app.models import Source
from app.research.citation_formats import bibtex_entry, citation_entries, csl_item, ris_record
from app.research.citations import SourceRef
from app.research.evidence import EvidenceItem
from app.services.apa_references import apa_references
from app.services.knowledge_view import source_ref
from app.services.live_source_store import source_values

JOURNAL = "Journal of Natural Fibers"
HOUSE = "Taylor & Francis"
DOI = "10.1080/15440478.2021.1"
READ_AT = datetime(2026, 11, 20, 10, 0, tzinfo=UTC)


def paper(*, publisher: str | None, journal: str | None) -> SourceRef:
    return SourceRef.model_validate(
        {
            "id": "a7c1",
            "kind": "PAPER",
            "title": "Alum mordanting of cotton with myrobalan",
            "authors": ["Asha Sharma"],
            "year": 2021,
            "doi": DOI,
            "url": f"https://doi.org/{DOI}",
            "publisher": publisher,
            "licence": None,
            "attribution": None,
            "reliability": "A",
            "containerTitle": journal,
        }
    )


def evidence(adapter: str, publisher: str, container_title: str | None = None) -> EvidenceItem:
    return EvidenceItem(
        id=f"{adapter}:{DOI}",
        adapter=adapter,
        tier="T3",
        source_type="PAPER",
        url=f"https://doi.org/{DOI}",
        title="Alum mordanting of cotton with myrobalan",
        retrieved_at=READ_AT,
        doi=DOI,
        publisher=publisher,
        container_title=container_title,
        trust="A",
    )


def test_a_paper_s_csl_item_names_its_journal_and_its_house_apart() -> None:
    shown = csl_item(1, paper(publisher=HOUSE, journal=JOURNAL), None).model_dump(mode="json", by_alias=True)
    assert shown == {
        "id": "kv1",
        "type": "article-journal",
        "title": "Alum mordanting of cotton with myrobalan",
        "author": [{"literal": "Asha Sharma"}],
        "issued": {"date-parts": [[2021]]},
        "container-title": JOURNAL,
        "publisher": HOUSE,
        "DOI": DOI,
        "URL": f"https://doi.org/{DOI}",
    }


def test_a_journal_stored_as_the_publisher_is_named_once_as_the_journal() -> None:
    item = csl_item(1, paper(publisher=JOURNAL, journal=JOURNAL), None)
    assert item.container_title == JOURNAL and item.publisher is None
    (entry,) = citation_entries([paper(publisher=JOURNAL, journal=JOURNAL)], accessed={}, apa=apa_references)
    assert entry.apa.count(JOURNAL) == 1


def test_the_apa_reference_of_a_paper_names_its_journal() -> None:
    (entry,) = citation_entries([paper(publisher=HOUSE, journal=JOURNAL)], accessed={}, apa=apa_references)
    assert entry.apa.startswith("Asha Sharma. (2021). Alum mordanting of cotton with myrobalan.")
    assert JOURNAL in entry.apa


def test_bibtex_files_the_journal_as_journal_and_the_house_as_publisher() -> None:
    assert bibtex_entry(1, paper(publisher=HOUSE, journal=JOURNAL)) == (
        "@article{kv1,\n"
        "  author = {{Asha Sharma}},\n"
        "  title = {{Alum mordanting of cotton with myrobalan}},\n"
        "  journal = {Journal of Natural Fibers},\n"
        "  publisher = {Taylor \\& Francis},\n"
        "  year = {2021},\n"
        f"  doi = {{{DOI}}},\n"
        f"  url = {{https://doi.org/{DOI}}},\n"
        "}\n"
    )
    assert "journal = " not in bibtex_entry(1, paper(publisher=HOUSE, journal=None))


def test_ris_files_the_journal_as_the_secondary_title() -> None:
    (record,) = rispy.loads(ris_record(1, paper(publisher=HOUSE, journal=JOURNAL)))
    assert record["secondary_title"] == JOURNAL and record["publisher"] == HOUSE
    (same,) = rispy.loads(ris_record(1, paper(publisher=JOURNAL, journal=JOURNAL)))
    assert same["secondary_title"] == JOURNAL and "publisher" not in same


def test_the_journal_comes_from_the_adapters_that_name_it_as_the_publisher() -> None:
    assert evidence("europe_pmc", JOURNAL).journal == JOURNAL
    assert evidence("semantic_scholar", JOURNAL).journal == JOURNAL
    assert evidence("crossref", "Informa UK Limited").journal is None
    assert evidence("crossref", "Informa UK Limited", JOURNAL).journal == JOURNAL


def test_a_live_source_is_stored_with_its_journal() -> None:
    assert source_values(evidence("europe_pmc", JOURNAL))["containerTitle"] == JOURNAL
    assert source_values(evidence("crossref", "Informa UK Limited"))["containerTitle"] is None


def test_a_stored_journal_reaches_the_source_reference() -> None:
    row = Source(
        id=uuid.UUID(int=5),
        kind="PAPER",
        title="Alum mordanting of cotton with myrobalan",
        authors=["Asha Sharma"],
        year=2021,
        doi=DOI,
        url=f"https://doi.org/{DOI}",
        publisher=HOUSE,
        containerTitle=JOURNAL,
        licence=None,
        attribution=None,
        reliability="A",
    )
    assert SourceRef.model_validate(source_ref(row)).container_title == JOURNAL
    row.containerTitle = None
    assert "containerTitle" not in source_ref(row)
    assert "containerTitle" not in SourceRef.model_validate(source_ref(row)).model_dump(by_alias=True)


def test_an_access_day_is_kept_beside_the_journal() -> None:
    item = csl_item(1, paper(publisher=None, journal=JOURNAL), date(2026, 11, 1))
    assert item.accessed is not None and item.accessed.date_parts == [[2026, 11, 1]]
