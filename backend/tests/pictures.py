from __future__ import annotations

import io
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

from PIL import Image, ImageDraw, PngImagePlugin

from app.research.image_screens import ScreenTools, VisionRequest, VisionVerdict
from app.services.object_store import PresignedGet

__all__ = [
    "AI_SOURCE",
    "FakeObjects",
    "SeenVision",
    "picture",
    "screen_tools",
]

AI_SOURCE = b"http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"
SHAPES = 14


def picture(
    width: int = 800, height: int = 600, *, seed: int = 1, kind: str = "PNG", note: bytes = b""
) -> bytes:
    rng = random.Random(seed)
    made = Image.new("RGB", (width, height), _colour(rng))
    draw = ImageDraw.Draw(made)
    for _ in range(SHAPES):
        x, y = rng.randrange(width), rng.randrange(height)
        box = (x, y, x + rng.randrange(width // 8, width // 2), y + rng.randrange(height // 8, height // 2))
        draw.rectangle(box, fill=_colour(rng))
    out = io.BytesIO()
    if note:
        info = PngImagePlugin.PngInfo()
        info.add_itxt("XML:com.adobe.xmp", note.decode("ascii"))
        made.save(out, "PNG", pnginfo=info)
    else:
        made.save(out, kind)
    return out.getvalue()


def _colour(rng: random.Random) -> tuple[int, int, int]:
    return rng.randrange(256), rng.randrange(256), rng.randrange(256)


@dataclass
class SeenVision:
    flags: tuple[str, ...] = ()
    note: str | None = None
    cost: Decimal = Decimal("0.000150")
    requests: list[VisionRequest] = field(default_factory=list)

    async def __call__(self, request: VisionRequest) -> VisionVerdict:
        self.requests.append(request)
        return VisionVerdict(
            ran=True,
            flags=self.flags,
            note=self.note,
            provider="GEMINI",
            model="gemini-test-flash-lite",
            input_tokens=900,
            output_tokens=40,
            cost_usd=self.cost,
        )


def screen_tools(vision: SeenVision | None = None) -> ScreenTools:
    return ScreenTools(vision=vision if vision is not None else SeenVision())


@dataclass
class FakeObjects:
    puts: dict[str, tuple[bytes, str]] = field(default_factory=dict)

    async def put(self, key: str, body: bytes, *, content_type: str) -> None:
        self.puts[key] = (body, content_type)

    async def get(self, key: str) -> bytes | None:
        stored = self.puts.get(key)
        return stored[0] if stored else None

    def presigned_get(self, key: str, *, disposition: str, seconds: int, now: datetime) -> PresignedGet:
        return PresignedGet(url=f"https://bucket.test/{key}", expires_at=now + timedelta(seconds=seconds))
