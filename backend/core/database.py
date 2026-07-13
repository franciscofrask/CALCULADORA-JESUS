"""
Conexión a MongoDB y funciones de base de datos.
"""
from motor.motor_asyncio import AsyncIOMotorClient
from .config import MONGO_URL, DB_NAME

# MongoDB connection
client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

async def create_indexes():
    """Crear índices necesarios en MongoDB.

    Cada índice se crea de forma independiente: si uno falla (p.ej. un índice
    preexistente con opciones distintas, como stripe_invoice_id sparse vs partial),
    se registra y se continúa con el resto en vez de abortar todos.
    """
    async def _ensure(collection, keys, **opts):
        try:
            await db[collection].create_index(keys, **opts)
        except Exception as e:
            print(f"[indexes] {collection} {keys}: {e}")

    await _ensure("foods", [("nombre", "text")])
    await _ensure("foods", "id", unique=True)
    await _ensure("foods", "categorias")
    await _ensure("diets", [("user_id", 1), ("fecha", 1)], unique=True)
    await _ensure("users", "email", unique=True)
    await _ensure("client_profiles", "user_id", unique=True)
    # Stripe: unique only when the field is a string (partial), so múltiples perfiles sin
    # customer/subscription no chocan por valores null repetidos.
    await _ensure("client_profiles", "stripe_customer_id", unique=True,
                  partialFilterExpression={"stripe_customer_id": {"$type": "string"}})
    await _ensure("client_profiles", "stripe_subscription_id", unique=True,
                  partialFilterExpression={"stripe_subscription_id": {"$type": "string"}})
    await _ensure("stripe_events", "id", unique=True)
    await _ensure("payments", "stripe_invoice_id", unique=True,
                  partialFilterExpression={"stripe_invoice_id": {"$type": "string"}})
    await _ensure("alerts", [("client_id", 1), ("type", 1), ("resolved", 1)])
    # Check-ins (seguimiento) y fotos de progreso.
    await _ensure("checkins", [("client_id", 1), ("created_at", -1)])
    await _ensure("checkins", [("client_id", 1), ("type", 1), ("created_at", -1)])
    await _ensure("client_photos", "id", unique=True)
    await _ensure("client_photos", [("client_id", 1), ("taken_at", -1)])
    await _ensure("client_photos", [("user_id", 1), ("taken_at", -1)])
    # Rendimiento (auditoría 2026-07-06): índices para las consultas reales más frecuentes.
    await _ensure("client_profiles", "status")                          # dashboard, listados
    await _ensure("client_profiles", [("status", 1), ("next_payment", 1)])  # próximos cobros
    await _ensure("leads", "status")                                    # kanban, stats, badge
    # Único parcial: no puede haber dos leads con el mismo email (solo si el email no está
    # vacío). Cierra la carrera de dos webhooks simultáneos del mismo contacto.
    await _ensure("leads", "email", unique=True,
                  partialFilterExpression={"email": {"$type": "string", "$gt": ""}})
    # sparse: coincide con el índice preexistente en Atlas (evita IndexKeySpecsConflict).
    # Filtramos por un assigned_to concreto (staff id), nunca por null, así que sparse es correcto.
    await _ensure("leads", "assigned_to", sparse=True)                  # filtro responsable
    await _ensure("messages", [("receiver_id", 1), ("read", 1)])        # unread-count (badge)
    await _ensure("messages", [("sender_id", 1), ("created_at", -1)])   # conversaciones
    await _ensure("messages", [("receiver_id", 1), ("created_at", -1)])
    await _ensure("reports", [("client_id", 1), ("created_at", -1)])    # ficha, at-risk
    await _ensure("macro_history", [("client_id", 1), ("effective_date", -1)])  # macros por fecha
    await _ensure("routines", [("client_id", 1), ("status", 1)])        # rutina activa, overview
    await _ensure("diet_favorites", "user_id")                          # dietas favoritas
    await _ensure("food_favorites", "user_id", unique=True)             # alimentos favoritos
    await _ensure("payments", [("client_id", 1), ("created_at", -1)])   # historial de pagos
    await _ensure("users", "role")                                      # trainers, staff
    await _ensure("notifications", [("user_id", 1), ("read", 1)])       # campanita cliente
    await _ensure("notifications", [("user_id", 1), ("created_at", -1)])
    await _ensure("audit_log", [("created_at", -1)])                    # registro de auditoría
    # Sugerencias de alimentos por clientes y sus fotos (frontal/reverso).
    await _ensure("food_suggestions", "id", unique=True)
    await _ensure("food_suggestions", [("status", 1), ("created_at", -1)])   # panel admin por estado
    await _ensure("food_suggestions", [("client_id", 1), ("created_at", -1)])  # límite semanal + mis sugerencias
    await _ensure("food_suggestion_photos", [("suggestion_id", 1), ("kind", 1)])
    # Envíos de reportes del coach (cadencia quincenal/mensual/semanal por plan).
    await _ensure("coach_reports", [("client_id", 1), ("tipo", 1), ("due_date", 1)], unique=True)

async def close_connection():
    """Cerrar conexión a MongoDB."""
    client.close()
