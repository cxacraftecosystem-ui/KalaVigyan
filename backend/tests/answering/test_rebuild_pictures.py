import uuid
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from app.providers import answer_routes
from app.providers.catalogue import AiTask
from app.providers.router import Principal
from app.scripts import rebuild_pieces
from app.services import answer_store
from app.services.block_builders import BlockBuilders
from app.services.section_enrichment import EnrichmentTools, no_pictures, without_pictures
from app.services.section_images import SectionImagesAsk

ASK = SectionImagesAsk(block_id="s1.b2", craft_name="Kutch Ajrakh", claim_ids=(uuid.UUID(int=5),))


async def searched(ask: SectionImagesAsk) -> None:
    raise AssertionError(f"the picture search ran for {ask.block_id}")


async def glossary(craft: Any) -> list[Any]:
    return []


async def test_tools_without_pictures_keep_the_glossary_and_answer_no_picture() -> None:
    tools = without_pictures(EnrichmentTools(glossary=glossary, pictures=searched))
    assert tools.glossary is glossary
    assert await tools.pictures(ASK) is None


async def test_the_nightly_rebuild_marks_terms_but_searches_no_picture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def model(task: AiTask, principal: Principal | None = None, **_: Any) -> SimpleNamespace:
        return SimpleNamespace(task=task, principal=principal)

    monkeypatch.setattr(answer_routes, "router_structured_model", model)
    monkeypatch.setattr(rebuild_pieces, "router_embedder", lambda principal: None)
    monkeypatch.setattr(
        answer_store.BlockBuilders, "from_registry", classmethod(lambda cls, *_, **__: BlockBuilders())
    )
    pipeline = rebuild_pieces.rebuild_pipeline(
        "DETAILED", day_left_usd=Decimal("100"), sessions=None, index=None, live=None, shield=None
    )
    assert pipeline.enrichment.pictures is no_pictures
    assert await pipeline.enrichment.pictures(ASK) is None
