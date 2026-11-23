import uuid
from typing import Any

import pytest

from app.research.candidate_gates import Candidate, HeldFact
from app.research.candidate_judge import JudgeAsk, parsed_comparisons, parsed_novelty

MONSOON_SLOWS = (
    "A clothing brand's blog says many hand block printing workshops in Jaipur, Sanganer and Bagru slow down during "
    "the monsoon."
)
MONSOON_DRYING = (
    "The same blog says monsoon humidity, cloudy skies and frequent rain significantly increase drying times, so "
    "drying that takes a few hours in summer can take a day or longer in the monsoon."
)
HARI_SARANA = (
    "In Sanganer, the pre-printing treatment called Hari Sarana, ending with the cloth spread on the ground to dry, "
    "takes 3-5 days depending on the weather."
)
MADDER = (
    "The GI application states the red alizarine bath is prepared from madder (Rubia tirctoria, Rubia manjista), "
    "which gives alizarine and purpurin, and that synthetic alizarine replaced it when madder ran short."
)
DHAWAI = (
    "The GI application states that alizarine and dhawai ka phool (Fordia Floribun<la, as the scan spells it) are "
    "mixed for a reddish shade."
)
OLDENLANDIA = "The GI application's dye table lists Oldenlandia umbellata, Indian Madar, as a source of red (alizarine)."
METALS = (
    "A study published online on 03.02.2014 says heavy metals in Sanganer's dyeing and printing wastewater decrease "
    "downstream as they accumulate in the soil and in crops."
)
GROUNDWATER = (
    "In a study published online on 03.02.2014, eleven groundwater samples from various locations of Sanganer were "
    "found polluted by wastewater soaking into the ground."
)
INDIGOFERA = (
    "The GI application states indigo blue (nil) is extracted from nil plants (Indigofera tinctoria), but nowadays "
    "synthetic indigo granules are used."
)
NEEL = "The GI application lists neel (indigo) among the dyes of Sanganer's blue."
LEUCO = "Indigo is insoluble in water, while its reduced form, leucoindigo, dissolves."
THREE_DIPS = "Ajrakh cloth is dipped in the indigo vat three times."
FOUR_DIPS = "Ajrakh cloth goes into the indigo vat four times."


def fact(name: str, text: str) -> HeldFact:
    return HeldFact(
        id=uuid.uuid5(uuid.NAMESPACE_URL, f"test-structural-verdicts/{name}"), text=text, similarity=0.9
    )


def answer(held: HeldFact, **said: Any) -> dict[str, Any]:
    return {
        "candidate": "c1",
        "held": str(held.id),
        "same": False,
        "reason": said.pop("reason", "They concern one thing."),
        **said,
    }


def relation_of(statement: str, held: HeldFact, reply: dict[str, Any]) -> str:
    ask = JudgeAsk(Candidate(ref="c1", statement=statement, field="CLIMATE"), (held,))
    (found,) = parsed_comparisons({"comparisons": [reply]}, [ask])["c1"]
    return found.relation


CLAIMED_CLASHES = [
    pytest.param(
        MONSOON_DRYING,
        fact("monsoon-slows", MONSOON_SLOWS),
        {"sameSubject": True, "sameProperty": False, "sameWhen": True, "bothTrue": False},
        ("the monsoon in the workshops", "effect", "drying takes longer", "workshops slow down"),
        id="two effects of the monsoon",
    ),
    pytest.param(
        HARI_SARANA,
        fact("monsoon-drying", MONSOON_DRYING),
        {"sameSubject": True, "sameProperty": True, "sameWhen": False, "bothTrue": False},
        ("drying the cloth", "duration", "3-5 days", "a day or longer"),
        id="two stages with their own drying times",
    ),
    pytest.param(
        DHAWAI,
        fact("madder", MADDER),
        {"sameSubject": True, "sameProperty": True, "sameWhen": True, "bothTrue": True},
        ("the red bath", "source of the red", "alizarine and dhawai ka phool", "madder"),
        id="dhawai beside madder",
    ),
    pytest.param(
        OLDENLANDIA,
        fact("madder", MADDER),
        {"sameSubject": True, "sameProperty": True, "sameWhen": True, "bothTrue": True},
        ("the red dye", "source of the red", "Oldenlandia umbellata", "madder"),
        id="Oldenlandia beside madder",
    ),
    pytest.param(
        GROUNDWATER,
        fact("metals", METALS),
        {"sameSubject": True, "sameProperty": False, "sameWhen": True, "bothTrue": False},
        (
            "the 2014 study of Sanganer's wastewater",
            "finding",
            "polluted groundwater",
            "metals in soil and crops",
        ),
        id="two findings of one study",
    ),
]


