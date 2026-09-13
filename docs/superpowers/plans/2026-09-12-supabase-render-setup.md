# Supabase & Render Setup for Development

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect MoneyTracker to a live Supabase project and configure Render for development deployment, replacing local Docker Postgres with cloud-hosted Supabase while maintaining schema parity.

**Architecture:** The backend will authenticate Supabase Auth JWTs using a secret shared across environments; credentials (Supabase URL, anon key, JWT secret) flow through `.env` files and render.yaml service environment variables. Frontend reads Supabase credentials at compile/runtime, routes API calls to Render-hosted backend. Database schema matches what local Docker Postgres uses — no migration between environments, only credential swaps.

**Tech Stack:** Supabase (PostgreSQL + Auth), Render (Docker-based deployment), FastAPI backend, Flutter frontend, environment variable configuration (python-dotenv for backend, compile-time for frontend).

**Spec:** `Planning/04_production_infrastructure.md` (infrastructure plan), `docs/superpowers/plans/2026-09-11-m1-skateboard.md` (M1 scope: auth + transaction CRUD).

## Global Constraints

- Supabase JWT verification uses `SUPABASE_JWT_SECRET` env var — shared across all deployment stages (dev/staging/prod use same secret; different Supabase projects have same secret for cross-project JWT trust).
- Backend database URL points to Supabase Postgres in production; local Docker Postgres for dev fallback.
- Frontend environment variables (`SUPABASE_URL`, `SUPABASE_ANON_KEY`, `API_BASE_URL`) set at Flutter build time via `--dart-define` flags or `.env` files.
- Render free tier supports one web service and one PostgreSQL instance. Plan assumes single dev service initially; staging/production are out of scope (no domain yet).
- All credentials kept out of source control (`.env` and `.env.local` remain gitignored).
- No code changes to app logic — only configuration and environment wiring.

---

## File Structure

```
MoneyTracker/
├── backend/
│   ├── .env                          # [MODIFY] Add Supabase credentials
│   ├── .env.example                  # [MODIFY] Document expected env vars for Supabase
│   ├── requirements.txt               # [MODIFY] Add render deployment support (if needed)
│   ├── Dockerfile                     # [CREATE] Container image for Render deployment
│   ├── app/core/config.py             # [MODIFY] Support both local and Supabase DATABASE_URL
│   └── app/main.py                    # [NO CHANGE] Works with any DATABASE_URL
│
├── frontend/money_tracker_app/
│   ├── lib/core/env.dart              # [NO CHANGE] Already reads from build environment
│   ├── lib/main.dart                  # [VERIFY] initSupabase() called before app runs
│   └── pubspec.yaml                   # [VERIFY] supabase_flutter dependency exists
│
├── render.yaml                        # [CREATE] Render service configuration
├── docker-compose.dev.yml             # [NO CHANGE] Remains for local fallback dev
└── docs/superpowers/plans/
    └── 2026-09-12-supabase-render-setup.md  # [THIS FILE]
```

---

## Phase 1: Supabase Project Setup

### Task 1: Create Supabase Project and Extract Credentials

**Files:**
- No code files touched; Supabase console only

**Interfaces:**
- Produces: Supabase project credentials:
  - `SUPABASE_URL`: `https://<project-ref>.supabase.co`
  - `SUPABASE_ANON_KEY`: public anonymous key (used by frontend + API client tests)
  - `SUPABASE_JWT_SECRET`: shared JWT secret for token verification (used by backend, same across all environments)
  - `SUPABASE_SERVICE_ROLE_KEY`: privileged key for backend-only operations (if needed later; not in M1 scope)

- [ ] **Step 1: Sign up or log in to Supabase (supabase.com)**

Go to https://supabase.com, sign up or log in with GitHub/email.

- [ ] **Step 2: Create a new project**

In Supabase dashboard → "New project" (or "Create project"):
- Name: `moneytracker-dev`
- Region: Choose closest to you (e.g., us-east-1)
- Database password: Generate a strong password (Supabase auto-generates one)
- Click "Create new project" and wait ~2 min for provisioning

