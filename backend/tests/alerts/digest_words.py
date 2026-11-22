import uuid
from collections.abc import Mapping

from app.research.translation import TranslationRequest
from app.services.alert_digest import DIGEST_OPENING, DIGEST_STOP, DIGEST_SUBJECT

__all__ = ["HINDI", "NEWS", "KnownTranslator", "NoCache"]

NEWS = "4 new findings (3 in Geography and water, 1 in History)"
HINDI = {
    DIGEST_SUBJECT: "आपके सहेजे गए KalaVigyan व्याख्यान बेहतर हुए",
    DIGEST_OPENING: "आपके सहेजे गए व्याख्यानों के लिए इस सप्ताह नए उद्धृत निष्कर्ष आए।",
    NEWS: "4 नए निष्कर्ष (भूगोल और जल में 3, इतिहास में 1)",
    DIGEST_STOP: "सेटिंग्स में ये ईमेल बंद करें:",
}


class KnownTranslator:
    def __init__(self, known: Mapping[str, str]) -> None:
        self.known = known
        self.asked: list[list[tuple[str, str]]] = []

    async def translate(self, request: TranslationRequest) -> dict[str, str]:
        self.asked.append([(item.key, item.text) for item in request.items])
        return {item.key: self.known[item.text] for item in request.items if item.text in self.known}


class NoCache:
    async def known(self, language: str, texts: Mapping[uuid.UUID, str]) -> dict[uuid.UUID, str]:
        return {}

    async def remember(self, language: str, entries: Mapping[uuid.UUID, tuple[str, str]]) -> None:
        return None
