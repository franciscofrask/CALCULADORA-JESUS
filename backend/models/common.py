"""
Modelos Pydantic para rutinas, reportes, mensajes y pagos.
"""
from datetime import datetime, date
from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional, Dict, List, Any

# Routine Models
class Exercise(BaseModel):
    name: str
    sets: int
    reps: str
    rest: str
    video_url: Optional[str] = None
    notes: Optional[str] = None

class RoutineDay(BaseModel):
    day: str
    is_rest: bool = False
    exercises: List[Exercise] = []
    cardio: Optional[Dict[str, Any]] = None

class RoutineCreate(BaseModel):
    client_id: str
    instructions: Optional[str] = None

class RoutineResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    client_id: str
    days: List[RoutineDay]
    trainer_notes: Optional[str] = None
    created_at: str
    status: str = "active"

# Report Models
class ReportCreate(BaseModel):
    weight: float
    measurements: Optional[Dict[str, float]] = None
    photos: Optional[List[str]] = None
    # Confirmación de huecos: {"dieta": "no_lo_hice"|"si_pero_no_apunte", "entrenamiento": ...}.
    # De aquí sale el cumplimiento; los dos campos de abajo quedan por compatibilidad con
    # los reportes viejos, que sí traían los deslizadores.
    huecos: Optional[Dict[str, str]] = None
    training_compliance: Optional[int] = None
    nutrition_compliance: Optional[int] = None
    sleep_quality: Optional[int] = None
    energy_level: Optional[int] = None
    stress_level: Optional[int] = None
    notes: Optional[str] = None
    # Las tres preguntas del formulario de siempre de Jesus que faltaban (punto 5 del
    # documento del 05-08):
    #  - `proximo_objetivo` DISPARA EL CAMBIO DE FASE: sin ella un Nivel 1 no puede cambiar
    #    de fase nunca, porque no tiene coach que se la cambie. Ademas es la que permite
    #    fechar el inicio de la fase (foto de "inicio de fase" del informe).
    #  - `viabilidad_ajuste` es el margen de la persona preguntado directamente: hasta ahora
    #    solo se sabia del cuestionario inicial, que se responde una vez y envejece.
    #  - `cumplimiento_entreno` devuelve la fuente a la barra de entrenos del informe, que
    #    se quedo sin dato en julio al recortar el check-in diario.
    proximo_objetivo: Optional[str] = None       # definicion | volumen | mantenimiento
    viabilidad_ajuste: Optional[str] = None      # me_adapto | necesito_mas | necesito_menos
    cumplimiento_entreno: Optional[str] = None   # todos | casi_todos | la_mitad | pocos | ninguno

class ReportResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    client_id: str
    weight: float
    measurements: Optional[Dict[str, float]] = None
    photos: Optional[List[str]] = None
    training_compliance: Optional[int] = None
    nutrition_compliance: Optional[int] = None
    sleep_quality: Optional[int] = None
    energy_level: Optional[int] = None
    stress_level: Optional[int] = None
    notes: Optional[str] = None
    proximo_objetivo: Optional[str] = None
    viabilidad_ajuste: Optional[str] = None
    cumplimiento_entreno: Optional[str] = None
    trainer_feedback: Optional[str] = None
    created_at: str

# Check-In Models (3 niveles: daily, weekly, monthly) - portado de calmajp
class CheckInCreate(BaseModel):
    type: str  # "daily" | "weekly" | "monthly"
    # Daily · DOS campos (documento 31-07-2026, partes 6 y 7.2): "solo lo que no está en
    # ningún dato: energía, y ansiedad y hambre. Lo de la dieta y el entreno se rellena
    # solo con lo registrado". `mood`, `trained` y `nutrition_followed` ya no se piden:
    # los dos últimos los deduce el servidor, y se conservan aquí por los check-ins viejos.
    energy: Optional[int] = None            # 1-5 (o 1-10 en weekly)
    hunger_anxiety: Optional[int] = None    # 1-5 · ansiedad y hambre (saturación en volumen)
    # Lo que ha comido hoy, con sus palabras (punto 18 del doc del 07-08). No es la dieta
    # planificada -- esa ya está en la app y el servidor la rellena solo -- sino lo que se ha
    # comido de verdad. Sirve para dos cosas, y las dos las dice Jesús: al cliente le hace
    # tomar conciencia de lo que se lleva a la boca, y a él le explica por qué alguien coge
    # peso sin saber por qué (el picoteo que nadie apunta en la dieta).
    comido_hoy: Optional[str] = None
    mood: Optional[int] = None
    trained: Optional[bool] = None
    nutrition_followed: Optional[bool] = None
    # Weekly
    weight: Optional[float] = None
    training_compliance: Optional[int] = None    # 0-100
    nutrition_compliance: Optional[int] = None   # 0-100
    sleep_quality: Optional[int] = None          # 1-10
    stress_level: Optional[int] = None           # 1-10
    # Monthly
    measurements: Optional[Dict[str, float]] = None
    body_fat_pct: Optional[float] = None
    photos: Optional[List[str]] = None
    goals_progress: Optional[str] = None
    challenges: Optional[str] = None
    # Común
    notes: Optional[str] = None

class CheckInResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    client_id: str
    type: str
    mood: Optional[int] = None
    energy: Optional[int] = None
    hunger_anxiety: Optional[int] = None
    comido_hoy: Optional[str] = None
    trained: Optional[bool] = None
    nutrition_followed: Optional[bool] = None
    weight: Optional[float] = None
    training_compliance: Optional[int] = None
    nutrition_compliance: Optional[int] = None
    sleep_quality: Optional[int] = None
    stress_level: Optional[int] = None
    measurements: Optional[Dict[str, float]] = None
    body_fat_pct: Optional[float] = None
    photos: Optional[List[str]] = None
    goals_progress: Optional[str] = None
    challenges: Optional[str] = None
    notes: Optional[str] = None
    trainer_feedback: Optional[str] = None
    created_at: str

    # Los check-ins migrados de Calma guardan created_at como datetime (los que crea
    # la app lo guardan como texto ISO). Sin esto, un solo registro migrado tumbaba
    # la respuesta entera con un 500 y el coach no veia ningun check-in.
    @field_validator("created_at", mode="before")
    @classmethod
    def _fecha_a_texto(cls, v):
        if isinstance(v, (datetime, date)):
            return v.isoformat()
        return v

# Message Models
class MessageCreate(BaseModel):
    # Opcional: si no se indica (o "support"), el backend lo resuelve al coach del
    # cliente o al primer admin (ver _resolve_receiver en routes/messages.py).
    receiver_id: Optional[str] = None
    content: str

class MessageResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    sender_id: str
    receiver_id: str
    content: str
    read: bool = False
    created_at: str

# Payment Models (Mocked)
class PaymentResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    client_id: str
    amount: float
    status: str
    method: str = "card"
    currency: Optional[str] = None
    stripe_invoice_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    failure_code: Optional[str] = None
    failure_message: Optional[str] = None
    paid_at: Optional[str] = None
    created_at: str

# ---- Stripe billing ----
class CheckoutSessionRequest(BaseModel):
    plan: str
    # La pantalla de planes es /planes (documento 31-07). /onboarding redirige allí, así
    # que un pago que volviera a la vieja perdía el session_id por el camino.
    success_path: Optional[str] = "/planes?checkout=success"
    cancel_path: Optional[str] = "/onboarding?checkout=canceled"

class CheckoutSessionResponse(BaseModel):
    checkout_url: str
    session_id: Optional[str] = None
    profile_id: Optional[str] = None

class BillingPortalResponse(BaseModel):
    url: str

class AlertResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    client_id: str
    type: str
    severity: str
    title: str
    message: str
    related_data: Optional[Dict[str, Any]] = None
    acknowledged: bool = False
    resolved: bool = False
    created_at: str

# Food Suggestion Models
class FoodSuggestion(BaseModel):
    """Datos que rellena el cliente al sugerir un alimento (formulario del proceso).
    Los nombres de campo replican los del documento de `db.foods` para que la
    aprobación por el admin sea una copia directa al catálogo."""
    nombre: str
    por_unidad: bool = False          # False = valores por 100 g; True = por unidad
    racion: float = 100.0             # gramos de la ración (100 si por 100 g; peso de la unidad si por_unidad)
    peso_tipo: str = "neto"           # "neto" | "escurrido" (informativo; el admin lo revisa a mano)
    proteinas: float = 0.0
    hidratos: float = 0.0
    grasas: float = 0.0
    url: Optional[str] = None         # enlace a la fuente de los datos nutricionales

class FoodSuggestionUpdate(BaseModel):
    """Campos que el admin puede editar de una sugerencia durante la revisión."""
    model_config = ConfigDict(extra="ignore")
    nombre: Optional[str] = None
    por_unidad: Optional[bool] = None
    racion: Optional[float] = None
    proteinas: Optional[float] = None
    hidratos: Optional[float] = None
    grasas: Optional[float] = None
    url: Optional[str] = None
    categorias: Optional[str] = None   # categorías asignadas por el admin (pipe: "2.2|FRE")
    admin_notes: Optional[str] = None

class AdminFoodCreate(BaseModel):
    """Alta directa de un alimento en el catálogo desde el panel admin."""
    model_config = ConfigDict(extra="ignore")
    nombre: str
    por_unidad: bool = False
    racion: float = 100.0
    proteinas: float = 0.0
    hidratos: float = 0.0
    grasas: float = 0.0
    url: Optional[str] = None
    categorias: Optional[str] = None

class FoodSuggestionResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    client_id: str
    food: FoodSuggestion
    status: str = "pending"
    created_at: str
    categorias: Optional[str] = None
    admin_notes: Optional[str] = None
    photos: List[str] = []            # tipos de foto subidos: "frontal" y/o "reverso"
