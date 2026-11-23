from app.data.craft_master_loader import parse_codes, parse_master
from app.data.craft_text import alias_norm

from alias_entries import ACTIVE, PROPOSED, TRUST, dedupe, entry, name_variants
from alias_scripts import common_romanisations, cross_script, latin_forms, pure_script, vocabulary_tokens
from aliases import merge


def master_row(serial, name, slug, *, sub="Hand-Block-Printing", states=("Rajasthan",), notes=()):
    return {
        "category": "Textiles based Craft Category",
        "categorySlug": "Textiles-Based-Craft-Category",
        "subCategory": "Hand Block Printing",
        "subCategorySlug": sub,
        "sourceSerial": serial,
        "craftName": name,
        "craftSlug": slug,
        "stateOfOrigin": list(states),
        "stateOfPractice": list(states),
        "giStatus": "GI",
        "notes": list(notes),
    }


CRAFTS = parse_master(
    [
        master_row(41, "Bagru Hand Block Print", "Bagru-Hand-Block-Print"),
        master_row(40, "Sanganeri Hand Block Printing", "Sanganeri-Hand-Block-Printing"),
        master_row(46, "Kutch Ajrakh", "Kutch-Ajrakh", states=("Gujarat",)),
        master_row(
            57,
            "Other Hand Block Print",
            "Other-Hand-Block-Print",
            notes=("Catch-all row for its sub-category ('Other ...'), not a single named craft.",),
        ),
    ]
)
CODES = parse_codes(
    {
        "version": 1,
        "crafts": [
            {"code": "ajrakh", "name": "Ajrakh", "spellings": ["Ajrak", "Ajrakh printing"]},
            {
                "code": "sanganeri",
                "name": "Sanganeri print",
                "spellings": ["Sanganeri Hand Block Printing", "Sanganer"],
            },
            {
                "code": "block-print",
                "name": "Block print",
                "spellings": ["Bagru Hand Block Print", "Sanganeri Hand Block Printing"],
            },
            {"code": "warli", "name": "Warli", "spellings": ["Warli painting"]},
        ],
    }
)
CURATED = {
    "crafts": [
        {"oldName": "Bagru Hand Block Printing", "sourceSerial": 41},
        {"oldName": "Dabu Hand Block Printing", "adopt": "Hand-Block-Printing"},
    ],
    "freeText": [{"text": "Bagru printing Jaipur", "sameAs": "Bagru Hand Block Printing"}],
}
WIKIDATA = {
    "crafts": [
        {
            "slug": "Bagru-Hand-Block-Print",
            "status": "MATCHED",
            "match": {
                "qid": "Q107598910",
                "labels": {"en": "Bagru print", "hi": "बगरू छपाई"},
                "aliases": {"en": ["Bagru prints"]},
                "enwiki": {"title": "Bagru print"},
                "sitelinks": {"hiwiki": "बगरू छपाई"},
            },
        },
        {
            "slug": "Kutch-Ajrakh",
            "status": "LOW_CONFIDENCE",
            "match": None,
            "candidate": {"qid": "Q1", "labels": {"en": "Ajrakhpur"}, "aliases": {}},
        },
    ]
}
IMMERSIVE = {"Kutch-Ajrakh": ["Ajrakh resist block printing (Kutch Ajrakh)", "Ajrak", "Sindhi Ajrak"]}


def run():
    return merge(
        CRAFTS, CODES, CURATED, wikidata=WIKIDATA, immersive=IMMERSIVE, vocabulary=frozenset({"bagru", "ajrakh"})
    )


def norms(result, slug, status=None):
    return {a["norm"] for a in result["crafts"][slug]["aliases"] if status is None or a["status"] == status}


def test_master_names_and_derived_variants_are_aliases():
    result = run()
    assert "bagru hand block print" in norms(result, "Bagru-Hand-Block-Print")
    assert name_variants('Nachiarkoil Kuthuvilakku ("Nachiarkoil Lamp")') == [
        'Nachiarkoil Kuthuvilakku ("Nachiarkoil Lamp")',
        "Nachiarkoil Kuthuvilakku",
        "Nachiarkoil Lamp",
    ]
    assert name_variants("Bagh Prints of Madhya Pradesh")[-1] == "Bagh Prints"


def test_curated_old_names_and_same_as_free_text_map_to_the_craft():
    result = run()
    bagru = norms(result, "Bagru-Hand-Block-Print")
    assert "bagru hand block printing" in bagru
    assert "bagru printing jaipur" in bagru


def test_adopt_rows_are_not_craft_aliases():
    result = run()
    assert not any("dabu" in n for slug in result["crafts"] for n in norms(result, slug))


