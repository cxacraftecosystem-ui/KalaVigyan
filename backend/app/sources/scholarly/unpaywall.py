from __future__ import annotations

from typing import Any
from urllib.parse import quote

from app.core.errors import ExternalFailure, InvalidInput
from app.research.evidence import OPEN_ACCESS_STATUSES, OpenAccessLocation

from ..adapter import Clock, utc_now
from ..http import SourceHttp
from ..records import clean_text, doi_of, https_or_none
from .pacing import ServiceLimits, SourceLimit

__all__ = ["UNPAYWALL_LIMITS", "UnpaywallLocator"]

UNPAYWALL_API = "https://api.unpaywall.org/v2"
UNPAYWALL_LIMITS = ServiceLimits(search=SourceLimit(requests=10))
HOST_TYPES = {"publisher": "PUBLISHER", "repository": "REPOSITORY"}


class UnpaywallLocator:
    name = "unpaywall"

    def __init__(self, http: SourceHttp, *, contact_email: str, clock: Clock = utc_now) -> None:
        self.http = http
        self.clock = clock
        self._params = {"email": contact_email}

    async def locate(self, doi: str) -> OpenAccessLocation:
        checked = doi_of(doi)
        if checked is None:
            raise InvalidInput(f"{doi!r} is not a DOI")
        response = await self.http.get(f"{UNPAYWALL_API}/{quote(checked, safe='/')}", params=self._params)
        record = response.json(self.name)
        status = str(record.get("oa_status") or "").upper()
        if status not in OPEN_ACCESS_STATUSES:
            raise ExternalFailure(f"unpaywall gave an unknown oa_status for {checked}", service=self.name)
        best = (record.get("best_oa_location") or {}) if status != "CLOSED" else {}
        return OpenAccessLocation(
            doi=checked,
            status=status,
            landing_url=https_or_none(best.get("url_for_landing_page")),
            pdf_url=https_or_none(best.get("url_for_pdf")),
            licence=clean_text(best.get("license")),
            version=clean_text(best.get("version")),
            host_type=_host_type(best.get("host_type")),
            checked_at=self.clock(),
        )


def _host_type(value: Any) -> str | None:
    return HOST_TYPES.get(str(value or "").lower())
