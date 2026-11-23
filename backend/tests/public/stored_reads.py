import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

from app.api.routes import (
    crafts,
    field_voices,
    learning_views,
    map_districts,
    map_layers,
    molecules,
    public,
    rivers,
    terms,
)
from app.core.http_cache import body_version
from app.data.craft_master_loader import build_catalogue
from app.research.craft_compare import CraftComparison
from app.research.craft_page import CraftPage
from app.research.field_voices import FieldTranscript, FieldVoicesList
from app.research.shared_science import SharedConcept, SharedScience
from app.services import craft_catalogue, knowledge_view
from app.services.craft_page_cache import ServedPage, served_content
from app.services.craft_page_snapshots import VARIANT_ACLS
from app.services.river_store import BasinFile
from app.services.term_summaries import StoredTermLookup, TermLookup

from ..answering.fakes import translation
from ..contracts.golden import golden_json
from ..contracts.learning_golden import SHARED_SCIENCE, learning
from ..geo.golden_region import golden_layer_values, golden_listing, golden_region_records
from ..geo.test_district_view import records as district_records
from ..geo.test_river_routes import KEY, OUTLET, SHA, TOPOLOGY, FakeBucket
from ..sources.recorded import recorded
from ..terms.fakes import CHECKED_AT, FakeResearch, FakeTermStore, golden_claims, kut_term
from ..voice.listen_fakes import MemoryObjects
from .summary_fixture import summary_fixture_records

__all__ = ["AJRAKH", "BAGRU", "OUTLET", "RECORDING", "Asked", "stored_reads"]

AJRAKH = "Kutch-Ajrakh"
BAGRU = "Bagru-Hand-Block-Print"
RECORDING = uuid.UUID(int=31)
AJRAKH_REF = {"slug": AJRAKH, "name": "Kutch Ajrakh", "path": f"/crafts/{AJRAKH}"}
POINTS = [
    {
        "key": "state-24",
        "name": "Gujarat",
        "latitude": 22.7,
        "longitude": 71.6,
        "total": 1,
        "crafts": [{"slug": AJRAKH, "name": "Kutch Ajrakh", "path": f"/crafts/{AJRAKH}"}],
    }
]
CRAFTS = {
    AJRAKH: SimpleNamespace(id=uuid.UUID(int=11), slug=AJRAKH, name="Kutch Ajrakh"),
    BAGRU: SimpleNamespace(id=uuid.UUID(int=12), slug=BAGRU, name="Bagru Hand Block Print"),
}


@dataclass
class Asked:
    acls: dict[str, set[tuple[str, ...]]] = field(default_factory=dict)

    def heard(self, name: str, acls: Sequence[str]) -> None:
        self.acls.setdefault(name, set()).add(tuple(acls))

    def loader(self, name: str, value: Any) -> Any:
        async def answer(*_args: Any, acls: Sequence[str], **_kwargs: Any) -> Any:
            self.heard(name, acls)
            return value

        return answer


@dataclass
class Conformers:
    sdf: str

    async def conformer(self, cid: int) -> str | None:
        return self.sdf if cid == 6293 else None


async def nothing(*_args: Any, **_kwargs: Any) -> None:
    return None


def returning(value: Any) -> Any:
    async def answer(*_args: Any, **_kwargs: Any) -> Any:
        return value

    return answer


def stored_reads(asked: Asked) -> dict[Any, dict[str, Any]]:
    return {
        **_craft_reads(asked),
        **_learning_reads(asked),
        **_map_reads(asked),
        **_media_reads(),
        **_term_reads(asked),
        **_field_voice_reads(),
        public: {"summary_records": returning(summary_fixture_records())},
    }


def _craft_reads(asked: Asked) -> dict[Any, dict[str, Any]]:
    page = CraftPage.model_validate(golden_json("craft.page.golden.json"))
    body = page.model_dump(mode="json", by_alias=True)

    async def resolve(_session: Any, slug: str) -> Any:
        return CRAFTS.get(slug)

    async def served(_session: Any, _craft: Any, variant: str, **_options: Any) -> ServedPage:
        asked.heard("craft_page_records", VARIANT_ACLS[variant])
        return ServedPage(served_content(body), body_version(body), f"stamp-{variant}")

    return {
        knowledge_view: {"resolve_craft": resolve, "map_points": returning(POINTS)},
        craft_catalogue: {"load_catalogue": returning(build_catalogue())},
        crafts: {
            "served_page": served,
            "region_records": returning(golden_region_records()),
        },
    }


