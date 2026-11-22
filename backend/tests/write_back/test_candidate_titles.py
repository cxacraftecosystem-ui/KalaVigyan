import math
import re
import uuid
from collections import Counter
from collections.abc import Sequence
from types import SimpleNamespace

from app.models.crafts import EMBEDDING_DIMENSIONS
from app.research.candidate_gates import DUPLICATE_GATE, Candidate, GateOutcome, HeldFact
from app.research.gate_thrift import VECTOR_TWIN_SIMILARITY, GateThrift
from app.retrieval.claim_titles import claim_document
from app.retrieval.text import context_title
from app.services.candidate_gates import later_gates
from app.services.candidate_store import FactSubject, subject_title

STORED_TEXT = "Ajrakh cloth is washed twice in running river water."
PARAPHRASE = "In running river water, Ajrakh cloth is washed twice."
TITLE = "Kutch Ajrakh · Washing · Process"
STORED_ID = uuid.UUID("0c9b8a7d-6e5f-4a3b-8c1d-2e3f4a5b6c7d")
WORD = re.compile(r"[a-z]+")


def words(text: str) -> Counter[str]:
    return Counter(WORD.findall(text.lower()))


def stored_document() -> str:
    row = SimpleNamespace(text=STORED_TEXT, owner="Kutch Ajrakh", concept="Washing", field="PROCESS")
    return claim_document(row)


class WordCounts:
    def __init__(self) -> None:
        self.vocabulary = sorted(set(words(stored_document())) | {"none"})
        self.calls: list[list[str]] = []

    def vector(self, text: str) -> list[float]:
        counts = words(text)
        found = [float(counts[word]) for word in self.vocabulary]
        return found + [0.0] * (EMBEDDING_DIMENSIONS - len(found))

    async def __call__(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [self.vector(text) for text in texts]


class StoredFact:
    def __init__(self, vector: list[float]) -> None:
        self.stored = vector

    async def nearest(self, field: str | None, vector: Sequence[float], limit: int) -> list[HeldFact]:
        dot = sum(a * b for a, b in zip(vector, self.stored, strict=True))
        norms = math.sqrt(sum(a * a for a in vector)) * math.sqrt(sum(b * b for b in self.stored))
        return [HeldFact(id=STORED_ID, text=STORED_TEXT, similarity=min(1.0, dot / norms))]

    async def twins(self, field: str | None, statement: str) -> list[HeldFact]:
        return []


async def duplicate_gate(candidate: Candidate) -> tuple[GateOutcome, list[str]]:
    embed = WordCounts()
    store = StoredFact(embed.vector(stored_document()))
    later = await later_gates(store, [candidate], embed=embed, judge=None, thrift=GateThrift())
    outcome = next(found for found in later[candidate.ref].outcomes if found.gate == DUPLICATE_GATE)
    return outcome, embed.calls[0]


def test_a_candidate_is_titled_as_the_stored_facts_are() -> None:
    subject = FactSubject(kind="craft", name="Kutch Ajrakh", slug="Kutch-Ajrakh")
    assert subject_title(subject, "Washing", "PROCESS") == TITLE
    assert context_title("Kutch Ajrakh", "Washing", "PROCESS") == TITLE
    assert stored_document() == f"title: {TITLE} | text: {STORED_TEXT}"


async def test_a_titled_paraphrase_of_a_stored_fact_reaches_the_vector_twin_floor() -> None:
    titled = Candidate(ref="c1", statement=PARAPHRASE, field="PROCESS", title=TITLE)
    outcome, sent = await duplicate_gate(titled)
    assert sent == [f"title: {TITLE} | text: {PARAPHRASE}"]
    assert (outcome.passed, outcome.related) == (False, [STORED_ID])
    assert "nearly the same words" in outcome.reasons[0]


async def test_an_untitled_paraphrase_sits_below_the_floor() -> None:
    untitled = Candidate(ref="c1", statement=PARAPHRASE, field="PROCESS")
    outcome, sent = await duplicate_gate(untitled)
    assert sent == [f"title: none | text: {PARAPHRASE}"]
    assert outcome.passed is True
    embed = WordCounts()
    (fact,) = await StoredFact(embed.vector(stored_document())).nearest("PROCESS", embed.vector(sent[0]), 1)
    assert round(fact.similarity, 4) == 0.8402 < VECTOR_TWIN_SIMILARITY
