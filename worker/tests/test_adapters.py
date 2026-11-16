"""Adapter tests on saved provider responses.

greenhouse.json, lever.json, ashby.json and smartrecruiters_*.json are real
responses captured from the public APIs on 2026-11-17 (trimmed to a few
postings). adzuna.json is hand-written from Adzuna's documented response shape,
because capturing a real one needs an API key.
"""
from __future__ import annotations

import httpx
import pytest
from conftest import fixture

from jobsworker.adapters import ADAPTERS
from jobsworker.filters import passes
from jobsworker.http import PoliteClient
from jobsworker.models import Source
from jobsworker.normalize import finalize
from jobsworker.pipeline import collect


def client(handler) -> PoliteClient:
    return PoliteClient("test-agent (+https://example.org)", 0.0, transport=httpx.MockTransport(handler))


def run(type_, config, handler, settings):
    source = Source(id=1, key=f"{type_}:test", type=type_, config=config)
    adapter = ADAPTERS[type_](client(handler), settings)
    raws = adapter.fetch(source)
    return source, adapter, raws, [adapter.normalize(source, r) for r in raws]


def check_common(jobs):
    assert jobs and all(j is not None for j in jobs)
    for job in jobs:
        assert job.title and job.company
        assert job.apply_url.startswith("https://")
        assert "<" not in job.description_text  # HTML was converted to text
        assert job.posted_at is not None and job.posted_at.tzinfo is not None


def test_greenhouse(settings, taxonomy):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["ua"] = request.headers["user-agent"]
        return httpx.Response(200, json=fixture("greenhouse.json"))

    _, _, raws, jobs = run("greenhouse", {"token": "sigmoid", "company": "Sigmoid"}, handler, settings)
    assert seen["url"] == "https://boards-api.greenhouse.io/v1/boards/sigmoid/jobs?content=true"
    assert "+https://example.org" in seen["ua"]  # identifies itself with a contact URL
    check_common(jobs)
    assert len(jobs) == 3
    trainee = jobs[0]
    assert trainee.title == "Industrial Trainee - Finance & Accounting"
    assert trainee.company == "Sigmoid"
    assert len(trainee.description_text) > 200
    assert [passes(finalize(j, taxonomy), taxonomy) for j in jobs] == [True, False, False]


def test_lever_falls_back_to_eu_host(settings, taxonomy):
    hosts = []

    def handler(request: httpx.Request) -> httpx.Response:
        hosts.append(request.url.host)
        if request.url.host == "api.lever.co":
            return httpx.Response(404, json={"ok": False})
        return httpx.Response(200, json=fixture("lever.json"))

    _, _, _, jobs = run("lever", {"site": "fampay", "company": "FamPay"}, handler, settings)
    assert hosts == ["api.lever.co", "api.eu.lever.co"]
    check_common(jobs)
    assert jobs[0].title == "People Operations Intern"
    assert jobs[0].apply_url.startswith("https://jobs.lever.co/fampay/")
    assert [passes(finalize(j, taxonomy), taxonomy) for j in jobs] == [True, True, False]


def test_ashby(settings, taxonomy):
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://api.ashbyhq.com/posting-api/job-board/composio"
        return httpx.Response(200, json=fixture("ashby.json"))

    _, _, _, jobs = run("ashby", {"name": "composio", "company": "Composio"}, handler, settings)
    check_common(jobs)
    intern = finalize(jobs[0], taxonomy)
    assert "Intern" in intern.title and intern.company == "Composio"
    assert passes(intern, taxonomy)
    assert taxonomy.mentions_india(intern.location_raw)


def test_smartrecruiters_skips_senior_postings_before_spending_detail_requests(settings):
    listing = fixture("smartrecruiters_list.json")
    detail_calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/postings"):
            assert request.url.params["country"] == "in"
            return httpx.Response(200, json=listing)
        detail_calls.append(request.url.path)
        return httpx.Response(200, json=fixture(f"smartrecruiters_detail_{request.url.path.split('/')[-1]}.json"))

    _, _, raws, _ = run("smartrecruiters", {"company_id": "Endava", "company": "Endava"}, handler, settings)
    # both real postings are senior ("Lead", "Senior"): no detail request is made for them
    assert raws == [] and detail_calls == []


