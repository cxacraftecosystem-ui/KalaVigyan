from app.data.craft_master_loader import MasterCraft

from wikidata_link import describe, resolve_shared
from wikidata_names import Candidate, clean_term, name_similarity, query_variants
from wikidata_scoring import ACCEPT, FLAG, LOW_CONFIDENCE, MATCHED, NO_MATCH, decide, score


def craft(name, slug, states=("Rajasthan",), gi="GI"):
    return MasterCraft(
        category="Textiles based Craft Category",
        category_slug="Textiles-Based-Craft-Category",
        sub_category="Hand Block Printing",
        sub_category_slug="Hand-Block-Printing",
        source_serial=1,
        name=name,
        slug=slug,
        state_of_origin=tuple(states),
        state_of_practice=tuple(states),
        gi_status=gi,
        notes=(),
    )


LABELS = {"Q1": "textile printing technique", "Q2": "village", "Q668": "India", "Q3": "embroidery"}


def candidate(qid, label, types, description="", country=("Q668",), gi=False, enwiki=None, categories=()):
    return Candidate(
        qid=qid,
        labels={"en": label},
        descriptions={"en": description},
        sitelinks={"enwiki": enwiki or label},
        claims={"P31": list(types), "P17": list(country), "P1389": ["Q98399252"] if gi else []},
        enwiki={"categories": list(categories), "coordinates": [], "description": ""},
    )


BAGRU = craft("Bagru Hand Block Print", "Bagru-Hand-Block-Print")


def test_craft_item_beats_place_with_the_same_name():
    names = query_variants(BAGRU)
    craft_item = candidate("Q10", "Bagru print", ["Q1"], "hand block printing from Rajasthan", gi=True)
    town = candidate("Q11", "Bagru", ["Q2"], "town in Jaipur district, Rajasthan", enwiki="Bagru (town)")
    good, _ = score(BAGRU, names, craft_item, LABELS)
    bad, reasons = score(BAGRU, names, town, LABELS)
    assert good >= ACCEPT
    assert bad < FLAG
    assert any("non-craft" in r for r in reasons)


def test_generic_parent_item_is_never_accepted():
    kasuti = craft("Kasuti Embroidery", "Kasuti-Embroidery", states=("Karnataka",))
    generic = candidate("Q12", "embroidery", ["Q3"], "art of decorating fabric", country=())
    conf, reasons = score(kasuti, query_variants(kasuti), generic, LABELS)
    assert conf < FLAG
    assert "generic item" in reasons


def test_decide_needs_margin_and_threshold():
    a = Candidate("Q1")
    b = Candidate("Q2")
    assert decide([]) == NO_MATCH
    assert decide([(0.95, a, []), (0.5, b, [])]) == MATCHED
    assert decide([(0.95, a, []), (0.93, b, [])]) == LOW_CONFIDENCE
    assert decide([(0.65, a, [])]) == LOW_CONFIDENCE
    assert decide([(0.4, a, [])]) == NO_MATCH


def test_shared_item_is_demoted_for_the_weaker_craft():
    match = {"qid": "Q9"}
    rows = [
        {"status": MATCHED, "confidence": 0.99, "match": dict(match), "reasons": []},
        {"status": MATCHED, "confidence": 0.85, "match": dict(match), "reasons": []},
    ]
    resolve_shared(rows)
    assert rows[0]["status"] == MATCHED
    assert rows[1]["status"] == LOW_CONFIDENCE and rows[1]["match"] is None and rows[1]["candidate"] == match


def test_query_variants_split_parentheses_and_state_suffix():
    bagh = craft("Bagh Prints Of Madhya Pradesh", "Bagh", states=("Madhya Pradesh",))
    assert query_variants(bagh) == ["Bagh Prints Of Madhya Pradesh", "Bagh Prints"]
    lamp = craft('Nachiarkoil Kuthuvilakku ("Nachiarkoil Lamp")', "Lamp", states=("Tamil Nadu",))
    assert query_variants(lamp)[1:] == ["Nachiarkoil Kuthuvilakku", "Nachiarkoil Lamp"]


def test_name_similarity_handles_spelling_drift():
    assert name_similarity(["Kutch Ajrakh"], ["Ajrak"]) > 0.7
    assert name_similarity(["Bagru Hand Block Print"], ["Hyderabad"]) < 0.5


def test_clean_term_is_safe_for_sparql_literals():
    assert clean_term('Nachiarkoil "Lamp"\\ x\n') == "Nachiarkoil Lamp x"


def test_describe_reports_gi_and_coordinates():
    cand = candidate("Q10", "Bagru print", ["Q1"], gi=True, categories=["Geographical indications in Rajasthan"])
    cand.claims["P625"] = ["Point(75.5 26.8)"]
    cand.claims["P373"] = ["Bagru print"]
    out = describe(cand, LABELS)
    assert out["gi"] == {
        "tagged": True,
        "wikidataCertification": True,
        "wikipediaCategories": ["Geographical indications in Rajasthan"],
    }
    assert out["coordinates"] == [{"lat": 26.8, "lon": 75.5}]
    assert out["commonsCategory"] == "Bagru print"
    assert out["enwiki"]["url"] == "https://en.wikipedia.org/wiki/Bagru_print"