def _learning_reads(asked: Asked) -> dict[Any, dict[str, Any]]:
    shared = learning(SHARED_SCIENCE)

    async def concept(
        _session: Any, term_key: str, _focus: Any, *, acls: Sequence[str]
    ) -> SharedConcept | None:
        asked.heard("shared_concept_of", acls)
        return SharedConcept.model_validate(shared["concept"]) if term_key == "alum" else None

    compared = CraftComparison.model_validate(golden_json("learning.compare.golden.json"))
    return {
        learning_views: {
            "craft_shared_science": asked.loader(
                "craft_shared_science", SharedScience.model_validate(shared["craft"])
            ),
            "shared_concept_of": concept,
            "craft_comparison": asked.loader("craft_comparison", compared),
        }
    }


def _map_reads(asked: Asked) -> dict[Any, dict[str, Any]]:
    return {
        map_layers: {
            "listed_layers": returning(golden_listing()),
            "layer_values": returning(golden_layer_values()),
        },
        map_districts: {"district_records": asked.loader("district_records", district_records())},
        rivers: {
            "basin_file": returning(BasinFile(main_riv=OUTLET, edition="v10", sha256=SHA)),
            "release_connection": nothing,
            "media_bucket": lambda: FakeBucket({KEY: TOPOLOGY}),
        },
    }


def _media_reads() -> dict[Any, dict[str, Any]]:
    sdf = recorded("pubchem_conformer.sdf").decode("ascii").strip()
    return {
        molecules: {
            "stored_compound_cid": returning(True),
            "release_connection": nothing,
            "media_bucket": MemoryObjects,
            "live_pubchem": returning(Conformers(sdf)),
            "sessionmaker": lambda: None,
        }
    }


def _term_reads(asked: Asked) -> dict[Any, dict[str, Any]]:
    store = FakeTermStore({"kut": kut_term()}, stored=golden_claims())

    def stored_terms(_sessions: Any, *, acls: Sequence[str]) -> StoredTermLookup:
        asked.heard("term_lookup", acls)
        return StoredTermLookup(store)

    async def signed_in_terms(*, acls: Sequence[str], **_kwargs: Any) -> TermLookup:
        asked.heard("term_lookup", acls)
        return TermLookup(
            store=store, research=FakeResearch(None), translation=translation(), clock=lambda: CHECKED_AT
        )

    return {
        terms: {
            "sessionmaker": lambda: None,
            "stored_term_lookup": stored_terms,
            "build_term_lookup": signed_in_terms,
        }
    }


def _field_voice_reads() -> dict[Any, dict[str, Any]]:
    listed = FieldVoicesList.model_validate(
        {
            "schemaVersion": 1,
            "craft": AJRAKH_REF,
            "kind": "quotes",
            "total": 0,
            "cursor": None,
            "nextCursor": None,
            "quotes": [],
            "images": [],
        }
    )
    return {
        field_voices: {"field_list": returning(listed), "field_transcript": returning(field_transcript())}
    }


def field_transcript() -> FieldTranscript:
    return FieldTranscript.model_validate(
        {
            "schemaVersion": 1,
            "id": str(RECORDING),
            "origin": "FIELD_REPOSITORY",
            "publisher": "Field Repository",
            "title": "Field interview, Ajrakh documentation visit, 14 March 2026",
            "mediaType": "AUDIO",
            "recordedAt": "2026-03-14T10:22:00+05:30",
            "durationMs": 790000,
            "crafts": [AJRAKH_REF],
            "workshop": "Ajrakh documentation visit",
            "context": ["Recorded in Kachchh, Gujarat"],
            "stage": None,
            "speakers": [{"key": "speaker_0", "label": "Asha Demo", "role": "ARTISAN"}],
            "lines": [
                {
                    "id": "fr-turn-2",
                    "position": 1,
                    "speakerKey": "speaker_0",
                    "locator": "0:06-0:33",
                    "language": "gu",
                    "text": "We wash the cloth in the river before the first print.",
                    "english": None,
                    "englishSource": None,
                    "quotable": True,
                }
            ],
            "english": None,
            "englishSource": None,
            "sourceId": str(uuid.UUID(int=32)),
            "citation": "Asha Demo, interview recorded 14 March 2026, Ajrakh documentation visit, Field Repository",
        }
    )
