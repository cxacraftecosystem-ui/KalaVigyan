from typing import Literal

from pydantic import field_validator

from app.research.vocabulary import ANSWER_LANGUAGES
from app.schemas.common import APIModel

AUTO_ANSWER_LANGUAGE = "auto"
Theme = Literal["system", "light", "dark"]
Contrast = Literal["system", "standard", "high"]
PreferredAnswerLanguage = Literal[AUTO_ANSWER_LANGUAGE, *ANSWER_LANGUAGES]
CONTRAST_FROM_FLAG: dict[bool, Contrast] = {True: "high", False: "system"}


class PreferencesUpdate(APIModel):
    theme: Theme | None = None
    reducedMotion: bool | None = None
    largerText: bool | None = None
    highContrast: Contrast | None = None
    answerLanguage: PreferredAnswerLanguage | None = None
    alertDigest: bool | None = None

    @field_validator("highContrast", mode="before")
    @classmethod
    def _contrast_from_the_old_flag(cls, value: object) -> object:
        return CONTRAST_FROM_FLAG[value] if isinstance(value, bool) else value
