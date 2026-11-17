"""Free-tier LLM tagging with a provider fallback chain.

Order (configurable with LLM_CHAIN): Gemini -> Groq -> OpenRouter free router ->
rule-based tagger. Only providers with a key are used.

Per job:
  * a provider gets one call plus exactly one retry when its output fails validation;
  * rate limits, quota, auth and repeated server errors take a provider out for the
    rest of the run, and the job moves to the next provider;
  * if every provider fails, the job gets a rule-based tag (model "heuristic-v1").
    Those rows are re-queued on later runs (db.jobs_needing_tags upgrade=True), so
    they are replaced by an LLM tag once quota is available again.

Every provider is called with plain HTTP (httpx) using its documented REST API; no
extra SDKs. Free tiers cost $0, so cost is recorded as 0 for these models.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import ValidationError

from .config import Settings
from .tagger import (
    MAX_OUTPUT_TOKENS,
    SYSTEM_PROMPT,
    HeuristicTagger,
    Tagged,
    TagOutcome,
    TagResult,
    build_user_message,
    output_schema,
    validate_tag,
)
from .taxonomy import Taxonomy

log = logging.getLogger(__name__)

MAX_WAIT_S = 60  # longest Retry-After we sit out before moving to the next provider
MAX_SERVER_FAILURES = 3  # consecutive 5xx/connection/400 errors before a provider is dropped


class ProviderError(Exception):
    """kind: rate_limit | auth | server | bad_request"""

    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind


@dataclass
class Completion:
    text: str
    input_tokens: int
    output_tokens: int
    truncated: bool = False


def portable_schema(taxonomy: Taxonomy) -> dict[str, Any]:
    """The tag schema with nullable fields as type arrays (["integer", "null"]).

    Both Gemini and Groq strict mode document this form; anyOf support varies.
    """
    schema = output_schema(taxonomy)
    for prop in schema["properties"].values():
        options = prop.pop("anyOf", None)
        if options:
            prop["type"] = [o["type"] for o in options]
    return schema


def _retry_after(response: httpx.Response) -> float | None:
    raw = response.headers.get("retry-after")
    try:
        return float(raw) if raw else None
    except ValueError:
        return None


class _HttpProvider:
    name = ""

    def __init__(self, key: str, model: str, min_interval_s: float, client: httpx.Client) -> None:
        self.key = key
        self.model = model
        self.min_interval_s = min_interval_s
        self.client = client
        self._last = 0.0

    @property
    def label(self) -> str:
        return f"{self.name}/{self.model}"

    def _pace(self) -> None:
        wait = self._last + self.min_interval_s - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()

    def _post(self, url: str, headers: dict[str, str], body: dict[str, Any]) -> dict[str, Any]:
        """POST with one wait-and-retry on a short rate limit or a server error."""
        for attempt in (1, 2):
            self._pace()
            try:
                r = self.client.post(url, headers=headers, json=body)
            except httpx.HTTPError as exc:
                if attempt == 1:
                    time.sleep(5)
                    continue
                raise ProviderError("server", f"connection: {exc}") from exc
            if r.status_code == 429:
                wait = _retry_after(r)
                if attempt == 1 and wait is not None and wait <= MAX_WAIT_S:
                    log.info("%s rate limited; waiting %.0fs", self.label, wait)
                    time.sleep(wait)
                    continue
                raise ProviderError("rate_limit", f"429: {r.text[:150]}")
            if r.status_code in (401, 403):
                raise ProviderError("auth", f"{r.status_code}: {r.text[:150]}")
            if r.status_code >= 500:
                if attempt == 1:
                    time.sleep(5)
                    continue
                raise ProviderError("server", f"{r.status_code}: {r.text[:150]}")
            if r.status_code >= 400:
                raise ProviderError("bad_request", f"{r.status_code}: {r.text[:200]}")
            return r.json()
        raise ProviderError("server", "retries exhausted")  # pragma: no cover

    def complete(self, system: str, user: str, schema: dict[str, Any]) -> Completion:
        raise NotImplementedError


class GeminiProvider(_HttpProvider):
    """Google AI Studio, REST generateContent with a JSON Schema response."""

    name = "gemini"
    URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(self, *args: Any, thinking_level: str = "", **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.thinking_level = thinking_level

    def complete(self, system: str, user: str, schema: dict[str, Any]) -> Completion:
        config: dict[str, Any] = {
            "responseMimeType": "application/json",
            "responseJsonSchema": schema,
            "maxOutputTokens": MAX_OUTPUT_TOKENS,  # includes thinking tokens
        }
        if self.thinking_level:
            config["thinkingConfig"] = {"thinkingLevel": self.thinking_level}
        data = self._post(
            self.URL.format(model=self.model),
            {"x-goog-api-key": self.key},
            {
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": config,
            },
        )
        usage = data.get("usageMetadata") or {}
        candidates = data.get("candidates") or []
        if not candidates:
            reason = (data.get("promptFeedback") or {}).get("blockReason", "no candidates")
            raise ValueError(f"gemini returned no answer ({reason})")
        cand = candidates[0]
        parts = (cand.get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        return Completion(
            text=text,
            input_tokens=int(usage.get("promptTokenCount") or 0),
            output_tokens=int(usage.get("candidatesTokenCount") or 0)
            + int(usage.get("thoughtsTokenCount") or 0),
            truncated=cand.get("finishReason") == "MAX_TOKENS",
        )


class ChatCompletionsProvider(_HttpProvider):
    """Groq and OpenRouter: Chat Completions with response_format json_schema."""

    def __init__(
        self, *args: Any, name: str, url: str, extra: dict[str, Any] | None = None, **kwargs: Any
    ) -> None:
        super().__init__(*args, **kwargs)
        self.name = name
        self.url = url
        self.extra = extra or {}

    def complete(self, system: str, user: str, schema: dict[str, Any]) -> Completion:
        data = self._post(
            self.url,
            {"Authorization": f"Bearer {self.key}"},
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {"name": "job_tags", "strict": True, "schema": schema},
                },
                "max_tokens": MAX_OUTPUT_TOKENS,
                **self.extra,
            },
        )
        choices = data.get("choices") or []
        if not choices:
            raise ValueError(f"{self.name} returned no choices")
        usage = data.get("usage") or {}
        return Completion(
            text=(choices[0].get("message") or {}).get("content") or "",
            input_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
            truncated=choices[0].get("finish_reason") == "length",
        )


def _parse(text: str, truncated: bool, taxonomy: Taxonomy) -> TagResult:
    if truncated:
        raise ValueError("output truncated")
    text = text.strip()
    if text.startswith("```"):  # some free models wrap JSON in a fence anyway
        text = text.strip("`").removeprefix("json").strip()
    return validate_tag(json.loads(text), taxonomy)


class ChainTagger:
    """Tries each free provider in order, then the rule-based tagger."""

    model = "free-chain"

    def __init__(
        self, providers: list[_HttpProvider], taxonomy: Taxonomy, *, fallback: bool = True
    ) -> None:
        self.providers = providers
        self.taxonomy = taxonomy
        self.fallback = HeuristicTagger(taxonomy) if fallback else None
        self.schema = portable_schema(taxonomy)
        self.disabled: dict[str, str] = {}  # label -> reason
        self._failures: dict[str, int] = {}
        if providers:
            self.model = providers[0].label

    def _try(self, p: _HttpProvider, job: dict[str, Any]) -> Tagged:
        """One call plus exactly one retry on invalid output. Raises on failure."""
        user = build_user_message(job)
        tin = tout = 0
        err = ""
        for attempt in (1, 2):
            note = (
                ""
                if attempt == 1
                else f"\n\nYour previous answer was rejected ({err}). "
                "Return only the JSON object, using allowed values."
            )
            c = p.complete(SYSTEM_PROMPT, user + note, self.schema)
            tin += c.input_tokens
            tout += c.output_tokens
            try:
                tag = _parse(c.text, c.truncated, self.taxonomy)
                return Tagged(job["id"], tag, tin, tout, model=p.label)
            except (ValueError, ValidationError) as exc:  # JSONDecodeError is a ValueError
                err = str(exc)[:200]
        raise ValueError(f"invalid output after retry: {err}")

    def _drop(self, p: _HttpProvider, reason: str) -> None:
        if p.label not in self.disabled:
            log.warning("dropping %s for this run: %s", p.label, reason)
            self.disabled[p.label] = reason

    def tag_one(self, job: dict[str, Any]) -> tuple[Tagged | None, list[str]]:
        problems: list[str] = []
        for p in self.providers:
            if p.label in self.disabled:
                continue
            try:
                tagged = self._try(p, job)
                self._failures[p.label] = 0
                return tagged, problems
            except ProviderError as exc:
                problems.append(f"{p.label}: {exc.kind}: {exc}"[:200])
                if exc.kind in ("rate_limit", "auth"):
                    self._drop(p, f"{exc.kind}: {exc}"[:200])
                else:
                    self._failures[p.label] = self._failures.get(p.label, 0) + 1
                    if self._failures[p.label] >= MAX_SERVER_FAILURES:
                        self._drop(p, f"{MAX_SERVER_FAILURES} errors in a row: {exc}"[:200])
            except (ValueError, ValidationError) as exc:
                problems.append(f"{p.label}: {exc}"[:200])
        if self.fallback:
            return Tagged(job["id"], self.fallback.tag_one(job), 0, 0, model=HeuristicTagger.model), problems
        return None, problems

    def tag_many(self, jobs: list[dict[str, Any]]) -> TagOutcome:
        out = TagOutcome(model=self.model)
        for job in jobs:
            try:
                tagged, problems = self.tag_one(job)
            except (ValueError, ValidationError) as exc:  # the rule-based tagger itself failed
                out.errors.append({"job_id": str(job["id"]), "error": str(exc)[:200]})
                continue
            if tagged:
                out.tagged.append(tagged)
            if problems and (tagged is None or tagged.model == HeuristicTagger.model):
                out.errors.append({"job_id": str(job["id"]), "error": "; ".join(problems)[:300]})
        for label, reason in self.disabled.items():
            out.errors.append({"stage": "tag", "provider": label, "error": reason})
        used: dict[str, int] = {}
        for t in out.tagged:
            used[t.model] = used.get(t.model, 0) + 1
        log.info("tags by model: %s", used)
        return out


def build_providers(settings: Settings, client: httpx.Client) -> list[_HttpProvider]:
    available: dict[str, _HttpProvider] = {}
    if settings.gemini_api_key:
        available["gemini"] = GeminiProvider(
            settings.gemini_api_key, settings.gemini_model, settings.gemini_interval_s, client,
            thinking_level=settings.gemini_thinking_level,
        )
    if settings.groq_api_key:
        extra = {"reasoning_effort": settings.groq_reasoning_effort} if settings.groq_reasoning_effort else {}
        available["groq"] = ChatCompletionsProvider(
            settings.groq_api_key, settings.groq_model, settings.groq_interval_s, client,
            name="groq", url="https://api.groq.com/openai/v1/chat/completions", extra=extra,
        )
    if settings.openrouter_api_key:
        available["openrouter"] = ChatCompletionsProvider(
            settings.openrouter_api_key, settings.openrouter_model, settings.openrouter_interval_s,
            client, name="openrouter", url="https://openrouter.ai/api/v1/chat/completions",
            # route only to endpoints that honour response_format
            extra={"provider": {"require_parameters": True}},
        )
    return [available[name] for name in settings.llm_chain if name in available]


def make_chain_tagger(settings: Settings, taxonomy: Taxonomy) -> ChainTagger:
    client = httpx.Client(timeout=httpx.Timeout(90.0, connect=10.0))
    providers = build_providers(settings, client)
    if not providers:
        log.warning("LLM_PROVIDER=chain but no GEMINI/GROQ/OPENROUTER key is set")
    log.info("tagger chain: %s -> heuristic-v1", " -> ".join(p.label for p in providers) or "(none)")
    return ChainTagger(providers, taxonomy)
