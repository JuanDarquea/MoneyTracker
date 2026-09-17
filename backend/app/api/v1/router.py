from fastapi import APIRouter

from app.api.v1 import budget, categories, health, summary, transactions

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(categories.router)
api_router.include_router(transactions.router)
api_router.include_router(summary.router)
api_router.include_router(budget.router)
