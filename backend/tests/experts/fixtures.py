import json
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.composer.expert_takes import RETAKE_SYSTEM_PROMPT
from app.models import Source
from app.research.planning import PlanRequest
from app.research.sections import SectionSpec
from app.research.structured import StructuredReply
from app.services.answer_events import CitedClaims, cited_claims
from app.services.builder_interface import BuildAsk, BuilderTools
from app.services.knowledge_view import ClaimView
from app.services.section_blocks import KeptSentence, prose_block

from ..answering.fakes import stored_view
from ..research.fixtures import AJRAKH

QUESTION = "When did the Khatris bring Ajrakh to Kutch?"
MIGRATION = uuid.UUID("5a000000-0000-4000-8000-000000000001")
CLIENTELE = uuid.UUID("5a000000-0000-4000-8000-000000000002")


def source(number: int, kind: str, title: str, url: str) -> Source:
    return Source(
        id=uuid.UUID(f"50000000-0000-4000-8000-{number:012d}"),
        kind=kind,
        title=title,
        authors=[],
        year=None,
        doi=None,
        url=url,
        publisher=None,
        licence=None,
        attribution=None,
        reliability="B",
    )


GI = source(1, "GI_JOURNAL", "GI Journal No. 188", "https://ipindia.gov.in/gi-journal-188")
KHAMIR = source(2, "WEB_PAGE", "The Khatris and their community", "https://exhibitions-khamir.org/ajrakh")
SAHAPEDIA = source(3, "WEB_PAGE", "Ajrakh: An Introduction", "https://www.sahapedia.org/ajrakh")
SOURCES = {GI.id: GI, KHAMIR.id: KHAMIR, SAHAPEDIA.id: SAHAPEDIA}


def claim(number: int) -> uuid.UUID:
    return uuid.UUID(f"c1000000-0000-4000-8000-{number:012d}")


FOUR_HUNDRED = stored_view(
    claim(1),
    "The technique came to Kutch from Sindh some 400 years ago at the behest of the King of Kutch.",
    "PROVISIONAL",
    (101, GI, "came to Kutch from Sindh some 400 years ago at the behest of the King of Kutch", "p. 9"),
    concept_id=MIGRATION,
)
SEVENTH_CENTURY = stored_view(
    claim(2),
    "Khamir's account says Hindu Khatris fled Sindh to Kachchh in the 7th century after Arab invasion.",
    "PROVISIONAL",
    (102, KHAMIR, "During the 7th century, the Khatris of Sindh were Hindu.", None),
    concept_id=MIGRATION,
)
DHAMADKA = stored_view(
    claim(3),
    "Khatri craftsmen were invited to practise their art on the banks of the Dhamadka river.",
    "PROVISIONAL",
    (103, GI, "invited craftsmen from Khatri community to come and practice their art", "p. 9"),
    concept_id=MIGRATION,
)
CLIENTS = stored_view(
    claim(4),
    "Khatris made cloth for Maldharis and farming communities, trading cloth for produce, milk or ghee.",
    "PROVISIONAL",
    (104, SAHAPEDIA, "They produced cloth for maldharis (cattle herders)", None),
    concept_id=CLIENTELE,
)
BHARMALJI = stored_view(
    claim(5),
    "Rao Bharmalji I invited Khatri printers from Sindh and gave them land.",
    "REVIEWED",
    (105, SAHAPEDIA, "Rao Bharmalji - I (1586-1631), invited the cloth-printing Khatri artisans", None),
    concept_id=MIGRATION,
)
GUESS = stored_view(
    claim(6),
    "The Khatris may have printed in Kutch before the invitation.",
    "HYPOTHESIS",
    (106, KHAMIR, None, None),
    concept_id=MIGRATION,
)
VIEWS = (FOUR_HUNDRED, SEVENTH_CENTURY, DHAMADKA, CLIENTS, BHARMALJI, GUESS)


