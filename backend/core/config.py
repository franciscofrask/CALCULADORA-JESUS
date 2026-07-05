"""
Configuración centralizada de la aplicación.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / '.env')

# Database
MONGO_URL = os.environ['MONGO_URL']
DB_NAME = os.environ['DB_NAME']

# JWT
JWT_SECRET = os.environ.get('JWT_SECRET', '12en12-secret-key')
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

if JWT_SECRET in ('12en12-secret-key', '12en12-super-secret-jwt-key-2024') or len(JWT_SECRET) < 32:
    import logging
    logging.getLogger("uvicorn.error").warning(
        "JWT_SECRET debil o por defecto: configura una clave aleatoria de 32+ caracteres en el .env / variables de Render"
    )

# CORS
CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*').split(',')

# Stripe (billing). Test mode by default: STRIPE_SECRET_KEY must be sk_test_...
STRIPE_API_VERSION = "2026-02-25.clover"
STRIPE_ALLOW_LIVE_MODE = os.environ.get('STRIPE_ALLOW_LIVE_MODE', 'false').strip().lower() == 'true'
# Frontend base URL for Stripe success/cancel redirects. Falls back to first CORS origin, else localhost:3000.
FRONTEND_URL = (os.environ.get('FRONTEND_URL') or os.environ.get('APP_BASE_URL') or '').strip()

# Billing cycle (matches calmajp: 12 weeks = 84 days). Change here if cobro mensual.
DEFAULT_BILLING_CYCLE_WEEKS = 12
DEFAULT_BILLING_CYCLE_DAYS = DEFAULT_BILLING_CYCLE_WEEKS * 7
