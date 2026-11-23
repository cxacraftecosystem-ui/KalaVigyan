from app.services.glossary_plan import SeedConcept, concepts_of, glossary_plan, stated_local_names

AJRAKH = "Kutch-Ajrakh"
TAMARIND_SAID = (
    "Alum is suspended in a sticky paste of boiled powder from roasted and ground tamarind seeds "
    "(locally known as kachika)."
)
TEAK_SAID = "The craftsmen only use teak wood, locally known as ‘Sagwan’, sourced from Valsad."
TURNERS_SAID = "Turners locally known as Kharadiyas produce the blocks from dried wood such as shisham."
ORDINARY = frozenset({"produce", "blocks", "from", "dried", "wood", "such"})


def test_a_name_said_right_after_the_term_s_own_words_is_its_local_name() -> None:
    assert stated_local_names("Tamarind seed paste", [TAMARIND_SAID]) == ["kachika"]
    assert stated_local_names("Teak wood", [TEAK_SAID]) == ["Sagwan"]


def test_a_name_said_of_something_else_in_the_sentence_is_not_the_term_s() -> None:
    assert stated_local_names("Wooden printing blocks", [TEAK_SAID]) == []
    assert stated_local_names("Kharadi block-carvers", [TURNERS_SAID], english=ORDINARY) == []


def test_an_unquoted_name_ends_at_the_first_ordinary_word() -> None:
    assert stated_local_names("Turners", [TURNERS_SAID], english=ORDINARY) == ["Kharadiyas"]


def test_a_short_word_or_an_ordinary_word_is_never_a_local_name() -> None:
    said = ["Turners locally called the master carvers shape the blocks."]
    assert stated_local_names("Turners", said, english=frozenset({"master", "carvers"})) == []


def test_a_stated_name_is_held_to_the_glossary_s_four_words() -> None:
    said = ["Turners locally called Alpha Bravo Charlie Delta Echo work here."]
    assert stated_local_names("Turners", said, english=frozenset()) == ["Alpha Bravo Charlie Delta"]


def test_the_glossary_seed_adds_a_name_a_claim_about_the_concept_states() -> None:
    seed_claims = {
        "concepts": [
            {
                "key": "ie:ajrakh.material.tamarind-seed-paste",
                "craftSlug": AJRAKH,
                "type": "MATERIAL",
                "name": "Tamarind seed paste (pa)",
                "localTerms": ["pa"],
            }
        ],
        "claims": [
            {
                "subjectType": "CONCEPT",
                "subjectKey": "ie:ajrakh.material.tamarind-seed-paste",
                "text": TAMARIND_SAID,
            },
            {
                "subjectType": "EDGE",
                "subjectKey": "ie:other|USES|ie:ajrakh.material.tamarind-seed-paste",
                "text": TEAK_SAID,
            },
        ],
    }
    (concept,) = concepts_of(seed_claims)
    assert concept.claim_texts == (TAMARIND_SAID,)
    (term,) = glossary_plan([], {}, [concept], [])
    assert (term.key, term.local_names) == ("tamarind-seed-paste", ["pa", "kachika"])


def test_a_stated_name_the_glossary_already_holds_is_kept_once() -> None:
    concept = SeedConcept(
        key="ie:teak",
        craft_slug=AJRAKH,
        type="MATERIAL",
        name="Teak wood (sagwan)",
        local_terms=("sagwan",),
        claim_texts=(TEAK_SAID,),
    )
    (term,) = glossary_plan([], {}, [concept], [])
    assert term.local_names == ["sagwan"]
