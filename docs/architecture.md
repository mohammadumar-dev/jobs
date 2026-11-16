# Architecture

```
  GitHub Actions (cron 21:00 UTC = 02:30 IST, + manual)
            |
            v
  worker/  Python 3.12 -----fetch----> Adzuna IN, Greenhouse, Lever, Ashby, SmartRecruiters
     pre-filter -> normalize -> upsert -> deactivate -> dedupe -> LLM tag
            |  (only writer of job tables)
            v
     PostgreSQL (Neon)      schema owned by Flyway migrations in jobs/
            ^
            |  (reads job tables; only writer of user tables)
  jobs/    Spring Boot 4.1 / Java 25     auth, sessions, jobs read API, saved, apply clicks
            ^
            |  same origin: client/proxy.ts forwards /api/*, /oauth2/*, /login/oauth2/*
  client/  Next.js 16                    landing, search, detail, login, dashboard, about
            ^
         browser (talks to one origin only)
```

Folder names: the plan calls these `/worker`, `/api`, `/web`. The repository uses
`worker/`, `jobs/` (API) and `client/` (web) because the last two already existed.

## Ownership rules

- The worker is the only writer of `sources`, `jobs`, `job_tags`, `ingest_runs`.
- The API is the only writer of `users`, `saved_jobs`, `apply_clicks` and the
  Spring Session tables. It never writes a job table.
- The browser never calls the API host. Everything goes through the web origin, so
  cookies are first-party and CORS is not enabled anywhere.
- Schema changes happen only through Flyway files in
  `jobs/src/main/resources/db/migration`. The worker tests apply `V1__init.sql`
  directly, so the worker is always tested against the real schema.

## Worker pipeline (one run)

1. **Fetch** each enabled source through its adapter (`fetch` + `normalize`). A
   failing source is recorded in `ingest_runs.errors_json` and skipped.
2. **Pre-filter**: India location and an entry-level signal (rules in `filters.py`).
   Nothing that fails this is stored or sent to the LLM.
3. **Normalize**: HTML to text, `content_hash = sha256(title, company, description)`,
   `dedupe_key = title | company | city`.
4. **Upsert** on `(source_id, external_id)`; bump `last_seen_at`. If the hash
   changed, the job's tags are deleted so it is re-tagged.
5. **Deactivate** jobs not seen in two consecutive runs. A run only counts as a
   "miss" for a source that was fetched successfully in it, so an outage never
   deactivates anything.
6. **Dedupe** across sources: per `dedupe_key` the oldest active row is kept; the
   others get `canonical_job_id` pointing at it and are hidden.
7. **Tag** active, canonical jobs that have no tags. Untagged = new or changed, so
   a second run with no changes makes zero LLM calls.
8. **Record** counts, cost and errors in `ingest_runs` (always, even on failure).

### Tagging

- Anthropic SDK, model from `LLM_MODEL` (default `claude-haiku-5-5`), effort low.
- Output is constrained to a JSON schema whose enums come from `taxonomy.yaml`,
  then validated with pydantic; invalid output gets exactly one retry.
- 20 or more jobs go through the Message Batches API (half price); smaller sets and
  retries are sent one by one. A batch that does not finish in time is cancelled and
  its jobs are picked up by the next run.
- `job_tags` stores model, prompt version and token counts for every tag.
- With no API key the worker uses a rule-based tagger (`heuristic-v1`) so local
  development works. It is not the LLM and must not be used for accuracy numbers.

## API security (plan section 5.3) and where each rule is tested

