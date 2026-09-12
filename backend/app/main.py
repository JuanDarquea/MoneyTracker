from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings

app = FastAPI(title="MoneyTracker API", version="0.1.0")

# Dev-stage CORS: allows the Flutter web dev server (flutter run -d
# web-server / chrome, which binds various localhost ports) to reach the
# API from the browser. This allow-list MUST be tightened to the real
# production domain before launch, per Planning/04_production_infrastructure.md.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")
