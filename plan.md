# PLAN.md — Fresher Jobs India (aggregator)

## 0. Goal
Live web tool that collects 200+ real fresher jobs/internships in India from
permitted public sources, dedupes them, tags each with an LLM, shows them on a
searchable page, and refreshes daily on its own.
Deliverables: working app, repo, video walkthrough, 50-post accuracy check,
LLM cost per 1,000 posts.

## 1. Architecture

  [GitHub Actions cron, daily]
            |
            v
  [Python worker] --fetch--> Adzuna IN, Greenhouse, Lever, Ashby, SmartRecruiters
     normalize -> dedupe -> LLM tag -> upsert
            |
            v
     [PostgreSQL]  <---- schema owned by Flyway (in Spring Boot)
            ^
            |
  [Spring Boot API]  auth, users, jobs read API, saved jobs, apply tracking
            ^
            |  same-origin via Next.js rewrite  /api/* -> Spring Boot
  [Next.js frontend]  landing, job search, login, dashboard

Rules:
- Python is the ONLY writer to job tables. Spring Boot only reads them.
- Spring Boot is the ONLY writer to user tables.
- Browser never calls Spring Boot directly; always through /api on the
  frontend origin (so cookies are first-party).

## 2. Repo layout (monorepo)

  /worker        Python 3.12, httpx, pydantic, psycopg, anthropic SDK
  /api           Java 21, Spring Boot 3, Spring Security, Flyway, JPA
  /web           Next.js (App Router), TypeScript, Tailwind
  /eval          50-post labelling sheet + accuracy script
  /design        reference screenshots + tokens.md
  /docs          architecture.md, what-broke.md, cost.md
  .github/workflows/ingest.yml, ci.yml
  docker-compose.yml   (postgres + api + web for local dev)

## 3. Database (Flyway migrations in /api)

sources(id, key, type, config_json, enabled)
  -- one row per company board or API; adding a source = adding a row

jobs(
  id uuid pk, source_id fk, external_id text,
  title, company, location_raw, description_text, apply_url,
  posted_at, first_seen_at, last_seen_at, is_active bool,
  content_hash text,            -- sha256 of title+company+description
  dedupe_key text,              -- normalized title|company|city
  canonical_job_id uuid null,   -- points to the kept row if duplicate
  UNIQUE(source_id, external_id)
)

job_tags(
  job_id pk fk, role_category, role_title_clean, city, state,
  work_mode,        -- onsite | hybrid | remote
  job_type,         -- internship | full_time | contract
  experience_min, experience_max, is_fresher bool,
  model, prompt_version, input_tokens, output_tokens, tagged_at
)

ingest_runs(id, started_at, finished_at, fetched, new, updated,
            deactivated, tagged, llm_cost_usd, errors_json)

users(id, email unique, password_hash null, name, provider, provider_id,
      email_verified, created_at)
saved_jobs(user_id, job_id, created_at)
apply_clicks(id, user_id null, job_id, clicked_at)

Indexes: jobs(is_active), job_tags(role_category, city, work_mode),
GIN full-text index on title+company+description.

## 4. Python worker

4.1 Adapter interface (one file per source type)
  class SourceAdapter:
      def fetch(self, source) -> list[RawJob]
      def normalize(self, raw) -> NormalizedJob

  Adapters: adzuna.py, greenhouse.py, lever.py, ashby.py, smartrecruiters.py
  Endpoints:
  - Adzuna:   api.adzuna.com/v1/api/jobs/in/search/{page}  (app_id, app_key)
  - Greenhouse: boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true
  - Lever:    api.lever.co/v0/postings/{site}?mode=json  (fallback api.eu.lever.co)
  - Ashby:    api.ashbyhq.com/posting-api/job-board/{name}
  - SmartRecruiters: api.smartrecruiters.com/v1/companies/{id}/postings

4.2 Compliance
  - Official APIs only. No login-walled pages, no CAPTCHA bypass.
  - Identify with a User-Agent containing a contact URL.
  - Rate limit: max 1 req/sec per host, retry with backoff on 429/5xx.
  - Always keep and show the source's own apply URL (Adzuna: redirect_url).
  - Read each provider's API terms before enabling it; note it in docs.

4.3 Pipeline steps
  1. fetch all enabled sources (one failing source must not stop the run)
  2. pre-filter: India location AND entry-level signal in title/description
     (intern, fresher, graduate, trainee, associate, junior, 0-2 years)
  3. normalize -> compute content_hash and dedupe_key
  4. upsert on (source_id, external_id); update last_seen_at
  5. cross-source dedupe: same dedupe_key -> set canonical_job_id on the newer
  6. LLM-tag only rows that are new or whose content_hash changed
  7. deactivate: not seen in 2 consecutive runs -> is_active=false
  8. write ingest_runs row with counts and cost

4.4 LLM tagging
  - Small, cheap model; model name in env (LLM_MODEL). Temperature 0.
  - Structured JSON output validated by pydantic; one retry on invalid JSON.
  - Fixed taxonomy in /worker/taxonomy.yaml:
    role_category: software, data, design, product, marketing, sales,
                   operations, finance, hr, support, content, other
    city: canonical list (Bengaluru, Mumbai, Delhi NCR, Hyderabad, Pune,
          Chennai, Kolkata, Ahmedabad, ... , Remote, Other)
  - Truncate description to ~1,500 tokens. Log tokens per call.
  - Use the Batch API if available for the provider (cheaper), else sequential.
  - Store prompt_version with every tag.

4.5 Schedule
  .github/workflows/ingest.yml: cron daily 02:30 IST + manual dispatch.
  Secrets: DATABASE_URL, ADZUNA_APP_ID, ADZUNA_APP_KEY, LLM_API_KEY.

## 5. Spring Boot API

5.1 Endpoints
  POST /api/auth/register        email + password
  POST /api/auth/login
  POST /api/auth/logout
  GET  /oauth2/authorization/google   (OAuth2 login)
  GET  /api/me
  GET  /api/jobs?q=&role=&city=&mode=&type=&exp=&page=   (public)
  GET  /api/jobs/{id}                                     (public)
  GET  /api/meta                 filter options + active count + last refresh
  POST /api/jobs/{id}/save       (auth)   DELETE to unsave
  GET  /api/me/saved             (auth)
  POST /api/jobs/{id}/apply      records click, returns apply_url (redirect)
  GET  /api/me/applied           (auth)

5.2 Apply flow
  Applying on the candidate's behalf is NOT possible: ATS apply endpoints need
  each employer's private API key. So: record apply_clicks row, open the
  source apply_url in a new tab (rel="noopener noreferrer"), show the job
  under "Applied" in the dashboard.

5.3 Security requirements
  - Auth: server-side session (Spring Session JDBC), NOT JWT in localStorage.
  - Session cookie: HttpOnly, Secure, SameSite=Lax, __Host- prefix, 7-day
    idle timeout, rotate session id on login.
  - OAuth2: Google via spring-security-oauth2-client, authorization code
    flow + PKCE, validate state. Link to existing user by verified email.
  - Passwords: Argon2id (or BCrypt cost 12), min 10 chars, breached-password
    check optional.
  - CSRF: enabled, cookie-to-header token (XSRF-TOKEN -> X-XSRF-TOKEN).
  - HTTPS only: HSTS, redirect http->https, trust proxy headers.
  - Headers: CSP (no inline scripts), X-Content-Type-Options, frame-ancestors
    'none', Referrer-Policy strict-origin-when-cross-origin.
  - CORS: disabled (same-origin through the Next.js rewrite).
  - Rate limiting (Bucket4j): login/register 5/min per IP, search 60/min.
  - Generic auth errors (no user enumeration). Lockout after 10 failures.
  - Bean Validation on every DTO; JPA parameters only, no string SQL.
  - Sanitize job description HTML server-side (jsoup allowlist) before return.
  - Validate apply_url is http(s) before redirecting (no open redirect).
  - Secrets from env only; DB user for API has read-only grants on job tables.
  - Dependency scanning in CI (OSV-Scanner, pip-audit, npm audit).

## 6. Next.js frontend

6.1 Pages
  /            landing: hero, stat tiles (active jobs, companies, last
               refresh), category chips, featured jobs, CTA
  /jobs        search bar + filters (role, city, work mode, type, experience),
               job cards, pagination, empty state, URL-synced filters
  /jobs/[id]   detail, tags, source badge, Apply button, Save button
  /login, /register    email/password + "Continue with Google"
  /dashboard   Saved and Applied tabs
  /about       sources, how tagging works, accuracy and cost numbers

6.2 Design (style reference: eventbeep.com)
  - BEFORE coding UI: user places 4-6 screenshots of the reference site in
    /design (hero, nav, job cards, buttons, footer, mobile).
  - Claude Code reads them and writes /design/tokens.md: colours, font
    family, radius, shadow, spacing, button and card styles. Map tokens
    into tailwind.config.
  - Match the layout rhythm and tone: bold hero headline, two CTAs, stat
    tiles, category-tabbed job section, rounded cards, logo strip, short
    energetic copy.
  - Use OUR OWN product name, logo and images. Do not copy their logo,
    wordmark, photos, press logos or text.
  - Mobile-first, accessible (contrast AA, keyboard focus, labels).

6.3 Tech
  - Server components for /jobs (SEO, fast). next.config rewrites
    /api/* and /oauth2/* and /login/oauth2/* -> API_ORIGIN.
  - fetch with credentials; send X-XSRF-TOKEN on mutations.
  - No tokens in localStorage or JS-readable cookies.

## 7. Deployment
  - DB: Supabase or Neon Postgres (TLS required).
  - Web: Vercel.
  - API: Render/Railway/Fly (Docker). Free tiers sleep; for the demo use an
    always-on plan or a keep-alive ping, and say so in the video.
  - Worker: GitHub Actions (no server).
  - Optional custom domain: app.example.com with /api rewrite.

## 8. Evaluation (/eval)
  - sample.py: pick 50 random active jobs (fixed seed), export CSV with
    title, company, location, description, and BLANK label columns.
  - Human fills labels WITHOUT seeing model tags.
  - score.py: per-field accuracy for role_category, city, work_mode,
    job_type, is_fresher; plus all-fields-correct rate; list mismatches.
  - cost.py: from job_tags tokens -> avg tokens/post x current model price
    (read from provider pricing page, put in config) -> USD and INR per
    1,000 posts. Also report cost saved by content_hash skipping.
  - Results go in docs/cost.md and the /about page.

## 9. Build phases (do in order; stop and verify each)

P1  Scaffold monorepo, docker-compose, Flyway V1 schema, CI skeleton.
    Done when: `docker compose up` gives DB + empty API health check.
P2  Worker: adapters + normalize + upsert for Adzuna and Greenhouse.
    Done when: one run stores real jobs; re-run creates zero duplicates.
P3  Add Lever, Ashby, SmartRecruiters; seed sources table with verified
    company slugs; India + fresher pre-filter; cross-source dedupe.
    Done when: 200+ active fresher posts in DB.
P4  LLM tagging + token logging + hash skip.
    Done when: all active jobs tagged; second run tags ~0 jobs.
P5  Spring Boot: jobs read API with filters, full-text search, pagination.
P6  Spring Boot: register/login, Google OAuth2, sessions, CSRF, rate limits,
    saved jobs, apply tracking. Security tests for each rule in 5.3.
P7  Frontend: tokens from /design, landing, /jobs, /jobs/[id].
P8  Frontend: auth pages, dashboard, apply flow.
P9  Deploy all; GitHub Actions daily cron; confirm an unattended run.
P10 Eval: label 50, run score.py and cost.py, publish numbers.
P11 docs/architecture.md, docs/what-broke.md, README, record video.

## 10. Tests
  - Worker: unit tests per adapter using saved fixture JSON; dedupe tests.
  - API: MockMvc tests for auth, CSRF, rate limit, filters, open-redirect.
  - Web: Playwright smoke test (search, filter, login, save, apply).

## 11. Rules for Claude Code
  - Work one phase at a time; run tests before moving on.
  - Append every real failure and its fix to docs/what-broke.md (needed for
    the video).
  - Never commit secrets; provide .env.example files.
  - Never add a source without an official API or clear permission.
  - Ask before changing schema, auth design or adding paid services.

## 12. Needed from the user before P1
  - Adzuna app_id and app_key
  - LLM API key
  - Google OAuth client id and secret (redirect URI: {origin}/login/oauth2/code/google)
  - Postgres URL, GitHub repo, Vercel and API host accounts
  - Product name + reference screenshots in /design