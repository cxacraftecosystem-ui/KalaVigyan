import uuid
from collections.abc import Sequence
from typing import Any

__all__ = ["DETAIL", "added_reason", "compared", "verdict"]

DETAIL = "the number of dips"


def compared(
    candidate: str, held: uuid.UUID | str, relation: str, reason: str | None = None
) -> dict[str, Any]:
    differs = relation == "DIFFERS"
    return {
        "candidate": candidate,
        "held": str(held),
        "same": relation == "SAME",
        "sameSubject": differs,
        "sameProperty": differs,
        "sameWhen": differs,
        "bothTrue": not differs,
        "subject": "the indigo vat" if differs else "",
        "property": "number of dips" if differs else "",
        "candidateValue": "three" if differs else "",
        "heldValue": "four" if differs else "",
        "reason": reason or f"{relation} reason.",
    }


def verdict(
    candidate: str, *, adds: bool, reason: str, covered: Sequence[uuid.UUID] = (), specific: bool = True
) -> dict[str, Any]:
    return {
        "candidate": candidate,
        "newDetails": [DETAIL] if adds else [],
        "specific": specific,
        "coveredBy": [str(fact_id) for fact_id in covered],
        "reason": reason,
    }


def added_reason(said: str) -> str:
    return f"it states what the held facts do not: {DETAIL}. {said}"
