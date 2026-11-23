from __future__ import annotations

import logging
import time

import httpx

from app.core.key_checks import KeyVerdict, checked_get
from app.core.retry_after import retry_after_of

from .base import Adapter, ChatRequest, ChatResult, ProviderError, format_refused, names_the_format
from .usage import anthropic_usage

_FORMAT_NEEDLES = ("output_config.format", "json_schema", "schema")
REASON_CHARS = 300
MODELS_URL = "https://api.anthropic.com/v1/models"
API_VERSION = "2023-06-01"

logger = logging.getLogger(__name__)

_NO_SAMPLING = (
    "claude-fable-5",
    "claude-mythos",
    "claude-opus-5",
    "claude-opus-4-8",
    "claude-opus-4-7",
    "claude-sonnet-5",
)
_ALWAYS_THINKS = ("claude-fable-5", "claude-mythos", "claude-opus-5-5")
_BUDGET_FAMILY = (
    "claude-haiku-4-5",
    "claude-sonnet-4-5",
    "claude-opus-4-5",
    "claude-opus-4-1",
    "claude-opus-4-2",
    "claude-opus-4-0",
    "claude-sonnet-4-0",
    "claude-sonnet-4-2",
    "claude-3",
)
_SAMPLING_OK = ("claude-opus-4-6", "claude-sonnet-4-6", *_BUDGET_FAMILY)


def _family(model: str) -> str:
    if model.startswith(_ALWAYS_THINKS):
        return "always"
    if model.startswith(_BUDGET_FAMILY) or model in ("claude-opus-4", "claude-sonnet-4"):
        return "budget"
    return "adaptive"


def _apply_budget_thinking(req: ChatRequest, params: dict, meta: dict) -> None:
    if not req.reasoning:
        meta["thinking"] = "off"
        return
    budget = max(1024, req.reasoning_budget or 4096)
    params["thinking"] = {"type": "enabled", "budget_tokens": budget}
    params["max_tokens"] = max(req.max_tokens, budget + 1024)
    params.pop("temperature", None)
    meta["thinking"] = f"budget:{budget}"


def _chat_result(msg, meta: dict, latency: int) -> ChatResult:
    meta["stop_reason"] = msg.stop_reason
    meta["served_model"] = msg.model
    meta["request_id"] = getattr(msg, "_request_id", None)
    if msg.stop_reason == "refusal":
        details = getattr(msg, "stop_details", None)
        cat = getattr(details, "category", None) if details else None
        raise ProviderError(f"Claude declined the request (category: {cat})", kind="refusal")
    text = "".join(b.text for b in msg.content if b.type == "text")
    u = anthropic_usage(msg.usage)
    return ChatResult(
        text=text,
        input_tokens=u.input_tokens,
        output_tokens=u.output_tokens,
        latency_ms=latency,
        meta=meta,
        cached_input_tokens=u.cached_input_tokens,
        cache_write_tokens=u.cache_write_tokens,
    )


