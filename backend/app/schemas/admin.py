from typing import Annotated, Literal

from pydantic import EmailStr, Field

from app.core.security import MAX_PASSWORD_LENGTH
from app.research.vocabulary import Depth
from app.schemas.common import APIModel
from app.schemas.voice import VoiceTransport

VOICE_ID_PATTERN = r"^[A-Za-z0-9]{1,64}$"
MAX_LIVE_SESSIONS_CEILING = 100


class AccessRosterCreate(APIModel):
    email: EmailStr
    fullName: str | None = Field(default=None, max_length=180)
    role: str | None = None
    notes: str | None = Field(default=None, max_length=4000)
    affiliation: str | None = Field(default=None, max_length=300)
    password: str | None = Field(default=None, min_length=10, max_length=MAX_PASSWORD_LENGTH)
    mustChangePassword: bool = True


class AccessRosterUpdate(APIModel):
    fullName: str | None = Field(default=None, max_length=180)
    role: str | None = None
    notes: str | None = Field(default=None, max_length=4000)
    affiliation: str | None = Field(default=None, max_length=300)


class AccessDecision(APIModel):
    decision: Literal["APPROVE", "REJECT"]
    role: str | None = None
    notes: str | None = Field(default=None, max_length=4000)


class UserUpdate(APIModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    role: str | None = None
    affiliation: str | None = Field(default=None, max_length=300)
    mustChangePassword: bool | None = None


class SuspendRequest(APIModel):
    reason: str | None = Field(default=None, max_length=1000)


class GuardianConsentRequest(APIModel):
    affirmed: Literal[True]
    noticeVersion: str = Field(min_length=1, max_length=40)


class ManagedSecretSetIn(APIModel):
    value: str = Field(min_length=1, max_length=8000)
    twoFactorCode: str | None = Field(default=None, max_length=64)


class ManagedSecretClearIn(APIModel):
    twoFactorCode: str | None = Field(default=None, max_length=64)


class RouteEntry(APIModel):
    provider: str = Field(min_length=1, max_length=40)
    model: str = Field(min_length=1, max_length=120)
    enabled: bool = True
    maxOutputTokens: int | None = Field(default=None, ge=1, le=128_000)
    temperature: float | None = Field(default=None, ge=0, le=2)


class RouteOrderUpdate(APIModel):
    routes: list[RouteEntry] = Field(min_length=1, max_length=8)


class RouteTestRequest(APIModel):
    provider: str = Field(min_length=1, max_length=40)
    model: str | None = Field(default=None, max_length=120)


class VoiceSettingsUpdate(APIModel):
    transport: VoiceTransport | None = None
    maxLiveSessions: int | None = Field(default=None, ge=0, le=MAX_LIVE_SESSIONS_CEILING)
    voiceId: str | None = Field(default=None, pattern=VOICE_ID_PATTERN)


class AppSettingsUpdate(APIModel):
    monthlyCeilingUsd: float | None = Field(default=None, ge=0, le=100_000)
    mediaCapUsd: float | None = Field(default=None, ge=0, le=100_000)
    roleDailyUsd: dict[str, float | None] | None = None
    signUpMode: Literal["ROSTER", "OPEN_DOMAIN_ALLOWLIST", "CLOSED"] | None = None
    domainAllowlist: list[str] | None = Field(default=None, max_length=200)
    degradeAtFraction: float | None = Field(default=None, gt=0, le=1)
    answerCapUsd: dict[Depth, Annotated[float, Field(ge=0, le=1_000)] | None] | None = None
    dailyAllowances: dict[str, dict[str, Annotated[int, Field(ge=0, le=1_000_000)] | None]] | None = None
    twoFactorCode: str | None = Field(default=None, max_length=64)
