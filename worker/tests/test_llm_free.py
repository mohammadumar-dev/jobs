"""Free-tier fallback chain: Gemini -> Groq -> OpenRouter -> rule-based tagger.

HTTP is faked with httpx.MockTransport; no network.
"""
from __future__ import annotations

import json
from dataclasses import replace

import httpx
import pytest

from jobsworker import llm_free
from jobsworker.llm_free import ChainTagger, build_providers, portable_schema
from jobsworker.tagger import cost_usd, load_pricing, make_tagger

JOB = {
    "id": "job-1",
    "title": "Software Engineer Intern",
    "company": "Acme",
    "location_raw": "Bangalore, India",
    "description_text": "Internship for students. Python.",
}

GOOD = {
    "role_category": "software",
    "role_title_clean": "Software Engineer Intern",
    "city": "Bengaluru",
    "state": None,
    "work_mode": "onsite",
    "job_type": "internship",
    "experience_min": 0,
    "experience_max": 0,
    "is_fresher": True,
}


def gemini_reply(payload, finish="STOP"):
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return httpx.Response(
        200,
        json={
            "candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": finish}],
            "usageMetadata": {"promptTokenCount": 800, "candidatesTokenCount": 50,
                              "thoughtsTokenCount": 10},
        },
    )


def chat_reply(payload, finish="stop"):
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": text}, "finish_reason": finish}],
            "usage": {"prompt_tokens": 700, "completion_tokens": 40},
        },
    )


class Router:
    """Queues responses per host and records requests."""

    def __init__(self, **queues):
        self.queues = {host: list(q) for host, q in queues.items()}
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        key = {"generativelanguage.googleapis.com": "gemini", "api.groq.com": "groq",
               "openrouter.ai": "openrouter"}[request.url.host]
        queue = self.queues.get(key) or []
        if not queue:
            raise AssertionError(f"unexpected call to {key}")
        return queue.pop(0)

    def hosts(self):
        return [r.url.host.split(".")[-2] for r in self.requests]


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(llm_free.time, "sleep", lambda s: None)


def chain(settings, taxonomy, router, **keys):
    keys = {"gemini_api_key": "g", "groq_api_key": "q", "openrouter_api_key": "o", **keys}
    s = replace(settings, gemini_interval_s=0, groq_interval_s=0, openrouter_interval_s=0, **keys)
    client = httpx.Client(transport=httpx.MockTransport(router))
    return ChainTagger(build_providers(s, client), taxonomy)


def test_gemini_success_uses_schema_and_records_model(settings, taxonomy):
    router = Router(gemini=[gemini_reply(GOOD)])
    out = chain(settings, taxonomy, router).tag_many([JOB])
    assert out.errors == []
    [t] = out.tagged
    assert t.model == "gemini/gemini-3.5-flash-lite"
    assert t.tag.state == "Karnataka"  # derived from the taxonomy
    assert (t.input_tokens, t.output_tokens) == (800, 60)
    req = router.requests[0]
    assert req.headers["x-goog-api-key"] == "g"
    body = json.loads(req.content)
    cfg = body["generationConfig"]
    assert cfg["responseMimeType"] == "application/json"
    assert cfg["responseJsonSchema"]["properties"]["experience_min"]["type"] == ["integer", "null"]
    assert "systemInstruction" in body


def test_invalid_output_gets_one_retry_on_same_provider(settings, taxonomy):
    router = Router(gemini=[gemini_reply("not json"), gemini_reply(GOOD)])
    out = chain(settings, taxonomy, router).tag_many([JOB])
    assert [t.model for t in out.tagged] == ["gemini/gemini-3.5-flash-lite"]
    assert out.tagged[0].input_tokens == 1600  # both calls counted
    retry_body = json.loads(router.requests[1].content)
    assert "previous answer was rejected" in retry_body["contents"][0]["parts"][0]["text"]


