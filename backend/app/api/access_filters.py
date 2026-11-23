from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import and_, or_

from app.core.roles import ROLE_RANK
from app.models import AccessRoster
from app.services import access_roster

ACCESS_ROLE_FILTER_TOKENS = frozenset(ROLE_RANK) | {"default"}

ACCESS_DATE_COLUMNS = {
    "added": "createdAt",
    "requested": "requestedAt",
    "decided": "decidedAt",
    "joined": "joinedAt",
    "firstSeen": "firstSeenAt",
}

ACCESS_SORT_COLUMNS = {
    "added": "createdAt",
    "email": "email",
    "name": "fullName",
    "standing": "status",
    "joined": "joinedAt",
    "requested": "requestedAt",
    "decided": "decidedAt",
    "firstSeen": "firstSeenAt",
    "attempts": "attemptCount",
}

ACCESS_SORT_DEFAULT_DIR = {
    "added": "desc",
    "email": "asc",
    "name": "asc",
    "standing": "asc",
    "joined": "desc",
    "requested": "desc",
    "decided": "desc",
    "firstSeen": "desc",
    "attempts": "desc",
}

ACCESS_DEFAULT_SORT = "added"


def _bad_filter(field: str, value: Any, allowed: frozenset[str]) -> HTTPException:
    return HTTPException(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        f"{field} {value!r} is not one of: {', '.join(sorted(allowed))}",
    )


def _tokens(values: list[str] | None, allowed: frozenset[str], field: str) -> set[str] | None:
    if not values:
        return None
    tokens = {part.strip() for value in values for part in value.split(",") if part.strip()}
    unknown = tokens - allowed
    if unknown:
        raise _bad_filter(field, sorted(unknown)[0], allowed)
    return tokens or None


def _status_condition(status_filter: list[str] | None) -> Any:
    statuses = _tokens(status_filter, frozenset(access_roster.STATUSES), "status")
    return AccessRoster.status.in_(sorted(statuses)) if statuses else None


def _search_condition(search: str | None) -> Any:
    if not (search and search.strip()):
        return None
    like = f"%{search.strip()}%"
    columns = (AccessRoster.email, AccessRoster.fullName, AccessRoster.notes)
    return or_(*(column.ilike(like) for column in columns))


def _role_condition(roles: list[str] | None) -> Any:
    wanted = _tokens(roles, ACCESS_ROLE_FILTER_TOKENS, "roles")
    if not wanted:
        return None
    arms: list[Any] = []
    named = sorted(wanted - {"default"})
    if named:
        arms.append(AccessRoster.admitRole.in_(named))
    if "default" in wanted:
        arms.append(AccessRoster.admitRole.is_(None))
    return or_(*arms)


def _date_conditions(field: str | None, start: datetime | None, end: datetime | None) -> list[Any]:
    if not field:
        return []
    if field not in ACCESS_DATE_COLUMNS:
        raise _bad_filter("dateField", field, frozenset(ACCESS_DATE_COLUMNS))
    column = getattr(AccessRoster, ACCESS_DATE_COLUMNS[field])
    conditions: list[Any] = []
    if start:
        conditions.append(column >= start)
    if end:
        conditions.append(column <= end)
    return conditions


def roster_filter(
    status_filter: list[str] | None,
    search: str | None,
    roles: list[str] | None,
    *,
    date_field: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
) -> Any:
    found = (_status_condition(status_filter), _search_condition(search), _role_condition(roles))
    conditions = [condition for condition in found if condition is not None]
    conditions += _date_conditions(date_field, date_from, date_to)
    return and_(*conditions) if conditions else None


def roster_ordering(sort: str | None, direction: str | None) -> Any:
    sort_token = sort or ACCESS_DEFAULT_SORT
    if sort_token not in ACCESS_SORT_COLUMNS:
        raise _bad_filter("sort", sort_token, frozenset(ACCESS_SORT_COLUMNS))
    dir_token = direction or ACCESS_SORT_DEFAULT_DIR[sort_token]
    if dir_token not in {"asc", "desc"}:
        raise _bad_filter("dir", dir_token, frozenset({"asc", "desc"}))
    column = getattr(AccessRoster, ACCESS_SORT_COLUMNS[sort_token])
    return column.asc().nulls_last() if dir_token == "asc" else column.desc().nulls_last()
