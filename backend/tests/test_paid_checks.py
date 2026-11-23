import json
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.core.errors import ExternalFailure
from app.providers.elevenlabs_socket import one_turn
from app.scripts.paid_check_ledger import CapLedger, Recorder, approved_cap
from app.scripts.paid_check_steps import NARRATIONS, CheckResult, PaidCheck, narration_estimate
from app.scripts.paid_checks import run_checks


def check(name: str, estimate: str, result: CheckResult | Exception, ran: list[str]) -> PaidCheck:
    async def run() -> CheckResult:
        ran.append(name)
        if isinstance(result, Exception):
            raise result
        return result

    return PaidCheck(name, Decimal(estimate), run)


def test_the_cap_never_passes_the_owner_s_five_dollars() -> None:
    assert approved_cap("5") == Decimal(5) and approved_cap("0.5") == Decimal("0.5")
    for refused in ("5.01", "0", "-1"):
        with pytest.raises(ValueError, match="at most US"):
            approved_cap(refused)


async def test_a_call_that_would_pass_the_cap_is_never_made(tmp_path: Path) -> None:
    ran: list[str] = []
    checks = [
        check("narration_en", "1.50", CheckResult({"model": "eleven_v4"}, {"narration_en.json": b"{}"}), ran),
        check("music_bed", "2.00", CheckResult({}, actual_usd=Decimal("2.50")), ran),
        check("gemini_image", "1.10", CheckResult({}), ran),
        check("agent_turn", "1.00", CheckResult({}), ran),
    ]
    report = await run_checks(checks, CapLedger(Decimal(5)), tmp_path)
    assert ran == ["narration_en", "music_bed", "agent_turn"]
    assert report["spentUsd"] == "5.00" and report["checks"]["gemini_image"]["skipped"]
    assert report["checks"]["narration_en"]["fixtures"] == ["narration_en.json"]
    assert (tmp_path / "narration_en.json").read_bytes() == b"{}"


async def test_a_failed_call_counts_its_estimate_and_the_run_goes_on(tmp_path: Path) -> None:
    ran: list[str] = []
    failure = ExternalFailure("ElevenLabs answered 500", kind="unavailable", service="elevenlabs")
    checks = [check("narration_hi", "0.04", failure, ran), check("music_bed", "0.05", CheckResult({}), ran)]
    report = await run_checks(checks, CapLedger(Decimal(5)), tmp_path)
    assert ran == ["narration_hi", "music_bed"] and report["spentUsd"] == "0.09" and not report["ok"]
    assert report["checks"]["narration_hi"]["error"].startswith("ExternalFailure")


def test_each_narration_is_estimated_at_thirty_cents_a_thousand_characters() -> None:
    assert narration_estimate("en") == Decimal(len(NARRATIONS["en"])) * Decimal("0.0003")
    assert "[" in NARRATIONS["en"] and "[" in NARRATIONS["hi"]


async def test_the_recorder_keeps_each_reply_without_the_request_headers() -> None:
    recorder = Recorder()

    def answer(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"alignment": {"characters": ["A"]}})

    transport = httpx.MockTransport(answer)
    async with httpx.AsyncClient(transport=transport, event_hooks={"response": [recorder]}) as client:
        await client.post(
            "https://api.elevenlabs.io/v1/text-to-speech/v/with-timestamps", headers={"xi-api-key": "k"}
        )
    reply = recorder.last("/with-timestamps")
    assert reply is not None and (reply.method, reply.status) == ("POST", 200)
    assert (
        json.loads(reply.fixture()) == {"alignment": {"characters": ["A"]}}
        and b"xi-api-key" not in reply.fixture()
    )


class FakeSocket:
    def __init__(self, events: list[dict[str, Any]]) -> None:
        self.events = [json.dumps(event) for event in events]
        self.sent: list[dict[str, Any]] = []

    async def send(self, message: str) -> None:
        self.sent.append(json.loads(message))

    async def recv(self) -> str:
        if not self.events:
            raise TimeoutError
        return self.events.pop(0)


async def test_one_agent_turn_binds_the_conversation_before_it_asks_and_keeps_no_audio() -> None:
    socket = FakeSocket(
        [
            {
                "type": "conversation_initiation_metadata",
                "conversation_initiation_metadata_event": {"conversation_id": "conv_1"},
            },
            {"type": "ping", "ping_event": {"event_id": 7}},
            {
                "type": "agent_response",
                "agent_response_event": {"agent_response": "Ajrakh is a resist-printed cloth."},
            },
            {"type": "audio", "audio_event": {"event_id": 8, "audio_base_64": "QUJD"}},
        ]
    )
    bound: list[str] = []

    async def bind(conversation_id: str) -> None:
        bound.append(conversation_id)
        assert socket.sent == []

    @asynccontextmanager
    async def opener(url: str) -> Any:
        yield socket

    turn = await one_turn(
        "wss://api.elevenlabs.io/v1/convai/conversation", "What is Ajrakh?", bind=bind, opener=opener
    )
    assert bound == ["conv_1"] and turn.conversation_id == "conv_1"
    assert socket.sent == [
        {"type": "user_message", "text": "What is Ajrakh?"},
        {"type": "pong", "event_id": 7},
    ]
    assert turn.replies == ["Ajrakh is a resist-printed cloth."]
    assert turn.events[-1] == {"type": "audio", "audio_event": {"event_id": 8, "base64Length": 4}}
