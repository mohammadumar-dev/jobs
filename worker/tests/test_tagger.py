from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from jobsworker.config import Settings
from jobsworker.tagger import (
    AnthropicTagger,
    HeuristicTagger,
    Tagged,
    build_user_message,
    cost_usd,
    load_pricing,
    output_schema,
    validate_tag,
)

GOOD = {
    "role_category": "software", "role_title_clean": "Software Engineer Intern",
    "city": "Bengaluru", "state": "wrong state", "work_mode": "hybrid",
    "job_type": "internship", "experience_min": 0, "experience_max": 0, "is_fresher": True,
}
JOB = {
    "id": "11111111-1111-1111-1111-111111111111", "title": "SWE Intern (2026)",
    "company": "Acme", "location_raw": "Bangalore", "description_text": "Hybrid. Freshers.",
}


def message(payload, stop="end_turn", tin=900, tout=60):
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return SimpleNamespace(
        stop_reason=stop,
        content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=tin, output_tokens=tout),
    )


class FakeBatches:
    def __init__(self, results):
        self._results = results
        self.created = None

    def create(self, requests):
        self.created = requests
        return SimpleNamespace(id="batch_1", processing_status="ended")

    def retrieve(self, batch_id):
        return SimpleNamespace(id=batch_id, processing_status="ended")

    def results(self, batch_id):
        return iter(self._results)


class FakeClient:
    def __init__(self, replies, batch_results=()):
        self._replies = list(replies)
        self.calls = []
        self.messages = SimpleNamespace(create=self._create, batches=FakeBatches(batch_results))

    def _create(self, **params):
        self.calls.append(params)
        return self._replies.pop(0)


def tagger(taxonomy, client, **overrides):
    settings = Settings(llm_provider="anthropic", llm_api_key="test", **overrides)
    return AnthropicTagger(settings, taxonomy, client=client)


def test_valid_output_is_parsed_and_state_comes_from_taxonomy(taxonomy):
    client = FakeClient([message(GOOD)])
    out = tagger(taxonomy, client).tag_many([JOB])
    assert not out.errors
    tag = out.tagged[0].tag
    assert tag.city == "Bengaluru" and tag.state == "Karnataka"
    assert (out.input_tokens, out.output_tokens) == (900, 60)
    params = client.calls[0]
    assert "temperature" not in params  # rejected by current models
    assert params["output_config"]["format"]["type"] == "json_schema"
    assert params["model"] == "claude-haiku-5-5"


def test_invalid_json_gets_exactly_one_retry(taxonomy):
    client = FakeClient([message("not json"), message(GOOD)])
    out = tagger(taxonomy, client).tag_many([JOB])
    assert len(client.calls) == 2 and len(out.tagged) == 1
    assert out.input_tokens == 1800  # both attempts are billed and logged
    assert "rejected" in client.calls[1]["messages"][0]["content"]


def test_two_bad_outputs_is_an_error_not_a_tag(taxonomy):
    bad = {**GOOD, "city": "Atlantis"}
    client = FakeClient([message(bad), message(bad)])
    out = tagger(taxonomy, client).tag_many([JOB])
    assert out.tagged == [] and len(client.calls) == 2
    assert "Atlantis" in out.errors[0]["error"]


def test_refusal_and_truncation_are_not_parsed(taxonomy):
    client = FakeClient([message(GOOD, stop="refusal"), message(GOOD, stop="max_tokens")])
    out = tagger(taxonomy, client).tag_many([JOB])
    assert out.tagged == [] and "max_tokens" in out.errors[0]["error"]


def test_batch_path_is_used_for_large_sets_and_bad_rows_retry_sequentially(taxonomy):
    jobs = [{**JOB, "id": f"job-{i}"} for i in range(3)]
    results = [
        SimpleNamespace(custom_id="job-0", result=SimpleNamespace(type="succeeded", message=message(GOOD))),
        SimpleNamespace(custom_id="job-1", result=SimpleNamespace(type="succeeded", message=message("oops"))),
        SimpleNamespace(custom_id="job-2", result=SimpleNamespace(type="errored")),
    ]
    client = FakeClient([message(GOOD)], batch_results=results)
    out = tagger(taxonomy, client, llm_batch=True, llm_batch_min=2).tag_many(jobs)
    assert len(client.messages.batches.created) == 3
    assert sorted((t.job_id, t.batched) for t in out.tagged) == [("job-0", True), ("job-1", False)]
    assert out.errors == [{"job_id": "job-2", "error": "batch result errored"}]


def test_schema_enums_match_taxonomy(taxonomy):
    schema = output_schema(taxonomy)
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert "Delhi NCR" in schema["properties"]["city"]["enum"]
    assert "Remote" in schema["properties"]["city"]["enum"]


def test_validate_rejects_bad_ranges(taxonomy):
    with pytest.raises(ValueError):
        validate_tag({**GOOD, "experience_min": 3, "experience_max": 1}, taxonomy)
    with pytest.raises(ValueError):
        validate_tag({**GOOD, "work_mode": "office"}, taxonomy)


def test_description_is_shortened(taxonomy):
    text = build_user_message({**JOB, "description_text": "x" * 20000})
    assert "[description shortened]" in text and len(text) < 4500


