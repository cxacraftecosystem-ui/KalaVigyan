from seed_immersive import QUOTE_MAX, clip_quote, convert_immersive
from seed_inferential import convert_inferential
from seed_terms import stage_type

TRADITION = {
    "format_version": 1,
    "slug": "bagru",
    "name": "Bagru hand block printing",
    "alt_names": ["Bagru print"],
    "region": {"place": "Bagru", "state": "Rajasthan", "lat": 26.8, "lon": 75.5},
    "gi": {"registered": True, "application_no": "183", "year": 2011, "source_ids": ["S1"]},
    "summary": "x",
    "sources": [
        {
            "id": "S1",
            "kind": "historical_documentation",
            "title": "GI Journal",
            "author": "Registry; Textiles Committee",
            "publisher": "IP India",
            "year": 2011,
            "url": "https://example.org/gi",
            "accessed": "2026-10-14",
            "reliability": "high",
            "notes": "n",
        },
    ],
    "concepts": [
        {
            "key": "bagru.process_stage.dabu",
            "type": "process_stage",
            "title": "Dabu mud resist",
            "summary": "s",
            "local_terms": ["dabu"],
            "provenance_kind": "historical_documentation",
            "verification_state": "verified",
            "claims": [
                {
                    "text": "Mud resist is applied by block.",
                    "source_ids": ["S1"],
                    "evidence": [{"source_id": "S1", "locator": "PDF p. 4", "quote": "the mud resist is printed"}],
                }
            ],
        },
        {
            "key": "bagru.process_stage.dye",
            "type": "process_stage",
            "title": "Indigo dyeing",
            "summary": "s",
            "provenance_kind": "hypothesis",
            "verification_state": "verified",
            "claims": [
                {
                    "text": "Indigo may fix better in heat.",
                    "source_ids": ["S1"],
                    "evidence": [{"source_id": "S1", "locator": "PDF p. 5", "quote": "possibly better in heat"}],
                }
            ],
        },
    ],
    "relationships": [
        {
            "source": "bagru.process_stage.dabu",
            "target": "bagru.process_stage.dye",
            "type": "PRECEDES",
            "explanation": "Resist comes before dyeing.",
            "ordinal": 1,
            "provenance_kind": "historical_documentation",
            "verification_state": "verified",
            "source_ids": ["S1"],
            "evidence": [
                {"source_id": "S1", "locator": "PDF p. 4", "quote": "after printing the resist, the cloth is dyed"}
            ],
        },
        {
            "source": "bagru.process_stage.dabu",
            "target": "bagru.tradition.bagru",
            "type": "BELONGS_TO",
            "explanation": "Part of Bagru.",
            "provenance_kind": "researcher_interpretation",
            "verification_state": "verified",
            "source_ids": ["S1"],
        },
    ],
}

INFERENTIAL = {
    "domain": {"slug": "terracotta", "name": "Terracotta", "kind": "craft"},
    "nodes": [
        {
            "key": "clay",
            "label": "Clay",
            "statement": "Clay is plastic when wet.",
            "node_type": "material",
            "knowledge_domain": "material",
            "aliases": [],
            "provenance": [
                {"source_type": "scientific_literature", "citation": "Rice, Pottery Analysis", "detail": "ch. 3"}
            ],
        },
        {
            "key": "firing",
            "label": "Open firing",
            "statement": "Firing drives off water.",
            "node_type": "process_stage",
            "knowledge_domain": "process",
            "provenance": [{"source_type": "expert_interpretation", "citation": "DCH draft", "detail": "d"}],
        },
    ],
    "edges": [
        {
            "source": "clay",
            "target": "firing",
            "relation": "precedes",
            "statement": "Clay is shaped before firing.",
            "determinism": "deterministic",
            "provenance": [
                {"source_type": "scientific_literature", "citation": "Rice, Pottery Analysis", "detail": "ch. 5"}
            ],
        },
    ],
    "chains": [{"key": "T-01", "title": "t", "nodes": ["clay", "firing"]}],
    "evidence": [
        {
            "key": "ev-a",
            "evidence_relation": "analogous",
            "source_type": "other",
            "text": "Mud cracks as it dries.",
            "citation": "General observation",
            "relevant_nodes": ["clay"],
            "misleading": False,
        },
        {
            "key": "ev-b",
            "evidence_relation": "contextual",
            "source_type": "other",
            "text": "Clay is a metal.",
            "citation": "Distractor",
            "relevant_nodes": ["clay"],
            "misleading": True,
        },
    ],
}


