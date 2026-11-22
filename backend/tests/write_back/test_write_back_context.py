import hashlib
import uuid

from app.research.composition import ComposedAnswer, ComposedSection, ComposedSentence, QuotedSpan
from app.research.evidence import EvidenceItem
from app.research.evidence_pack import EvidencePack, PackedEvidence
from app.research.sections import DISCIPLINE_TITLES
from app.services.write_back_crafts import HELD_UNNAMED, SKIP_ABROAD
from app.services.write_back_plan import WriteBackPlan, write_back_plan
from app.sources.adapter import build_document

from ..composer.fixtures import PLAN, STORED, pack
from ..research.fixtures import evidence_item
from .names import BLUE_POTTERY, KHURJA, MUD_FAMILY, names_for

ANSWER_ID = uuid.UUID("6a1b2c3d-4e5f-4a60-8b71-9c0d1e2f3a4b")
PROCESS = DISCIPLINE_TITLES["PROCESS"]
CHEMISTRY = DISCIPLINE_TITLES["CHEMISTRY"]
KHURJA_NAMES = names_for(KHURJA, family=MUD_FAMILY)
AGED = "The clay is aged for two days"
TURQUOISE = "copper oxide in an alkaline glaze gives turquoise"
FRIT = "a body of quartz frit with no clay at all"
LIQUID = "Feldspar can contribute to the formulation of the liquid phase"
CELADON = "Iron oxide in a reducing fire gives celadon greens"
BISQUE = "A bisque firing hardens the ware before glazing"
KHURJA_STUDY_TEXT = (
    "Potters prepare the body from local clays mixed with quartz and feldspar. "
    f"{AGED} before it is wedged.\n"
    "\n"
    f"Glaze chemistry: {TURQUOISE}, and cobalt oxide gives blue.\n"
    "\n"
    f"Jaipur blue pottery, by contrast, has {FRIT}."
)
NIGERIA_TEXT = f"The feldspar used holds 43.2 wt.% silica. {LIQUID}."
HANDBOOK_TEXT = f"{CELADON}. {BISQUE}."


def study(name: str, title: str) -> EvidenceItem:
    url = f"https://studies.example.org/{name}"
    return evidence_item(id=f"openalex:{name}", url=url, doi=None, title=title, quotes=[])


KHURJA_STUDY = study("khurja", "Clay bodies and glazes of Khurja pottery")
NIGERIA_STUDY = study("nigeria", "Characterisation of Nigerian porcelain bodies")
HANDBOOK = study("handbook", "A handbook of ceramic glazes")


def studies_pack() -> EvidencePack:
    items = (KHURJA_STUDY, NIGERIA_STUDY, HANDBOOK)
    texts = (KHURJA_STUDY_TEXT, NIGERIA_TEXT, HANDBOOK_TEXT)
    return pack(
        plan=PLAN.model_copy(update={"craft": KHURJA}),
        stored=STORED.model_copy(update={"craft_slug": KHURJA.slug, "claims": (), "chunks": ()}),
        evidence=tuple(
            PackedEvidence(item=item, facet_indexes=(0,), found_by=("openalex",), hits=1, best_rank=1)
            for item in items
        ),
        documents=tuple(
            build_document(item, text, "FULL_TEXT") for item, text in zip(items, texts, strict=True)
        ),
    )


def said(text: str, item: EvidenceItem, quote: str) -> ComposedSentence:
    return ComposedSentence(text=text, evidence_ids=[item.id], spans=[QuotedSpan(ref=item.id, text=quote)])


def written(heading: str, *sentences: ComposedSentence) -> WriteBackPlan:
    composed = ComposedAnswer(sections=[ComposedSection(heading=heading, sentences=list(sentences))])
    return write_back_plan(
        studies_pack(), composed, found_by="ANSWER", answer_id=ANSWER_ID, names=KHURJA_NAMES
    )


def family_key(text: str) -> str:
    parts = ["claim-write-back/v2", "category:Mud-based-Craft-Category", "CHEMISTRY", text]
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def test_a_khurja_study_s_title_files_its_unnamed_process_sentence_under_khurja() -> None:
    plan = written(PROCESS, said(f"{AGED}.", KHURJA_STUDY, AGED))
    (claim,) = plan.claims
    assert (claim.craft_slug, claim.category_slug, claim.held_because) == (KHURJA.slug, None, None)
    assert plan.held == ()


def test_a_khurja_study_s_chemistry_goes_to_khurja_not_to_the_family() -> None:
    plan = written(
        CHEMISTRY, said("Copper oxide in an alkaline glaze gives turquoise.", KHURJA_STUDY, TURQUOISE)
    )
    (claim,) = plan.claims
    assert (claim.craft_slug, claim.category_slug, claim.field) == (KHURJA.slug, None, "CHEMISTRY")


def test_a_nigerian_study_named_by_its_title_stays_refused() -> None:
    plan = written(CHEMISTRY, said(f"{LIQUID}.", NIGERIA_STUDY, LIQUID))
    assert (plan.claims, plan.held) == ((), ())
    assert [skipped.reason for skipped in plan.skipped] == [SKIP_ABROAD.format(places="Nigerian")]


def test_a_paragraph_about_jaipur_blue_pottery_files_its_fact_under_blue_pottery() -> None:
    plan = written(PROCESS, said("The body is quartz frit with no clay at all.", KHURJA_STUDY, FRIT))
    (claim,) = plan.claims
    assert claim.craft_slug == BLUE_POTTERY.slug


def test_a_handbook_s_glaze_chemistry_goes_to_the_family_and_its_process_sentence_is_held() -> None:
    chemistry = written(CHEMISTRY, said(f"{CELADON}.", HANDBOOK, CELADON))
    (claim,) = chemistry.claims
    assert (claim.craft_slug, claim.category_slug) == (None, MUD_FAMILY.slug)
    assert (claim.subject.concept_type, claim.subject.concept_name) == ("MECHANISM", MUD_FAMILY.name)
    assert claim.dedupe_key == family_key("iron oxide in a reducing fire gives celadon greens")
    process = written(PROCESS, said(f"{BISQUE}.", HANDBOOK, BISQUE))
    (held,) = process.held
    assert (process.claims, process.sentence_keys) == ((), (None,))
    assert (held.craft_slug, held.held_because, held.field) == (KHURJA.slug, HELD_UNNAMED, "PROCESS")


def test_a_held_sentence_and_the_same_sentence_filed_are_one_filed_fact() -> None:
    held = said(f"{BISQUE}.", HANDBOOK, BISQUE)
    filed = ComposedSentence(
        text=f"{BISQUE}.",
        evidence_ids=[KHURJA_STUDY.id],
        spans=[QuotedSpan(ref=KHURJA_STUDY.id, text=AGED)],
    )
    plan = written(PROCESS, held, filed)
    (claim,) = plan.claims
    assert (claim.craft_slug, claim.held_because, plan.held) == (KHURJA.slug, None, ())
    assert plan.sentence_keys == (claim.dedupe_key, claim.dedupe_key)
    assert [citation.evidence.id for citation in claim.citations] == [HANDBOOK.id, KHURJA_STUDY.id]
