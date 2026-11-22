import json
from datetime import date

import bibtexparser
import pytest
import rispy

from app.data.craft_master_loader import DATA_DIR
from app.research.citation_export import CitationExport
from app.research.citation_formats import (
    bibtex_entry,
    citation_entries,
    citation_file,
    csl_item,
    dataset_access_key,
    exported_citations,
    ris_record,
)
from app.research.citations import SourceRef
from app.research.datasets import DatasetRef
from app.services.apa_references import apa_references

from ..contracts.learning_golden import CITATIONS, VERSIONS, learning

SEED_RETRIEVED = date(2026, 10, 14)
CHIRPS = DatasetRef.model_validate(
    {
        "code": "CHIRPS_3_0",
        "title": "Climate Hazards Center InfraRed Precipitation with Station data",
        "publisher": "Climate Hazards Center, UC Santa Barbara",
        "edition": "3.0",
        "period": "1981-2025",
        "nativeResolution": "0.05 degree",
        "licence": "CC BY 4.0",
        "licenceUrl": "https://creativecommons.org/licenses/by/4.0/",
        "attribution": None,
        "citation": None,
        "url": "https://www.chc.ucsb.edu/data/chirps3",
    }
)


def latest_sources() -> list[SourceRef]:
    return [SourceRef.model_validate(s) for s in learning(VERSIONS)["latest"]["explainer"]["sources"]]


def seed_retrieved() -> dict[str, date]:
    seed = {(s["title"], s["url"]): s["retrievedAt"] for s in golden_seed_sources()}
    return {s.id: date.fromisoformat(seed[(s.title, s.url)]) for s in latest_sources()}


def golden_seed_sources() -> list[dict]:
    return json.loads((DATA_DIR / "seed_claims.json").read_text(encoding="utf-8"))["sources"]


def test_the_citation_fixture_is_the_versions_sources_through_the_stated_rules_and_apa_style() -> None:
    entries = citation_entries(latest_sources(), accessed=seed_retrieved(), apa=apa_references)
    latest = learning(VERSIONS)["latest"]["mark"]
    built = exported_citations(latest["explainerId"], latest["version"], entries)
    assert built.model_dump(mode="json", by_alias=True) == learning(CITATIONS)


def test_an_undated_web_page_is_retrieved_on_the_day_its_source_was_read() -> None:
    entry = CitationExport.model_validate(learning(CITATIONS)).entries[4]
    assert entry.csl.issued is None and entry.csl.accessed is not None
    assert entry.csl.accessed.date_parts == [[2026, 10, 14]]
    assert entry.apa.endswith(
        "Khamir. Retrieved October 14, 2026, from https://exhibitions-khamir.org/ajrakh/adapting"
    )


def test_bibtex_parses_back_to_the_fields_it_was_written_from() -> None:
    sources = latest_sources()
    text = "\n".join(bibtex_entry(n, s) for n, s in enumerate(sources, 1))
    library = bibtexparser.parse_string(text)
    assert not library.failed_blocks
    for number, (source, entry) in enumerate(zip(sources, library.entries, strict=True), 1):
        fields = {field.key: field.value for field in entry.fields}
        assert entry.key == f"kv{number}"
        assert fields["url"] == source.url
        assert fields.get("year") == (str(source.year) if source.year else None)
        assert fields["howpublished"] == source.publisher.replace("&", "\\&")
        assert fields["title"] == "{" + source.title + "}"
        names = fields["author"].split(" and ")
        assert [name.strip("{}").replace("\\&", "&") for name in names] == source.authors


def test_ris_parses_back_to_the_fields_it_was_written_from() -> None:
    sources = latest_sources()
    records = rispy.loads("".join(ris_record(n, s) for n, s in enumerate(sources, 1)))
    assert len(records) == len(sources)
    for number, (source, record) in enumerate(zip(sources, records, strict=True), 1):
        assert record["id"] == f"kv{number}"
        assert record["authors"] == source.authors
        assert record["title"] == source.title
        assert record["publisher"] == source.publisher
        assert record["urls"] == [source.url]
        assert record.get("year") == (str(source.year) if source.year else None)
        assert record["type_of_reference"] in {"GOVDOC", "ELEC"}


