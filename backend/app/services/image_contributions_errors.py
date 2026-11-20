from __future__ import annotations

__all__ = ["ContributionRefused", "UnknownImage"]


class UnknownImage(Exception):
    pass


class ContributionRefused(Exception):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail
