# LLM cost and tagging accuracy

**Status: not measured yet.** No LLM API key has been configured, so every tag
currently in the database was produced by the rule-based fallback
(`model = heuristic-v1`), which costs nothing and is not what this page is about.

**Provider.** Tagging runs on free tiers (Gemini, then Groq, then the OpenRouter
free router; see `worker/src/jobsworker/llm_free.py`), because paying for the
Claude API needs an international card. Free-tier calls cost $0, so the USD column
will read 0 for them; token counts are still stored per row in `job_tags`, so the
cost of the same volume on a paid model can be worked out from `worker/pricing.yaml`.
The `model` column records which provider tagged each row, and accuracy should be
reported per model.
The numbers below are filled in from script output only; nothing here is estimated
from memory.

## How to produce the numbers

1. Put at least one of `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY` in
   `worker/.env`, then tag:

       cd worker
       uv run jobsworker tag

   An LLM tagger also re-tags rows that only have a rule-based tag, up to
   `LLM_MAX_JOBS` (default 300) per run. Repeat on later days until
   `select model, count(*) from job_tags group by 1` shows no `heuristic-v1` rows.

2. Export the blind labelling sheet (50 jobs, fixed seed):

       uv run python ../eval/sample.py

   Fill in the five label columns of `eval/out/labels.csv` **without opening**
   `eval/out/model_tags.csv`.

3. Score and cost:

       uv run python ../eval/score.py     # per-field accuracy, mismatches
       uv run python ../eval/cost.py      # USD and INR per 1,000 posts, hash-skip saving

4. Copy the results into the tables below and into `client/lib/eval-results.ts`
   (the /about page reads that file).

## Accuracy (50 human-labelled posts)

Measured 2026-11-21 on prompt v2: 50 random jobs (seed 20261116), 26 tagged by
Gemini 3.5 Flash-Lite and 24 by Groq gpt-oss-120b. Labelled blind by a person.

| Field              | Exact match | Fits the rules |
| ------------------ | ----------- | -------------- |
| role_category      | 66%         | 92%            |
| city               | 96%         | 98%            |
| work_mode          | 96%         | 98%            |
| job_type           | 88%         | 88%            |
| is_fresher         | 92%         | 94%            |
| **all five right** | 48%         | **74%**        |

"Exact match" is `eval/score.py` as is. "Fits the rules" comes from reviewing each
of the 33 mismatches against the prompt's rules: when both answers fit (mostly hotel
jobs, which have no category of their own, as `other`, `support` or `operations`),
the model's answer counts as correct. That review was done after seeing the model's
answers; every verdict and its reason is in `eval/out/adjudication.csv`.

15 tags in 13 jobs were clearly wrong. The two biggest groups are fixed in prompt v3:
"Graduate Trainee" jobs tagged as internships (6) and jobs asking for 0-1 years
marked as not for freshers (3), both now also enforced in `apply_guards`. v3 only
applies to newly tagged jobs, so re-measure on a fresh sample once enough exist.

## Cost per 1,000 posts

The About page shows this live from `GET /api/meta/tagging`: actual spend (free
tiers, $0) and the paid equivalent, i.e. the stored token counts of every tagged job
priced at `app.pricing.*` in `jobs/src/main/resources/application.properties`
(Claude Haiku 5.5 list price; keep it in step with `worker/pricing.yaml`). Rows tagged
by the rule-based fallback have no tokens and are left out of the average.

First measurement, 2026-11-19, local run: 132 jobs, all Gemini; on average 1,029
input and 96 output tokens per job; paid equivalent $0.151 (about ₹13.29) per 1,000
jobs.

| Model | Avg input tokens | Avg output tokens | USD / 1,000 | INR / 1,000 | With Batch API |
| ----- | ---------------- | ----------------- | ----------- | ----------- | -------------- |
| pending | | | | | |

Saved by the content-hash skip: pending.

## What the cost depends on

- **Prices** are in `worker/pricing.yaml`, copied from the provider's pricing page
  on 2026-11-16 (Claude Haiku 5.5: $0.10 input / $0.50 output per million tokens
  for prompts under 100K tokens). Re-check before publishing.
- **USD to INR** in the same file is a placeholder (88.0). Use the day's rate.
- **Batch API** halves the price; the worker uses it automatically for 20 or more
  jobs in a run. `cost.py` reports both prices.
- **Focused description (prompt v2):** at most 4,000 characters (~1,000 tokens)
  per job. EEO, benefits and privacy paragraphs are dropped first; if it is still
  too long, the opening paragraph and the paragraphs that mention experience,
  eligibility, location, work mode or job type are kept before the rest. On the
  146 jobs of the first local run this sent 8% less text and lost no experience line
  (plain head-truncation at 6,000 characters was used before).
- **Hash skip:** a job is only sent to the model when it is new or its
  title/company/description hash changed. Duplicates are never tagged, and when a
  duplicate becomes the canonical row it reuses the identical posting's LLM tag
  instead of a new call.
- **Every token counts.** Tokens of failed attempts (invalid output, then the next
  provider) are added to the job's row, and re-tagging a job adds to its tokens
  instead of replacing them, so the paid equivalent is what a paid API would have
  billed. Each run logs its tokens and paid equivalent at the end of tagging.
- **Guards:** after validation, answers that contradict the title are corrected
  ("Intern" title is an internship open to freshers; "Senior"/"Lead"/"Manager", or a
  stated minimum of 2+ years, is not for freshers). The run log lists each fix.
- **Output tokens include thinking.** The default model thinks briefly before
  answering (effort is set to low); those tokens are billed as output and are
  included in `job_tags.output_tokens`.

## Deviation from the plan: no `temperature=0`

The plan asked for temperature 0. Current Claude models reject non-default sampling
parameters, so the request does not send one. Consistency comes from the
enum-constrained JSON schema (`output_config.format`) plus pydantic validation and
one retry.
