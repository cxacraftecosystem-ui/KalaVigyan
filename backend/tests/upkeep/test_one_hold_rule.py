from app.retrieval import citation_access
from app.services import claim_holds


def test_the_upkeep_hold_is_retrieval_s_one_rule_and_not_a_copy() -> None:
    assert claim_holds.held_claim is citation_access.held_claim
    assert claim_holds.FAILED_QUOTE is citation_access.FAILED_QUOTE
