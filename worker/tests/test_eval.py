from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCORE = Path(__file__).resolve().parents[2] / "eval" / "score.py"
spec = importlib.util.spec_from_file_location("eval_score", SCORE)
score_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(score_mod)

MODEL = {
    "1": {"role_category": "software", "city": "Bengaluru", "work_mode": "hybrid",
          "job_type": "internship", "is_fresher": "True", "model": "m", "prompt_version": "v1"},
    "2": {"role_category": "data", "city": "Pune", "work_mode": "onsite",
          "job_type": "full_time", "is_fresher": "False", "model": "m", "prompt_version": "v1"},
}


def label(job_id, **over):
    base = {"job_id": job_id, "title": f"Job {job_id}", **{k: MODEL[job_id][k] for k in score_mod.FIELDS}}
    return {**base, **over}


def test_scores_per_field_and_all_fields():
    labels = [label("1", is_fresher="yes", role_category="Software"), label("2", city="Mumbai", is_fresher="no")]
    result = score_mod.score(labels, MODEL)
    assert result["accuracy"] == {"role_category": 100.0, "city": 50.0, "work_mode": 100.0,
                                  "job_type": 100.0, "is_fresher": 100.0}
    assert result["all_fields_correct"] == 50.0
    assert result["mismatches"] == [
        {"job_id": "2", "title": "Job 2", "field": "city", "human": "Mumbai", "model": "Pune"}
    ]


def test_refuses_blank_labels():
    with pytest.raises(SystemExit, match="blank"):
        score_mod.score([label("1", city=" ")], MODEL)
