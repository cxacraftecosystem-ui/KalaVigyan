import dataclasses
from typing import Any

import pytest

from app.services import craft_matter as craft_matter_module
from app.services.block_builders import BLOCK_BUILDERS, BlockBuilders
from app.services.builder_interface import BuilderTools
from app.services.matter_builders import MaterialCardBuilder, MoleculeBuilder, ReactionPlayerBuilder
from app.sources.reference.pubchem import PubChemAdapter

from ..answering.fakes import FakeStore, enriched, pipeline, streamed
from ..answering.piece_fakes import MemoryPieces
from ..answering.test_answer_flow import REPLY, detailed, events
from ..sources.recorded import Recorder, Reply, fixed_clock, source_http
from ..voice.listen_fakes import MemoryObjects
from .fixtures import ALIZARIN_RECORD, CardModel, matter

MATTER_KINDS = ("reaction_player", "material_card", "molecule_3d")
CARD_REPLY = {"cards": [{"material": "m1", "facts": ["m1.c1"], "handling": []}]}
CONFORMER = "pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/6293/record/SDF"


@pytest.fixture
def stored_matter(monkeypatch: pytest.MonkeyPatch) -> None:
    async def load(sessions: Any, craft: Any) -> Any:
        return matter()

    monkeypatch.setattr(craft_matter_module, "craft_matter", load)


def matter_builders_for_the_flow() -> BlockBuilders:
    tools = BuilderTools(sessions=None, live=None, plan_model=CardModel(CARD_REPLY), compose_model=None)
    adapter = PubChemAdapter(
        source_http(Recorder({CONFORMER: Reply("pubchem_conformer.sdf")}), "pubchem"), clock=fixed_clock()
    )

    async def pubchem() -> PubChemAdapter:
        return adapter

    objects = MemoryObjects()
    made = {
        "reaction_player": ReactionPlayerBuilder(tools),
        "material_card": MaterialCardBuilder(tools),
        "molecule_3d": MoleculeBuilder(tools, bucket=lambda: objects, pubchem=pubchem),
    }
    return BlockBuilders([(entry, made[entry.kind]) for entry in BLOCK_BUILDERS if entry.kind in made])


async def test_matter_blocks_stream_after_the_prose_and_join_the_explainer_and_its_pieces(
    stored_matter: None,
) -> None:
    store, pieces = FakeStore(), MemoryPieces()
    answer = dataclasses.replace(
        pipeline(replies=[REPLY], store=store, pieces=pieces, enrichment=enriched()),
        builders=matter_builders_for_the_flow(),
    )
    found = events(await streamed(detailed(), answer))
    shown = [(payload["block"]["id"], payload["block"]["kind"]) for name, payload in found if name == "block"]
    assert shown[:4] == [
        ("s1.b1", "prose"),
        ("s1.b2", "reaction_player"),
        ("s1.b3", "material_card"),
        ("s1.b4", "molecule_3d"),
    ]
    sent = [payload["id"] for name, payload in found if name == "source"]
    first_molecule = next(
        i
        for i, (name, payload) in enumerate(found)
        if name == "block" and payload["block"]["kind"] == "molecule_3d"
    )
    assert ALIZARIN_RECORD in sent[: sum(1 for name, _ in found[:first_molecule] if name == "source")]
    (finished,) = store.finished
    kinds = [block.kind for block in finished["explainer"].sections[0].blocks]
    assert kinds[:4] == ["prose", *MATTER_KINDS]
    ((_, _, sections),) = pieces.kept
    assert [block.kind for block in sections[0].blocks] == ["prose", *MATTER_KINDS]
