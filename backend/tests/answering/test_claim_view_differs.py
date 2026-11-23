import uuid
from dataclasses import replace

from app.models import Claim
from app.services.answer_events import cited_claims
from app.services.knowledge_view import cited_view
from app.services.section_blocks import KeptSentence, explainer_sentence

from .fakes import SOURCES, VIEWS

BATH = "How long the red dye bath lasts"


def test_a_claim_view_carries_what_the_claim_s_sources_differ_on() -> None:
    claim = Claim(
        id=uuid.uuid4(),
        text="Alum is the mordant.",
        evidenceLevel="PROVISIONAL",
        sourcesDiffer=True,
        differsOn=BATH,
    )
    view = cited_view(claim, [], (None, "MATERIAL"))
    assert (view.sources_differ, view.differs_on) == (True, BATH)
    plain = cited_view(
        Claim(id=uuid.uuid4(), text="Alum is the mordant.", evidenceLevel="PROVISIONAL"),
        [],
        (None, "MATERIAL"),
    )
    assert (plain.sources_differ, plain.differs_on) == (False, None)


def test_an_answer_sentence_names_what_the_sources_of_its_claim_differ_on() -> None:
    alum = replace(VIEWS[0], sources_differ=True, differs_on=f"  {BATH} ")
    sentence = KeptSentence(alum.text, (alum.id,), (), False)
    shown = explainer_sentence("s1.b1.1", sentence, cited_claims([alum], SOURCES)).model_dump(
        mode="json", by_alias=True
    )
    assert (shown["sourcesDiffer"], shown["differsOn"]) == (True, BATH)
    blank = replace(VIEWS[0], sources_differ=True, differs_on="   ")
    unnamed = explainer_sentence("s1.b1.1", sentence, cited_claims([blank], SOURCES)).model_dump(
        mode="json", by_alias=True
    )
    assert unnamed["sourcesDiffer"] is True and "differsOn" not in unnamed