def test_smartrecruiters_detail_is_normalized(settings, taxonomy):
    listing = fixture("smartrecruiters_list.json")
    posting_id = listing["content"][0]["id"]
    listing["content"] = [{**listing["content"][0], "name": "Graduate Engineer Trainee", "experienceLevel": {"id": "entry_level"}}]
    detail = fixture(f"smartrecruiters_detail_{posting_id}.json")
    detail["name"] = "Graduate Engineer Trainee"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=listing if request.url.path.endswith("/postings") else detail)

    _, _, raws, jobs = run("smartrecruiters", {"company_id": "Endava", "company": "Endava", "max_details": 5}, handler, settings)
    assert len(raws) == 1
    check_common(jobs)
    job = finalize(jobs[0], taxonomy)
    assert job.country_code == "IN" and "india" in job.location_raw.lower()
    assert len(job.description_text) > 200


def test_adzuna_uses_redirect_url_and_strips_markup(settings, taxonomy):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url)
        assert request.url.path.startswith("/v1/api/jobs/in/search/")
        assert request.url.params["app_id"] == "test-id"
        return httpx.Response(200, json=fixture("adzuna.json"))

    config = {"queries": ["fresher", "intern"], "max_pages": 3}
    source, _, raws, jobs = run("adzuna", config, handler, settings)
    assert len(calls) == 2  # one short page per query, then stop paging
    assert len(raws) == 2  # the same ad returned by two queries is kept once
    check_common(jobs)
    assert jobs[0].title == "Graduate Trainee Engineer"
    assert jobs[0].apply_url.startswith("https://www.adzuna.in/land/ad/")  # Adzuna's own redirect link
    assert jobs[0].country_code == "IN"
    fetched, kept = collect(source, client(handler), settings, taxonomy)
    assert fetched == 2 and [j.title for j in kept] == ["Graduate Trainee Engineer"]


def test_adzuna_without_keys_fails_loudly(settings):
    from dataclasses import replace

    with pytest.raises(RuntimeError, match="ADZUNA"):
        run("adzuna", {}, lambda r: httpx.Response(200, json={}), replace(settings, adzuna_app_id=""))


def test_posting_without_a_usable_apply_url_is_dropped(settings):
    payload = {"jobs": [{"id": 1, "title": "Intern", "absolute_url": "javascript:alert(1)", "location": {"name": "Pune"}}]}
    _, _, _, jobs = run("greenhouse", {"token": "x"}, lambda r: httpx.Response(200, json=payload), settings)
    assert jobs == [None]


# ---- polite HTTP client ------------------------------------------------------

def test_http_waits_one_second_between_requests_to_the_same_host():
    now = [0.0]
    slept = []

    def sleep(seconds):
        slept.append(seconds)
        now[0] += seconds

    http = PoliteClient(
        "ua", 1.0, transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})),
        sleep=sleep, clock=lambda: now[0],
    )
    http.get("https://a.example/1")
    http.get("https://a.example/2")
    http.get("https://b.example/1")  # different host: no wait
    assert slept == [1.0]


def test_http_retries_429_and_5xx_with_backoff_then_gives_up():
    statuses = iter([429, 503, 200])
    slept = []
    http = PoliteClient(
        "ua", 0.0, transport=httpx.MockTransport(lambda r: httpx.Response(next(statuses), json={})),
        sleep=slept.append,
    )
    assert http.get("https://a.example/").status_code == 200
    assert slept == [2.0, 4.0]

    always = PoliteClient(
        "ua", 0.0, max_retries=2,
        transport=httpx.MockTransport(lambda r: httpx.Response(500)), sleep=lambda s: None,
    )
    with pytest.raises(httpx.HTTPStatusError):
        always.get_json("https://a.example/")
