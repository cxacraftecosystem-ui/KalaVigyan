import json
import uuid

from app.services.write_back_crafts import HELD_UNNAMED, SKIP_ABROAD, FilingTexts
from app.services.write_back_filing import (
    StoredCitation,
    StoredFiling,
    filing_row,
    report_lines,
    stored_texts,
)

from .names import KHURJA, MUD_FAMILY, names_for

KHURJA_NAMES = names_for(KHURJA, family=MUD_FAMILY)
STUDY = "Clay bodies and glazes of Khurja pottery"
HANDBOOK = "A handbook of ceramic glazes"
AGED = "The clay is aged for two days"
PARAGRAPHS = f"Jaipur blue pottery uses quartz frit.\n\n{AGED} before it is wedged."
KHOREZM = "In Khorezm practice, clay is kneaded thoroughly by hand."


def claim_id(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-write-back-filing-report/{name}")


def cited(title: str, quote: str | None = None, *, kind: str = "PAPER", passage: str | None = None):
    return StoredCitation(
        quote=quote, quote_check="PASS" if quote else "NA", title=title, kind=kind, passage_text=passage
    )


def stored(name: str, text: str, *citations: StoredCitation, field: str = "PROCESS") -> StoredFiling:
    return StoredFiling(
        claim_id=claim_id(name),
        text=text,
        status="IN_REVIEW",
        field=field,
        place=f"craft:{KHURJA.slug}",
        checked=name != "unchecked",
        citations=citations,
    )


def test_the_stored_quote_its_chunk_s_paragraph_and_the_titles_are_read_but_a_field_interview_s_are_not() -> (
    None
):
    failed = StoredCitation(
        quote="a quote that failed", quote_check="FAIL", title=HANDBOOK, kind="PAPER", passage_text=None
    )
    texts = stored_texts(
        f"{AGED}.",
        [
            cited(STUDY, AGED, passage=PARAGRAPHS),
            failed,
            cited("Field interview, Khurja, 2026", AGED, kind="FIELD_TESTIMONY", passage=PARAGRAPHS),
        ],
    )
    assert texts == FilingTexts(
        text=f"{AGED}.",
        quotes=(AGED,),
        passages=(f"{AGED} before it is wedged.",),
        titles=(STUDY, HANDBOOK),
    )


def test_each_fact_is_shown_where_it_is_and_where_today_s_rule_would_file_it() -> None:
    named = filing_row(stored("named", f"{AGED}.", cited(STUDY, AGED, passage=PARAGRAPHS)), KHURJA_NAMES)
    assert (named.would, named.why, named.moves) == (f"craft:{KHURJA.slug}", None, False)
    abroad = filing_row(stored("abroad", KHOREZM, cited(HANDBOOK)), KHURJA_NAMES)
    assert (abroad.would, abroad.why, abroad.moves) == ("refused", SKIP_ABROAD.format(places="Khorezm"), True)
    unnamed = filing_row(stored("unnamed", f"{AGED}.", cited(HANDBOOK, AGED)), KHURJA_NAMES)
    assert (unnamed.would, unnamed.why, unnamed.moves) == (f"held:{KHURJA.slug}", HELD_UNNAMED, True)
    family = filing_row(stored("family", f"{AGED}.", cited(HANDBOOK, AGED), field="CHEMISTRY"), KHURJA_NAMES)
    assert (family.would, family.moves) == (f"family:{MUD_FAMILY.slug}", True)


def test_a_field_interview_alone_stays_with_the_craft_researched_and_an_unknown_craft_moves_nothing() -> None:
    spoken = stored("spoken", f"{AGED}.", cited("Field interview", AGED, kind="FIELD_TESTIMONY"))
    assert filing_row(spoken, KHURJA_NAMES).would == f"craft:{KHURJA.slug}"
    unknown = filing_row(stored("unknown", KHOREZM, cited(HANDBOOK)), None)
    assert (unknown.would, unknown.moves) == ("unknown", False)


def test_the_report_prints_one_line_per_fact_and_a_summary_with_the_unchecked_ones() -> None:
    rows = [
        filing_row(stored("named", f"{AGED}.", cited(STUDY, AGED, passage=PARAGRAPHS)), KHURJA_NAMES),
        filing_row(stored("unchecked", KHOREZM, cited(HANDBOOK)), KHURJA_NAMES),
        filing_row(stored("unnamed", f"{AGED}.", cited(HANDBOOK, AGED)), KHURJA_NAMES),
    ]
    lines = [json.loads(line) for line in report_lines(rows)]
    assert [line["claim"] for line in lines[:3]] == [
        str(claim_id(n)) for n in ("named", "unchecked", "unnamed")
    ]
    assert lines[1] == {
        "claim": str(claim_id("unchecked")),
        "status": "IN_REVIEW",
        "checked": False,
        "is": f"craft:{KHURJA.slug}",
        "would": "refused",
        "why": SKIP_ABROAD.format(places="Khorezm"),
        "text": KHOREZM,
    }
    assert lines[3] == {
        "claims": 3,
        "moves": 2,
        "held": 1,
        "refused": 1,
        "unknown": 0,
        "unchecked": [str(claim_id("unchecked"))],
    }
