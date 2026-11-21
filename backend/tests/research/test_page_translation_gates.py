from app.research.page_translation_gates import (
    ADDED,
    CURRENT,
    KEPT,
    SHAPE,
    GateInput,
    checks_passed,
    refusal,
    translation_checks,
)
from app.research.translation_passages import passage_leaves

CITE = {"m": "cite", "key": "c1", "g": ["g1"], "c": ["vat."]}
NODES = [{"m": "s", "c": ["The cloth is dyed 3 times at 40 °C in an indigo ", CITE]}]
PLANT = [{"m": "s", "c": ["Madder is ", {"m": "i", "role": "bot", "c": ["Rubia cordifolia"]}, ".", CITE]}]
HASH = "a" * 64
HINDI = ["कपड़े को 40 °C पर नील के घोल में 3 बार ", "रंगा जाता है।"]


def checked(
    texts: list[str], *, nodes: list[object] = NODES, given: str = HASH, language: str = "hi"
) -> list:
    return translation_checks(
        GateInput(
            leaves=passage_leaves(nodes), current_hash=HASH, given_hash=given, texts=texts, language=language
        )
    )


def test_a_faithful_translation_passes_every_gate() -> None:
    checks = checked(HINDI)
    assert [check.check for check in checks] == [CURRENT, SHAPE, KEPT, ADDED]
    assert checks_passed(checks) and refusal(checks) is None


def test_a_translation_of_an_english_sentence_that_has_changed_is_refused_first() -> None:
    checks = checked(HINDI, given="b" * 64)
    assert [(check.check, check.passed) for check in checks] == [(CURRENT, False)]


def test_each_english_text_has_one_translated_text_and_the_citation_keeps_its_words() -> None:
    short = refusal(checked(HINDI[:1]))
    assert short is not None and short.check == SHAPE
    assert short.reasons == [
        "The passage holds 2 texts and the translation gives 1: one text for each, in order."
    ]
    empty = refusal(checked([HINDI[0], " "]))
    assert empty is not None and empty.reasons == [
        "texts[1] carries the citation and holds the sentence's last words, so it cannot be empty."
    ]


def test_a_botanical_name_stays_exactly_as_the_english_has_it() -> None:
    kept = checked(["मजीठ ", "Rubia cordifolia", " है", "।"], nodes=PLANT)
    assert checks_passed(kept)
    renamed = refusal(checked(["मजीठ ", "रूबिया कॉर्डिफ़ोलिया", " है", "।"], nodes=PLANT))
    assert renamed is not None and renamed.check == SHAPE
    assert renamed.reasons == [
        "texts[1] is a name, a botanical name, a quote or part of a formula and stays exactly 'Rubia cordifolia'."
    ]


def test_numbers_and_units_are_kept_and_none_is_added() -> None:
    dropped = refusal(checked(["कपड़े को 40 °C पर नील के घोल में कई बार ", "रंगा जाता है।"]))
    assert dropped is not None and dropped.check == KEPT and dropped.reasons == ["number 3 is missing"]
    added = refusal(checked(["कपड़े को 40 °C पर नील के घोल में 3 बार, 5 दिन ", "रंगा जाता है।"]))
    assert added is not None and added.reasons == ["number 5 is not in the original"]


def test_a_translation_left_in_english_or_written_in_another_script_is_refused() -> None:
    english = refusal(checked(["The cloth is dyed 3 times at 40 °C in an indigo ", "vat."]))
    assert english is not None and english.reasons == ["the translation is not written in the Deva script"]
    tamil = refusal(checked(HINDI, language="ta"))
    assert tamil is not None and tamil.reasons == ["the translation is not written in the Taml script"]


def test_a_translation_says_no_more_than_the_english_and_adds_no_link() -> None:
    padded = refusal(checked([HINDI[0] + "बहुत " * 60, HINDI[1]]))
    assert padded is not None and padded.check == ADDED
    assert padded.reasons[0].startswith("The translation runs to ")
    linked = refusal(checked([HINDI[0] + "https://a.io ", HINDI[1]]))
    assert linked is not None and linked.reasons == [
        "The translation holds a link the English passage does not."
    ]