@pytest.mark.parametrize(("statement", "held", "answers", "named"), CLAIMED_CLASHES)
def test_the_five_sanganeri_pairs_flagged_on_2026_11_22_are_distinct(
    statement: str, held: HeldFact, answers: dict[str, bool], named: tuple[str, str, str, str]
) -> None:
    subject, quality, said, kept = named
    reply = answer(held, subject=subject, property=quality, candidateValue=said, heldValue=kept, **answers)
    assert relation_of(statement, held, reply) == "DISTINCT"


def test_a_real_disagreement_on_one_thing_at_one_stage_is_kept_as_sources_differ() -> None:
    held = fact("four-dips", FOUR_DIPS)
    reply = answer(
        held,
        sameSubject=True,
        sameProperty=True,
        sameWhen=True,
        bothTrue=False,
        subject="the indigo vat",
        property="number of dips",
        candidateValue="three",
        heldValue="four",
    )
    ask = JudgeAsk(Candidate(ref="c1", statement=THREE_DIPS, field="PROCESS"), (held,))
    (found,) = parsed_comparisons({"comparisons": [reply]}, [ask])["c1"]
    assert found.relation == "DIFFERS"
    assert found.reason.startswith(
        "the indigo vat, number of dips: the candidate says three, the held fact four."
    )


def test_a_clash_the_judge_cannot_name_as_two_values_is_not_a_disagreement() -> None:
    held = fact("four-dips", FOUR_DIPS)
    unnamed = {"sameSubject": True, "sameProperty": True, "sameWhen": True, "bothTrue": False}
    for values in (("", ""), ("four", "four"), ("Four.", "four")):
        reply = answer(
            held, subject="the vat", property="dips", candidateValue=values[0], heldValue=values[1], **unnamed
        )
        assert relation_of(THREE_DIPS, held, reply) == "DISTINCT"
    assert (
        relation_of(
            THREE_DIPS,
            held,
            {
                **answer(held, **unnamed, subject="", property="", candidateValue="", heldValue=""),
                "same": True,
            },
        )
        == "SAME"
    )


def test_the_indigofera_fact_refused_on_2026_11_22_adds_because_it_names_details_the_section_lacks() -> None:
    neel, leuco = fact("neel", NEEL), fact("leuco", LEUCO)
    ask = JudgeAsk(Candidate(ref="c1", statement=INDIGOFERA, field="BOTANY"), (neel, leuco))
    reply = {
        "verdicts": [
            {
                "candidate": "c1",
                "newDetails": [
                    "Indigofera tinctoria as the nil plant",
                    "synthetic indigo granules used nowadays",
                ],
                "specific": True,
                "coveredBy": [str(neel.id), str(leuco.id)],
                "reason": "The held facts cover indigo as a blue dye but not its plant or its synthetic substitute.",
            }
        ]
    }
    found = parsed_novelty(reply, [ask])["c1"]
    assert (found.adds, found.covered_by) == (True, [])
    assert found.reason.startswith(
        "it states what the held facts do not: Indigofera tinctoria as the nil plant; synthetic indigo granules used "
        "nowadays."
    )


def test_a_candidate_with_no_new_detail_or_too_general_to_teach_adds_nothing() -> None:
    neel = fact("neel", NEEL)
    ask = JudgeAsk(Candidate(ref="c1", statement=NEEL, field="BOTANY"), (neel,))
    for details, specific in (([], True), (["   "], True), (["indigo is blue"], False)):
        reply = {
            "verdicts": [
                {
                    "candidate": "c1",
                    "newDetails": details,
                    "specific": specific,
                    "coveredBy": [],
                    "reason": "Said.",
                }
            ]
        }
        assert parsed_novelty(reply, [ask])["c1"].adds is False
