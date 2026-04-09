"""
JG12 API Server - Refactored
============================
Main FastAPI application with modular routes.
"""
from fastapi import FastAPI, APIRouter
from starlette.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from core.config import CORS_ORIGINS
from core.database import create_indexes, close_connection
from routes import (
    auth_router,
    users_router,
    admin_router,
    calculator_router,
    diets_router,
    chatbot_router,
    routines_router,
    routines_admin_router,
    reports_router,
    messages_router,
    payments_router
)
from models.user import PLAN_TYPES

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting JG12 API...")
    await create_indexes()
    logger.info("Database indexes created successfully")
    yield
    # Shutdown
    logger.info("Shutting down JG12 API...")
    await close_connection()

# Create FastAPI app
app = FastAPI(
    title="JG12 - Plataforma de Entrenamiento Personal",
    description="API para la plataforma de entrenamiento personal JG12 con calculadora CALMA",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS if CORS_ORIGINS != ['*'] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Main API router
api_router = APIRouter(prefix="/api")

# Root endpoints
@api_router.get("/")
async def root():
    return {"message": "JG12 API v2.0", "status": "running"}

@api_router.get("/health")
async def health():
    return {"status": "healthy"}

@api_router.get("/plans")
async def get_plans():
    return PLAN_TYPES

# Include all routers
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(admin_router)
api_router.include_router(calculator_router)
api_router.include_router(diets_router)
api_router.include_router(chatbot_router)
api_router.include_router(routines_router)
api_router.include_router(routines_admin_router)
api_router.include_router(reports_router)
api_router.include_router(messages_router)
api_router.include_router(payments_router)

# Mount API router
app.include_router(api_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
