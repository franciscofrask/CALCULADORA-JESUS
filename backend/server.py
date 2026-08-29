"""
JG12 API Server - Refactored
============================
Main FastAPI application with modular routes.
"""
from fastapi import FastAPI, APIRouter
from starlette.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import logging
import os

from core.config import CORS_ORIGINS
from core.database import create_indexes, close_connection
from routes import (
    auth_router,
    users_router,
    admin_router,
    calculator_router,
    diets_router,
    chatbot_router,
    chat_traces_router,
    routines_router,
    routines_admin_router,
    supplements_router,
    supplements_admin_router,
    reports_router,
    reports_admin_router,
    checkins_router,
    messages_router,
    payments_router,
    billing_router,
    billing_webhook_router,
    billing_admin_router,
)
from routes.leads import router as leads_router
from routes.menu_templates import router as menu_templates_router
from routes.biblioteca_menus import router as biblioteca_menus_router
from routes.tareas import router as tareas_router
from routes.pagos_historicos import router as pagos_historicos_router
from routes.notifications import router as notifications_router
from routes.audit import router as audit_router
from routes.plans import router as plans_router, admin_router as plans_admin_router
from routes.settings import router as settings_router, admin_router as settings_admin_router
from routes.workout_logs import router as workout_logs_router
from routes.paneles import router as paneles_router
from routes.diary import router as diary_router
from routes.report_cadence import (
    router as report_cadence_router,
    client_router as report_due_router,
)

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
    # Los correos de avisos (P59, doc 23-08): un bucle de fondo cada 15 minutos.
    # Detrás del interruptor `correos_avisos` (apagado de fábrica) y con dedupe por
    # índice único, así las dos réplicas pueden llevarlo sin mandar nada dos veces.
    from core.correo_avisos import bucle_de_correos
    tarea_correos = asyncio.create_task(bucle_de_correos())
    yield
    # Shutdown
    tarea_correos.cancel()
    logger.info("Shutting down JG12 API...")
    await close_connection()

# LA DOCUMENTACION DE LA API VA CERRADA salvo que se pida a proposito con API_DOCS=1.
#
# FastAPI publica /docs, /redoc y /openapi.json sin ninguna llave, y ahi dentro esta el mapa
# completo de la casa: las 226 rutas, que parametros acepta cada una y la forma exacta de
# cada modelo. Eso no es un manual, es un indice para el que busca por donde entrar. Medido
# en produccion el 24-08: 134 peticiones a /docs en una hora desde una sola IP de fuera,
# mas que cualquier endpoint de verdad de la app.
#
# Por defecto CERRADO, que es lo que hace que produccion quede tapada sin tener que acordarse
# de nada: alli esa variable no existe. En el .env de desarrollo va API_DOCS=1 y se sigue
# trabajando igual. Nada de la app las llama, ni el frontend ni los tests ni los guiones de
# _guia: se comprobo antes de cerrarlas.
DOCS_ABIERTAS = os.environ.get("API_DOCS", "").strip() in ("1", "true", "True", "si", "sí")

# Create FastAPI app
app = FastAPI(
    title="JG12 - Plataforma de Entrenamiento Personal",
    description="API para la plataforma de entrenamiento personal JG12 con calculadora CALMA",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs" if DOCS_ABIERTAS else None,
    redoc_url="/redoc" if DOCS_ABIERTAS else None,
    openapi_url="/openapi.json" if DOCS_ABIERTAS else None,
)
logger.info("Documentacion de la API: %s",
            "ABIERTA en /docs (API_DOCS=1)" if DOCS_ABIERTAS else "cerrada")

# CORS middleware
#
# Se registra en el log de arranque QUE ORIGENES quedan permitidos. Sin esto, una lista mal
# escrita en las variables del servidor solo se nota cuando alguien no puede entrar, y desde
# el navegador parece un fallo de credenciales: la peticion ni sale, asi que el backend no
# tiene ni constancia del intento. Con la linea en el log se mira y se acabo.
logging.getLogger("uvicorn.error").info("CORS permitido para: %s", CORS_ORIGINS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# SIN PLAN NO SE USA LA APP (Francisco, 29-08-2026). Va como middleware y no como
# dependencia de cada ruta a propósito: la regla es «no puede usar el sistema», y puesta
# endpoint por endpoint el agujero vuelve con la siguiente ruta que se añada. El porqué,
# lo que queda abierto y quién no pasa por aquí, en `core/candado_de_plan`.
from core.candado_de_plan import candado_de_plan  # noqa: E402

app.middleware("http")(candado_de_plan)

# Manejadores globales de errores de entrada que, si no, saldrían como 500.
# Un número entero enorme (> int64) revienta al escribir en MongoDB (OverflowError);
# lo convertimos en un 400 limpio para TODOS los endpoints de una vez, en vez de
# validar el rango campo por campo. Igual para documentos con claves inválidas.
from fastapi.responses import JSONResponse
from bson.errors import InvalidDocument


@app.exception_handler(OverflowError)
async def _overflow_handler(request, exc):
    return JSONResponse(status_code=400, content={"detail": "Valor numérico fuera de rango."})


@app.exception_handler(InvalidDocument)
async def _invalid_document_handler(request, exc):
    return JSONResponse(status_code=400, content={"detail": "Datos con formato no válido."})

# Main API router
api_router = APIRouter(prefix="/api")

# Root endpoints
@api_router.get("/")
async def root():
    return {"message": "JG12 API v2.0", "status": "running"}

@api_router.get("/health")
async def health():
    return {"status": "healthy"}

# Include all routers
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(admin_router)
api_router.include_router(calculator_router)
api_router.include_router(diets_router)
api_router.include_router(chatbot_router)
api_router.include_router(chat_traces_router)
api_router.include_router(routines_router)
api_router.include_router(routines_admin_router)
api_router.include_router(supplements_router)
api_router.include_router(supplements_admin_router)
api_router.include_router(reports_router)
api_router.include_router(reports_admin_router)
api_router.include_router(checkins_router)
api_router.include_router(messages_router)
api_router.include_router(payments_router)
api_router.include_router(billing_router)
api_router.include_router(billing_webhook_router)
api_router.include_router(billing_admin_router)
api_router.include_router(leads_router)
api_router.include_router(menu_templates_router)
api_router.include_router(biblioteca_menus_router)
api_router.include_router(tareas_router)
api_router.include_router(pagos_historicos_router)
api_router.include_router(notifications_router)
api_router.include_router(audit_router)
api_router.include_router(plans_router)
api_router.include_router(plans_admin_router)
api_router.include_router(settings_router)
api_router.include_router(settings_admin_router)
api_router.include_router(workout_logs_router)
api_router.include_router(diary_router)
api_router.include_router(report_cadence_router)
api_router.include_router(report_due_router)
# Los cuatro paneles del doc 19-08 (bloque 12).
api_router.include_router(paneles_router)

# Mount API router
app.include_router(api_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