def test_immersive_claims_with_checked_quotes_are_provisional():
    part = convert_immersive(TRADITION, "bagru", "Bagru-Hand-Block-Print", "Hand-Block-Printing")
    claim = next(c for c in part["claims"] if c["text"] == "Mud resist is applied by block.")
    assert claim["evidenceLevel"] == "PROVISIONAL"
    assert claim["sources"] == [
        {
            "sourceId": "ie:bagru:S1",
            "locator": "PDF p. 4",
            "quote": "the mud resist is printed",
            "quoteClipped": False,
            "quoteCheck": "PASS",
            "relation": "DIRECT",
            "note": None,
        }
    ]
    assert claim["stage"]["ordinal"] == 1
    assert claim["stage"]["stageType"] == "RESIST"
    assert claim["origin"] == "IMPORT" and claim["systemActor"] == "import"


def test_hypothesis_provenance_stays_hypothesis_even_with_a_quote():
    part = convert_immersive(TRADITION, "bagru", "Bagru-Hand-Block-Print", "Hand-Block-Printing")
    claim = next(c for c in part["claims"] if c["text"].startswith("Indigo may"))
    assert claim["evidenceLevel"] == "HYPOTHESIS"
    assert claim["stage"]["ordinal"] == 2


def test_relationship_explanations_become_edge_claims_except_belongs_to():
    part = convert_immersive(TRADITION, "bagru", "Bagru-Hand-Block-Print", "Hand-Block-Printing")
    edge_claims = [c for c in part["claims"] if c["subjectType"] == "EDGE"]
    assert [c["text"] for c in edge_claims] == ["Resist comes before dyeing."]
    assert {e["relation"] for e in part["edges"]} == {"PRECEDES", "PART_OF"}
    assert part["sources"][0]["reliability"] == "A"
    assert part["sources"][0]["authors"] == ["Registry", "Textiles Committee"]
    assert part["tradition"]["gi"]["sourceIds"] == ["ie:bagru:S1"]


def test_inferential_seeds_are_hypothesis_and_drop_misleading_evidence():
    part = convert_inferential(INFERENTIAL, "terracotta", "Terracotta-Pottery-Works")
    assert {c["evidenceLevel"] for c in part["claims"]} == {"HYPOTHESIS"}
    texts = {c["text"] for c in part["claims"]}
    assert "Clay is a metal." not in texts
    assert "Mud cracks as it dries." in texts
    assert all(c["craftSlug"] is None and c["subCategorySlug"] == "Terracotta-Pottery-Works" for c in part["claims"])
    analog = next(c for c in part["claims"] if c["text"] == "Mud cracks as it dries.")
    assert analog["sources"][0]["relation"] == "ANALOGOUS"
    assert part["chains"][0]["nodes"] == ["inf:terracotta:clay", "inf:terracotta:firing"]
    reliabilities = {s["title"]: s["reliability"] for s in part["sources"]}
    assert reliabilities == {
        "Rice, Pottery Analysis": "C",
        "DCH draft": "D",
        "General observation": "D",
        "Distractor": "D",
    }


def test_claim_ids_are_deterministic():
    a = convert_inferential(INFERENTIAL, "terracotta", "Terracotta-Pottery-Works")
    b = convert_inferential(INFERENTIAL, "terracotta", "Terracotta-Pottery-Works")
    assert [c["id"] for c in a["claims"]] == [c["id"] for c in b["claims"]]
    assert len({c["id"] for c in a["claims"]}) == len(a["claims"])


def test_long_quotes_are_clipped_to_a_verbatim_prefix():
    quote = " ".join(["word"] * 120)
    clipped, flag = clip_quote(quote)
    assert flag and len(clipped) <= QUOTE_MAX and quote.startswith(clipped)
    assert clip_quote("short  quote") == ("short quote", False)


def test_stage_type_keywords():
    assert stage_type("Saaj (scouring)") == "SCOUR"
    assert stage_type("Open firing") == "FIRE"
    assert stage_type("Something else") == "OTHER"
