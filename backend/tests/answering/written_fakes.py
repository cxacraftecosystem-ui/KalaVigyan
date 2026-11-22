import uuid
from collections.abc import Mapping

from app.research.composition import ComposedAnswer
from app.research.evidence_pack import EvidencePack
from app.research.write_back import WriteBackResult
from app.retrieval.indexing import EmbeddedCounts
from app.services.research_write_back import StoredResearch
from app.services.write_back_plan import write_back_plan

from ..write_back.names import names_for


def written_research(
    pack: EvidencePack, composed: ComposedAnswer, answer_id: uuid.UUID, written: Mapping[str, uuid.UUID]
) -> StoredResearch:
    plan = write_back_plan(
        pack, composed, found_by="ANSWER", answer_id=answer_id, names=names_for(pack.plan.craft)
    )
    results = tuple(
        WriteBackResult(dedupe_key=claim.dedupe_key, claim_id=written[claim.text], created=True)
        for claim in plan.claims
        if claim.text in written
    )
    return StoredResearch(
        source_ids=(),
        results=results,
        skipped=plan.skipped,
        embedded=EmbeddedCounts(claims=0, chunks=0),
        sentence_keys=plan.sentence_keys,
    )
