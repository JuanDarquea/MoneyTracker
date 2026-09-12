# MoneyTracker

Personal finance tracker (mobile + web). See `Planning/` for the full
product spec, agent structure, testing strategy, and production plan.

## Backend (FastAPI)

    cd backend
    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env   # fill in DATABASE_URL / SUPABASE_JWT_SECRET
    docker compose -f ../docker-compose.dev.yml up -d
    alembic upgrade head
    uvicorn app.main:app --reload

## Frontend (Flutter)

    cd frontend/money_tracker_app
    flutter pub get
    flutter run -d web-server   # or -d linux, once a device is available