class AnthropicAdapter(Adapter):
    def __init__(self, **kw):
        super().__init__(**kw)
        try:
            import anthropic
        except ImportError as exc:
            raise ProviderError(
                "The `anthropic` package is not installed on this server", kind="unavailable"
            ) from exc
        import anthropic

        self._mod = anthropic
        args = {"max_retries": 2, "timeout": 600.0}
        if self.api_key:
            args["api_key"] = self.api_key
        if self.base_url:
            args["base_url"] = self.base_url
        self.client = anthropic.AsyncAnthropic(**args)

    def _build(self, req: ChatRequest) -> tuple[dict, dict]:
        model = req.model
        fam = _family(model)
        meta: dict = {"family": fam, "dropped": []}
        params: dict = {
            "model": model,
            "max_tokens": req.max_tokens,
            "system": req.system,
            "messages": [{"role": "user", "content": req.user}],
        }
        self._apply_temperature(req, params, meta)
        output_config = self._apply_thinking(req, fam, params, meta)
        if req.json_schema:
            output_config["format"] = {"type": "json_schema", "schema": req.json_schema}
            meta["structured"] = True
        if output_config:
            params["output_config"] = output_config
        return params, meta

    def _apply_temperature(self, req: ChatRequest, params: dict, meta: dict) -> None:
        if req.temperature is None:
            return
        model = req.model
        sampling_ok = model.startswith(_SAMPLING_OK) and not model.startswith(_NO_SAMPLING)
        if sampling_ok and not self.rejects(model, "temperature"):
            params["temperature"] = req.temperature
        else:
            meta["dropped"].append("temperature")

    def _apply_thinking(self, req: ChatRequest, fam: str, params: dict, meta: dict) -> dict:
        if fam == "always":
            meta["thinking"] = "forced_on"
            return {"effort": req.reasoning_effort or ("high" if req.reasoning else "low")}
        if fam == "budget":
            _apply_budget_thinking(req, params, meta)
            return {}
        return self._apply_adaptive_thinking(req, params, meta)

    def _apply_adaptive_thinking(self, req: ChatRequest, params: dict, meta: dict) -> dict:
        model = req.model
        output_config: dict = {}
        if req.reasoning:
            params["thinking"] = {"type": "adaptive"}
            if not self.rejects(model, "effort"):
                output_config["effort"] = req.reasoning_effort or "high"
            meta["thinking"] = "adaptive"
        elif not self.rejects(model, "thinking_disabled"):
            params["thinking"] = {"type": "disabled"}
            meta["thinking"] = "off"
        else:
            meta["thinking"] = "forced_on"
            if not self.rejects(model, "effort"):
                output_config["effort"] = "low"
        return output_config

    def _adapt(self, model: str, message: str) -> bool:
        low = message.lower()
        for needle, param in (
            ("temperature", "temperature"),
            ("disabled", "thinking_disabled"),
            ("effort", "effort"),
        ):
            if needle in low and not self.rejects(model, param):
                self.learn(model, param)
                return True
        return False

    def batch_params(self, req: ChatRequest) -> tuple[dict, dict]:
        return self._build(req)

    def batch_adapt(self, model: str, message: str) -> bool:
        return self._adapt(model, message)

    async def chat(self, req: ChatRequest) -> ChatResult:
        a = self._mod
        for _ in range(4):
            params, meta = self._build(req)
            t0 = time.perf_counter()
            try:
                async with self.client.messages.stream(**params) as stream:
                    msg = await stream.get_final_message()
            except a.BadRequestError as e:
                failure = self._bad_request_failure(req, e)
                if failure is None:
                    continue
                raise failure from e
            except (a.APIStatusError, a.APIConnectionError) as e:
                raise self._call_failure(req.model, e) from e
            latency = int((time.perf_counter() - t0) * 1000)
            return _chat_result(msg, meta, latency)
        raise ProviderError(
            "Anthropic request could not be adapted to the model's accepted parameters", kind="bad_request"
        )

    def _bad_request_failure(self, req: ChatRequest, e) -> ProviderError | None:
        if req.json_schema and names_the_format(str(e.message), _FORMAT_NEEDLES):
            logger.warning("Anthropic's reason for refusing the format: %s", str(e.message)[:REASON_CHARS])
            return format_refused("Anthropic", req.model)
        if self._adapt(req.model, str(e.message)):
            return None
        return ProviderError(f"Anthropic rejected the request: {e.message}", status=400, kind="bad_request")

    def _call_failure(self, model: str, e) -> ProviderError:
        a = self._mod
        if isinstance(e, a.AuthenticationError):
            return ProviderError("Anthropic API key is invalid", status=401, kind="auth")
        if isinstance(e, a.PermissionDeniedError):
            return ProviderError(f"Anthropic permission denied: {e.message}", status=403, kind="auth")
        if isinstance(e, a.NotFoundError):
            return ProviderError(f"Unknown Claude model '{model}'", status=404, kind="not_found")
        if isinstance(e, a.RateLimitError):
            return ProviderError(
                "Anthropic rate limit",
                retryable=True,
                status=429,
                kind="rate_limit",
                retry_after=retry_after_of(e),
            )
        if isinstance(e, a.APIStatusError):
            return ProviderError(
                f"Anthropic error {e.status_code}: {e.message}",
                retryable=e.status_code >= 500,
                status=e.status_code,
                retry_after=retry_after_of(e),
            )
        return ProviderError(f"Cannot reach Anthropic: {e}", retryable=True, kind="unavailable")

    async def list_models(self) -> list[dict]:
        a = self._mod
        out = []
        try:
            async for mdl in self.client.models.list(limit=100):
                out.append(
                    {
                        "id": mdl.id,
                        "label": getattr(mdl, "display_name", mdl.id),
                        "context_window": getattr(mdl, "max_input_tokens", None),
                    }
                )
        except a.AuthenticationError as e:
            raise ProviderError("Anthropic API key is invalid", status=401, kind="auth") from e
        except a.APIConnectionError as e:
            raise ProviderError(f"Cannot reach Anthropic: {e}", retryable=True, kind="unavailable") from e
        return out

    async def aclose(self) -> None:
        await self.client.close()


async def check_key(client: httpx.AsyncClient, value: str) -> KeyVerdict:
    return await checked_get(
        client, MODELS_URL, headers={"x-api-key": value, "anthropic-version": API_VERSION}
    )
