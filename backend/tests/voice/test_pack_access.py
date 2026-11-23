from app.research.crafts import CraftRef
from app.research.retrieval import EVERY_CHUNK_ACLS, SIGNED_IN_CHUNK_ACLS, chunk_acls_for
from app.voice.pack import Acls, VoicePack, VoicePackStore

from .fakes import CRAFT, alum_pack


async def test_a_pack_is_kept_per_reader_access_so_a_student_never_reads_a_researcher_s_pack() -> None:
    packs = VoicePackStore()
    loaded: list[Acls] = []

    async def load(craft: CraftRef, mode: str, acls: Acls) -> VoicePack:
        loaded.append(acls)
        return alum_pack()

    student = await packs.get(CRAFT, "HYBRID", ("PUBLIC", "SIGNED_IN"), load)
    researcher = await packs.get(CRAFT, "HYBRID", ("PUBLIC", "RESEARCHER", "SIGNED_IN"), load)
    again = await packs.get(CRAFT, "HYBRID", ("SIGNED_IN", "PUBLIC"), load)
    assert loaded == [("PUBLIC", "SIGNED_IN"), ("PUBLIC", "RESEARCHER", "SIGNED_IN")]
    assert again is student and researcher is not student


def test_a_student_reads_signed_in_passages_and_a_researcher_every_passage() -> None:
    assert chunk_acls_for("STUDENT") == SIGNED_IN_CHUNK_ACLS == ("PUBLIC", "SIGNED_IN")
    assert chunk_acls_for("RESEARCHER") == EVERY_CHUNK_ACLS
