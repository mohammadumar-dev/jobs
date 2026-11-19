# Fresher Jobs India

Collects entry-level jobs and internships in India from official public job APIs,
removes duplicates, tags each job with an LLM, and shows them on a searchable site
that refreshes itself every day.

| Folder | What | Stack |
| ------ | ---- | ----- |
| `worker/` | daily ingest: fetch, filter, dedupe, tag | Python 3.12, httpx, pydantic, psycopg, Anthropic SDK |
| `jobs/` | API: auth, sessions, job search, saved jobs, apply tracking | Java 25, Spring Boot 4.1, Spring Security, Flyway |
| `client/` | website | Next.js 16, TypeScript, Tailwind 4 |
| `eval/` | 50-post accuracy check and cost per 1,000 posts | Python |
| `design/` | design tokens | |
| `docs/` | [architecture](docs/architecture.md), [what broke](docs/what-broke.md), [cost](docs/cost.md) | |

The product name shown on the site ("FirstRung") is a placeholder. Change it in
`client/lib/brand.ts`.

## Run it locally

You need Java 25, Node 24, [uv](https://docs.astral.sh/uv/) and a Postgres database.

1. **Configuration.** Copy each example file and fill it in. These files are
   gitignored; never commit them.

       worker/.env.example  -> worker/.env
       jobs/.env.example    -> jobs/.env
       client/.env.example  -> client/.env.local

   The API wants the database URL in JDBC form
   (`jdbc:postgresql://host/db?sslmode=require`, user and password separate); the
   worker wants the `postgresql://user:password@host/db` form.

2. **API** (creates the schema on first start):

       cd jobs
       SPRING_PROFILES_ACTIVE=dev ./mvnw spring-boot:run

   `dev` allows plain http on localhost. Without it the API insists on https and
   `Secure` cookies.

3. **Ingest:**

       cd worker
       uv sync
       uv run jobsworker seed     # load sources.yaml into the sources table
       uv run jobsworker run      # fetch, filter, dedupe, tag (about 15 minutes)
       uv run jobsworker stats

4. **Web:**

       cd client
       npm install
       npm run dev                # http://localhost:3000

No database handy? `cd worker && uv run python scripts/devdb.py` starts a throwaway
local Postgres without Docker and prints the two URLs. With Docker,
`docker compose up --build` starts Postgres, the API and the web app.

## Tests

    cd worker && uv run pytest              # adapters (saved API responses), pipeline, tagger
    cd jobs   && ./mvnw test                # MockMvc: auth, CSRF, rate limits, filters, open redirect
    cd client && npm run build && npm run test:e2e   # Playwright; needs the API running with jobs in the DB

Worker and API tests start their own embedded Postgres; no setup needed.

## What you still have to provide

- **Adzuna keys** (`ADZUNA_APP_ID`, `ADZUNA_APP_KEY`): the Adzuna source is skipped
  without them, and it is the source that takes the site past 200 jobs.
- **LLM keys** (free, no card): any of `GEMINI_API_KEY` (aistudio.google.com),
  `GROQ_API_KEY` (console.groq.com) and `OPENROUTER_API_KEY` (openrouter.ai). The
  worker tries them in that order and falls back to a rule-based tagger; rows tagged
  by the fallback are re-tagged by an LLM on later runs. `LLM_PROVIDER=anthropic`
  with `LLM_API_KEY` switches to paid Claude tagging instead.
- **Google OAuth client** for "Continue with Google".
- Hosting accounts for the API and the web app, and the GitHub Actions secrets for
  the daily run. Step by step: [docs/deploy.md](docs/deploy.md).
- The 50 human labels for the accuracy check. See [docs/cost.md](docs/cost.md).

## Adding a source

Add a row to `worker/sources.yaml` and run `uv run jobsworker seed`. Check a board
first with `uv run jobsworker probe candidates.yaml`. Only add sources that have an
official API or have given permission.
