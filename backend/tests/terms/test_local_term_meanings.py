from app.services.claim_seed import load_seed_claims
from app.services.glossary_plan import SeedConcept, StatedMeaning, concepts_of, glossary_plan
from app.services.local_term_meanings import (
    MeaningRow,
    checked_meanings,
    dossier_quotes,
    load_local_term_meanings,
    meaning_problems,
)

AJRAKH = "Kutch-Ajrakh"
KUT_STAGE = SeedConcept(
    key="ie:kut-stage",
    craft_slug=AJRAKH,
    type="PROCESS_STAGE",
    name="Kut (iron-black printing)",
    local_terms=("kut", "datla"),
    claim_texts=("Black is printed with kut paste, usually an infill (datla) between outlines.",),
)
KUT_PASTE = SeedConcept(
    key="ie:kut-paste",
    craft_slug=AJRAKH,
    type="MATERIAL",
    name="Kut (iron-water black paste)",
    local_terms=("kut", "lokhand", "gud"),
)


def row(term: str, meaning: str, stated: str, *, concept: str = "ie:kut-stage", **more: str) -> MeaningRow:
    return MeaningRow.model_validate(
        {"concept": concept, "term": term, "meaning": meaning, "stated": stated, **more}
    )


def no_quotes(dossier_claim: str) -> list[str]:
    return []


def test_a_meaning_stated_by_a_claim_of_its_concept_passes() -> None:
    concepts = {KUT_STAGE.key: KUT_STAGE}
    assert meaning_problems([row("datla", "infill", "an infill (datla)")], concepts, no_quotes) == []


def test_a_meaning_no_claim_states_or_a_word_the_concept_does_not_list_is_refused() -> None:
    concepts = {KUT_STAGE.key: KUT_STAGE, KUT_PASTE.key: KUT_PASTE}
    rows = [
        row("datla", "filling", "a filling (datla)"),
        row("datla", "infill", "datla"),
        row("mavi", "red", "mavi (red) areas"),
        row("gud", "jaggery", "gud (jaggery)", concept="ie:kut-paste"),
        row("gud", "jaggery", "gud (jaggery)", concept="ie:unknown"),
    ]
    assert meaning_problems(rows, concepts, no_quotes) == [
        "datla: 'a filling (datla)' is not in ie:kut-stage",
        "datla: the stated words name the word or its meaning only",
        "mavi: not a local word of ie:kut-stage",
        "mavi: 'mavi (red) areas' is not in ie:kut-stage",
        "gud: 'gud (jaggery)' is not in ie:kut-paste",
        "gud: no seed concept ie:unknown",
    ]


def test_a_meaning_may_rest_on_a_quote_of_the_named_curated_claim() -> None:
    concepts = {KUT_PASTE.key: KUT_PASTE}
    gud = row("gud", "jaggery", "gud (jaggery)", concept="ie:kut-paste", dossierClaim="Kutch-Ajrakh:C075")
    asked: list[str] = []

    def quotes_of(dossier_claim: str) -> list[str]:
        asked.append(dossier_claim)
        return ["scrap iron, kachuka no loat (tamarind seeds powder) and gud (jaggery) to make paste."]

    assert (meaning_problems([gud], concepts, quotes_of), asked) == ([], ["Kutch-Ajrakh:C075"])


def test_every_shipped_meaning_is_stated_by_the_seed_or_its_curated_claim() -> None:
    concepts = concepts_of(load_seed_claims())
    meanings = checked_meanings(concepts, dossier_quotes)
    assert len(meanings) == len(load_local_term_meanings().meanings)
    found = {meaning.term: meaning.meaning for meaning in meanings}
    assert (found["datla"], found["mavi"], found["gudh"], found["lokhand"], found["gud"]) == (
        "infill",
        "areas where red is required",
        "background",
        "scrap iron",
        "jaggery",
    )


def test_a_stated_meaning_is_a_term_of_its_concept_s_craft_and_a_glossed_term_keeps_its_own_meaning() -> None:
    meanings = [
        StatedMeaning("ie:kut-stage", "datla", "infill"),
        StatedMeaning("ie:kut-paste", "kut", "a guessed second meaning"),
    ]
    found = {seed.key: seed for seed in glossary_plan([], {}, [KUT_STAGE, KUT_PASTE], [], meanings)}
    datla = found["datla"]
    assert (datla.label, datla.meaning, datla.craft_slugs, datla.concept_keys) == (
        "datla",
        "infill",
        [AJRAKH],
        ["ie:kut-stage"],
    )
    assert found["kut"].meaning == "iron-black printing"
