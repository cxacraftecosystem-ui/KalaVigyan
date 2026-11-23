from app.services.glossary_plan import (
    CraftNames,
    SeedCompound,
    SeedConcept,
    WikidataLink,
    glossary_plan,
    wikidata_links,
)

AJRAKH = "Kutch-Ajrakh"
BAGH = "Bagh-Prints-Of-Madhya-Pradesh"


def concept(
    key: str, name: str, *local: str, kind: str = "MATERIAL", craft: str | None = AJRAKH
) -> SeedConcept:
    return SeedConcept(key=key, craft_slug=craft, type=kind, name=name, local_terms=local)


def planned(*concepts: SeedConcept, crafts=(), wikidata=None, compounds=()) -> dict:
    return {
        seed.key: seed
        for seed in glossary_plan(list(crafts), wikidata or {}, list(concepts), list(compounds))
    }


def test_a_local_name_heading_its_concept_is_a_term_meaning_the_gloss() -> None:
    kut = planned(concept("ie:kut", "Kut (iron-water black paste)", "kut", "lokhand", "gud"))["kut"]
    assert (kut.label, kut.meaning, kut.local_names) == ("Kut", "iron-water black paste", [])
    assert (kut.craft_slugs, kut.concept_keys) == ([AJRAKH], ["ie:kut"])


def test_spelling_variants_of_a_local_head_are_its_local_names() -> None:
    harde = planned(concept("ie:harde", "Harde (myrobalan, Terminalia chebula)", "harde", "harda"))["harde"]
    assert (harde.meaning, harde.local_names) == ("myrobalan, Terminalia chebula", ["harda"])


def test_an_english_head_takes_the_local_names_its_gloss_lists() -> None:
    found = planned(
        concept("ie:alum", "Alum (fatakdi)", "fatakdi"),
        concept("ie:madder", "Indian madder (majith/majeeta, Rubia cordifolia)", "majith", "majeeta", "al"),
    )
    assert (found["alum"].local_names, found["alum"].meaning) == (["fatakdi"], None)
    assert (found["indian-madder"].local_names, found["indian-madder"].meaning) == (
        ["majith", "majeeta"],
        "Rubia cordifolia",
    )


def test_names_that_are_not_terms_are_left_out() -> None:
    found = planned(
        concept("ie:cotton", "Cotton (and silk) base cloth", "bepota"),
        concept("ie:wash", "Washing and beating", "dhoki", kind="PROCESS_STAGE"),
        concept("ie:harara", "3. Harara treatment (yellowing)", "harara", kind="PROCESS_STAGE"),
        concept("ie:secondary", "Secondary yellow/green dye sources", "haldi"),
        concept("ie:idea", "Kut (iron-water black paste)", "kut", kind="MECHANISM"),
        concept("ie:loose", "Gach (mud resist)", "gach", craft=None),
    )
    assert found == {}


def test_a_plain_material_is_a_term_and_a_numbered_stage_with_a_local_gloss_is_one() -> None:
    found = planned(
        concept("ie:beeswax", "Beeswax (resist)"),
        concept("ie:sukhai", "4. Ageing / drying (sukhai)", "sukhai", kind="PROCESS_STAGE"),
        concept(
            "ie:dabu", "1. Scouring (hari sarana, teluni)", "hari sarana", "teluni", kind="PROCESS_STAGE"
        ),
    )
    assert (found["beeswax"].label, found["beeswax"].meaning) == ("Beeswax", "resist")
    assert "ageing-drying" not in found
    assert found["scouring"].local_names == ["hari sarana", "teluni"]


def test_the_same_term_in_two_crafts_is_one_entry_with_both() -> None:
    alum = planned(
        concept("ie:ajrakh.alum", "Alum (fatakdi)", "fatakdi"),
        concept("ie:bagh.alum", "Alum (fitkari)", "fitkari", craft=BAGH),
    )["alum"]
    assert alum.local_names == ["fatakdi", "fitkari"]
    assert alum.craft_slugs == [AJRAKH, BAGH]
    assert alum.concept_keys == ["ie:ajrakh.alum", "ie:bagh.alum"]


def test_a_craft_term_carries_its_aliases_wikidata_labels_and_tradition() -> None:
    craft = CraftNames(
        slug=AJRAKH,
        name="Kutch Ajrakh",
        aliases=("Ajrakh", "Ajrak", "Kutch Ajrakh"),
        local_names=("अज्रख",),
    )
    link = WikidataLink(qid="Q104218192", description="form of blockprinting", labels=("अजरक", "ਅਜਰਕ"))
    tradition = concept(
        "ie:ajrakh.tradition", "Kutch Ajrakh (Ajrakh resist block printing)", kind="TRADITION"
    )
    term = planned(tradition, crafts=[craft], wikidata={AJRAKH: link})["kutch-ajrakh"]
    assert term.aliases == ["Ajrakh", "Ajrak"]
    assert term.local_names == ["अज्रख", "अजरक", "ਅਜਰਕ"]
    assert (term.wikidata_id, term.meaning) == ("Q104218192", "form of blockprinting")
    assert term.concept_keys == ["ie:ajrakh.tradition"]


def test_a_compound_is_a_term_of_the_crafts_whose_materials_use_it() -> None:
    material = concept("ie:ajrakh.material.synthetic-alizarin", "Synthetic alizarin")
    found = planned(
        material,
        compounds=[
            SeedCompound("Alizarin", ("ie:ajrakh.material.synthetic-alizarin",)),
            SeedCompound("Iron(II) acetate", ("ie:unknown.material",)),
        ],
    )
    assert found["alizarin"].craft_slugs == [AJRAKH]
    assert found["alizarin"].concept_keys == ["ie:ajrakh.material.synthetic-alizarin"]
    assert "iron-ii-acetate" not in found


def test_only_matched_wikidata_rows_are_links() -> None:
    document = {
        "crafts": [
            {
                "slug": "A",
                "status": "MATCHED",
                "match": {"qid": "Q1", "description": "d", "labels": {"en": "A", "hi": "ए"}},
            },
            {"slug": "B", "status": "LOW_CONFIDENCE", "match": None, "candidate": {"qid": "Q2"}},
        ]
    }
    assert wikidata_links(document) == {"A": WikidataLink(qid="Q1", description="d", labels=("ए",))}


def test_a_term_is_tagged_with_the_zoom_level_its_definition_or_its_source_states() -> None:
    craft = CraftNames(slug="Kutch-Embroidery", name="Kutch Embroidery")
    link = WikidataLink(
        qid="Q6448245",
        description="handicraft and textile art tradition of Kutch, Gujarat, India",
        labels=("કચ્છ ભરતકામ",),
    )
    found = planned(
        concept("ie:kantan", "Kantan (jute cloth)", "kantan", kind="TOOL"),
        concept("ie:kut", "Kut (iron-water black paste)", "kut"),
        concept("ie:ajrakh.material.synthetic-alizarin", "Synthetic alizarin"),
        crafts=[craft],
        wikidata={"Kutch-Embroidery": link},
        compounds=[SeedCompound("Alizarin", ("ie:ajrakh.material.synthetic-alizarin",))],
    )
    assert found["kantan"].zoom_level == "CLOTH"
    assert (found["kutch-embroidery"].zoom_level, found["kutch-embroidery"].local_names) == (
        "CLOTH",
        ["કચ્છ ભરતકામ"],
    )
    assert found["alizarin"].zoom_level == "MOLECULE"
    assert found["kut"].zoom_level is None
    assert found["synthetic-alizarin"].zoom_level is None