def cited(views: Sequence[ClaimView] = VIEWS) -> CitedClaims:
    return cited_claims(list(views), SOURCES)


def prose(section_id: str, views: Sequence[ClaimView], claims: CitedClaims) -> Any:
    sentences = [KeptSentence(view.text, (view.id,), (), False) for view in views]
    return prose_block(f"{section_id}.b1", sentences, claims)


SHOWN = (SEVENTH_CENTURY, DHAMADKA)


def build_ask(
    seats: Sequence[str],
    *,
    discipline: str = "HISTORY",
    depth: str = "DETAILED",
    views: Sequence[ClaimView] = VIEWS,
    shown: Sequence[ClaimView] = SHOWN,
) -> BuildAsk:
    claims = cited(views)
    request = PlanRequest(question=QUESTION, mode="HYBRID", craft=AJRAKH, depth=depth, seats=tuple(seats))
    spec = SectionSpec(id="s5", discipline=discipline, title="History", order=5)
    return BuildAsk(uuid.uuid4(), spec, request, (prose("s5", shown, claims),), claims)


def tools(model: Any) -> BuilderTools:
    return BuilderTools(sessions=None, live=None, plan_model=None, compose_model=model)


def said(view: ClaimView, text: str | None = None, quote: str | None = None) -> dict[str, Any]:
    stated = text or view.text
    return {"text": stated, "quotes": [{"source": str(view.id), "quote": quote or stated.rstrip(".")}]}


def take(seat: str, *sentences: dict[str, Any]) -> dict[str, Any]:
    return {"seat": seat, "take": list(sentences)}


def differ(seat: str, mine: ClaimView, other_seat: str, theirs: ClaimView) -> dict[str, str]:
    return {
        "seat": seat,
        "statement": str(mine.id),
        "otherSeat": other_seat,
        "otherStatement": str(theirs.id),
    }


@dataclass
class PanelModel:
    views: Mapping[str, dict[str, Any]]
    differences: Sequence[dict[str, str]] = ()
    calls: list[dict[str, Any]] = field(default_factory=list)
    retakes: Mapping[str, dict[str, Any]] = field(default_factory=dict)

    async def __call__(self, *, system: str, user: str, schema: Mapping[str, Any]) -> StructuredReply:
        self.calls.append({"system": system, "user": user, "schema": schema})
        if "differences" in schema["properties"]:
            return StructuredReply(text=json.dumps({"differences": list(self.differences)}), degraded=False)
        seat = asked_seat(user)
        view = self.views.get(seat, {"take": []})
        if system == RETAKE_SYSTEM_PROMPT:
            view = self.retakes.get(seat, view)
        return StructuredReply(
            text=json.dumps({k: v for k, v in view.items() if k != "seat"}), degraded=False
        )

    @property
    def seat_calls(self) -> list[dict[str, Any]]:
        return [
            call
            for call in self.calls
            if "take" in call["schema"]["properties"] and call["system"] != RETAKE_SYSTEM_PROMPT
        ]

    @property
    def retake_calls(self) -> list[dict[str, Any]]:
        return [call for call in self.calls if call["system"] == RETAKE_SYSTEM_PROMPT]

    @property
    def difference_calls(self) -> list[dict[str, Any]]:
        return [call for call in self.calls if "differences" in call["schema"]["properties"]]


def asked_seat(user: str) -> str:
    (line,) = [line for line in user.splitlines() if line.startswith("Expert ")]
    return line.removeprefix("Expert ").split(":")[0]


def asked_seats(user: str) -> list[str]:
    return [
        line.removeprefix("Expert ").split(":")[0] for line in user.splitlines() if line.startswith("Expert ")
    ]


def panel_model(
    views: Sequence[dict[str, Any]],
    differences: Sequence[dict[str, str]] = (),
    *,
    retakes: Sequence[dict[str, Any]] = (),
) -> PanelModel:
    return PanelModel(
        {view["seat"]: view for view in views},
        list(differences),
        retakes={view["seat"]: view for view in retakes},
    )
