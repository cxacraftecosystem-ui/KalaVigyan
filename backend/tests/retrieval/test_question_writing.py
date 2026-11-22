import hashlib
import json
import uuid

import pytest

from app.core.errors import ExternalFailure
from app.research.structured import StructuredReply, schema_problems
from app.retrieval.question_writing import (
    CraftFacts,
    EvalFact,
    common_stems,
    distinctive_stems,
    sampled_facts,
    second_language_of,
    wants_second_language,
    worded_apart,
    writing_message,
    writing_schema,
    written_questions,
)


def fact_id(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-question-writing/{name}")


ALUM = EvalFact(fact_id("alum"), "Alum fixes madder red on the cloth.", "CHEMISTRY")
IRON = EvalFact(fact_id("iron"), "Iron turns the cloth black.", "CHEMISTRY")
FACTS = (
    ALUM,
    IRON,
    EvalFact(fact_id("indigo"), "Indigo dyes the cloth blue.", "MATERIALS"),
    EvalFact(fact_id("river"), "Kutch Ajrakh cloth is washed in the river.", "PROCESS"),
    EvalFact(fact_id("roots"), "Madder roots give the cloth its red.", "BOTANY"),
)
NAMES = ("Kutch Ajrakh", "Ajrakh")


def craft(second_language: str = "hi") -> CraftFacts:
    return CraftFacts(
        slug="Kutch-Ajrakh", names=NAMES, second_language=second_language, facts=FACTS, sampled=FACTS
    )


def test_a_stem_in_three_facts_and_a_fifth_of_them_is_common_to_the_craft() -> None:
    assert common_stems(FACTS) == {"clot"}
    assert common_stems(FACTS[:2]) == frozenset()


def test_the_distinctive_words_leave_out_the_craft_s_names_and_its_common_words() -> None:
    assert distinctive_stems(ALUM, NAMES, frozenset({"clot"})) == {"alum", "fixe", "madd"}
    assert distinctive_stems(FACTS[3], NAMES, frozenset({"clot"})) == {"wash", "rive"}


def test_a_question_reuses_at_most_two_distinctive_words_and_only_those_it_names() -> None:
    distinctive = frozenset({"alum", "fixe", "madd"})
    assert worded_apart("Which salt makes the red stay on the textile?", distinctive, [])
    assert not worded_apart("Which salt fixes the red?", distinctive, [])
    assert worded_apart("Which salt fixes the red?", distinctive, ["fixes"])
    assert worded_apart("How does alum fix madder?", distinctive, ["alum", "madder"])
    assert not worded_apart("How does alum fix madder?", distinctive, ["alum"])
    assert not worded_apart("How does alum fix madder?", distinctive, ["alum", "madder", "red"])
    assert not worded_apart("Alum fixes madder how?", distinctive, ["alum", "madder"])


def test_the_sample_is_the_facts_first_by_the_hash_of_the_seed_and_their_id() -> None:
    def rank(fact: EvalFact) -> str:
        return hashlib.sha256(f"7:{fact.id}".encode()).hexdigest()

    expected = sorted(FACTS, key=rank)[:3]
    assert sampled_facts(FACTS, seed=7, per_craft=3) == tuple(expected)
    assert sampled_facts(tuple(reversed(FACTS)), seed=7, per_craft=3) == tuple(expected)
    grown = (*FACTS, EvalFact(fact_id("new"), "A new fact.", None))
    assert set(sampled_facts(grown, seed=7, per_craft=3)) <= {*expected, grown[-1]}


def test_about_one_fact_in_five_asks_a_second_language() -> None:
    wanted = [wants_second_language(fact_id(f"many-{n}"), seed=7) for n in range(2000)]
    assert 300 <= sum(wanted) <= 500
    assert wanted == [wants_second_language(fact_id(f"many-{n}"), seed=7) for n in range(2000)]


@pytest.mark.parametrize(
    ("languages", "second"),
    [
        (["gu"], "gu"),
        (["en", "ta"], "ta"),
        ([], "hi"),
        (["kok"], "hi"),
        (["ur", "ks"], "ur"),
        (["hi", "mai"], "hi"),
    ],
)
def test_the_second_language_is_the_craft_s_own_where_the_site_answers_in_it(
    languages: list[str], second: str
) -> None:
    assert second_language_of(languages) == second


def seed_where_only_the_first_fact_asks_a_second_language() -> int:
    return next(
        seed
        for seed in range(1000)
        if wants_second_language(ALUM.id, seed=seed) and not wants_second_language(IRON.id, seed=seed)
    )


def test_the_message_numbers_the_facts_and_names_the_second_language_where_asked() -> None:
    seed = seed_where_only_the_first_fact_asks_a_second_language()
    message = writing_message(craft(), (ALUM, IRON), seed=seed)
    assert "1. [second language: Hindi] Alum fixes madder red on the cloth." in message
    assert "2. Iron turns the cloth black." in message
    assert message.count("untrusted_source") == 4
    assert schema_problems(writing_schema()) == []


def reply(*items: dict[str, object]) -> StructuredReply:
    return StructuredReply(text=json.dumps({"questions": list(items)}), degraded=False, model="cheap")


def test_questions_that_copy_the_fact_or_name_no_fact_are_dropped() -> None:
    seed = seed_where_only_the_first_fact_asks_a_second_language()
    hindi = "कौन सा नमक लाल रंग को कपड़े पर टिकाता है?"
    written = written_questions(
        reply(
            {
                "ref": "1",
                "question": "Which salt makes the red stay on the textile?",
                "unavoidable": [],
                "translated": hindi,
            },
            {
                "ref": "2",
                "question": "Why does iron turn the cloth black?",
                "unavoidable": [],
                "translated": "",
            },
            {"ref": "9", "question": "What is it?", "unavoidable": [], "translated": ""},
            {"ref": "1", "question": "Again?", "unavoidable": [], "translated": ""},
        ),
        craft(),
        (ALUM, IRON),
        seed=seed,
    )
    assert [(one.fact.id, one.language, one.question) for one in written.questions] == [
        (ALUM.id, "en", "Which salt makes the red stay on the textile?"),
        (ALUM.id, "hi", hindi),
    ]
    assert sorted(written.dropped) == sorted(
        [
            "the question reuses the fact's distinctive words",
            "the reply named a fact it was not given",
            "the reply wrote twice for one fact",
        ]
    )


def test_a_second_question_must_be_written_in_its_language_and_only_where_asked() -> None:
    seed = seed_where_only_the_first_fact_asks_a_second_language()
    item = {"question": "Which salt makes the red stay on the textile?", "unavoidable": []}
    latin = written_questions(
        reply({"ref": "1", **item, "translated": "Kaun sa namak?"}), craft(), (ALUM,), seed=seed
    )
    assert [one.language for one in latin.questions] == ["en"]
    assert latin.dropped == ("the second-language question is not written in that language",)
    unasked = written_questions(
        reply(
            {
                "ref": "1",
                "question": "What darkens the textile where the metal touches it?",
                "unavoidable": [],
                "translated": "क्या?",
            }
        ),
        craft(),
        (IRON,),
        seed=seed,
    )
    assert [one.language for one in unasked.questions] == ["en"]


HINDI = "कौन सा नमक लाल रंग को कपड़े पर टिकाता है?"
BENGALI = "কোন লবণ লাল রং কাপড়ে ধরে রাখে?"
TELUGU = "ఏ ఉప్పు ఎరుపు రంగును బట్టపై నిలుపుతుంది?"


@pytest.mark.parametrize(
    ("language", "translated", "kept"),
    [
        ("bn", HINDI, False),
        ("bn", BENGALI, True),
        ("as", BENGALI, True),
        ("te", HINDI, False),
        ("te", TELUGU, True),
        ("mr", HINDI, True),
        ("hi", BENGALI, False),
        ("hi", "Kaun sa namak lāl rang ko ṭikātā hai?", False),
    ],
)
def test_a_second_question_is_kept_only_when_half_its_letters_or_more_are_in_its_language_s_script(
    language: str, translated: str, kept: bool
) -> None:
    seed = seed_where_only_the_first_fact_asks_a_second_language()
    item = {"ref": "1", "question": "Which salt makes the red stay on the textile?", "unavoidable": []}
    written = written_questions(
        reply({**item, "translated": translated}), craft(language), (ALUM,), seed=seed
    )
    languages = [one.language for one in written.questions]
    assert languages == (["en", language] if kept else ["en"])
    assert written.dropped == (
        () if kept else ("the second-language question is not written in that language",)
    )


def test_a_reply_without_a_questions_list_is_an_external_failure() -> None:
    with pytest.raises(ExternalFailure):
        written_questions(StructuredReply(text="{}", degraded=False), craft(), (ALUM,), seed=7)
