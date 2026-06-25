"""
JG12 API Routes
"""
from .auth import router as auth_router
from .users import router as users_router
from .admin import router as admin_router
from .calculator import router as calculator_router
from .diets import router as diets_router
from .chatbot import router as chatbot_router
from .routines import router as routines_router, admin_router as routines_admin_router
from .reports import router as reports_router
from .messages import router as messages_router
from .payments import router as payments_router
from .billing import (
    router as billing_router,
    webhook_router as billing_webhook_router,
    admin_router as billing_admin_router,
)

__all__ = [
    "auth_router",
    "users_router", 
    "admin_router",
    "calculator_router",
    "diets_router",
    "chatbot_router",
    "routines_router",
    "routines_admin_router",
    "reports_router",
    "messages_router",
    "payments_router",
    "billing_router",
    "billing_webhook_router",
    "billing_admin_router",
]
