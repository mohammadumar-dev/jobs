# Deploying

Everything below runs on free plans: Vercel (web), Render (API), Neon (database),
GitHub Actions (daily worker), and free LLM tiers (tagging).

```
browser ──https──▶ Vercel: Next.js (client/)
                     │  /api/*, /oauth2/*, /login/oauth2/*  forwarded by client/proxy.ts
                     │  with X-Proxy-Secret + X-Client-IP
                     ▼
                   Render: Spring Boot API (jobs/) ──TLS──▶ Neon Postgres
                                                              ▲
GitHub Actions, daily 02:30 IST: Python worker (worker/) ─────┘
```

**Why there is no CORS setting.** The browser only ever talks to the Vercel
domain. Vercel forwards API calls to Render server-to-server, so the browser never
makes a cross-origin request, and CORS stays disabled on the API (safer: no other
site can call it with a user's cookies). The two services are linked by three
values instead:

| Value | Set on | Meaning |
| --- | --- | --- |
| `API_ORIGIN` | Vercel | Render URL, e.g. `https://firstrung-api.onrender.com` |
| `APP_PUBLIC_ORIGIN` | Render | Vercel URL, e.g. `https://firstrung.vercel.app` (used for redirects, Origin checks, Google login) |
| `PROXY_SECRET` | both, same value | proves a request came through Vercel, so per-visitor rate limits work |

Generate the secret once and keep it in a password manager:

    python -c "import secrets; print(secrets.token_hex(32))"

## 0. Repository

- Code on `main` (CI runs on every push: worker tests, API tests, web lint/build).
- `.env` files are gitignored; only `.env.example` files are committed.

## 1. Web on Vercel (first, to get the domain)

1. vercel.com, sign in with GitHub, **Add New, Project**, import this repository.
2. **Root Directory**: `client`. Framework preset: Next.js (auto-detected).
3. Environment variables (Production):
   - `API_ORIGIN` = `https://placeholder.invalid` for now (step 3 replaces it)
   - `PROXY_SECRET` = the generated secret
4. Deploy. Pages will say the job service is not responding; expected until step 3.
5. Note the domain, e.g. `https://firstrung.vercel.app` (Settings, Domains).

## 2. API on Render

1. render.com, sign in with GitHub, **New, Blueprint**, pick this repository.
   Render reads `render.yaml` (Docker, region Ohio next to Neon, free plan,
   health check `/actuator/health`).
2. Fill the secret values it asks for:
   - `SPRING_DATASOURCE_URL` = `jdbc:postgresql://<neon-host>/neondb?sslmode=require&channel_binding=require`
     (the host from your Neon URL; JDBC form, no user/password in it)
   - `SPRING_DATASOURCE_USERNAME` = `neondb_owner`
   - `SPRING_DATASOURCE_PASSWORD` = your Neon password
   - `APP_PUBLIC_ORIGIN` = the Vercel domain from step 1, no trailing slash
   - `PROXY_SECRET` = the same secret as on Vercel
3. Wait for the first deploy (Docker build takes a few minutes), then open
   `https://<service>.onrender.com/actuator/health`. It should say `{"status":"UP"}`.

Free-plan behaviour: the API sleeps after about 15 minutes without traffic, and
the first request afterwards takes up to a minute while it starts. The site shows
"Jobs are loading slowly" during that time. A paid instance removes this.

## 3. Connect the web app to the API

1. Vercel, project Settings, Environment Variables: set `API_ORIGIN` to the Render
   URL (no trailing slash).
2. Deployments, latest, **Redeploy** (environment changes need a new deploy).
3. Open the Vercel domain: home page shows job counts; sign up, save a job, log out.

## 4. Worker on GitHub Actions

Repository, **Settings, Secrets and variables, Actions**:

| Secret | Value |
| --- | --- |
| `DATABASE_URL` | Neon URL in `postgresql://...` form (same as `worker/.env`) |
| `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY` | free LLM keys (any subset) |
| `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | when you have them |

Optional **variables**: `CONTACT_URL` (sent in the crawler User-Agent, e.g. the
site's about page).

Then **Actions, ingest, Run workflow** once to check it; after that it runs daily
at 21:00 UTC (02:30 IST). Each run's summary is in the job log (Stats step) and in
the `ingest_runs` table.

## 5. Google login (optional)

1. Google Cloud Console, APIs & Services: OAuth consent screen (External), then
   Credentials, **Create OAuth client ID**, type Web application.
2. Authorised redirect URI: `<Vercel domain>/login/oauth2/code/google`.
3. On Render add `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` and
   `SPRING_PROFILES_ACTIVE=google`.

## 6. Check after deploying

- `https://<api>/actuator/health` is `UP`.
- Home page shows counts and "last refresh" after the first worker run.
- Sign up, log in, save, apply, dashboard, log out all work.
- Response headers on the Vercel site include `Content-Security-Policy` and
  `Strict-Transport-Security`; the session cookie is `__Host-SESSION`,
  `HttpOnly`, `Secure`.
- Calling the API directly without the proxy secret still works but every such
  caller shares one rate-limit bucket.

## Custom domain later

Add it in Vercel (Settings, Domains), then change `APP_PUBLIC_ORIGIN` on Render and
the Google redirect URI to the new domain.
