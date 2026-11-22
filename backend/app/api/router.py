from fastapi import APIRouter
from backend.app.api.routes import health, customer, admin

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(customer.router)
api_router.include_router(admin.router)
