import uuid

import pytest

from app.services.market_store import PriceOffer, stated_price_offer

CLAIM = uuid.UUID(int=5)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("In Barmer an ajrakh piece was valued at Rs. 7 in 1975.", ("1975", "Barmer", 90)),
        ("In 1971 a cotton bandhani of Kutch cost Rs. 10.", ("1971", "Kutch", 449)),
        ("A cotton one cost Rs. 10 and a silk one Rs. 50 in Kutch in 1971.", None),
        ("In Barmer an ajrakh piece was valued at Rs. 7.", None),
        ("In 1975 an ajrakh piece was valued at Rs. 7 in Barmer and Kachchh.", None),
        ("Between 1975 and 1980 a piece in Barmer cost Rs. 7.", None),
    ],
)
def test_a_cited_claim_gives_a_price_only_when_it_states_one_price_one_year_and_one_district(
    text: str, expected: tuple[str, str, int] | None
) -> None:
    offer = stated_price_offer(CLAIM, text)
    if expected is None:
        assert offer is None
        return
    priced_on, place, district = expected
    assert offer == PriceOffer(claim_id=CLAIM, priced_on=priced_on, place=place, district_lgd=district)
