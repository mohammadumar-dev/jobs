from __future__ import annotations

import pytest

from jobsworker.filters import experience_range, has_fresher_signal, is_india, passes
from jobsworker.models import NormalizedJob
from jobsworker.normalize import content_hash, dedupe_key, html_to_text, norm_company


def job(title="Software Engineer", location="Bengaluru, India", desc="", **kw) -> NormalizedJob:
    return NormalizedJob(
        external_id="1", title=title, company="Acme", location_raw=location,
        description_text=desc, apply_url="https://example.com/a", **kw,
    )


@pytest.mark.parametrize(
    "title,desc,expected",
    [
        ("Software Engineer Intern", "", True),
        ("Senior Intern Programme Manager", "", True),  # intern wins over senior words
        ("Graduate Engineer Trainee", "", True),
        ("Junior Data Analyst", "1-2 years of experience", True),
        ("Junior Data Analyst", "Requires 4+ years of experience", False),
        ("Senior Software Engineer", "freshers welcome", False),
        ("Engineering Manager", "", False),
        ("Associate Product Manager", "", False),  # "manager" is a senior word
        ("Associate Consultant", "0-1 years experience", True),
        ("Associate Consultant", "3-5 years experience", False),
        ("Software Engineer", "Open to freshers and recent graduates.", True),
        ("Software Engineer", "We need 5+ years in Java.", False),
        ("Software Engineer", "Great team, great perks.", False),
        ("Software Engineer II", "0-2 years", False),
        ("Customer Support Executive", "0 - 2 yrs experience", True),
    ],
)
def test_fresher_signal(title, desc, expected):
    assert has_fresher_signal(job(title=title, desc=desc)) is expected


def test_internship_employment_hint_counts():
    assert has_fresher_signal(job(title="Marketing", employment_hint="Intern"))


@pytest.mark.parametrize(
    "location,country,expected",
    [
        ("Bengaluru", None, True),
        ("Gurugram, Haryana", None, True),
        ("Remote - India", None, True),
        ("Indianapolis, Indiana", None, False),
        ("London, UK", None, False),
        ("Remote", None, False),
        ("Remote", "IN", True),
        ("Bangalore", "US", False),  # an explicit country code wins
        ("San Francisco; Hyderabad, India", None, True),
    ],
)
def test_is_india(taxonomy, location, country, expected):
    assert is_india(job(location=location, country_code=country), taxonomy) is expected


def test_passes_needs_both(taxonomy):
    assert passes(job(title="SDE Intern"), taxonomy)
    assert not passes(job(title="SDE Intern", location="Berlin"), taxonomy)
    assert not passes(job(title="Staff Engineer"), taxonomy)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("0-2 years of experience", (0, 2)),
        ("at least 3+ years", (3, None)),
        ("2 to 4 yrs", (2, 4)),
        ("5+ years overall, 1 year in fintech", (1, None)),
        ("founded 30 years ago", (None, None)),
        ("no numbers here", (None, None)),
    ],
)
def test_experience_range(text, expected):
    assert experience_range(text) == expected


def test_html_to_text_handles_escaped_and_lists():
    escaped = "&lt;p&gt;Hello&amp;nbsp;world&lt;/p&gt;&lt;ul&gt;&lt;li&gt;One&lt;/li&gt;&lt;li&gt;Two&lt;/li&gt;&lt;/ul&gt;"
    assert html_to_text(escaped) == "Hello world\n- One\n- Two"
    wrapped = "<ul><li><p>Wrapped</p></li><li>Plain</li></ul><p>After</p>"
    assert html_to_text(wrapped) == "- Wrapped\n- Plain\n\nAfter"
    assert html_to_text("<script>alert(1)</script><p>Safe</p>") == "Safe"
    assert html_to_text(None) == ""


def test_dedupe_key_normalizes_city_and_company(taxonomy):
    a = dedupe_key("Software Engineer - Intern", "Acme Pvt. Ltd.", "Bangalore, Karnataka", taxonomy)
    b = dedupe_key("software engineer intern", "ACME", "Bengaluru, India", taxonomy)
    assert a == b == "software engineer intern|acme|bengaluru"
    assert a != dedupe_key("Software Engineer Intern", "Acme", "Pune", taxonomy)
    assert norm_company("Razorpay Software Private Limited") == "razorpay software"


def test_content_hash_ignores_whitespace_only_changes():
    assert content_hash("A", "B", "x  y\n") == content_hash("A ", "B", "x y")
    assert content_hash("A", "B", "x y") != content_hash("A", "B", "x z")
