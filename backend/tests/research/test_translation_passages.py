import hashlib
import json

import pytest

from app.core.errors import InvalidInput
from app.research.translation_passages import (
    PassageLeaf,
    is_translatable,
    passage_leaves,
    task_passage,
    unit_hash,
    with_texts,
)

PLANT = {"m": "i", "role": "bot", "c": ["Indigofera tinctoria"]}
CITE = {"m": "cite", "key": "c2", "g": ["g1", "g4"], "c": ["shrub."]}
NODES = [{"m": "s", "sid": "s1", "c": ["The dye comes from ", PLANT, ", a ", CITE]}]


def test_a_passage_s_texts_are_its_leaves_in_order_with_names_fixed_and_the_citation_marked() -> None:
    assert passage_leaves(NODES) == [
        PassageLeaf("The dye comes from ", fixed=False, cited=False),
        PassageLeaf("Indigofera tinctoria", fixed=True, cited=False),
        PassageLeaf(", a ", fixed=False, cited=False),
        PassageLeaf("shrub.", fixed=False, cited=True),
    ]
    passage = task_passage("u1", NODES, ["claim-2"])
    assert passage.english == "The dye comes from Indigofera tinctoria, a shrub."
    assert (passage.fixed, passage.cited) == ([1], [3])


def test_quotes_formulas_and_their_parts_are_fixed_in_italic_sub_and_sup() -> None:
    nodes = [
        "Alum is K",
        {"m": "sub", "c": ["2"]},
        "SO",
        {"m": "sub", "c": ["4"]},
        " and ",
        {"m": "i", "c": ["kut"]},
    ]
    assert [leaf.fixed for leaf in passage_leaves(nodes)] == [False, True, False, True, False, True]


def test_the_hash_reads_the_text_and_the_claims_but_not_how_the_sources_are_numbered() -> None:
    body = {
        "claims": ["claim-2"],
        "nodes": [
            {
                "m": "s",
                "sid": "s1",
                "c": [
                    "The dye comes from ",
                    PLANT,
                    ", a ",
                    {"m": "cite", "c": ["shrub."]},
                ],
            }
        ],
    }
    expected = hashlib.sha256(
        json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert unit_hash(NODES, ["claim-2"]) == expected
    renumbered = [{**NODES[0], "c": [*NODES[0]["c"][:3], {**CITE, "key": "c9", "g": ["g7"]}]}]
    assert unit_hash(renumbered, ["claim-2"]) == expected
    assert unit_hash(NODES, ["claim-3"]) != expected
    reworded = [{**NODES[0], "c": ["The dye is made from ", *NODES[0]["c"][1:]]}]
    assert unit_hash(reworded, ["claim-2"]) != expected


def test_texts_replace_the_leaves_in_order_and_keep_every_mark() -> None:
    texts = ["रंग ", "Indigofera tinctoria", " से आता है, जो एक ", "झाड़ी है।"]
    assert with_texts(NODES, texts) == [
        {
            "m": "s",
            "sid": "s1",
            "c": [
                "रंग ",
                {"m": "i", "role": "bot", "c": ["Indigofera tinctoria"]},
                " से आता है, जो एक ",
                {"m": "cite", "key": "c2", "g": ["g1", "g4"], "c": ["झाड़ी है।"]},
            ],
        }
    ]
    with pytest.raises(InvalidInput, match="fewer texts"):
        with_texts(NODES, texts[:3])
    with pytest.raises(InvalidInput, match="more texts"):
        with_texts(NODES, [*texts, "और"])


@pytest.mark.parametrize(
    ("key", "nodes", "translatable"),
    [
        ("u1", NODES, True),
        ("masthead-title", ["Kutch Ajrakh"], False),
        ("u2", ["1998"], False),
        ("u3", [{"m": "i", "role": "bot", "c": ["Rubia cordifolia"]}], False),
        ("u4", ["12th century"], True),
    ],
)
def test_a_name_a_date_alone_or_a_botanical_name_alone_is_not_a_passage_to_translate(
    key: str, nodes: list[object], translatable: bool
) -> None:
    assert is_translatable(key, nodes) is translatable
