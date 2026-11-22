import uuid
from collections.abc import Sequence

from app.research.crafts import CraftRef
from app.services.craft_index import AliasRecord, CraftRecord, build_index
from app.services.write_back_names import CraftFamily, CraftNames, craft_names

from ..research.fixtures import AJRAKH


def ref(slug: str, name: str) -> CraftRef:
    return CraftRef(slug=slug, name=name, path=f"/crafts/{slug}")


def craft_id(slug: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-write-back-names/{slug}")


KHURJA = ref("Khurja-Pottery", "Khurja Pottery")
BLUE_POTTERY = ref("Blue-Pottery-Of-Jaipur", "Blue Pottery of Jaipur")
NIZAMABAD = ref("Nizamabad-Black-Pottery", "Nizamabad Black Pottery")
BAGH = ref("Bagh-Prints-of-Madhya-Pradesh", "Bagh Prints of Madhya Pradesh")
MUD_FAMILY = CraftFamily(name="Mud based Craft Category", slug="Mud-based-Craft-Category")
TEXTILE_FAMILY = CraftFamily(name="Textiles Based Craft Category", slug="Textiles-Based-Craft-Category")
PLACES = {
    AJRAKH.slug: ("Gujarat", "Kachchh"),
    KHURJA.slug: ("Uttar Pradesh", "Bulandshahr", "Khurja"),
    BLUE_POTTERY.slug: ("Rajasthan", "Jaipur"),
    NIZAMABAD.slug: ("Uttar Pradesh", "Azamgarh"),
    BAGH.slug: ("Madhya Pradesh", "Dhar"),
}
ALIASES = {
    AJRAKH.slug: ("Ajrakh",),
    KHURJA.slug: ("Khurja Glazed Pottery",),
    BLUE_POTTERY.slug: ("Jaipur Blue Pottery", "Blue Pottery"),
    BAGH.slug: ("Bagh Print",),
}
CRAFTS = (AJRAKH, KHURJA, BLUE_POTTERY, NIZAMABAD, BAGH)
INDEX = build_index(
    [
        CraftRecord(craft_id(craft.slug), craft.slug, craft.name, "ACTIVE", places=PLACES[craft.slug])
        for craft in CRAFTS
    ],
    [AliasRecord(craft_id(slug), alias) for slug, aliases in ALIASES.items() for alias in aliases],
    [],
)


def names_for(
    lead: CraftRef | None, compared: Sequence[CraftRef] = (), *, family: CraftFamily | None = TEXTILE_FAMILY
) -> CraftNames:
    return craft_names(INDEX, lead, compared, family=family)


AJRAKH_NAMES = names_for(AJRAKH)
