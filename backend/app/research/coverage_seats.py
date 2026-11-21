from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from types import MappingProxyType

from app.models.enums import DISCIPLINES

from .expert_panel import EXPERT_PANEL, TESTIMONY_SEATS

__all__ = ["FIELD_LEADS", "covering_seats", "relevant_fields", "uncovered_fields"]


def _lead(discipline: str) -> str:
    ranked = [
        (brief.fields.index(discipline), order, seat)
        for order, (seat, brief) in enumerate(EXPERT_PANEL.items())
        if seat not in TESTIMONY_SEATS and discipline in brief.fields
    ]
    if not ranked:
        raise RuntimeError(f"no expert seat speaks for {discipline}")
    return min(ranked)[2]


FIELD_LEADS: Mapping[str, str] = MappingProxyType(
    {discipline: _lead(discipline) for discipline in DISCIPLINES}
)


def relevant_fields(asked: Sequence[str], held: Collection[str] | None) -> tuple[str, ...]:
    known = [discipline for discipline in dict.fromkeys(asked) if discipline in DISCIPLINES]
    if held is None:
        return tuple(known)
    return tuple(discipline for discipline in known if discipline in held)


def covering_seats(fields: Sequence[str], chosen: Sequence[str], *, limit: int) -> tuple[str, ...]:
    offered = [seat for seat in dict.fromkeys(chosen) if seat in EXPERT_PANEL]
    seats: list[str] = []
    for discipline in uncovered_fields(fields, ()):
        if len(seats) >= limit:
            break
        if not _speaks_for(discipline, seats):
            seats.append(_field_seat(discipline, offered))
    extra = [seat for seat in offered if seat not in seats]
    return tuple([*seats, *extra][:limit])


def uncovered_fields(fields: Sequence[str], seats: Sequence[str]) -> tuple[str, ...]:
    return tuple(
        discipline
        for discipline in dict.fromkeys(fields)
        if discipline in FIELD_LEADS and not _speaks_for(discipline, seats)
    )


def _field_seat(discipline: str, offered: Sequence[str]) -> str:
    return next((seat for seat in offered if _speaks_for(discipline, (seat,))), FIELD_LEADS[discipline])


def _speaks_for(discipline: str, seats: Sequence[str]) -> bool:
    return any(
        seat in EXPERT_PANEL and seat not in TESTIMONY_SEATS and discipline in EXPERT_PANEL[seat].fields
        for seat in seats
    )