def test_a_dataset_row_is_cited_under_its_publisher_edition_and_access_day() -> None:
    item = csl_item(7, CHIRPS, date(2026, 11, 1))
    shown = item.model_dump(mode="json", by_alias=True)
    assert shown == {
        "id": "kv7",
        "type": "dataset",
        "title": CHIRPS.title,
        "author": [{"literal": "Climate Hazards Center, UC Santa Barbara"}],
        "accessed": {"date-parts": [[2026, 11, 1]]},
        "publisher": "Climate Hazards Center, UC Santa Barbara",
        "version": "3.0",
        "URL": "https://www.chc.ucsb.edu/data/chirps3",
    }
    assert ris_record(7, CHIRPS) == (
        "TY  - DATA\r\n"
        "AU  - Climate Hazards Center, UC Santa Barbara\r\n"
        "TI  - Climate Hazards Center InfraRed Precipitation with Station data\r\n"
        "PB  - Climate Hazards Center, UC Santa Barbara\r\n"
        "UR  - https://www.chc.ucsb.edu/data/chirps3\r\n"
        "ID  - kv7\r\n"
        "ER  - \r\n"
    )
    assert bibtex_entry(7, CHIRPS) == (
        "@misc{kv7,\n"
        "  author = {{Climate Hazards Center, UC Santa Barbara}},\n"
        "  title = {{Climate Hazards Center InfraRed Precipitation with Station data}},\n"
        "  howpublished = {Climate Hazards Center, UC Santa Barbara},\n"
        "  url = {https://www.chc.ucsb.edu/data/chirps3},\n"
        "}\n"
    )


def test_a_media_file_is_cited_as_a_graphic_work() -> None:
    picture = latest_sources()[0].model_copy(update={"kind": "MEDIA"})
    assert csl_item(1, picture, None).type == "graphic"
    assert ris_record(1, picture).startswith("TY  - ART\r\n")
    assert bibtex_entry(1, picture).startswith("@misc{kv1,\n")


def test_a_dataset_with_its_own_citation_text_is_cited_in_those_words() -> None:
    stated = CHIRPS.model_copy(
        update={
            "citation": "Funk, C. et al. (2015). The climate hazards infrared precipitation with stations."
        }
    )
    entries = citation_entries(
        [stated], accessed={dataset_access_key("CHIRPS_3_0"): date(2026, 11, 1)}, apa=apa_references
    )
    assert entries[0].apa == stated.citation
    assert entries[0].dataset_code == "CHIRPS_3_0" and entries[0].source_id is None


def test_bibtex_escapes_its_special_characters_but_keeps_links_as_stored() -> None:
    source = latest_sources()[0].model_copy(
        update={
            "title": "50% of #1 dyes_cost $5 {or} ~less^ \\ more",
            "url": "https://example.org/a_b?c=1&d=2",
        }
    )
    written = bibtex_entry(1, source)
    assert (
        "  title = {{50\\% of \\#1 dyes\\_cost \\$5 \\textbraceleft{}or\\textbraceright{} "
        "\\textasciitilde{}less\\textasciicircum{} \\textbackslash{} more}},\n" in written
    )
    assert "  url = {https://example.org/a_b?c=1&d=2},\n" in written


def closing_points(entry: str) -> list[tuple[int, int]]:
    depth, closes = 0, []
    for place, ch in enumerate(entry):
        depth += {"{": 1, "}": -1}.get(ch, 0)
        if ch == "}" and depth <= 0:
            closes.append((place, depth))
    return closes


def test_a_source_s_own_braces_cannot_close_a_bibtex_field_or_entry() -> None:
    source = latest_sources()[0].model_copy(
        update={
            "title": "Unbalanced { brace and a closing } one",
            "doi": "10.1234/x}},@misc{kv99,title={injected",
            "url": "https://example.org/a}b\\c{d",
        }
    )
    written = bibtex_entry(1, source)
    assert closing_points(written) == [(written.rindex("}"), 0)]
    assert written.startswith("@misc{kv1,\n") and written.endswith("\n}\n")
    assert "  doi = {10.1234/x%7D%7D,@misc%7Bkv99,title=%7Binjected},\n" in written
    assert "  url = {https://example.org/a%7Db%5Cc%7Bd},\n" in written
    (entry,) = bibtexparser.parse_string(written).entries
    assert set(entry.fields_dict) == {"author", "title", "howpublished", "year", "doi", "url"}


def test_each_citation_file_joins_the_entries_in_their_own_format() -> None:
    export = CitationExport.model_validate(learning(CITATIONS))
    bib = citation_file(export, "bib")
    assert bib.media_type == "application/x-bibtex" and bib.text.count("@") == 6
    ris = citation_file(export, "ris")
    assert ris.text.count("ER  - \r\n") == 6 and "\n" not in ris.text.replace("\r\n", "")
    txt = citation_file(export, "txt")
    assert txt.text.splitlines()[3] == f"[4] {export.entries[3].apa}"
    csl = json.loads(citation_file(export, "json").text)
    assert [item["id"] for item in csl] == [f"kv{n}" for n in range(1, 7)]
    with pytest.raises(ValueError, match="not 'xml'"):
        citation_file(export, "xml")