def test_rate_limit_falls_through_to_groq_and_drops_gemini(settings, taxonomy):
    router = Router(
        gemini=[httpx.Response(429, text="quota exceeded")],
        groq=[chat_reply(GOOD), chat_reply(GOOD)],
    )
    tagger = chain(settings, taxonomy, router)
    out = tagger.tag_many([JOB, {**JOB, "id": "job-2"}])
    assert [t.model for t in out.tagged] == ["groq/openai/gpt-oss-120b"] * 2
    assert router.hosts() == ["googleapis", "groq", "groq"]  # gemini not retried for job 2
    assert "gemini/gemini-3.5-flash-lite" in tagger.disabled
    groq_body = json.loads(router.requests[1].content)
    assert groq_body["response_format"]["json_schema"]["strict"] is True
    assert router.requests[1].headers["authorization"] == "Bearer q"


def test_short_retry_after_is_waited_out(settings, taxonomy):
    router = Router(gemini=[httpx.Response(429, headers={"retry-after": "3"}), gemini_reply(GOOD)])
    out = chain(settings, taxonomy, router).tag_many([JOB])
    assert out.tagged[0].model.startswith("gemini/")


def test_everything_fails_falls_back_to_rules(settings, taxonomy):
    router = Router(
        gemini=[httpx.Response(403, text="bad key")],
        groq=[httpx.Response(429)],
        openrouter=[chat_reply("{}"), chat_reply("{}")],  # invalid twice
    )
    out = chain(settings, taxonomy, router).tag_many([JOB])
    [t] = out.tagged
    assert t.model == "heuristic-v1"
    assert t.tag.job_type == "internship"
    job_error = next(e for e in out.errors if e.get("job_id") == "job-1")
    assert "gemini" in job_error["error"] and "openrouter" in job_error["error"]
    assert {e.get("provider") for e in out.errors if e.get("stage") == "tag"} >= {
        "gemini/gemini-3.5-flash-lite", "groq/openai/gpt-oss-120b",
    }


def test_truncated_output_is_not_parsed(settings, taxonomy):
    router = Router(
        gemini=[gemini_reply(GOOD, finish="MAX_TOKENS"), gemini_reply(GOOD, finish="MAX_TOKENS")],
        groq=[chat_reply(GOOD)],
    )
    out = chain(settings, taxonomy, router).tag_many([JOB])
    assert out.tagged[0].model.startswith("groq/")


def test_repeated_server_errors_drop_provider(settings, taxonomy):
    router = Router(
        openrouter=[httpx.Response(500)] * 6,
    )
    tagger = chain(settings, taxonomy, router, gemini_api_key="", groq_api_key="")
    out = tagger.tag_many([{**JOB, "id": f"j{i}"} for i in range(4)])
    assert all(t.model == "heuristic-v1" for t in out.tagged)
    assert len(router.requests) == 6  # 3 jobs x (call + one server retry), then dropped
    assert "openrouter/openrouter/free" in tagger.disabled


def test_only_configured_providers_in_chain_order(settings, taxonomy):
    s = replace(settings, groq_api_key="q", openrouter_api_key="o", llm_chain=("openrouter", "groq"))
    providers = build_providers(s, httpx.Client())
    assert [p.name for p in providers] == ["openrouter", "groq"]


def test_fenced_json_is_accepted(settings, taxonomy):
    router = Router(openrouter=[chat_reply("```json\n" + json.dumps(GOOD) + "\n```")])
    out = chain(settings, taxonomy, router, gemini_api_key="", groq_api_key="").tag_many([JOB])
    assert out.tagged[0].model == "openrouter/openrouter/free"


def test_free_models_cost_nothing(settings, taxonomy):
    router = Router(gemini=[gemini_reply(GOOD)])
    out = chain(settings, taxonomy, router).tag_many([JOB])
    assert cost_usd(load_pricing(settings.pricing_path), "free-chain", out.tagged) == 0.0


def test_portable_schema_has_no_anyof(taxonomy):
    assert "anyOf" not in json.dumps(portable_schema(taxonomy))


def test_make_tagger_selects_chain(settings, taxonomy):
    s = replace(settings, llm_provider="chain", gemini_api_key="g")
    assert isinstance(make_tagger(s, taxonomy), ChainTagger)