def test_long_description_keeps_signals_and_drops_boilerplate():
    from jobsworker.tagger import MAX_DESC_CHARS, focus_description

    filler = [f"We build great things, part {i}. " * 12 for i in range(20)]
    desc = "\n\n".join(
        ["You will join the payments team as a backend engineer."]
        + filler
        + ["We are an equal opportunity employer and value diversity. " * 3,
           "Requirements: 0-1 years of experience, B.Tech 2026 batch. Hybrid, Pune office."]
    )
    out = focus_description(desc)
    assert len(out) <= MAX_DESC_CHARS + 40
    assert out.startswith("You will join the payments team")
    assert "0-1 years of experience" in out  # was cut off by head-truncation before
    assert "equal opportunity" not in out


def test_one_block_description_keeps_the_experience_sentence():
    """HTML-stripped descriptions often have no paragraph breaks at all."""
    from jobsworker.tagger import MAX_DESC_CHARS, focus_description

    blob = "You will build payment APIs. " + "Our culture values ownership and speed. " * 200
    blob += "Candidates need 0-1 years of experience and a B.Tech degree."
    out = focus_description(blob)
    assert len(out) <= MAX_DESC_CHARS + 40
    assert out.startswith("You will build payment APIs.")
    assert "0-1 years of experience" in out


def test_guards_fix_contradictions(taxonomy):
    from jobsworker.tagger import apply_guards

    tag = validate_tag({**GOOD, "job_type": "full_time", "is_fresher": False}, taxonomy)
    fixes = apply_guards(tag, {"title": "Data Analyst Intern"})
    assert tag.job_type == "internship" and tag.is_fresher is True and len(fixes) == 2

    tag = validate_tag({**GOOD, "job_type": "full_time", "is_fresher": True}, taxonomy)
    assert apply_guards(tag, {"title": "Senior Backend Engineer"}) and tag.is_fresher is False

    tag = validate_tag({**GOOD, "job_type": "full_time", "is_fresher": True,
                        "experience_min": 3, "experience_max": None}, taxonomy)
    assert apply_guards(tag, {"title": "Backend Engineer"}) and tag.is_fresher is False

    tag = validate_tag({**GOOD, "job_type": "full_time", "is_fresher": True}, taxonomy)
    assert apply_guards(tag, {"title": "Graduate Engineer"}) == []

    # a Graduate Engineer Trainee is a full-time job in India: type kept, fresher forced
    tag = validate_tag({**GOOD, "job_type": "full_time", "is_fresher": False}, taxonomy)
    assert apply_guards(tag, {"title": "Graduate Engineer Trainee - Design"}) == ["is_fresher false->true"]
    assert tag.job_type == "full_time" and tag.is_fresher is True


def test_guards_graduate_trainee_is_full_time(taxonomy):
    from jobsworker.tagger import apply_guards

    for title in ["Graduate Trainee- Security", "Mechancial Engineer_Graduate Engineering Trainee",
                  "2027 IT Graduate Talent Trainee"]:
        tag = validate_tag({**GOOD, "job_type": "internship", "is_fresher": True}, taxonomy)
        assert apply_guards(tag, {"title": title}) == ["job_type internship->full_time (graduate trainee)"]
        assert tag.job_type == "full_time" and tag.is_fresher is True
    # an actual graduate internship stays an internship
    tag = validate_tag({**GOOD, "job_type": "internship", "is_fresher": True}, taxonomy)
    assert apply_guards(tag, {"title": "Graduate Intern - Finance"}) == []
    assert tag.job_type == "internship"


def test_guards_min_one_year_is_fresher(taxonomy):
    from jobsworker.tagger import apply_guards

    tag = validate_tag({**GOOD, "job_type": "full_time", "is_fresher": False,
                        "experience_min": 1, "experience_max": None}, taxonomy)
    assert apply_guards(tag, {"title": "Laundry Associate"}) == ["is_fresher false->true (min 1 years)"]
    assert tag.is_fresher is True
    # a senior title still wins, and an unstated minimum is left to the model
    tag = validate_tag({**GOOD, "job_type": "full_time", "is_fresher": False,
                        "experience_min": 1, "experience_max": None}, taxonomy)
    assert apply_guards(tag, {"title": "Senior Chef"}) == []
    tag = validate_tag({**GOOD, "job_type": "full_time", "is_fresher": False,
                        "experience_min": None, "experience_max": None}, taxonomy)
    assert apply_guards(tag, {"title": "Associate, Marketing Technology"}) == []


def test_cost_uses_batch_discount(settings):
    pricing = load_pricing(settings.pricing_path)
    tag = validate_tag(GOOD, __import__("jobsworker.taxonomy", fromlist=["x"]).load_taxonomy(settings.taxonomy_path))
    rows = [Tagged("a", tag, 1_000_000, 100_000, batched=False),
            Tagged("b", tag, 1_000_000, 100_000, batched=True)]
    # haiku 5.5: $0.10 in + $0.50 out per MTok -> 0.15 full price, 0.075 batched
    assert cost_usd(pricing, "claude-haiku-5-5", rows) == pytest.approx(0.225)
    assert cost_usd(pricing, "unknown-model", rows) == 0.0


def test_heuristic_tagger(taxonomy):
    out = HeuristicTagger(taxonomy).tag_many([JOB])
    tag = out.tagged[0].tag
    assert (tag.role_category, tag.city, tag.work_mode, tag.job_type, tag.is_fresher) == (
        "software", "Bengaluru", "hybrid", "internship", True,
    )
    assert tag.role_title_clean == "SWE Intern"
