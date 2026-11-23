import pytest

from app.research.images import ImageCandidate
from app.services.picture_sites import blocked_picture
from app.services.section_images import SectionImages

from ..images.fakes import RETRIEVED, FakeMediaStore, FakeSource, searched_by
from ..images.test_section_images import STICKY, ask


def at(page_url: str, image_url: str | None = None, title: str = "Ajrakh cloth") -> ImageCandidate:
    return ImageCandidate(
        provider="searxng",
        page_url=page_url,
        image_url=image_url or f"{page_url.rstrip('/')}/picture.jpg",
        original_url=image_url or f"{page_url.rstrip('/')}/picture.jpg",
        title=title,
        site="pictures",
        retrieved_at=RETRIEVED,
    )


@pytest.mark.parametrize(
    "page_url",
    [
        "https://www.itokri.com/kutch-ajrakh-dress",
        "https://www.jiomart.com/p/ajrakh-saree",
        "https://houseofelegance.in/indigo-duo",
        "https://gitagged.com/ajrakh",
        "https://festivefolks.com/ajrakh",
        "https://www.instagram.com/p/Cx1",
        "https://m.facebook.com/ajrakh",
        "https://in.pinterest.com/pin/1",
        "https://www.amazon.in/dp/B0",
        "https://www.flipkart.com/ajrakh",
        "https://www.etsy.com/listing/1",
        "https://www.meesho.com/ajrakh",
        "https://ajrakh-store.myshopify.com/collections/all",
        "https://craftmark.example.org/products/ajrakh-stole",
        "https://weavers.example.org/shop/ajrakh",
        "https://www.fabindia.com/ajrakh-kurta-10712345",
        "https://www.gocoop.com/ajrakh-saree",
        "https://www.exportersindia.com/ajrakh.htm",
        "https://www.tjori.com/ajrakh",
        "https://www.biba.in/ajrakh",
        "https://www.kalkifashion.com/ajrakh",
        "https://www.unnatisilks.com/ajrakh",
        "https://www.peachmode.com/ajrakh",
        "https://www.youtube.com/watch?v=abc",
        "https://anystore.in/collections/ajrakh-dupatta",
        "https://weavers.example.org/store/ajrakh",
    ],
)
def test_a_shop_marketplace_or_social_page_is_never_shown(page_url: str) -> None:
    found = at(page_url)
    assert blocked_picture(page_url=found.page_url, image_url=found.image_url, title=found.title)


def test_a_shop_s_image_host_or_a_buy_title_is_never_shown() -> None:
    assert blocked_picture(
        page_url="https://blog.example.org/ajrakh",
        image_url="https://i.pinimg.com/originals/ab/cd/ajrakh.jpg",
        title="Ajrakh",
    )
    assert blocked_picture(
        page_url="https://blog.example.org/ajrakh",
        image_url="https://blog.example.org/a.jpg",
        title="Buy Ajrakh",
    )


@pytest.mark.parametrize(
    "page_url",
    [
        "https://commons.wikimedia.org/wiki/File:Ajrak_Printing_Materials_1.jpg",
        "https://www.flickr.com/photos/nevilzaveri/123",
        "https://collections.vam.ac.uk/item/O132500/",
        "https://www.metmuseum.org/art/collection/search/1",
        "https://exhibitions-khamir.org/ajrakh/art-of-ajrakh",
        "https://harvardartmuseums.org/collections/object/229947",
    ],
)
def test_museum_archive_and_open_photo_pages_are_shown(page_url: str) -> None:
    found = at(page_url)
    assert not blocked_picture(page_url=found.page_url, image_url=found.image_url, title=found.title)


async def test_section_pictures_never_offer_a_shop_s_picture() -> None:
    shop = at("https://www.itokri.com/sticky-gums-printing", title="Printing with sticky gums")
    museum = at("https://collections.vam.ac.uk/item/O1/", title="Printing with sticky gums, a museum sample")
    store = FakeMediaStore({STICKY.claim_id: STICKY})
    block = await SectionImages(
        sources=searched_by(
            FakeSource("searxng", [shop, museum]),
        ),
        store=store,
    ).block(ask(STICKY))
    assert block is not None
    assert [item.media.page_url for item in block.items] == ["https://collections.vam.ac.uk/item/O1/"]
