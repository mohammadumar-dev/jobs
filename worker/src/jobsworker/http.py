from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import urlsplit

import httpx

log = logging.getLogger(__name__)

RETRY_STATUS = {429, 500, 502, 503, 504}


class PoliteClient:
    """httpx wrapper: identifies itself, <=1 request/sec per host, backoff on 429/5xx."""

    def __init__(
        self,
        user_agent: str,
        min_interval_s: float = 1.0,
        max_retries: int = 3,
        transport: httpx.BaseTransport | None = None,
        sleep=time.sleep,
        clock=time.monotonic,
    ) -> None:
        self._client = httpx.Client(
            headers={"User-Agent": user_agent, "Accept": "application/json"},
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=True,
            transport=transport,
        )
        self._min_interval = min_interval_s
        self._max_retries = max_retries
        self._last: dict[str, float] = {}
        self._sleep = sleep
        self._clock = clock

    def _throttle(self, host: str) -> None:
        last = self._last.get(host)
        if last is not None:
            wait = self._min_interval - (self._clock() - last)
            if wait > 0:
                self._sleep(wait)
        self._last[host] = self._clock()

    def get(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        host = urlsplit(url).netloc
        attempt = 0
        while True:
            self._throttle(host)
            resp: httpx.Response | None
            try:
                resp = self._client.get(url, params=params)
            except httpx.TransportError:
                if attempt >= self._max_retries:
                    raise
                resp = None
            if resp is not None and (
                resp.status_code not in RETRY_STATUS or attempt >= self._max_retries
            ):
                return resp
            delay = min(60.0, 2.0 ** (attempt + 1))
            if resp is not None:
                retry_after = resp.headers.get("Retry-After", "")
                if retry_after.isdigit():
                    delay = min(120.0, float(retry_after))
            log.warning("retrying %s in %.0fs (attempt %d)", host, delay, attempt + 1)
            self._sleep(delay)
            attempt += 1

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        resp = self.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        self._client.close()
