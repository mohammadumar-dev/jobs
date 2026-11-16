# What broke (and how it was fixed)

Real failures hit while building, in order. Kept for the video walkthrough.

## 1. Session cookie had none of its security flags

- **Symptom:** the first security test failed. After login the cookie was
  `SESSION=...; Path=/` with no `HttpOnly`, no `Secure`, no `SameSite`, and not
  the `__Host-` name, even though `server.servlet.session.cookie.*` was set.
  The idle timeout was also 30 minutes, not 7 days.
- **Cause:** on Spring Boot 4.1 with Spring Session JDBC, those `server.servlet.*`
  properties were not what configured Spring Session's cookie in this setup.
- **Fix:** an explicit `CookieSerializer` bean in `SecurityConfig` (name,
  HttpOnly, Secure, SameSite=Lax, Path=/, Max-Age 7d) and `spring.session.timeout=7d`.
  `AuthSecurityTests.loginSetsHardenedServerSideSessionCookie` asserts every attribute
  and the 604800-second timeout stored in Postgres.
- **Lesson:** a security setting that is not asserted by a test is a guess.

## 2. One failing source rolled back every other source

- **Symptom:** worker test "a failing source does not stop the run": after source
  B failed, source A's jobs from the same run were gone.
- **Cause:** the psycopg connection was not in autocommit mode, so the per-source
  `with conn.transaction()` blocks were only savepoints inside one big implicit
  transaction; the `rollback()` in the error handler discarded all of it.
- **Fix:** connect with `autocommit=True`; every write is a single statement or an
  explicit transaction block. One source = one transaction.

## 3. "Second run tags ~0 jobs" looked false

- **Symptom:** the re-run test reported `tagged: 3` on a run that should tag nothing.
- **Cause:** not a re-tag. The run summary merged two dicts and the "total tagged
  jobs" statistic overwrote the "tagged in this run" counter (same key).
- **Fix:** renamed the statistics to `tagged_total` / `fresher_total`. The test also
  counts actual tagger calls, which was 0 all along.

## 4. Everyone would have shared one rate-limit bucket

- **Symptom:** found in design review before deploy, not in a test. The API limits
  login to 5/minute per IP, but every browser request reaches the API through the
  Next.js server, so the API would see one IP for all users: five logins a minute
  for the whole site.
- **Fix:** the Next.js proxy forwards the visitor's IP in `X-Client-IP` together
  with a shared secret in `X-Proxy-Secret`. The API believes the header only when
  the secret matches (constant-time compare); otherwise it uses the socket address.
  The proxy strips both headers from incoming browser requests. Covered by
  `forwardedClientIpIsOnlyTrustedWithTheProxySecret`.

## 5. Rate-limit test let the 61st request through

- **Symptom:** 61 searches from one IP, expected 429 on the last, got 200.
- **Cause:** the bucket refilled "greedily" (one token per second), and the 60
  requests took about 7 seconds, so 7 tokens had come back.
- **Fix:** `refillIntervally`: 60 per minute means 60, then wait for the minute.

## 6. Strict CSP vs. Next.js Cache Components

- **Symptom:** the plan requires a CSP with no inline scripts. Next.js needs a
  per-request nonce for that, and its docs state that nonces are incompatible with
  prerendered shells (Cache Components / Partial Prerendering), which the generated
  project had switched on.
- **Fix:** `cacheComponents` is off and every page renders per request; `proxy.ts`
  sets a nonce-based CSP. Trade-off: no static caching of pages. Chosen because the
  security rule is explicit and job lists change daily anyway.

## 7. Account lockout leaked between tests

- **Symptom:** unrelated login tests returned 401 when run after the lockout test.
- **Cause:** lockout state is in memory and the tests reused one email address.
- **Fix:** tests clear the lockout cache before each test. (In production this
  in-memory state is per API instance; see "Known limits" in architecture.md.)

## 8. Local Postgres rejected the JVM's time zone

- **Symptom:** API failed to start against a local Postgres:
  `FATAL: invalid value for parameter "TimeZone": "Asia/Calcutta"`.
- **Cause:** the JDBC driver sends the JVM's default zone; the machine reports the
  legacy id `Asia/Calcutta`, which that Postgres build does not know.
- **Fix:** the API sets its default time zone to UTC at startup (also the right
  choice for a server: all timestamps are `timestamptz`).

## 9. Experience parser read "2011" as "11 years"

- **Symptom:** an internship card showed "11+ yrs".
- **Cause:** the years regex matched the last two digits of a four-digit number.
- **Fix:** a look-behind so a number that is part of a longer number is ignored.
  (This parser is only the pre-filter and the no-LLM fallback tagger.)

## 10. Guessed company board names were mostly wrong

- **Symptom:** of roughly 1,200 candidate board slugs tried, only about 45 existed
  with India postings, and most large tech boards had zero entry-level India roles
  on the day (for example 84 India jobs at one company, none junior).
- **Fix:** `jobsworker probe` checks candidates against the live APIs;
  `sources.yaml` contains only boards that returned a match. Volume for the 200+
  target comes from the Adzuna India API, which needs its API keys.

## 11. Package installed before its source existed

- **Symptom:** `No module named 'jobsworker'` right after `uv sync`.
- **Cause:** the first `uv sync` ran before `src/jobsworker/` was created, so the
  editable install pointed at nothing.
- **Fix:** `uv sync --reinstall-package jobsworker`.
