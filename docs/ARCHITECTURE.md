# Architecture

## Topology

```
Flutter Web/Mobile              FastAPI Backend              Supabase
(local run, or a static  ---->  (local uvicorn, or  ---->    Postgres + Auth
 build served anywhere)          Render web service)
```

The frontend talks to two things directly: Supabase Auth (for sign
up/log in — see "Auth flow" below) and the FastAPI backend (for
transaction CRUD). The backend is the only thing that talks to Postgres;
the frontend never queries the database directly.

## Credential flow

| Layer | Config source | Variables |
|---|---|---|
| Frontend | compile-time `--dart-define` flags (`lib/core/env.dart` reads them) | `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `API_BASE_URL` |
| Backend (local dev) | `backend/.env` (gitignored, `pydantic-settings`) | `DATABASE_URL`, `TEST_DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_JWT_SECRET`, `SUPABASE_JWT_AUD` |
| Backend (Render) | Render dashboard env vars, per `render.yaml` | same as above, minus `TEST_DATABASE_URL` |
| Supabase | Project Settings → API / Auth | issues `SUPABASE_ANON_KEY` (public, safe client-side) and signs JWTs via its own key pair |

Nothing above is ever committed to git except the two genuinely
non-secret values already inline in `render.yaml` (`SUPABASE_JWT_AUD`,
`PYTHON_VERSION`) and the project's public URL (`SUPABASE_URL` — this is
not sensitive; it's already embedded in the compiled frontend anyway).
`DATABASE_URL` and `SUPABASE_JWT_SECRET` are set by hand in the Render
dashboard and in each developer's local `.env`.

## Auth flow

1. User signs up/logs in via the Flutter app → Supabase Auth directly
   (the backend is not involved in this step).
2. Supabase issues a JWT, signed with the project's **asymmetric JWT
   Signing Key** (ES256) — not a legacy shared HS256 secret. This project
   was created after Supabase's shift to asymmetric keys by default; an
   older project might still be on the legacy scheme.
3. The Flutter app attaches that JWT as `Authorization: Bearer <token>` on
   every request to the backend (`lib/core/api_client.dart`).
4. The backend (`app/core/security.py`) verifies the token's signature
   against the Supabase project's public JWKS
   (`<SUPABASE_URL>/auth/v1/.well-known/jwks.json`), fetched and cached via
   `PyJWKClient`. Self-issued HS256 tokens (used only by the backend's own
   test suite) are verified against `SUPABASE_JWT_SECRET` instead — real
   traffic never takes that path.
5. On success, the token's `sub` claim becomes the `user_id` every
   transaction query is scoped to (`app/api/deps.get_current_user_id`).

Any failure in that verification — bad signature, expired token, or the
JWKS fetch itself failing (misconfiguration, network issue) — is caught
and turned into a plain `401`, never an unhandled `500`. This matters
because FastAPI's default error handling sits *outside* `CORSMiddleware`;
an uncaught exception produces a response with no CORS headers at all,
which browsers report as an opaque "blocked by CORS policy" error that
has nothing to do with CORS and hides the real cause.

## Testing

- Backend unit/integration tests always run against the local Docker
  Postgres (`TEST_DATABASE_URL`), never against Supabase — fast, isolated,
  no live credentials required. JWT tests mint their own HS256 tokens and
  mock the JWKS client rather than hitting Supabase over the network.
- Frontend widget tests (`flutter test`) don't hit any network either.
- No automated test talks to the deployed Render service or the real
  Supabase project — those are verified manually (or by an agent driving
  a browser) when a deploy-affecting change lands.
