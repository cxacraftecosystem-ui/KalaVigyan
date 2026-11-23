from collections.abc import Sequence

from app.research.crafts import CraftRef
from app.research.gi_registry import GiFields
from app.science.records import KnownClaim
from app.services.market_builder import IMITATION_MAX, market_block
from app.services.market_store import GiRecordOffer, MarketOffers

from .insight_fixtures import claim_view, source, written

CRAFT = CraftRef(slug="Kutch-Ajrakh", name="Kutch Ajrakh", path="/crafts/Kutch-Ajrakh")
BLOCK = "s5.market1"
SOURCES = {"s-gi": source("s-gi"), "s-paper": source("s-paper", "PAPER")}
DUPLICATE = written("duplicate", "Duplicate ajrakh is sold in the markets of Bhuj as the real cloth.")
COPIES = written("copies", "Copies of ajrakh designs are made on other cloth and sold as Kutch Ajrakh.")
FAKE = written("fake", "Fake ajrakh made by screen printing is sold to tourists.")
PAPER_SIGN = written("paper", "Substitute cloth is sold under the ajrakh name.", source_id="s-paper")


def offers(curated: Sequence[KnownClaim], worded: Sequence[KnownClaim]) -> MarketOffers:
    claims = [*curated, *worded]
    record = GiRecordOffer(GiFields(), claim_ids=(), imitation=tuple(claim.id for claim in curated))
    return MarketOffers(
        craft=CRAFT,
        record=record,
        candidates=tuple(claim.id for claim in worded),
        views={claim.id: claim_view(claim) for claim in claims},
        sources=SOURCES,
    )


def signs(found: MarketOffers) -> list[str]:
    block = market_block(found, block_id=BLOCK)
    return [] if block is None else [sentence.text for sentence in block.imitation]


def test_the_curated_signs_of_imitation_are_shown_first_and_in_their_order() -> None:
    assert signs(offers([COPIES, DUPLICATE], [FAKE])) == [COPIES.text, DUPLICATE.text, FAKE.text]


def test_without_the_curated_list_the_word_list_alone_finds_a_sign() -> None:
    assert signs(offers([], [DUPLICATE, FAKE])) == [FAKE.text]


def test_a_curated_sign_citing_no_gi_journal_is_not_shown() -> None:
    assert signs(offers([PAPER_SIGN, DUPLICATE], [])) == [DUPLICATE.text]


def test_the_signs_stay_within_their_limit() -> None:
    extra = written("passed-off", "Mill-made cloth is passed off as ajrakh.")
    shown = signs(offers([COPIES, DUPLICATE], [FAKE, extra]))
    assert IMITATION_MAX == 3
    assert len(shown) == 3 and shown[:2] == [COPIES.text, DUPLICATE.text]
