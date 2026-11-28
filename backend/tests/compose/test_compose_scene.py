from app.research.component_specs_kit_scene import KitScene
from app.services.compose_held import HeldReaction, HeldSpecies
from app.services.compose_parts import UnitBook
from app.services.compose_scene import species_drawn, species_scene

from .held import BAGRU, claim

BLACK = claim(3)


def drawn(reaction: HeldReaction) -> tuple[list[tuple[str, str, str | None, bool]], dict]:
    book = UnitBook()
    scene = species_scene(BAGRU, reaction, book)
    units = book.units()
    KitScene.model_validate(scene)
    parts = [
        (units[part["label"]].text, part["role"], part.get("material"), part.get("breaks", False))
        for part in scene["parts"]
    ]
    return parts, scene


def reaction(
    kind: str, reactants: tuple[HeldSpecies, ...], products: tuple[HeldSpecies, ...]
) -> HeldReaction:
    return HeldReaction("R09", kind, "S03", reactants, products, (BLACK,))


def test_oxygen_arrives_in_an_oxidation_before_any_mordant_and_the_product_forms_after() -> None:
    parts, scene = drawn(
        reaction(
            "REDOX",
            (HeldSpecies("ferrous tannate", "Fe2+"), HeldSpecies("atmospheric oxygen")),
            (HeldSpecies("ferric tannate", "Fe3+"),),
        )
    )
    assert parts == [
        ("ferrous tannate", "reactant", None, False),
        ("atmospheric oxygen", "reagent", None, False),
        ("ferric tannate", "product", None, False),
    ]
    assert scene["motion"] == "react"
    formula, _ = drawn(
        reaction("REDOX", (HeldSpecies("leucoindigo"), HeldSpecies("O", "O 2")), (HeldSpecies("x"),))
    )
    assert [role for _, role, _, _ in formula] == ["reactant", "reagent", "product"]


def test_a_mordant_arrives_by_its_material_s_role_or_its_own_name_and_never_when_it_is_all_there_is() -> None:
    parts, _ = drawn(
        reaction("COMPLEXATION", (HeldSpecies("tannin"), HeldSpecies("Syahi")), (HeldSpecies("black"),))
    )
    assert parts[:2] == [("tannin", "reactant", None, False), ("Syahi", "reagent", "--dye-kut", False)]
    named, _ = drawn(
        reaction("COMPLEXATION", (HeldSpecies("turmeric"), HeldSpecies("alum")), (HeldSpecies("yellow"),))
    )
    assert [role for _, role, _, _ in named] == ["reactant", "reagent", "product"]
    alone, _ = drawn(
        reaction("COMPLEXATION", (HeldSpecies("alum"), HeldSpecies("iron")), (HeldSpecies("grey"),))
    )
    assert [role for _, role, _, _ in alone] == ["reactant", "reactant", "product"]
    plain, _ = drawn(
        reaction("COMPLEXATION", (HeldSpecies("tannin"), HeldSpecies("cotton")), (HeldSpecies("cloth"),))
    )
    assert [role for _, role, _, _ in plain] == ["reactant", "reactant", "product"]


def test_a_bond_breaks_only_where_a_hydrolysis_or_a_species_splitting_in_two_says_so() -> None:
    split, _ = drawn(
        reaction(
            "DEHYDROXYLATION",
            (HeldSpecies("kaolinite"),),
            (HeldSpecies("metakaolin"), HeldSpecies("water", "H2O")),
        )
    )
    assert split[0] == ("kaolinite", "reactant", None, True)
    water, _ = drawn(
        reaction(
            "HYDROLYSIS",
            (HeldSpecies("water", "H2O"), HeldSpecies("indican")),
            (HeldSpecies("indoxyl"), HeldSpecies("glucose")),
        )
    )
    assert [(name, breaks) for name, _, _, breaks in water[:2]] == [("water", False), ("indican", True)]
    joined, _ = drawn(
        reaction(
            "COMPLEXATION",
            (HeldSpecies("alizarin"), HeldSpecies("aluminium")),
            (HeldSpecies("lake"), HeldSpecies("water")),
        )
    )
    assert not any(breaks for *_, breaks in joined)


def test_a_species_takes_only_its_own_material_s_colour_and_every_label_cites_the_reaction_s_facts() -> None:
    book = UnitBook()
    scene = species_scene(
        BAGRU,
        reaction("COMPLEXATION", (HeldSpecies("alizarin"), HeldSpecies("aluminium")), (HeldSpecies("red"),)),
        book,
    )
    assert [part.get("material") for part in scene["parts"]] == ["--dye-madder", None, None]
    assert {tuple(unit.claim_ids) for unit in book.units().values()} == {(BLACK,)}
    assert [unit.text for unit in book.units().values()] == ["alizarin", "aluminium", "red"]


def test_a_reaction_draws_as_species_only_when_its_scene_holds_every_one() -> None:
    eight = reaction(
        "OTHER",
        tuple(HeldSpecies(f"r{at}") for at in range(5)),
        tuple(HeldSpecies(f"p{at}") for at in range(3)),
    )
    nine = reaction(
        "OTHER",
        tuple(HeldSpecies(f"r{at}") for at in range(5)),
        tuple(HeldSpecies(f"p{at}") for at in range(4)),
    )
    assert species_drawn(eight) and not species_drawn(nine)
    assert not species_drawn(reaction("OTHER", (), (HeldSpecies("p"),)))
    no_product = species_scene(BAGRU, reaction("OTHER", (HeldSpecies("r"),), ()), UnitBook())
    assert "motion" not in no_product


def test_a_colourless_species_is_drawn_by_its_mark_and_a_species_with_no_recorded_colour_by_neither() -> None:
    book = UnitBook()
    scene = species_scene(
        BAGRU,
        reaction(
            "REDOX",
            (
                HeldSpecies("ferrous ions", "Fe2+"),
                HeldSpecies("atmospheric oxygen"),
                HeldSpecies("water", "H2O"),
            ),
            (HeldSpecies("ferric tannate"), HeldSpecies("hydrogen", "H2"), HeldSpecies("alizarin")),
        ),
        book,
    )
    KitScene.model_validate(scene)
    drawn = [
        (book.units()[part["label"]].text, part.get("material"), part.get("mark")) for part in scene["parts"]
    ]
    assert drawn == [
        ("ferrous ions", None, "ion"),
        ("atmospheric oxygen", None, "gas"),
        ("water", None, "clear"),
        ("ferric tannate", None, None),
        ("hydrogen", None, "gas"),
        ("alizarin", "--dye-madder", None),
    ]
