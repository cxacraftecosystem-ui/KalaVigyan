from __future__ import annotations

from app.research.evidence import OpenAccessLocation, OpenAccessLocator

from .zenodo import zenodo_doi_record

__all__ = ["OpenCopyLocator"]


class OpenCopyLocator:
    name = "open_access"

    def __init__(self, unpaywall: OpenAccessLocator, zenodo: OpenAccessLocator) -> None:
        self._unpaywall = unpaywall
        self._zenodo = zenodo

    async def locate(self, doi: str) -> OpenAccessLocation:
        if zenodo_doi_record(doi) is not None:
            return await self._zenodo.locate(doi)
        return await self._unpaywall.locate(doi)