def test_codes_map_by_exact_spelling_and_ambiguous_codes_are_reported():
    result = run()
    assert result["codes"]["mapped"]["ajrakh"]["slug"] == "Kutch-Ajrakh"
    assert result["codes"]["mapped"]["sanganeri"]["slug"] == "Sanganeri-Hand-Block-Printing"
    assert result["codes"]["ambiguous"]["block-print"] == ["Bagru-Hand-Block-Print", "Sanganeri-Hand-Block-Printing"]
    assert "warli" in result["codes"]["unmapped"]
    assert {"ajrak", "ajrakh printing"} <= norms(result, "Kutch-Ajrakh", ACTIVE)


def test_only_matched_wikidata_rows_contribute():
    result = run()
    assert "bagru print" in norms(result, "Bagru-Hand-Block-Print")
    assert "बगरू छपाई" in norms(result, "Bagru-Hand-Block-Print")
    assert "ajrakhpur" not in norms(result, "Kutch-Ajrakh")


def test_indic_labels_gain_latin_transliterations():
    result = run()
    bagru = result["crafts"]["Bagru-Hand-Block-Print"]["aliases"]
    latin = {a["norm"] for a in bagru if a["source"] == "TRANSLITERATION" and a["script"] == "Latn"}
    assert "bagru chapai" in latin
    assert "bagaru chapai" in latin


def test_cross_script_and_latin_to_devanagari_are_proposed_only():
    result = run()
    gujarati = [a for a in result["crafts"]["Kutch-Ajrakh"]["aliases"] if a["via"] and a["via"].endswith("-to-Gujr")]
    deva = [a for a in result["crafts"]["Kutch-Ajrakh"]["aliases"] if a["via"] == "Latn-to-Deva"]
    assert deva and all(a["status"] == PROPOSED for a in deva)
    assert all(a["status"] == PROPOSED for a in gujarati)
    assert not [a for a in result["crafts"]["Sanganeri-Hand-Block-Printing"]["aliases"] if a["via"] == "Latn-to-Deva"]


def test_dedupe_keeps_most_trusted_source_and_records_all_sources():
    rows = dedupe(
        [
            entry("Bagru Print", "WIKIDATA"),
            entry("bagru print", "IMMERSIVE"),
            entry("BAGRU  PRINT", "TRANSLITERATION", status=PROPOSED),
        ]
    )
    assert len(rows) == 1
    assert rows[0]["source"] == "IMMERSIVE"
    assert rows[0]["sources"] == ["IMMERSIVE", "WIKIDATA", "TRANSLITERATION"]
    assert rows[0]["status"] == ACTIVE


def test_generic_and_short_aliases_are_dropped():
    assert entry("Embroidery", "WIKIDATA") is None
    assert entry("Hand Block Printing", "WIKIDATA") is None
    assert entry("ab", "WIKIDATA") is None
    assert entry("", "WIKIDATA") is None


def test_collisions_list_norms_shared_by_crafts():
    result = merge(
        CRAFTS,
        CODES,
        CURATED,
        immersive={"Bagru-Hand-Block-Print": ["Syahi Begar"], "Sanganeri-Hand-Block-Printing": ["Syahi Begar"]},
    )
    assert {"norm": "syahi begar", "slugs": ["Bagru-Hand-Block-Print", "Sanganeri-Hand-Block-Printing"]} in result[
        "collisions"
    ]


def test_catch_all_rows_get_their_name_but_no_code():
    result = run()
    assert "other hand block print" in norms(result, "Other-Hand-Block-Print")
    assert result["crafts"]["Other-Hand-Block-Print"]["craftCodes"] == []


def test_norms_are_rapidfuzz_friendly():
    from rapidfuzz import fuzz

    assert alias_norm("Bāgru  Print!") == "bagru print"
    assert fuzz.ratio(alias_norm("Bagru Print"), alias_norm("bagroo print")) > 80


def test_romanisation_helpers():
    assert "chikankari" in common_romanisations("cikankari")
    assert "bandhni" in common_romanisations("bamdhni")
    assert latin_forms("बगरू")[:2] == ["bagaru", "bagru"]
    assert vocabulary_tokens("# comment\ndabu\nkesula flower\n\nab\n") == frozenset({"dabu", "kesula", "flower"})


def test_merge_is_deterministic():
    assert run() == run()
    assert TRUST["MASTER"] < TRUST["TRANSLITERATION"]


def test_cross_script_output_is_pure_or_dropped():
    assert cross_script("बगरू", "Gujr") == "બગરૂ"
    assert cross_script("ওয়ারলি", "Gujr") is None
    assert pure_script("બગરૂ છાપ", "Gujr")
    assert not pure_script("ओय়ारलि", "Deva")
