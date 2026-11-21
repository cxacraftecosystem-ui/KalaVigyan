import uuid

from app.media.claim_set import claim_set, enough_claims
from app.media.records import CitationFacts
from app.research.retrieval import chunk_acls_for
from app.schemas.media import names_a_group

from .fakes import claim, passing, unchecked


def ids(n: int) -> list[uuid.UUID]:
    return [uuid.UUID(int=i) for i in range(1, n + 1)]


STUDENT = ("PUBLIC",)
EVERY_READER = ("PUBLIC", "SIGNED_IN")
RESEARCHER = ("PUBLIC", "RESEARCHER", "SIGNED_IN")


def test_only_reviewed_verified_and_quote_checked_provisional_claims_enter() -> None:
    a, b, c, d, e = ids(5)
    found = claim_set(
        [
            claim(a, "Verified fact.", level="VERIFIED"),
            claim(b, "Reviewed fact.", level="REVIEWED", citations=(unchecked(),)),
            claim(c, "Provisional with a passing quote.", level="PROVISIONAL"),
            claim(d, "Provisional without a passing quote.", level="PROVISIONAL", citations=(unchecked(),)),
            claim(e, "A hypothesis.", level="HYPOTHESIS"),
        ],
        acls=STUDENT,
    )
    assert [x.id for x in found] == [a, b, c]


def test_hidden_statuses_closed_sensitivity_and_restricted_sources_stay_out() -> None:
    a, b, c, d, e, f = ids(6)
    restricted = CitationFacts(quote_check="PASS", restricted=True, chunk_acl=None)
    found = claim_set(
        [
            claim(a, "Draft.", status="DRAFT"),
            claim(b, "Rejected.", status="REJECTED"),
            claim(c, "Retracted.", status="RETRACTED"),
            claim(d, "Attribute required.", sensitivity="ATTRIBUTE_REQUIRED"),
            claim(e, "Cited once by a restricted source.", citations=(passing(), restricted)),
            claim(f, "Proposed but reviewed.", status="PROPOSED"),
        ],
        acls=STUDENT,
    )
    assert [x.id for x in found] == [f]


def test_a_researcher_only_quote_counts_only_for_researchers() -> None:
    a, b = ids(2)
    claims = [
        claim(
            a, "Quoted from a researcher passage.", level="PROVISIONAL", citations=(passing("RESEARCHER"),)
        ),
        claim(b, "Reviewed through a researcher passage.", citations=(unchecked("RESEARCHER"),)),
    ]
    assert claim_set(claims, acls=STUDENT) == ()
    assert [x.id for x in claim_set(claims, acls=RESEARCHER)] == [b, a]


def test_strongest_level_then_own_claims_then_id_and_at_most_eight() -> None:
    claims = [
        claim(uuid.UUID(int=20), "Material, verified.", level="VERIFIED", own=False),
        claim(uuid.UUID(int=30), "Own, verified.", level="VERIFIED"),
        claim(uuid.UUID(int=10), "Own, provisional.", level="PROVISIONAL"),
        *[claim(uuid.UUID(int=100 + i), f"Own reviewed {i}.") for i in range(8)],
    ]
    found = [x.id.int for x in claim_set(claims, acls=STUDENT)]
    assert found == [30, 20, 100, 101, 102, 103, 104, 105]


def test_a_claim_reached_twice_counts_once_as_the_stage_s_own() -> None:
    (a,) = ids(1)
    found = claim_set([claim(a, "Alum.", own=False), claim(a, "Alum.", own=True)], acls=STUDENT)
    assert len(found) == 1 and found[0].own


def test_claims_naming_a_community_or_caste_never_reach_a_prompt() -> None:
    a, b = ids(2)
    found = claim_set(
        [claim(a, "The Khatri community prints Ajrakh."), claim(b, "Alum fixes the red dye.")],
        acls=STUDENT,
    )
    assert [x.id for x in found] == [b]
    assert names_a_group("A caste of dyers") and not names_a_group("Communicating vessels")


def test_two_claims_are_enough_and_acls_follow_the_role() -> None:
    a, b = ids(2)
    assert not enough_claims(claim_set([claim(a, "One.")], acls=STUDENT))
    assert enough_claims(claim_set([claim(a, "One."), claim(b, "Two.")], acls=STUDENT))
    assert chunk_acls_for("STUDENT") == EVERY_READER
    assert chunk_acls_for("RESEARCHER") == RESEARCHER


def test_a_citation_no_reader_may_read_counts_for_nobody() -> None:
    a, b = ids(2)
    unreadable = CitationFacts(quote_check="PASS", restricted=False, chunk_acl=None)
    claims = [
        claim(a, "Quoted from a passage no reader may read.", level="PROVISIONAL", citations=(unreadable,)),
        claim(b, "Reviewed through it alone.", citations=(unreadable,)),
    ]
    assert claim_set(claims, acls=STUDENT) == ()
    assert claim_set(claims, acls=RESEARCHER) == ()
