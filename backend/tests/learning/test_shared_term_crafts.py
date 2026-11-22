import uuid

from app.services.shared_term_crafts import ConceptClaim, ConceptLink, TermCrafts, shared_term_crafts

ALUM, INDIGO = uuid.UUID(int=1), uuid.UUID(int=2)
AJRAKH, BAGRU, AKOLA = uuid.UUID(int=11), uuid.UUID(int=12), uuid.UUID(int=13)
LABELS = {ALUM: "Alum", INDIGO: "Indigo"}
NOT_NAMING = "Aluminium pots are kept out of the dye house."


def concept(n: int) -> uuid.UUID:
    return uuid.UUID(int=100 + n)


def claim(n: int) -> uuid.UUID:
    return uuid.UUID(int=1000 + n)


def test_a_craft_whose_naming_claim_comes_after_four_others_still_shares_the_term() -> None:
    links = [
        ConceptLink(ALUM, AJRAKH, concept(1)),
        ConceptLink(ALUM, BAGRU, concept(2)),
        ConceptLink(ALUM, BAGRU, concept(3)),
        ConceptLink(ALUM, AKOLA, concept(4)),
    ]
    claims = [
        *(ConceptClaim(concept(1), claim(n), (NOT_NAMING,)) for n in range(1, 5)),
        ConceptClaim(concept(1), claim(5), ("Alum fixes the madder red.",)),
        ConceptClaim(concept(2), claim(6), ("The paste is boiled.", "the alum paste is boiled")),
        ConceptClaim(concept(4), claim(7), ("Madder gives the red.",)),
    ]
    assert shared_term_crafts(LABELS, links, claims) == [
        TermCrafts(ALUM, AJRAKH, (concept(1),), (claim(5),)),
        TermCrafts(ALUM, BAGRU, (concept(2), concept(3)), (claim(6),)),
    ]


def test_every_claim_that_names_the_term_is_kept_however_many_a_concept_holds() -> None:
    links = [ConceptLink(ALUM, AJRAKH, concept(1)), ConceptLink(ALUM, BAGRU, concept(2))]
    claims = [
        *(ConceptClaim(concept(1), claim(n), (f"Alum is weighed for bath {n}.",)) for n in (9, 3, 7, 5, 1)),
        ConceptClaim(concept(2), claim(2), ("Alum brightens the red.",)),
    ]
    assert shared_term_crafts(LABELS, links, claims) == [
        TermCrafts(ALUM, AJRAKH, (concept(1),), (claim(1), claim(3), claim(5), claim(7), claim(9))),
        TermCrafts(ALUM, BAGRU, (concept(2),), (claim(2),)),
    ]


def test_a_term_only_one_craft_s_claims_name_is_not_shared() -> None:
    links = [ConceptLink(INDIGO, AJRAKH, concept(1)), ConceptLink(INDIGO, BAGRU, concept(2))]
    claims = [
        ConceptClaim(concept(1), claim(1), ("Indigo is fermented in the vat.",)),
        ConceptClaim(concept(2), claim(2), ("The vat is stirred each morning.",)),
    ]
    assert shared_term_crafts(LABELS, links, claims) == []
