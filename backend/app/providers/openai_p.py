from __future__ import annotations

import time

import httpx

from app.core.key_checks import KeyCheck, KeyVerdict, checked_get
from app.core.retry_after import retry_after_of

from .base import Adapter, ChatRequest, ChatResult, ProviderError, format_refused, names_the_format
from .usage import openai_usage

_LOCAL_PLACEHOLDER_KEY = "not-required"
_FORMAT_NEEDLES = ("json_schema", "response_format", "json_object")


class OpenAICompatAdapter(Adapter):
    def __init__(self, *, native: bool = False, **kw):
        super().__init__(**kw)
        try:
            import openai
        except ImportError as exc:
            raise ProviderError(
                "The `openai` package is not installed on this server", kind="unavailable"
            ) from exc
        self._mod = openai
        self.native = native
        self.client = openai.AsyncOpenAI(
            api_key=self.api_key or _LOCAL_PLACEHOLDER_KEY,
            base_url=self.base_url or None,
            max_retries=2,
            timeout=600.0,
        )

    def _reasoning(self, req: ChatRequest, params: dict, extra_body: dict, meta: dict) -> None:
        p = self.preset
        if p == "zai" or p == "zhipu":
            extra_body["thinking"] = {"type": "enabled" if req.reasoning else "disabled"}
        elif p == "dashscope":
            extra_body["enable_thinking"] = bool(req.reasoning)
        elif p == "ollama":
            extra_body["think"] = bool(req.reasoning)
        elif p == "openrouter":
            extra_body["reasoning"] = {"enabled": bool(req.reasoning)} | (
                {"effort": req.reasoning_effort} if req.reasoning and req.reasoning_effort else {}
            )
        elif p == "deepseek":
            meta["thinking"] = "model_defined"
            return
        elif req.reasoning and not self.rejects(req.model, "reasoning_effort"):
            params["reasoning_effort"] = req.reasoning_effort or "medium"
        meta["thinking"] = "on" if req.reasoning else "off"

    def _build(self, req: ChatRequest) -> tuple[dict, dict]:
        model = req.model
        meta: dict = {"dropped": []}
        params: dict = {
            "model": model,
            "messages": [{"role": "system", "content": req.system}, {"role": "user", "content": req.user}],
        }
        extra_body: dict = {}
        tok_param = (
            "max_completion_tokens" if (self.native or self.rejects(model, "max_tokens")) else "max_tokens"
        )
        if self.rejects(model, "max_completion_tokens"):
            tok_param = "max_tokens"
        params[tok_param] = req.max_tokens
        if req.temperature is not None:
            if self.rejects(model, "temperature"):
                meta["dropped"].append("temperature")
            else:
                params["temperature"] = req.temperature
        self._reasoning(req, params, extra_body, meta)
        if req.json_schema:
            params["response_format"] = self._response_format(req.json_schema)
            meta["structured"] = params["response_format"]["type"]
        if extra_body:
            params["extra_body"] = extra_body
        return params, meta

    def _response_format(self, schema: dict) -> dict:
        if self.native:
            return {
                "type": "json_schema",
                "json_schema": {"name": "inference", "schema": schema, "strict": False},
            }
        return {"type": "json_object"}

    def _adapt(self, model: str, message: str, params: dict) -> bool:
        low = message.lower()
        checks = [
            ("temperature", "temperature"),
            ("max_tokens", "max_tokens"),
            ("max_completion_tokens", "max_completion_tokens"),
            ("reasoning_effort", "reasoning_effort"),
        ]
        for needle, param in checks:
            if needle in low and not self.rejects(model, param):
                if param == "max_tokens" and "max_tokens" not in params:
                    continue
                self.learn(model, param)
                return True
        if (
            "extra_body" in params
            and ("thinking" in low or "enable_thinking" in low or "think" in low or "reasoning" in low)
            and not self.rejects(model, "reasoning_extra")
        ):
            self.learn(model, "reasoning_extra")
            return True
        return False

    def batch_params(self, req: ChatRequest) -> tuple[dict, dict]:
        params, meta = self._build(req)
        if self.rejects(req.model, "reasoning_extra"):
            params.pop("extra_body", None)
            meta["thinking"] = "unsupported"
        body = {k: v for k, v in params.items() if k != "extra_body"}
        body.update(params.get("extra_body") or {})
        return body, meta

    def batch_adapt(self, model: str, message: str) -> bool:
        params, _ = self._build(ChatRequest(model=model, system="", user="", max_tokens=1))
        return self._adapt(model, message, params)

    async def chat(self, req: ChatRequest) -> ChatResult:
        o = self._mod
        for _ in range(6):
            params, meta = self._build(req)
            if self.rejects(req.model, "reasoning_extra"):
                params.pop("extra_body", None)
                meta["thinking"] = "unsupported"
            t0 = time.perf_counter()
            try:
                resp = await self.client.chat.completions.create(**params)
            except o.BadRequestError as e:
                if req.json_schema and names_the_format(str(e), _FORMAT_NEEDLES):
                    raise format_refused(self.preset, req.model) from e
                if self._adapt(req.model, str(e), params):
                    continue
                raise ProviderError(
                    f"{self.preset} rejected the request: {e}", status=400, kind="bad_request"
                ) from e
            except o.AuthenticationError as e:
                raise ProviderError(
                    f"{self.preset}: API key is invalid or missing", status=401, kind="auth"
                ) from e
            except o.PermissionDeniedError as e:
                raise ProviderError(f"{self.preset}: permission denied: {e}", status=403, kind="auth") from e
            except o.NotFoundError as e:
                raise ProviderError(
                    f"{self.preset}: unknown model '{req.model}'", status=404, kind="not_found"
                ) from e
            except o.RateLimitError as e:
                raise ProviderError(
                    f"{self.preset}: rate limited",
                    retryable=True,
                    status=429,
                    kind="rate_limit",
                    retry_after=retry_after_of(e),
                ) from e
            except o.APIStatusError as e:
                raise ProviderError(
                    f"{self.preset} error {e.status_code}: {e}",
                    retryable=e.status_code >= 500,
                    status=e.status_code,
                    retry_after=retry_after_of(e),
                ) from e
            except o.APIConnectionError as e:
                raise ProviderError(
                    f"Cannot reach {self.preset} at {self.base_url}: {e}", retryable=True, kind="unavailable"
                ) from e
            latency = int((time.perf_counter() - t0) * 1000)
            if not resp.choices:
                raise ProviderError(f"{self.preset} returned no choices", retryable=True)
            choice = resp.choices[0]
            msg = choice.message
            meta["stop_reason"] = choice.finish_reason
            meta["served_model"] = getattr(resp, "model", req.model)
            rc = getattr(msg, "reasoning_content", None) or getattr(msg, "reasoning", None)
            if rc:
                meta["reasoning_chars"] = len(rc) if isinstance(rc, str) else None
            if getattr(msg, "refusal", None):
                raise ProviderError(f"{self.preset} refused: {msg.refusal}", kind="refusal")
            if choice.finish_reason == "content_filter":
                raise ProviderError(f"{self.preset} content filter stopped the response", kind="refusal")
            u = openai_usage(resp.usage)
            return ChatResult(
                text=msg.content or "",
                input_tokens=u.input_tokens,
                output_tokens=u.output_tokens,
                latency_ms=latency,
                meta=meta,
                cached_input_tokens=u.cached_input_tokens,
                cache_write_tokens=u.cache_write_tokens,
            )
        raise ProviderError(
            f"{self.preset}: request could not be adapted to the model's accepted parameters",
            kind="bad_request",
        )

    async def list_models(self) -> list[dict]:
        o = self._mod
        try:
            page = await self.client.models.list()
        except o.AuthenticationError as e:
            raise ProviderError(
                f"{self.preset}: API key is invalid or missing", status=401, kind="auth"
            ) from e
        except o.APIConnectionError as e:
            raise ProviderError(
                f"Cannot reach {self.preset} at {self.base_url}", retryable=True, kind="unavailable"
            ) from e
        except o.APIStatusError as e:
            raise ProviderError(
                f"{self.preset} error {e.status_code} listing models: {e}", status=e.status_code
            ) from e
        out = []
        async for mdl in page:
            out.append(
                {"id": mdl.id, "label": mdl.id, "context_window": getattr(mdl, "context_length", None)}
            )
        return sorted(out, key=lambda x: x["id"])

    async def embed(self, texts: list[str], model: str, dimensions: int | None = None) -> list[list[float]]:
        o = self._mod
        extra = {"dimensions": dimensions} if dimensions else {}
        try:
            resp = await self.client.embeddings.create(model=model, input=texts, **extra)
        except o.APIStatusError as e:
            raise ProviderError(
                f"{self.preset} embeddings error {e.status_code}: {e}",
                retryable=e.status_code >= 500 or e.status_code == 429,
                status=e.status_code,
            ) from e
        except o.APIConnectionError as e:
            raise ProviderError(
                f"Cannot reach {self.preset} for embeddings", retryable=True, kind="unavailable"
            ) from e
        return [d.embedding for d in sorted(resp.data, key=lambda d: d.index)]

    async def aclose(self) -> None:
        await self.client.close()


def key_check_at(base_url: str) -> KeyCheck:
    models_url = f"{base_url.rstrip('/')}/models"

    async def check_key(client: httpx.AsyncClient, value: str) -> KeyVerdict:
        return await checked_get(client, models_url, headers={"Authorization": f"Bearer {value}"})

    return check_key
