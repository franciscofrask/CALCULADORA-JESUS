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
    # UNA fila por (cliente, fecha de vigencia) -- punto 62. El upsert de
    # `core/historial_macros.py` es quien lo hace bien; este indice es el cinturon: cierra
    # la carrera de dos guardados a la vez, que el upsert por si solo no cierra.
    # Parcial porque las filas viejas pueden no tener effective_date, y un unique con
    # varios null en la misma clave chocaria.
    await _ensure("macro_history", [("client_id", 1), ("effective_date", 1)], unique=True,
                  name="una_por_cliente_y_fecha",
                  partialFilterExpression={"client_id": {"$type": "string"},
                                           "effective_date": {"$type": "string"}})
    # Las filas sustituidas: no se pintan en ningun sitio, se consultan cuando hace falta
    # saber quien escribio que.
    await _ensure("macro_history_auditoria", [("client_id", 1), ("effective_date", -1)])
    # EL CUADERNO DE CICLOS (`core/ciclos.py`; doc de Jesus del 2-09, Francisco el 4-09:
    # «cuando renueva no podemos perder el ciclo anterior»). UNA fila por (cliente, dia de
    # inicio): los avisos de Stripe se repiten -- un `customer.subscription.updated` llega
    # varias veces con el mismo periodo, y dos pueden llegar a la vez --. `abrir_ciclo` mira
    # antes si ya esta, pero mirar-y-escribir no cierra la carrera; este unico si.
    await _ensure("ciclos", [("client_id", 1), ("inicio", 1)], unique=True,
                  name="un_ciclo_por_cliente_y_dia")
    # El ciclo abierto del cliente (`fin: None`) y el de un dia concreto se buscan por aqui.
    await _ensure("ciclos", [("client_id", 1), ("fin", 1)])
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
    # Motor de macros v2: respuestas del quiz (append-only, para calibrar el modelo
    # predictivo) y revisiones pendientes de dieta reportada que no cuadra.
    await _ensure("quiz_respuestas", [("client_id", 1), ("created_at", -1)])
    await _ensure("macro_revisiones", [("trainer_id", 1), ("status", 1), ("created_at", -1)])
    # Registro de sesiones de entreno (T3 del doc 16-08): UNA por cliente y día. El
    # guardado es un upsert por (client_id, fecha); el unique cierra la carrera de dos
    # guardados a la vez. `fecha` es el día del cliente (hora de España), "YYYY-MM-DD".
    await _ensure("workout_logs", [("client_id", 1), ("fecha", 1)], unique=True)
    # Rotación de textos de los avisos (regla 6 del doc 16-08): la última variante de
    # cada familia se busca por aquí.
    await _ensure("notifications", [("user_id", 1), ("familia", 1), ("created_at", -1)],
                  partialFilterExpression={"familia": {"$type": "string"}})
    # Sesiones del chatbot persistidas: TTL de 7 días desde la última interacción.
    await _ensure("chatbot_sessions", "session_id", unique=True)
    await _ensure("chatbot_sessions", "updated_at", expireAfterSeconds=7 * 24 * 3600)
    # La traza de cada turno del asistente (`core/trazas_chat`). Caduca a los 30 días: es
    # para diagnosticar, no un archivo. Más margen que las sesiones porque un fallo se
    # reporta días después, y la sesión ya no está cuando llega el vídeo.
    await _ensure("chat_traces", [("user_id", 1), ("created_at", -1)])
    await _ensure("chat_traces", [("session_id", 1), ("created_at", 1)])
    await _ensure("chat_traces", "created_at", expireAfterSeconds=30 * 24 * 3600)
    # Puerta anti fuerza bruta del login/registro (`core/rate_limit.py`). Se cuentan las
    # marcas recientes por clave (compuesto clave+cuando), y caducan solas a las 2 horas:
    # más que la ventana más larga (1 h del "olvidé la contraseña"), con margen de sobra.
    # `cuando` es un Date real para que el TTL lo borre; un índice TTL debe ir sobre un
    # solo campo, por eso va aparte del compuesto.
    await _ensure("intentos_auth", [("clave", 1), ("cuando", 1)])
    await _ensure("intentos_auth", "cuando", expireAfterSeconds=2 * 3600)
    # EL PDF DE LA RUTINA (`db.rutina_pdfs`). El índice que `routes/workout_logs.py` y
    # `routes/routines.py` llevaban dos comentarios prometiendo y que no estaba: medido en
    # producción el 24-08, `index_information()` solo devolvía `_id_`.
    #
    # POR QUÉ IMPORTA MÁS DE LO QUE PARECE PARA 35 FILAS: cada fila lleva el PDF ENTERO
    # dentro (hasta `MAX_PDF_BYTES`, 15 MB), así que la colección son 15,2 MB en 35
    # documentos. Sin índice, `tiene_rutina_puesta()` hace un COLLSCAN -- comprobado con
    # explain contra producción: `totalDocsExamined: 35` para un cliente que no tiene PDF --
    # y desde el arreglo del 24-08 (punto 51) eso se llama en CADA carga del cierre del día.
    # Al que NO tiene PDF se le leen todas antes de contestar que no. Con los 165 clientes
    # a los que hay que subírsela, eso es medio giga recorrido por apertura de pantalla.
    #
    # Compuesto y no solo `client_id` a propósito: los `find_one({"client_id": ...},
    # sort=[("uploaded_at", -1)])` de `routines.py` (la última entrega del cliente) salen
    # del propio índice y se ahorran también el ordenado en memoria.
    await _ensure("rutina_pdfs", [("client_id", 1), ("uploaded_at", -1)])
    # El PDF que se entrega al que COMPRA la rutina del mes (`routes/routines.py`). Una
    # sola fila vigente; el índice es para que buscarla no dependa de cuántas se archiven.
    await _ensure("rutina_mes_pdf", [("vigente", 1), ("uploaded_at", -1)])
    # EL MOMENTO DEL DÍA DE LOS MENÚS DE LA BIBLIOTECA (29-08). Desde que «Sugiéreme un
    # menú» filtra por momento y no por posición, esta es la consulta que se hace sobre las
    # 266.199 filas, y va con los mismos macros detrás que el índice de `tipo_comida` que ya
    # había: sin él, pedir meriendas recorre la colección entera.
    await _ensure("meal_library", [("momentos", 1), ("macros.P", 1),
                                   ("macros.H", 1), ("macros.G", 1)])

async def close_connection():
    """Cerrar conexión a MongoDB."""
    client.close()
