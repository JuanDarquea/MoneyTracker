# MoneyTracker

Personal finance tracker (mobile + web). See `Planning/` for the full
product spec, agent structure, testing strategy, and production plan, and
`docs/ARCHITECTURE.md` for how the deployed pieces fit together.

## Prerequisites

- Python 3.12+, pip, a virtual environment
- Flutter 3.47+ (https://flutter.dev)
- Docker (for the local Postgres dev/test database)
- A Supabase project (https://supabase.com) — Auth + Postgres
- A Render account, if deploying the backend (https://render.com)

## Backend (FastAPI)

    cd backend
    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env   # fill in DATABASE_URL / SUPABASE_URL / SUPABASE_JWT_SECRET
    docker compose -f ../docker-compose.dev.yml up -d
    alembic upgrade head
    uvicorn app.main:app --reload

`docker-compose.dev.yml` provisions both the dev database (`moneytracker`) and a
separate test database (`moneytracker_test`) automatically on first container
init; `.env` needs `TEST_DATABASE_URL` set alongside `DATABASE_URL` so the test
suite uses its own database instead of the dev one. `DATABASE_URL` itself
points at Supabase Postgres for real use; tests always use the local Docker
database, never Supabase.

`SUPABASE_URL`, `SUPABASE_JWT_SECRET`, and `SUPABASE_JWT_AUD` come from your
Supabase project's **Project Settings → API** (URL, anon key) and
**Project Settings → Auth → JWT Settings**. This project verifies Supabase's
newer asymmetric JWT Signing Keys (ES256) against the project's public JWKS
— `SUPABASE_JWT_SECRET` is only actually used for self-issued tokens in the
test suite, but the app requires it to be set regardless.

Run the tests:

    pytest -v

### Deploying the backend (Render)

The backend is deployed at `https://moneytracker-9i1w.onrender.com` as a
Render web service on the **native Python runtime** (this Render
account/plan has no Docker runtime option, so `backend/Dockerfile` exists
only for local `docker build`/testing, not for the live deploy).

`render.yaml` at the repo root defines the service (`rootDir: backend`,
`buildCommand: pip install -r requirements.txt`,
`startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT`,
health check `/api/v1/health`). Since the service was created manually
rather than via a Render Blueprint sync, `render.yaml` isn't
auto-applied to it — changes to build/start commands need to be mirrored
by hand in the Render dashboard.

Required env vars, set directly in the Render dashboard (never committed):
`DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_JWT_SECRET`. `SUPABASE_JWT_AUD`
and `PYTHON_VERSION` are plain (non-secret) values already in `render.yaml`.

Free-tier note: the service spins down after ~15 minutes idle; the first
request after that takes tens of seconds to wake it back up.

Migrations note: this Render plan has no pre-deploy command hook, so a new
Alembic migration is not applied automatically on push. When a change adds
a migration, run `alembic upgrade head` by hand against the Supabase
database (using its connection string as `DATABASE_URL`), either just
before or right after pushing the deploy — don't rely on Render to do it.

## Frontend (Flutter)

    cd frontend/money_tracker_app
    flutter pub get

Run against a local backend, with real Supabase credentials:

    flutter run -d chrome \
      --dart-define=SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co \
      --dart-define=SUPABASE_ANON_KEY=YOUR_SUPABASE_ANON_KEY \
      --dart-define=API_BASE_URL=http://localhost:8000/api/v1

Run against the deployed Render backend instead, by changing `API_BASE_URL`:

    flutter run -d chrome \
      --dart-define=SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co \
      --dart-define=SUPABASE_ANON_KEY=YOUR_SUPABASE_ANON_KEY \
      --dart-define=API_BASE_URL=https://moneytracker-9i1w.onrender.com/api/v1

`-d web-server` also works, but its debug/hot-reload service needs the
[Dart Debug Extension](https://pub.dev/packages/dwds#debug-extension)
installed in the browser you point at it — without it the page loads but
never actually runs. For a quick static preview with no debugger at all,
build once and serve the output with any static file server:

    flutter build web \
      --dart-define=SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co \
      --dart-define=SUPABASE_ANON_KEY=YOUR_SUPABASE_ANON_KEY \
      --dart-define=API_BASE_URL=http://localhost:8000/api/v1
    cd build/web && python3 -m http.server 5000

Run the tests:

    flutter test