| Rule | Implementation | Test |
| ---- | -------------- | ---- |
| Server-side sessions, no JWT in the browser | Spring Session JDBC | `loginSetsHardenedServerSideSessionCookie`, e2e storage check |
| Cookie HttpOnly, Secure, SameSite=Lax, `__Host-`, 7-day idle | explicit `CookieSerializer`, `spring.session.timeout` | same |
| Rotate session id on login | `ChangeSessionIdAuthenticationStrategy` in `SessionLogin` | `sessionIdIsRotatedOnLogin` |
| Google OAuth2, code flow + PKCE + state | `oauth2Login` + PKCE customizer (profile `google`) | `GoogleOAuthTests` |
| Link by verified email | `UserService.upsertGoogleUser`; an unverified password is dropped on link | `googleLoginLinksByVerifiedEmail...` |
| Argon2id, min 10 chars | `Argon2PasswordEncoder`, bean validation | `passwordIsStoredAsArgon2idHash`, `registrationValidatesInput` |
| CSRF cookie-to-header | `csrf().spa()` with `XSRF-TOKEN` / `X-XSRF-TOKEN` | `stateChangingRequestsNeedTheCsrfHeader`, `logoutWithoutCsrfTokenIsRejected` |
| HTTPS only, HSTS | `redirectToHttps` (health probe exempt), HSTS header | `HttpsRedirectTests`, `securityHeadersArePresent` |
| CSP, nosniff, frame-ancestors, Referrer-Policy | API headers; page CSP with nonce in `client/proxy.ts` | `securityHeadersArePresent`, e2e CSP check |
| CORS disabled | no CORS configuration | `corsIsNotEnabled` |
| Rate limits 5/min auth, 60/min search | Bucket4j filter, per client IP | `loginIsLimitedToFivePerMinutePerIp`, `searchIsLimitedToSixtyPerMinutePerIp` |
| No user enumeration, lockout after 10 | identical responses; `LoginAttemptService` | `registeringAnExistingEmail...`, `wrongPasswordAndUnknownEmail...`, `accountLocksAfterTenFailures...` |
| Validation, parameterised SQL only | bean validation; constant SQL with named parameters | `rejectsInvalidParametersAndTreatsSqlAsPlainText` |
| Sanitise description (jsoup) | `TextSafety.plainText`, allowlist of nothing | `detailStripsAllMarkupFromDescription` |
| No open redirect on apply | only stored http(s) URLs are returned | `applyNeverReturnsANonHttpUrl` |
| Secrets from env only | `.env` files are gitignored; `.env.example` provided | - |
| Read-only DB role for job tables | optional, `docs/db-roles.sql` | not automated |
| Dependency scanning | `pip-audit`, `npm audit`, OWASP dependency-check in CI | CI |

### Apply flow

Applying on a candidate's behalf is not possible (ATS apply endpoints need each
employer's private key). The Apply button is a real link to the source's own URL,
opened in a new tab with `rel="noopener noreferrer"`. Clicking it also posts to
`/api/jobs/{id}/apply`, which records an `apply_clicks` row; the job then appears
under "Applied" in the dashboard.

## Sources and terms

All five source types are the providers' public, documented job-posting APIs,
called without logging in. The worker sends a descriptive User-Agent (add your
contact URL with `CONTACT_URL`), makes at most one request per second per host,
backs off on 429/5xx, and always links to the source's own apply URL.

**Before going live, read each provider's API terms yourself** and note the date
here. This was not done as part of the build:

- Adzuna: API terms require attribution and linking through `redirect_url` (the
  worker does the latter; add visible "Jobs by Adzuna" attribution if their terms
  ask for it).
- Greenhouse, Lever, Ashby, SmartRecruiters: the job board APIs are published for
  listing a company's jobs. Each company in `sources.yaml` was chosen because its
  board is public, not because it gave explicit permission.

## Deployment

| Part | Where | Notes |
| ---- | ----- | ----- |
| Database | Neon Postgres (TLS required) | already migrated by the API's Flyway run |
| API | Render / Railway / Fly, from `jobs/Dockerfile` | free tiers sleep: use an always-on plan or a keep-alive ping on `/actuator/health`, and say so in the video |
| Web | Vercel, root directory `client` | env: `API_ORIGIN`, `PROXY_SECRET` |
| Worker | GitHub Actions, `.github/workflows/ingest.yml` | secrets: `DATABASE_URL`, `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `LLM_API_KEY` |

API environment: `SPRING_DATASOURCE_URL` (JDBC form), `SPRING_DATASOURCE_USERNAME`,
`SPRING_DATASOURCE_PASSWORD`, `APP_PUBLIC_ORIGIN` (the web origin), `PROXY_SECRET`
(same value as the web app), and for Google login `SPRING_PROFILES_ACTIVE=google`,
`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`. Google redirect URI:
`{APP_PUBLIC_ORIGIN}/login/oauth2/code/google`.

## Deviations from PLAN.md

- Spring Boot 4.1 / Java 25 and Next.js 16 (the scaffolded projects) instead of
  Boot 3 / Java 21.
- Forwarding to the API is done in `client/proxy.ts`, not `next.config` rewrites,
  so the proxy secret and client IP can be attached.
- Next.js Cache Components are off (required by the nonce CSP), so pages are
  rendered per request rather than cached.
- Job reads use Spring's `JdbcClient` with named parameters rather than JPA
  entities (full-text search needs native SQL). Users are JPA.
- No `temperature=0` (rejected by current models); see docs/cost.md.
- Descriptions are stored and served as plain text, not sanitised HTML.
- Tailwind v4 has no `tailwind.config`; tokens are CSS variables in `globals.css`.

## Known limits

- Rate-limit buckets and lockout counters are in memory: correct for one API
  instance, per-instance if you scale out.
- Without `PROXY_SECRET` set on both sides, all visitors share one rate-limit bucket.
- The dedupe key merges identical title + company + city, which also merges two
  genuinely separate openings with the same title at the same company and city.
- Email addresses are not verified for password sign-ups (no mail is sent).
- A job from a source that is later disabled is deactivated on the next run.