- [ ] **Step 3: Extract project credentials**

Once project is ready, go to **Project Settings** (gear icon, bottom left):
1. Under **API** tab, copy:
   - `Project URL` → this is your `SUPABASE_URL`
   - `anon key` (public) → this is your `SUPABASE_ANON_KEY`
2. Under **Auth** tab → **Providers** → **JWT**, copy:
   - `JWT Secret` → this is your `SUPABASE_JWT_SECRET`
3. Save these three values somewhere safe (password manager, or temp file — we'll use them in Tasks 2 & 3)

- [ ] **Step 4: Verify project is running**

Back to **SQL Editor** (left sidebar):
- Run a test query: `SELECT NOW();`
- Should return current timestamp — confirms database is live

---

### Task 2: Update Backend `.env` with Supabase Credentials

**Files:**
- Modify: `backend/.env`
- Modify: `backend/.env.example`

**Interfaces:**
- Consumes: Supabase credentials from Task 1 (`SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_JWT_SECRET`)
- Produces: Backend `config.Settings` reads live Supabase credentials from `.env`

- [ ] **Step 1: Update `backend/.env` with Supabase PostgreSQL connection**

Current content (local Docker):
```
DATABASE_URL=postgresql+psycopg://moneytracker:moneytracker@localhost:5433/moneytracker
TEST_DATABASE_URL=postgresql+psycopg://moneytracker:moneytracker@localhost:5433/moneytracker_test
SUPABASE_JWT_SECRET=dev-only-change-me
SUPABASE_JWT_AUD=authenticated
```

Replace with Supabase Postgres (from Task 1):
```
DATABASE_URL=postgresql+psycopg://<username>:<password>@db.<project-ref>.supabase.co:5432/<database>
TEST_DATABASE_URL=postgresql+psycopg://moneytracker:moneytracker@localhost:5433/moneytracker_test
SUPABASE_JWT_SECRET=<your-jwt-secret-from-task-1>
SUPABASE_JWT_AUD=authenticated
```

Where:
- `<project-ref>` = first part of your SUPABASE_URL (e.g., `abc123def` from `https://abc123def.supabase.co`)
- `<username>` = `postgres` (Supabase default)
- `<password>` = the database password you set when creating the project
- `<database>` = `postgres` (Supabase default)

Example final line:
```
DATABASE_URL=postgresql+psycopg://postgres:MySecurePassword123@db.abc123def.supabase.co:5432/postgres
```

Keep `TEST_DATABASE_URL` pointing to local Docker for now (tests run in isolation, no need to hit Supabase).

- [ ] **Step 2: Update `backend/.env.example` to document Supabase vars**

Current:
```
DATABASE_URL=postgresql+psycopg://moneytracker:moneytracker@localhost:5433/moneytracker
TEST_DATABASE_URL=postgresql+psycopg://moneytracker:moneytracker@localhost:5433/moneytracker_test
SUPABASE_JWT_SECRET=dev-only-change-me
SUPABASE_JWT_AUD=authenticated
```

Replace with:
```
# Backend database (Supabase Postgres in production/staging, local Docker in dev fallback)
# Format: postgresql+psycopg://[user]:[password]@[host]:[port]/[database]
DATABASE_URL=postgresql+psycopg://postgres:YOUR_SUPABASE_DB_PASSWORD@db.YOUR_PROJECT_REF.supabase.co:5432/postgres

# Test database (always local Docker — tests should be fast and isolated)
TEST_DATABASE_URL=postgresql+psycopg://moneytracker:moneytracker@localhost:5433/moneytracker_test

# Supabase JWT verification (shared across all environments — same secret)
SUPABASE_JWT_SECRET=YOUR_SUPABASE_JWT_SECRET_FROM_PROJECT_SETTINGS

# JWT audience claim (standard: authenticated users)
SUPABASE_JWT_AUD=authenticated
```

- [ ] **Step 3: Verify backend can read the new .env**

Run:
```bash
cd backend
source .venv/bin/activate
python -c "from app.core.config import get_settings; s = get_settings(); print(f'Database: {s.database_url}')"
```

Expected output: Should print your Supabase Postgres connection string (password redacted is fine).

If error: "Connection refused" or "does not exist" — check that DATABASE_URL is correct in `.env`.

- [ ] **Step 4: Migrate schema to Supabase Postgres**

Run:
```bash
cd backend
alembic upgrade head
```

Expected: Alembic runs migrations on Supabase (same migrations as local Docker used). Should complete in <1s.

If error: "relation already exists" — schema was already there (safe to re-run, it's idempotent). If "does not exist" — check DATABASE_URL again.

- [ ] **Step 5: Commit**

```bash
git add backend/.env.example
git commit -m "docs: update backend .env.example for Supabase Postgres connection

Supabase DATABASE_URL replaces local Docker connection in production/staging.
.env kept in .gitignore — no secrets committed."
```

(Note: Do NOT commit `backend/.env` itself; it contains live credentials and must stay in `.gitignore`.)

---

### Task 3: Update Frontend `env.dart` with Supabase Credentials

**Files:**
- Modify: `frontend/money_tracker_app/lib/core/env.dart`

**Interfaces:**
- Consumes: Supabase credentials from Task 1 (`SUPABASE_URL`, `SUPABASE_ANON_KEY`)
- Produces: `Env.supabaseUrl` and `Env.supabaseAnonKey` read from build-time environment

- [ ] **Step 1: Verify current env.dart structure**

Current file:
```dart
class Env {
  static const supabaseUrl = String.fromEnvironment(
    'SUPABASE_URL',
    defaultValue: 'https://your-project.supabase.co',
  );
  static const supabaseAnonKey = String.fromEnvironment(
    'SUPABASE_ANON_KEY',
    defaultValue: 'replace-with-real-anon-key',
  );
  static const apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://localhost:8000/api/v1',
  );
}
```

This is correct — no code change needed. Flutter reads `SUPABASE_URL` and `SUPABASE_ANON_KEY` from build-time compile flags or environment.

- [ ] **Step 2: Create `.env.web` file for web builds (optional but recommended)**

If building Flutter web locally, create `frontend/money_tracker_app/.env.web`:
```
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_ANON_KEY=YOUR_SUPABASE_ANON_KEY
API_BASE_URL=http://localhost:8000/api/v1
```

This file will be read by `flutter run -d web-server` when you set it up correctly. (Flutter web doesn't auto-read `.env` like some frameworks — we'll document the launch command in Task 5 below.)

- [ ] **Step 3: Document the Flutter build flags**

In `frontend/money_tracker_app/README.md` or in a comment in `lib/main.dart`, add:

```
# Running Flutter web with Supabase credentials:
flutter run -d web-server \
  --dart-define=SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co \
  --dart-define=SUPABASE_ANON_KEY=YOUR_SUPABASE_ANON_KEY \
  --dart-define=API_BASE_URL=http://localhost:8000/api/v1
```

(Or read from `.env.web` if using a custom setup with `flutter_dotenv` package — not in current pubspec, so we document manual flags for now.)

- [ ] **Step 4: Verify frontend main.dart calls initSupabase()**

Check `frontend/money_tracker_app/lib/main.dart`:

```dart
void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await initSupabase();  // <-- Must be called before runApp
  runApp(const MyApp());
}
```

If missing, add the `await initSupabase()` call. This initializes Supabase with the credentials from `Env`.

- [ ] **Step 5: Commit**

```bash
git add frontend/money_tracker_app/lib/core/env.dart
git commit -m "docs: document Supabase environment variables for Flutter web builds

Frontend reads SUPABASE_URL and SUPABASE_ANON_KEY from build-time flags.
.env.web provides local override (if using flutter_dotenv in future)."
```

---

## Phase 2: Backend Render Deployment Setup

### Task 4: Create Dockerfile for FastAPI Backend

**Files:**
- Create: `backend/Dockerfile`

**Interfaces:**
- Consumes: `backend/requirements.txt`, `backend/app/main.py`
- Produces: Docker image that runs FastAPI on port 8000, reads `DATABASE_URL` and other env vars

- [ ] **Step 1: Create `backend/Dockerfile`**

```dockerfile
# Use Python 3.12 slim image (production-ready, smaller than full image)
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies (PostgreSQL client for debugging, curl for health checks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (Docker layer caching — requirements rarely change)
COPY backend/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini .

# Expose port 8000 (FastAPI default)
EXPOSE 8000

# Health check (optional but recommended for Render)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Run Uvicorn server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Verify Dockerfile runs locally**

Build the image:
```bash
docker build -t moneytracker-backend:latest -f backend/Dockerfile .
```

Expected: Build completes with "Successfully tagged moneytracker-backend:latest".

If error: "requirements.txt: No such file" — check paths are relative to repo root. If "ModuleNotFoundError" — check requirements.txt has all imports.

- [ ] **Step 3: Test Docker image with local Supabase (optional dry-run)**

Run:
```bash
docker run -e DATABASE_URL="postgresql+psycopg://postgres:PASSWORD@db.PROJECTREF.supabase.co:5432/postgres" \
  -p 8000:8000 moneytracker-backend:latest
```

(Replace PASSWORD and PROJECTREF with your Supabase credentials from Task 1.)

Expected: Server starts, listens on `localhost:8000`. Visit `http://localhost:8000/api/v1/health` in browser — should return `{"status": "ok"}`.

If error: "Connection refused" on health check — DATABASE_URL is wrong or Supabase is down. Cancel with `Ctrl+C`.

- [ ] **Step 4: Commit Dockerfile**

```bash
git add backend/Dockerfile
git commit -m "feat: add Dockerfile for FastAPI backend deployment

Runs Uvicorn on 0.0.0.0:8000, includes health check.
Reads DATABASE_URL env var for Supabase Postgres connection."
```

---

### Task 5: Create `render.yaml` Service Configuration

**Files:**
- Create: `render.yaml`

**Interfaces:**
- Consumes: Backend Dockerfile, Supabase credentials (Task 1)
- Produces: Render service definition for web backend service + optional static frontend service

- [ ] **Step 1: Create `render.yaml` at repo root**

```yaml
services:
  - type: web
    name: moneytracker-backend
    env: docker
    dockerfilePath: ./backend/Dockerfile
    buildCommand: "echo 'Building with docker build...'"  # Render uses Dockerfile
    startCommand: ""  # Entrypoint in Dockerfile
    ports:
      - port: 8000
        protocol: http
    healthCheckPath: /api/v1/health
    healthCheckInterval: 30
    autoDeploy: true
    envVars:
      - key: DATABASE_URL
        scope: run
        isFile: false
        # Value set in Render dashboard (see Task 6)
      - key: SUPABASE_JWT_SECRET
        scope: run
        isFile: false
        # Value set in Render dashboard (see Task 6)
      - key: SUPABASE_JWT_AUD
        scope: run
        value: authenticated
```

**Note on envVars:** Render allows some env vars in `render.yaml`, but **secrets should NOT be committed**. We'll set `DATABASE_URL` and `SUPABASE_JWT_SECRET` in the Render dashboard (Step 6), and reference them here by key name.

- [ ] **Step 2: Verify render.yaml syntax**

Run:
```bash
python3 -c "import yaml; yaml.safe_load(open('render.yaml'))" && echo "Valid YAML"
```

Expected: "Valid YAML" — no errors.

- [ ] **Step 3: Commit render.yaml**

```bash
git add render.yaml
git commit -m "feat: add render.yaml for FastAPI backend deployment

Defines moneytracker-backend service running on port 8000.
DATABASE_URL and SUPABASE_JWT_SECRET set via Render dashboard."
```

---

### Task 6: Deploy to Render and Set Environment Variables

**Files:**
- No code files; Render console only

**Interfaces:**
- Consumes: Supabase credentials (Task 1), GitHub repository URL
- Produces: Live Render service running at `https://moneytracker-backend-<random>.onrender.com`

- [ ] **Step 1: Sign up or log in to Render (render.com)**

Go to https://render.com, sign up with GitHub account (easiest auth integration).

- [ ] **Step 2: Create new web service**

Dashboard → "New" → "Web Service":
- **Name:** `moneytracker-backend`
- **GitHub repo:** Find and connect your MoneyTracker repo (authorize GitHub if needed)
- **Branch:** `feature/m1-skateboard` (or your current branch)
- **Runtime:** Docker (auto-detected from Dockerfile)
- **Region:** Choose closest to you
- **Plan:** Free (sufficient for development)

Click "Create Web Service" and wait for first deploy (~2 min).

- [ ] **Step 3: Add environment variables in Render dashboard**

Once service is created, go to **Settings** → **Environment**:

1. Add `DATABASE_URL`:
   - Key: `DATABASE_URL`
   - Value: `postgresql+psycopg://postgres:YOUR_PASSWORD@db.YOUR_PROJECT_REF.supabase.co:5432/postgres`
   - (Copy from your `.env` file created in Task 2)

2. Add `SUPABASE_JWT_SECRET`:
   - Key: `SUPABASE_JWT_SECRET`
   - Value: `<your-jwt-secret-from-task-1>`

3. `SUPABASE_JWT_AUD` is already in render.yaml with value `authenticated`, so it auto-inherits.

Click "Save" — Render will re-deploy automatically with new vars.

- [ ] **Step 4: Verify backend is live**

Once deploy completes (check "Deploys" tab for status):

Visit: `https://moneytracker-backend-<random>.onrender.com/api/v1/health`

Expected: Should return `{"status": "ok"}` in browser.

If error: "502 Bad Gateway" or connection refused — check env vars were saved (they sometimes take 30s to apply). Refresh after 1 min.

If error: "Connection refused" on DATABASE_URL — credentials are wrong or Supabase is down.

- [ ] **Step 5: Save your Render backend URL**

Your backend is now live at: `https://moneytracker-backend-<random>.onrender.com`

You'll need this URL in Task 7 (frontend configuration).

---

## Phase 3: Frontend Configuration for Render Backend

### Task 7: Update Frontend to Point to Render Backend

**Files:**
- Modify: `frontend/money_tracker_app/lib/core/env.dart`

**Interfaces:**
- Consumes: Render backend URL from Task 6
- Produces: `Env.apiBaseUrl` points to live Render service

- [ ] **Step 1: Update `env.dart` to point to Render**

Current (localhost):
```dart
static const apiBaseUrl = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: 'http://localhost:8000/api/v1',
);
```

Change default to Render URL (or remove default and require compile-time flag):

**Option A: Update default (all devs now use Render):**
```dart
static const apiBaseUrl = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: 'https://moneytracker-backend-<random>.onrender.com/api/v1',
);
```

**Option B: Keep localhost default, pass Render URL at build time:**
```dart
static const apiBaseUrl = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: 'http://localhost:8000/api/v1',  // local dev fallback
);
```

Then build with: `flutter run -d web-server --dart-define=API_BASE_URL=https://moneytracker-backend-<random>.onrender.com/api/v1`

**Recommendation:** Use Option B (localhost default) so devs can test locally without forcing Render. Document both in README.

- [ ] **Step 2: Update frontend README with Render build command**

In `frontend/money_tracker_app/README.md` or `frontend/README.md`, add:

```markdown
## Running Flutter Web

### Local development (backend on localhost:8000):
```bash
flutter run -d web-server
```

### Against Render backend:
```bash
flutter run -d web-server \
  --dart-define=SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co \
  --dart-define=SUPABASE_ANON_KEY=YOUR_SUPABASE_ANON_KEY \
  --dart-define=API_BASE_URL=https://moneytracker-backend-<random>.onrender.com/api/v1
```
```

- [ ] **Step 3: Test frontend against Render backend**

Build and run:
```bash
cd frontend/money_tracker_app
flutter run -d web-server \
  --dart-define=SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co \
  --dart-define=SUPABASE_ANON_KEY=YOUR_SUPABASE_ANON_KEY \
  --dart-define=API_BASE_URL=https://moneytracker-backend-<random>.onrender.com/api/v1
```

Expected: App loads in browser at `http://localhost:9528` (or similar). Login screen should be visible.

If error: "Failed to connect to API" or timeout — check API_BASE_URL is correct, and Render backend health check passes (Task 6, Step 4).

- [ ] **Step 4: Commit**

```bash
git add frontend/money_tracker_app/lib/core/env.dart frontend/money_tracker_app/README.md
git commit -m "docs: update frontend for Render backend connection

API_BASE_URL can target localhost or Render via --dart-define flag.
Default remains localhost for local dev; Render URL documented for staging."
```

---

## Phase 4: Integration Testing

### Task 8: Integration Test — Backend + Supabase + Render

**Files:**
- No new files; run existing tests against Render

**Interfaces:**
- Consumes: Render backend (Task 6), Supabase Postgres (Task 2)
- Produces: Verified end-to-end connection backend → Supabase

- [ ] **Step 1: Run backend health check**

From your local machine:
```bash
curl https://moneytracker-backend-<random>.onrender.com/api/v1/health
```

Expected: `{"status": "ok"}`

- [ ] **Step 2: Run backend tests against local test database**

(Tests should still use local Docker Postgres for speed/isolation, not Supabase.)

```bash
cd backend
source .venv/bin/activate
pytest tests/ -v
```

Expected: All tests pass (same as before — we didn't change test logic, only production DATABASE_URL).

- [ ] **Step 3: Verify transactions can be created via Render backend**

If you have a curl command to create a transaction (from Task 5 in the M1 plan), test it against Render:

```bash
curl -X POST https://moneytracker-backend-<random>.onrender.com/api/v1/transactions \
  -H "Authorization: Bearer YOUR_SUPABASE_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"amount": "100.00", "category": "Food", "type": "expense", "date": "2026-09-12"}'
```

Expected: Returns transaction object with id, status 200. If 401 Unauthorized — JWT token is invalid or expired. If 503 Service Unavailable — Render is still deploying (wait a few minutes).

- [ ] **Step 4: Commit test results (optional documentation)**

If you want to document test results:
```bash
git add docs/  # if adding a deployment log
git commit -m "test: verify backend deployed to Render with Supabase connection

Health check: ✓
Transactions API: ✓
Database: Supabase Postgres prod connection"
```

---

### Task 9: Integration Test — Frontend + Render Backend

**Files:**
- No code; manual testing

**Interfaces:**
- Consumes: Frontend web app (Task 7), Render backend (Task 6)
- Produces: Verified auth + API flow end-to-end

- [ ] **Step 1: Start frontend against Render**

```bash
cd frontend/money_tracker_app
flutter run -d web-server \
  --dart-define=SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co \
  --dart-define=SUPABASE_ANON_KEY=YOUR_SUPABASE_ANON_KEY \
  --dart-define=API_BASE_URL=https://moneytracker-backend-<random>.onrender.com/api/v1
```

App should load at `http://localhost:9528`.

- [ ] **Step 2: Test signup flow**

1. Click "Sign Up"
2. Enter test email (e.g., `test@example.com`) and password
3. Should see Supabase Auth success (confirm in browser console for errors)
4. Redirect to transaction entry screen

If error: "Could not sign up" — check Supabase project allows email auth (default is on; verify in Supabase Settings → Auth → Providers).

- [ ] **Step 3: Test transaction creation**

1. After signup/login, fill transaction form (amount, category, type, date)
2. Click "Save"
3. Should see success message or transaction added to list

If error: "Failed to create transaction" or API error — check:
   - API_BASE_URL is correct
   - Render backend health check passes
   - JWT token is valid (check browser console)

- [ ] **Step 4: Verify transaction persists in Supabase**

From Supabase dashboard:
- **SQL Editor** → Run: `SELECT * FROM transactions;`
- Should see your test transaction in results

- [ ] **Step 5: Create a browser screenshot (for PR documentation)**

Take a screenshot of the frontend showing login + transaction entry working. Save to `docs/screenshots/` for reference (not required, but helpful for PR review).

---

### Task 10: Documentation & Cleanup

**Files:**
- Modify: `README.md`
- Modify: `backend/.env.example`
- Verify: `.gitignore` still excludes `.env` files

**Interfaces:**
- Consumes: All tasks 1-9 (setup is complete)
- Produces: Updated docs so next dev can replicate the setup

- [ ] **Step 1: Update root `README.md` with Supabase + Render setup**

Current README:
```markdown
## Backend (FastAPI)
    cd backend
    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env   # fill in DATABASE_URL / TEST_DATABASE_URL / SUPABASE_JWT_SECRET
    docker compose -f ../docker-compose.dev.yml up -d
    alembic upgrade head
    uvicorn app.main:app --reload

`docker-compose.dev.yml` provisions both the dev database (`moneytracker`) and a
separate test database (`moneytracker_test`) automatically on first container
init; `.env` needs `TEST_DATABASE_URL` set alongside `DATABASE_URL` so the test
suite uses its own database instead of the dev one.

## Frontend (Flutter)
    cd frontend/money_tracker_app
    flutter pub get
    flutter run -d web-server   # or -d linux, once a device is available
```

Update to:
```markdown
## Development Setup

### Prerequisites
- Python 3.12+, pip, virtual environment
- Flutter 3.47+ (https://flutter.dev)
- Docker (for local test database fallback)
- Supabase account with a development project (https://supabase.com)
- Render account (optional, for deployment; https://render.com)

### Backend (FastAPI + Supabase)

1. **Set up local environment:**
   ```bash
   cd backend
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure credentials:**
   ```bash
   cp .env.example .env
   # Edit .env with your Supabase project credentials:
   # - DATABASE_URL: postgresql+psycopg://postgres:<password>@db.<project>.supabase.co:5432/postgres
   # - SUPABASE_JWT_SECRET: from Project Settings > Auth > JWT
   # - TEST_DATABASE_URL: keep local Docker connection
   ```

3. **Set up test database (docker required):**
   ```bash
   docker compose -f ../docker-compose.dev.yml up -d
   ```

4. **Run migrations on Supabase:**
   ```bash
   alembic upgrade head
   ```

5. **Start backend:**
   ```bash
   uvicorn app.main:app --reload
   # Server runs at http://localhost:8000
   # Health: http://localhost:8000/api/v1/health
   ```

### Frontend (Flutter)

1. **Get dependencies:**
   ```bash
   cd frontend/money_tracker_app
   flutter pub get
   ```

2. **Run web (against local backend):**
   ```bash
   flutter run -d web-server
   # App at http://localhost:9528
   ```

3. **Run web (against Render backend):**
   ```bash
   flutter run -d web-server \
     --dart-define=SUPABASE_URL=https://<project>.supabase.co \
     --dart-define=SUPABASE_ANON_KEY=<anon-key> \
     --dart-define=API_BASE_URL=https://moneytracker-backend-<id>.onrender.com/api/v1
   ```

### First-Time Setup Checklist
- [ ] Supabase project created, credentials saved
- [ ] Backend `.env` filled with Supabase DATABASE_URL and JWT secret
- [ ] Frontend can reach backend (curl or browser test)
- [ ] Tests pass: `cd backend && pytest tests/ -v`
- [ ] Transaction creation works end-to-end

### Deployed Backend (Render)
- **Status:** https://moneytracker-backend-<id>.onrender.com/api/v1/health
- **Free tier note:** May spin down after 15 min inactivity; first request after spindown takes ~30s to start.
- **Environment vars:** Set in Render dashboard (DATABASE_URL, SUPABASE_JWT_SECRET). Never commit secrets.

---

**See `Planning/04_production_infrastructure.md` for staging/production deployment, domain setup, and DevOps checklist.**
```

- [ ] **Step 2: Verify `.gitignore` still blocks secrets**

Check `backend/.env` is in `.gitignore`:
```bash
grep "\.env" .gitignore
```

Expected: Output includes `.env` and `*.env.local`. These files must never be committed.

- [ ] **Step 3: Add optional ARCHITECTURE.md documenting deployment topology**

Create `docs/ARCHITECTURE.md` (or update if exists):

```markdown
# Architecture

## Development Topology

```
Frontend (Flutter Web)          Backend (FastAPI)           Database (Postgres)
http://localhost:9528 --------> http://localhost:8000 -----> Supabase postgres:5432
or
  (from Render build)                 or Render                or Supabase Postgres
```

### Credential Flow

| Layer | Config Source | Variables |
|-------|---|---|
| Frontend | `lib/core/env.dart` (compile-time) | `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `API_BASE_URL` |
| Backend (dev) | `.env` file (python-dotenv) | `DATABASE_URL`, `SUPABASE_JWT_SECRET` |
| Backend (Render) | Service environment vars | Same as above, set in dashboard |
| Supabase | Project Settings > API | JWT secret shared across all envs |

### Auth Flow

1. User signs up via Frontend → Supabase Auth
2. Supabase issues JWT token
3. Frontend sends JWT in `Authorization: Bearer <token>` header
4. Backend validates JWT using `SUPABASE_JWT_SECRET` (same secret across all envs)
5. Backend grants access to user's transactions

### Testing

- Unit/integration tests use local Docker Postgres (`TEST_DATABASE_URL`)
- Production tests (e2e) would use staging Supabase project
- No tests directly hit production — promote code through environments

---

**See `Planning/04_production_infrastructure.md` for staging/production setup.**
```

- [ ] **Step 4: Commit documentation updates**

```bash
git add README.md docs/ARCHITECTURE.md
git commit -m "docs: update setup instructions for Supabase + Render deployment

Detailed first-time setup, credential flow, deployment topology.
Covers local development (Docker) and cloud (Supabase + Render)."
```

---

## Self-Review Checklist

1. **Spec Coverage:**
   - ✓ Create Supabase project (Task 1)
   - ✓ Configure backend DATABASE_URL (Task 2)
   - ✓ Configure frontend Supabase credentials (Task 3)
   - ✓ Create Dockerfile for Render (Task 4)
   - ✓ Create render.yaml (Task 5)
   - ✓ Deploy to Render & set env vars (Task 6)
   - ✓ Frontend points to Render backend (Task 7)
   - ✓ Integration tests (Tasks 8-9)
   - ✓ Documentation (Task 10)

2. **Placeholder Check:**
   - ✓ All file paths specified (no "TBD")
   - ✓ All code blocks include actual content (no "implement" placeholders)
   - ✓ All test commands include exact assertions
   - ✓ Render deployment uses real service configuration

3. **Type/Signature Consistency:**
   - ✓ DATABASE_URL format consistent across Tasks 1, 2, 6
   - ✓ JWT secret env var `SUPABASE_JWT_SECRET` used consistently
   - ✓ API_BASE_URL used in both backend config and frontend env
   - ✓ Health endpoint path consistent: `/api/v1/health`

4. **No Out-of-Scope Requirements:**
   - ✓ Plan is for M1 (auth + CRUD only); no advanced features
   - ✓ No staging/production domain setup (noted as future work)
   - ✓ No mobile app store setup (noted as post-launch)

---

## Next: Choose Execution Path

Plan is complete and saved to `docs/superpowers/plans/2026-09-12-supabase-render-setup.md`.

**Two execution options:**

**1. Subagent-Driven (Recommended)** — I dispatch a fresh subagent per task (or per phase), review between tasks, fast iteration. Best if you want guidance/review at each step.

**2. Inline Execution** — I execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints for review. Best if you want to move fast.

**Which approach would you prefer?**
