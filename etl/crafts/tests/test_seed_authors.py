from common import read_json

from app.data.craft_master_loader import SEED_CLAIMS_FILE

GI_JOURNAL_1050 = "ie:ajrakh:S1"
VAM_PROCESS_SAMPLE = "ie:ajrakh:S3"
AIACA_DABU = "ie:dabu:S20"


def stored_authors() -> dict[str, list[str]]:
    return {source["id"]: source["authors"] for source in read_json(SEED_CLAIMS_FILE)["sources"]}


def test_the_victoria_and_albert_museum_is_one_author() -> None:
    authors = stored_authors()
    assert authors[VAM_PROCESS_SAMPLE] == ["Victoria and Albert Museum"]
    assert not [sid for sid, names in authors.items() if "Victoria" in names or "Albert Museum" in names]


def test_the_gi_journal_s_applicant_note_stays_with_its_registry() -> None:
    assert stored_authors()[GI_JOURNAL_1050] == [
        "Office of the Controller General of Patents, Designs & Trade Marks (applicant: Ajarakhpur Hastkala"
        " Vikas Sangathan; facilitated by Textiles Committee, Ministry of Textiles)"
    ]


def test_an_organisation_named_with_and_is_one_author() -> None:
    assert stored_authors()[AIACA_DABU] == ["All India Artisans and Craftworkers Welfare Association (AIACA)"]


def test_no_stored_author_is_cut_inside_its_brackets() -> None:
    cut = {sid: name for sid, names in stored_authors().items() for name in names if name.count("(") != name.count(")")}
    assert cut == {}
