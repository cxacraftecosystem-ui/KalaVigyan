from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

__all__ = ["FLAGSHIPS", "FLAGSHIP_KINDS", "FLAGSHIP_TASK", "Flagship"]

FLAGSHIP_TASK = "FLAGSHIP"
FLAGSHIP_KINDS = ("reaction_player", "dip_player", "stage_player", "experiment_lab")


@dataclass(frozen=True)
class Flagship:
    category: str
    family: str
    mechanism: str
    anchor: str
    facts: tuple[str, ...]
    lacks: str


FLAGSHIPS: Mapping[str, Flagship] = MappingProxyType(
    {
        flagship.category: flagship
        for flagship in (
            Flagship(
                "Textiles-Based-Craft-Category",
                "Textiles",
                "two mordants, one bath, then the vat",
                "Machilipatnam-Kalamkari",
                (
                    "927272fb-c58c-5fc5-b35c-2c1baffc4430",
                    "9c16ca66-9f3f-5231-967a-5ea5aa091725",
                    "8d1cc58b-91ab-5b47-b99e-5218c76468b9",
                    "a12abe8c-bc7e-50f0-b815-e9724fd661e8",
                    "278fbf07-3721-50c9-95e1-8eae1778e016",
                    "2a26748e-4f03-5009-a9f5-7aac56adc219",
                    "b25ce086-7bb1-5708-b119-f511e4058f99",
                    "0fe8538d-c217-56ce-bbab-eee0dfa4fd26",
                    "e5b26369-810a-5de7-bcbe-3414f9c10706",
                    "31e2c359-79b2-57f1-aa7a-477032b9941e",
                    "d08e97d1-fb66-5840-893a-a747e4b71a3f",
                    "ec41630b-5440-5a1a-9aa6-5c0b3134e005",
                    "3aa18c50-239e-502d-9ceb-c19dab86996b",
                    "bcd937f4-463e-5f0a-81d1-07c0c95dc582",
                ),
                (
                    "the colour of myrobalan-soaked cloth and of printed alum at Machilipatnam; the "
                    "madder bath's temperature; a specimen token for beeswax; the iron and tannin "
                    "reaction stated for the family (Ajrakh's player states it for Ajrakh only)"
                ),
            ),
            Flagship(
                "Metal-Craft-Category",
                "Metal",
                "lost-wax casting",
                "Bastar-Dhokra",
                (
                    "b6ecc15b-7df9-5345-910e-3567fcde20d1",
                    "719ce082-e2c6-554c-bcd2-2069430b0518",
                    "363142f6-a0b1-54ad-8273-ecff710ff523",
                    "b834a61e-7cfb-5df9-959e-c1a9ecdbf2ba",
                    "e5f65f11-3e43-5f28-b278-77e75e6089d1",
                    "c8a447a1-455a-5fa5-98ee-1d2616204aaf",
                    "d22cb755-2059-5839-b597-f70f60cd5040",
                    "cfa22a02-e146-5020-997c-5f3b99e01ce0",
                    "cbbb14cc-0a00-5f36-b426-6e16a6e980ac",
                    "0a31b75b-2546-5e26-9dfe-68e39cd13a3d",
                    "03e7bd26-45bd-54ef-a3fa-aea9560ce658",
                    "8d62a631-8933-58d2-85f0-5098a089938e",
                    "4dc046eb-3fa2-5ebc-8584-b3194827909c",
                    "ce27e50f-2373-58f5-9667-fa0ce474ef29",
                    "9e65aba7-c844-5752-97ad-af78d9106301",
                    "28c1ea0f-4f42-5eaf-b177-683590ecc598",
                    "cdcfbd45-cc3d-54c2-9c66-8f1a21a05655",
                ),
                (
                    "specimen tokens for beeswax, the clay coat, the glowing mould and molten and cast "
                    "bell metal; the melting range of dhokra's mixed metal (the 750 °C held for Aranmula "
                    "is delta bronze, another alloy, and is never borrowed); what happens at the cast's "
                    "surface as it cools"
                ),
            ),
            Flagship(
                "Mud-Based-Craft-Category",
                "Clay",
                "firing, heat and air",
                "Nizamabad-Black-Pottery",
                (
                    "f00fb976-29ea-5525-bfb9-5d7fd313bb55",
                    "7687cf86-9ccf-5fcc-9cd0-85f76c30a8dc",
                    "ad03d709-7849-511e-98b2-dda5b12bfd24",
                    "984c0242-7fc8-5ecd-b38a-67203e513576",
                    "7a6778e6-06c6-5706-b6d9-879f633986c0",
                    "e11b81ee-0c66-5e9a-b51a-2886642c3e6e",
                    "bc57e48d-04bf-529d-83f4-02da47aa31ea",
                    "0c1f8353-55e9-5de9-b2da-b28c006c32f6",
                    "15f7e5c5-ddd4-5c72-872b-b15228f8afbd",
                    "8a9cc95d-a573-5bcc-92b1-a136054a1a91",
                    "366c1697-ea97-5158-a028-46711b74a7c5",
                    "49f1e3a3-108b-55bc-8f64-8efa70881ac8",
                ),
                (
                    "specimen tokens for raw, leather-hard, red-fired and black-fired clay; iron's "
                    "oxidation as a source writes it (the facts give hematite and the lower oxides, not a "
                    "reaction); a second source for Nizamabad's firing temperature"
                ),
            ),
            Flagship(
                "Stone-Craft-Category",
                "Stone",
                "carving by removal",
                "Mahabalipuram-Stone-Sculpture",
                (
                    "155b60df-ed58-546d-b1f2-d245845be43f",
                    "07e5f9ae-c420-5e77-974a-d64cc72408c1",
                    "5054bc9f-f908-5bb6-aeaf-14ebe1c97216",
                    "73505123-c9bd-5539-8d2c-54b9e893b9a1",
                    "b7435f29-072b-5c06-96b8-5d61e049fe42",
                    "5bf5c0b6-b563-5f8b-bc6d-400e27b9e49d",
                    "d9bbc332-3e25-5d56-9818-a6b0b50562a1",
                    "db60eee1-e2e3-564c-8f21-dc333bc06c87",
                    "b6401a06-aab9-5c77-8ad7-95969a72ca65",
                ),
                (
                    "specimen tokens for the stones; the family's stones on a stated hardness scale (none "
                    "is held); the minerals that make granite hard (talc in soapstone is held)"
                ),
            ),
            Flagship(
                "Wood-Craft-Category",
                "Wood",
                "turning and lac",
                "Sankheda-Furniture",
                (
                    "6f8ef9d6-2b9a-5cea-ad62-e371d3ee2eb6",
                    "81c9cdfb-2596-56ec-b935-eeb56e487e31",
                    "73e3eeab-bfa7-54bd-8006-100034806a72",
                    "a1d89010-6517-529a-8041-540bafbfe770",
                    "a5eaac63-1b72-5a13-937a-6a91f584f40f",
                    "d6f8a0af-89cd-5ed1-9241-3d9d42e9c624",
                    "2fbf8f6d-97da-55c6-9ac2-cf55c5afe6f0",
                    "a377d2ad-b29b-5543-9ef4-8caeba8d55eb",
                    "7fee6004-37be-50ae-9cac-54807ee91807",
                    "1568c8f6-8a9a-5398-a8ba-cde38a73d830",
                ),
                (
                    "specimen tokens for wood, lac and its colours; a stated softening temperature of "
                    "lac; the moisture content of seasoned wood"
                ),
            ),
            Flagship(
                "Leather-Craft-Category",
                "Leather",
                "tanning",
                "Kolhapuri-Chappal",
                (
                    "a240e9b6-5aea-5374-a343-b4f5d4e40729",
                    "fda07b59-6896-5ea8-badc-9495a04c3adc",
                    "bb10778f-9257-5885-b98c-84f0b981ba54",
                    "13bc3616-50db-5c1e-87b3-74b9ff3ec235",
                    "ba23d94c-b5c1-582c-a1b6-115fe8d6c832",
                    "4465cb61-d2fd-5e8a-a7c0-ae65380c29c5",
                    "65b57b2b-2cdb-56df-8181-938fb52275c9",
                    "45bc75db-1cb2-5474-a7df-1e1b043b9cda",
                    "b184c5f6-38e0-5987-9b10-2094351d759b",
                    "7fd9700d-1d34-52b0-b977-575ce8709c2e",
                    "42881c1f-5d9d-5fac-82df-23075047868d",
                    "648bc8e4-3aa9-583d-827a-4b7ad2f92fac",
                ),
                (
                    "specimen tokens for raw hide and tanned leather; Kolhapuri's own bag-tanning steps "
                    "as facts of its page; the shrinkage temperature of vegetable-tanned buffalo hide "
                    "(the 70 °C held is goatskin with pala tannin)"
                ),
            ),
            Flagship(
                "Natural-Fibre-Grass-Work",
                "Natural fibre and grass",
                "along the fibre",
                "Bareilly-Cane-Bamboo-Craft",
                (
                    "e0dc751d-3300-54de-b1bc-29dabef95ad0",
                    "532581ac-8c01-5c78-9321-f74bc6d9022a",
                    "02f920d3-7526-533c-b9df-c4b3c5b60941",
                    "c99f6416-1543-5378-9787-3f5b2c30f3a3",
                    "d0eabd9a-0205-53ed-865b-70f8a86f4395",
                    "e5913f0e-87ef-5539-970f-69ba27168e2a",
                    "2bba60b1-94a0-536c-bffd-0ea11eb228a0",
                    "2517cbb5-4a67-59bf-89eb-924a759df027",
                    "dbf22725-80ac-5f2f-9ff7-231d9176ccae",
                    "ea9cfc86-03c6-5ec7-b481-9d62684b11cb",
                ),
                (
                    "specimen tokens for green and dried culm, cane and grass; why water and heat let a "
                    "culm bend (no fact states it); the temperature a cane is heated to"
                ),
            ),
            Flagship(
                "Paper-Craft-Category",
                "Paper",
                "fibre to sheet",
                "Arunachal-Pradesh-Monpa-Handmade-Paper",
                (
                    "04b2042e-7cb8-5c1d-8602-71151acac909",
                    "cf9723f9-b37b-5f24-8b4e-f5a76017b450",
                    "9162fca0-1070-5399-bb39-b75b8e647d6f",
                    "8042aba6-a2d6-533a-b2bd-2d00ef2ab2c8",
                    "83c9435a-58c5-557c-bb42-68c3ffc8cccc",
                    "aeded621-328e-52b8-b762-1b8b71325d42",
                    "f3709b99-e5f6-5fe6-a62c-699ee32b0d52",
                    "812cb2b5-18e1-5505-bc41-9050aa5d680e",
                    "ac4a3298-a802-5d5e-b582-723a64e30431",
                    "783feae0-f0b8-5f67-b338-772a634ac181",
                    "f970a7a4-4855-5fe9-8756-4091c0f0dbb3",
                    "5d929173-765a-5256-9c7f-7c660280ba85",
                ),
                (
                    "specimen tokens for pulp and sheet; what holds a sheet together as it dries (no fact "
                    "states it); Monpa's own steps as facts of its page"
                ),
            ),
            Flagship(
                "Miscellaneous",
                "More crafts",
                "ground, pigment and binder",
                "Orissa-Pattachitra",
                (
                    "f395c728-6b5f-5dc8-9aa8-b758aafc068a",
                    "0d7746b3-01f0-590a-a0f1-c475ce138bab",
                    "bf44fb5f-7de4-56ff-b074-9a218e315ce0",
                    "8542c006-62d2-5b78-abba-549b828fa841",
                    "0430065e-2578-513e-8f6f-27c28e077ae3",
                    "bc7ab964-9fc9-5d08-b340-45b6c2a8354c",
                    "2ebb2b37-5c74-56f1-a5da-ce6ef802950d",
                    "0fed20dd-4259-55d2-987d-35a98f59673b",
                    "2c2db602-b5cb-52a4-b84d-36e0378c64a4",
                    "f4cfb73c-87ab-5253-bbfa-c7df6767af2a",
                    "b983d8c7-d0b4-5fb3-83ef-30805fb2deaa",
                    "3a6c9021-d269-59f3-a5a8-60a993dbe001",
                ),
                (
                    "specimen tokens for the mineral pigments, the chalk ground and the lacquer; what a "
                    "gum binder does as the paint dries (no fact states it); glass's melting reactions as "
                    "a source writes them (the facts give the fluxes, the carbon dioxide and the "
                    "silicates, not an equation)"
                ),
            ),
        )
    }
)
