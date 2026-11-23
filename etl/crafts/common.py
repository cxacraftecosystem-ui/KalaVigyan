from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx

ETL_DIR = Path(__file__).resolve().parent
REPO = ETL_DIR.parents[1]
BACKEND = REPO / "backend"
DATA_DIR = BACKEND / "app" / "data"
CACHE_DIR = ETL_DIR / ".cache"

if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

USER_AGENT = "KalaVigyan-craft-etl/0.1 (open craft-science research data pipeline; httpx)"
RETRY_STATUSES = (429, 500, 502, 503, 504)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=1, sort_keys=False)
    path.write_text(text + "\n", encoding="utf-8", newline="\n")


class _Retry(Exception):
    def __init__(self, cause: Exception, pause: float | None = None) -> None:
        super().__init__(str(cause))
        self.cause = cause
        self.pause = pause


class PoliteClient:
    def __init__(
        self,
        *,
        cache_dir: Path | None = CACHE_DIR,
        min_interval: float = 1.0,
        retries: int = 6,
        timeout: float = 60.0,
    ) -> None:
        self._http = httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"},
            timeout=timeout,
            follow_redirects=True,
        )
        self.cache_dir = cache_dir
        self.min_interval = min_interval
        self.retries = retries
        self._last = 0.0
        self.requests = 0
        self.cache_hits = 0

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> PoliteClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _cache_path(self, url: str, params: dict[str, Any], data: dict[str, Any] | None) -> Path | None:
        if self.cache_dir is None:
            return None
        key = json.dumps([url, sorted(params.items()), sorted((data or {}).items())], ensure_ascii=False)
        digest = hashlib.sha1(key.encode()).hexdigest()
        return self.cache_dir / digest[:2] / f"{digest}.json"

    def get_json(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        *,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        params = dict(params or {})
        cached = self._cache_path(url, params, data)
        if cached is not None and cached.exists():
            self.cache_hits += 1
            return read_json(cached)
        payload = self._fetch_json(url, params, data, headers)
        if cached is not None:
            write_json(cached, payload)
        return payload

    def _fetch_json(
        self, url: str, params: dict[str, Any], data: dict[str, Any] | None, headers: dict[str, str] | None
    ) -> Any:
        delay = 2.0
        last_error: Exception | None = None
        for _ in range(self.retries):
            try:
                return self._attempt(url, params, data, headers)
            except _Retry as retry:
                last_error = retry.cause
                time.sleep(delay if retry.pause is None else retry.pause)
                delay = min(delay * 2, 60)
        raise RuntimeError(f"giving up on {url}") from last_error

    def _attempt(
        self, url: str, params: dict[str, Any], data: dict[str, Any] | None, headers: dict[str, str] | None
    ) -> Any:
        self._wait_turn()
        try:
            response = self._send(url, params, data, headers)
        except httpx.HTTPError as error:
            raise _Retry(error) from error
        if response.status_code in RETRY_STATUSES:
            retry_after = response.headers.get("retry-after", "")
            pause = float(retry_after) if retry_after.isdigit() else None
            raise _Retry(RuntimeError(f"HTTP {response.status_code} from {url}"), pause)
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and payload.get("error", {}).get("code") == "maxlag":
            raise _Retry(RuntimeError("maxlag"))
        return payload

    def _wait_turn(self) -> None:
        wait = self.min_interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()
        self.requests += 1

    def _send(
        self, url: str, params: dict[str, Any], data: dict[str, Any] | None, headers: dict[str, str] | None
    ) -> httpx.Response:
        if data is not None:
            return self._http.post(url, params=params, data=data, headers=headers)
        return self._http.get(url, params=params, headers=headers)
