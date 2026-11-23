from __future__ import annotations

import time

import httpx

from app.core.key_checks import KeyVerdict, checked_get
from app.core.retry_after import retry_after_of

from .base import (
    Adapter,
    ChatRequest,
    ChatResult,
    MediaPoll,
    MediaRequest,
    MediaResult,
    ProviderError,
    format_refused,
    names_the_format,
)
from .gemini_media import GEMINI_API, GeminiMediaWire
from .usage import gemini_cached_tokens

_SCHEMA_NEEDLES = ("response_json_schema", "schema")
_BLOCKED_FINISHES = ("SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "RECITATION")


def _chat_result(req: ChatRequest, resp, meta: dict, latency: int) -> ChatResult:
    cand = (resp.candidates or [None])[0]
    finish = getattr(cand, "finish_reason", None) if cand else None
    meta["stop_reason"] = str(finish) if finish else None
    meta["served_model"] = getattr(resp, "model_version", None) or req.model
    if cand is None or (finish and str(finish).endswith(_BLOCKED_FINISHES)):
        fb = getattr(resp, "prompt_feedback", None)
        raise ProviderError(
            f"Gemini blocked the response ({finish or getattr(fb, 'block_reason', 'no candidate')})",
            kind="refusal",
        )
    u = resp.usage_metadata
    if u is not None and getattr(u, "thoughts_token_count", None):
        meta["thought_tokens"] = u.thoughts_token_count
    out_tokens = None
    if u is not None:
        out_tokens = (u.candidates_token_count or 0) + (u.thoughts_token_count or 0)
    return ChatResult(
        text=resp.text or "",
        input_tokens=getattr(u, "prompt_token_count", None),
        output_tokens=out_tokens,
        latency_ms=latency,
        meta=meta,
        cached_input_tokens=gemini_cached_tokens(u),
    )


class GeminiAdapter(Adapter):
    def __init__(self, *, media_client: httpx.AsyncClient | None = None, **kw):
        super().__init__(**kw)
        self._media_client = media_client
        self._owns_media_client = media_client is None
        try:
            from google import genai
            from google.genai import errors, types
        except ImportError as exc:
            raise ProviderError(
                "The `google-genai` package is not installed on this server", kind="unavailable"
            ) from exc
        self._types = types
        self._errors = errors
        if not self.api_key:
            raise ProviderError("Gemini requires an API key", kind="auth")
        self.client = genai.Client(api_key=self.api_key)

    def _config(self, req: ChatRequest, meta: dict):
        t = self._types
        cfg: dict = {"system_instruction": req.system, "max_output_tokens": req.max_tokens}
        if req.temperature is not None and not self.rejects(req.model, "temperature"):
            cfg["temperature"] = req.temperature
        elif req.temperature is not None:
            meta["dropped"].append("temperature")
        if req.json_schema:
            cfg["response_mime_type"] = "application/json"
            cfg["response_json_schema"] = req.json_schema
            meta["structured"] = True
        uses_level = req.model.startswith(("gemini-3", "models/gemini-3"))
        if not self.rejects(req.model, "thinking"):
            if uses_level:
                cfg["thinking_config"] = t.ThinkingConfig(
                    thinking_level=(req.reasoning_effort or "high") if req.reasoning else "low"
                )
                meta["thinking"] = "level:" + ((req.reasoning_effort or "high") if req.reasoning else "low")
            elif req.reasoning:
                cfg["thinking_config"] = t.ThinkingConfig(thinking_budget=req.reasoning_budget or -1)
                meta["thinking"] = f"budget:{req.reasoning_budget or 'dynamic'}"
            else:
                cfg["thinking_config"] = t.ThinkingConfig(thinking_budget=0)
                meta["thinking"] = "off"
        else:
            meta["thinking"] = "model_default"
        return t.GenerateContentConfig(**cfg)

    def batch_params(self, req: ChatRequest) -> tuple[dict, dict]:
        meta: dict = {"dropped": []}
        return {"model": req.model, "contents": req.user, "config": self._config(req, meta)}, meta

    def _adapt(self, model: str, message: str) -> bool:
        low = message.lower()
        for needle, param in (("thinking", "thinking"), ("temperature", "temperature")):
            if needle in low and not self.rejects(model, param):
                self.learn(model, param)
                return True
        return False

    def batch_adapt(self, model: str, message: str) -> bool:
        return self._adapt(model, message)

    async def chat(self, req: ChatRequest) -> ChatResult:
        err = self._errors
        for _ in range(4):
            meta: dict = {"dropped": []}
            config = self._config(req, meta)
            t0 = time.perf_counter()
            try:
                resp = await self.client.aio.models.generate_content(
                    model=req.model, contents=req.user, config=config
                )
            except err.ClientError as e:
                failure = self._client_failure(req, e)
                if failure is None:
                    continue
                raise failure from e
            except err.ServerError as e:
                raise ProviderError(
                    f"Gemini server error {e.code}: {e}",
                    retryable=True,
                    status=e.code,
                    retry_after=retry_after_of(e),
                ) from e
            except (OSError, TimeoutError) as e:
                raise ProviderError(f"Cannot reach Gemini: {e}", retryable=True, kind="unavailable") from e
            latency = int((time.perf_counter() - t0) * 1000)
            return _chat_result(req, resp, meta, latency)
        raise ProviderError(
            "Gemini request could not be adapted to the model's accepted parameters", kind="bad_request"
        )

    def _client_failure(self, req: ChatRequest, e) -> ProviderError | None:
        msg = str(e).lower()
        if e.code == 400 and req.json_schema and names_the_format(msg, _SCHEMA_NEEDLES):
            return format_refused("Gemini", req.model)
        if e.code == 400:
            if self._adapt(req.model, msg):
                return None
            return ProviderError(f"Gemini rejected the request: {e}", status=400, kind="bad_request")
        if e.code in (401, 403):
            return ProviderError("Gemini API key is invalid or lacks access", status=e.code, kind="auth")
        if e.code == 404:
            return ProviderError(f"Unknown Gemini model '{req.model}'", status=404, kind="not_found")
        if e.code == 429:
            return ProviderError(
                "Gemini rate limit / quota",
                retryable=True,
                status=429,
                kind="rate_limit",
                retry_after=retry_after_of(e),
            )
        return ProviderError(f"Gemini error {e.code}: {e}", status=e.code)

    async def list_models(self) -> list[dict]:
        err = self._errors
        out = []
        try:
            pager = await self.client.aio.models.list()
            async for mdl in pager:
                actions = mdl.supported_actions or []
                if "generateContent" not in actions and "embedContent" not in actions:
                    continue
                mid = (mdl.name or "").removeprefix("models/")
                out.append(
                    {
                        "id": mid,
                        "label": mdl.display_name or mid,
                        "context_window": mdl.input_token_limit,
                        "embedding": "embedContent" in actions and "generateContent" not in actions,
                    }
                )
        except err.ClientError as e:
            raise ProviderError(
                f"Gemini: {e}", status=e.code, kind="auth" if e.code in (401, 403) else "error"
            ) from e
        return sorted(out, key=lambda x: x["id"])

    async def embed(self, texts: list[str], model: str, dimensions: int | None = None) -> list[list[float]]:
        err = self._errors
        config = self._types.EmbedContentConfig(output_dimensionality=dimensions) if dimensions else None
        contents = [self._types.Content(parts=[self._types.Part(text=text)]) for text in texts]
        try:
            resp = await self.client.aio.models.embed_content(model=model, contents=contents, config=config)
        except err.APIError as e:
            raise ProviderError(
                f"Gemini embeddings error {e.code}: {e}", retryable=e.code in (429, 500, 503), status=e.code
            ) from e
        self.last_usage = getattr(resp, "metadata", None)
        return [list(e.values) for e in resp.embeddings]

    async def generate_image(self, req: MediaRequest) -> MediaResult:
        return await self._media_wire().generate_image(req)

    async def start_video(self, req: MediaRequest) -> str:
        return await self._media_wire().start_video(req)

    async def poll_video(self, ref: str) -> MediaPoll:
        return await self._media_wire().poll_video(ref)

    async def forget_media(self, ref: str) -> None:
        await self._media_wire().forget(ref)

    async def aclose(self) -> None:
        if self._owns_media_client and self._media_client is not None:
            await self._media_client.aclose()
            self._media_client = None

    def _media_wire(self) -> GeminiMediaWire:
        if self._media_client is None:
            self._media_client = httpx.AsyncClient()
        return GeminiMediaWire(api_key=self.api_key or "", client=self._media_client)


async def check_key(client: httpx.AsyncClient, value: str) -> KeyVerdict:
    return await checked_get(
        client, f"{GEMINI_API}/models", headers={"x-goog-api-key": value}, params={"pageSize": "1"}
    )
