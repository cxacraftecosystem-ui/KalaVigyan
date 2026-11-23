from typing import Any

from pydantic import TypeAdapter

from app.research.blocks import BlockBase
from app.research.blocks_place import SeasonsBlock
from app.research.explainer import Block
from app.services.claim_ledger import ClaimLedger, admission_batches
from app.services.ledgered_explainer import ledgered_explainer

from ..contracts.phase_b_golden import phase_b, phase_b_blocks
from .indigo_answer import recorded_indigo
from .indigo_blocks import block
from .indigo_claims import GI_JOURNAL, NAAND, SOURCES, Claim, uid
from .shown import blocks_of, restated_in_other_words

BLOCK = TypeAdapter(Block)
REFS = {ref["id"]: ref for ref in (*SOURCES, *phase_b()["sources"])}
TOLD_AGAIN = {
    0: "Ajrakh work prevailed at Dhamadka for 450 years because a stream of the Indus river gave it water, "
    "until the stream dried up in 1989.",
    2: "After the 2001 earthquake about a hundred families moved from Dhamadka to their present home 40 km "
    "away, seeking good quality groundwater.",
    3: "Excess iron in the groundwater threatened Ajrakh at Dhamadka and threatens it again at Ajrakhpur.",
}
GI_SAID = (
    "Kutch Ajrakh was registered as a Geographical Indication, with its certificate dated 22 April 2024."
)
GI_TOLD_AGAIN = "The Geographical Indication registry granted Kutch Ajrakh its certificate on 22 April 2024."


def doubled_geography() -> list[Block]:
    story = phase_b_blocks()["s1.b1"]
    told = [
        {**story["steps"][step]["sentence"], "id": f"s1.b1.{n}", "text": text, "terms": []}
        for n, (step, text) in enumerate(TOLD_AGAIN.items(), start=1)
    ]
    prose = block("s1.b1", "prose", sentences=told)
    return [BLOCK.validate_python(prose), BLOCK.validate_python({**story, "id": "s1.b2"})]


def admitted_as_streamed(blocks: list[Block]) -> list[BlockBase]:
    ledger = ClaimLedger()
    return [shown for batch in admission_batches(blocks) for shown in ledger.admit("s1", batch, REFS)]


def gi_sentence(sentence_id: str, text: str, claim: str, quote: str = GI_SAID) -> dict[str, Any]:
    citation = {
        "id": uid(f"citation/{claim}"),
        "claimId": uid(f"claim/{claim}"),
        "sourceId": GI_JOURNAL["id"],
        "quote": quote,
        "locator": None,
        "context": None,
        "evidence": "QUOTED",
        "level": "PROVISIONAL",
    }
    return {"id": sentence_id, "text": text, "level": "PROVISIONAL", "citations": [citation], "terms": []}


def said_in(section: str, *sentences: dict[str, Any]) -> Block:
    return BLOCK.validate_python(block(f"{section}.b1", "prose", sentences=list(sentences)))


def test_the_doubled_geography_section_tells_three_of_its_story_steps_twice() -> None:
    assert len(restated_in_other_words(doubled_geography())) == 3


def test_a_story_step_retelling_the_prose_nearly_word_for_word_is_held_back() -> None:
    prose, story = admitted_as_streamed(doubled_geography())
    original = phase_b_blocks()["s1.b1"]["steps"]
    assert [sentence.text for sentence in prose.cited_sentences()] == list(TOLD_AGAIN.values())
    assert [step.sentence.text for step in story.steps] == [original[1]["sentence"]["text"]]
    assert restated_in_other_words([prose, story]) == []


def test_a_figure_whose_every_item_retells_the_prose_keeps_its_first_item() -> None:
    seasons = phase_b_blocks()["s3.b1"]
    (row,) = BLOCK.validate_python(seasons).rows
    told = {
        **row.sentence.model_dump(mode="json", by_alias=True),
        "id": "s1.b1.1",
        "text": "Monsoon humidity slows the production of Ajrakh.",
        "terms": [],
    }
    rowless = {**seasons, "rainfall": None, "datasets": []}
    ledger = ClaimLedger()
    ledger.admit("s1", [BLOCK.validate_python(block("s1.b1", "prose", sentences=[told]))], REFS)
    (kept,) = ledger.admit("s3", [BLOCK.validate_python(rowless)], REFS)
    assert [shown.sentence.text for shown in kept.rows] == [row.sentence.text]
    rained = ClaimLedger()
    rained.admit("s1", [BLOCK.validate_python(block("s1.b1", "prose", sentences=[told]))], REFS)
    (rain,) = rained.admit("s3", [BLOCK.validate_python(seasons)], REFS)
    assert isinstance(rain, SeasonsBlock) and (rain.rows, rain.rainfall is not None) == ([], True)


def test_the_same_fact_filed_under_two_fields_is_said_once() -> None:
    ledger = ClaimLedger()
    first = ledger.admit("s1", [said_in("s1", gi_sentence("s1.b1.1", GI_SAID, "gi-economics"))], REFS)
    again = ledger.admit("s2", [said_in("s2", gi_sentence("s2.b1.1", GI_TOLD_AGAIN, "gi-history"))], REFS)
    assert ([b.id for b in first], again) == (["s1.b1"], [])


def test_the_same_date_of_one_certificate_from_other_evidence_is_said_once() -> None:
    other = "The registry's journal lists the certificate of Kutch Ajrakh as granted on 22 April 2024."
    ledger = ClaimLedger()
    ledger.admit("s1", [said_in("s1", gi_sentence("s1.b1.1", GI_SAID, "gi-economics"))], REFS)
    told = gi_sentence("s2.b1.1", GI_TOLD_AGAIN, "gi-history", quote=other)
    assert ledger.admit("s2", [said_in("s2", told)], REFS) == []


def test_another_passage_of_the_same_source_still_says_something_new() -> None:
    makers = "The registry's journal names the Khatri community of Dhamadka and Ajrakhpur as its makers."
    ledger = ClaimLedger()
    ledger.admit("s1", [said_in("s1", gi_sentence("s1.b1.1", GI_SAID, "gi-economics"))], REFS)
    told = gi_sentence("s2.b1.1", makers, "gi-makers", quote=makers)
    (kept,) = ledger.admit("s2", [said_in("s2", told)], REFS)
    assert [sentence.text for sentence in kept.cited_sentences()] == [makers]


def test_a_near_copy_that_changes_a_quantity_or_a_negation_is_kept() -> None:
    longer = Claim(
        "naand-longer", "The cloth is dyed in indigo for 20 minutes in a naand dug into the ground.", ()
    )
    unwashed = Claim("unwashed", "The cloth is not dyed in indigo for 10 to 15 minutes in a naand dug.", ())
    ledger = ClaimLedger()
    said = gi_sentence("s1.b1.1", NAAND.text, "naand", quote=NAAND.text)
    ledger.admit("s1", [said_in("s1", said)], REFS)
    for n, claim in enumerate((longer, unwashed), start=2):
        told = gi_sentence(f"s{n}.b1.1", claim.text, claim.key, quote=claim.text)
        (kept,) = ledger.admit(f"s{n}", [said_in(f"s{n}", told)], REFS)
        assert [sentence.text for sentence in kept.cited_sentences()] == [claim.text]


def test_the_recorded_indigo_answer_retells_facts_and_its_rebuild_does_not() -> None:
    recorded = recorded_indigo()
    assert restated_in_other_words(blocks_of(recorded))
    assert restated_in_other_words(blocks_of(ledgered_explainer(recorded))) == []
