from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Sequence
from decimal import ROUND_UP, Decimal
from functools import partial
from pathlib import Path
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.core.db import dispose_engine, session_scope
from app.core.errors import AppError
from app.providers.elevenlabs import ElevenLabs
from app.providers.gemini_media import GeminiMediaWire
from app.voice.runtime import voice_settings

from .paid_check_agent import AGENT_TURN_USD, agent_check
from .paid_check_ledger import CapLedger, Recorder, approved_cap, written_fixture
from .paid_check_steps import (
    IMAGE_USD,
    MUSIC_SECONDS,
    MUSIC_USD_PER_SECOND,
    CheckResult,
    PaidCheck,
    image_check,
    music_check,
    narration_check,
    narration_estimate,
)

__all__ = ["run", "run_checks"]

CENT_TENTHS = Decimal("0.001")


async def run(*, cap: str, out: Path) -> dict[str, Any]:
    settings = get_settings()
    recorder = Recorder()
    try:
        async with session_scope() as session:
            voice = await voice_settings(session, settings)
        ledger = CapLedger(approved_cap(cap))
        async with httpx.AsyncClient(follow_redirects=False, event_hooks={"response": [recorder]}) as client:
            keys = _Keys(client, recorder, elevenlabs=voice.api_key, gemini=settings.gemini_api_key)
            return await run_checks(_checks(keys, voice.voice_id, settings), ledger, out)
    finally:
        await dispose_engine()


async def run_checks(checks: Sequence[PaidCheck], ledger: CapLedger, out: Path) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for check in checks:
        if not ledger.allows(check.estimate_usd):
            ledger.skip(check.name, check.estimate_usd)
            results[check.name] = {"skipped": "the next call would pass the cap"}
            continue
        try:
            result = await check.run()
        except (AppError, httpx.HTTPError, OSError, ValueError) as error:
            ledger.spend(check.name, check.estimate_usd)
            results[check.name] = {"error": f"{type(error).__name__}: {str(error)[:300]}"}
            continue
        ledger.spend(check.name, check.estimate_usd, result.actual_usd)
        fixtures = [written_fixture(out, name, body) for name, body in result.fixtures.items()]
        results[check.name] = {**result.findings, "fixtures": fixtures}
    return {
        "ok": all("error" not in found and "refused" not in found for found in results.values()),
        "capUsd": str(ledger.cap_usd),
        "spentUsd": str(ledger.spent_usd),
        "spend": ledger.rows,
        "checks": results,
    }


class _Keys:
    def __init__(
        self, client: httpx.AsyncClient, recorder: Recorder, *, elevenlabs: str | None, gemini: str | None
    ) -> None:
        self.client = client
        self.recorder = recorder
        self._elevenlabs = elevenlabs or ""
        self._gemini = gemini or ""

    def elevenlabs(self) -> ElevenLabs:
        return ElevenLabs(api_key=self._elevenlabs, client=self.client)

    def gemini(self) -> GeminiMediaWire:
        return GeminiMediaWire(api_key=self._gemini, client=self.client)


def _checks(keys: _Keys, voice_id: str, settings: Settings) -> list[PaidCheck]:
    async def narration(language: str) -> CheckResult:
        return await narration_check(keys.elevenlabs(), keys.recorder, voice_id=voice_id, language=language)

    async def music() -> CheckResult:
        return await music_check(keys.elevenlabs(), keys.recorder)

    async def image() -> CheckResult:
        return await image_check(keys.gemini(), keys.recorder)

    music_usd = (MUSIC_USD_PER_SECOND * Decimal(str(MUSIC_SECONDS))).quantize(CENT_TENTHS, rounding=ROUND_UP)
    return [
        PaidCheck("narration_en", narration_estimate("en"), partial(narration, "en")),
        PaidCheck("narration_hi", narration_estimate("hi"), partial(narration, "hi")),
        PaidCheck("music_bed", music_usd, music),
        PaidCheck("gemini_image", IMAGE_USD, image),
        PaidCheck("agent_turn", AGENT_TURN_USD, partial(agent_check, keys.client, settings)),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the owner-approved paid checks and record each reply.")
    parser.add_argument(
        "--cap", default="5", help="US dollars at most, never more than 5 (the owner's approval)"
    )
    parser.add_argument(
        "--out", type=Path, required=True, help="the folder the recorded replies are written to"
    )
    args = parser.parse_args()
    report = asyncio.run(run(cap=args.cap, out=args.out))
    written_fixture(
        args.out, "paid_checks_report.json", (json.dumps(report, indent=2) + "\n").encode("utf-8")
    )
    print(json.dumps(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
