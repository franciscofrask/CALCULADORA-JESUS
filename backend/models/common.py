"""
Modelos Pydantic para rutinas, reportes, mensajes y pagos.
"""
from pydantic import BaseModel, ConfigDict
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
    training_compliance: Optional[int] = None
    nutrition_compliance: Optional[int] = None
    sleep_quality: Optional[int] = None
    energy_level: Optional[int] = None
    stress_level: Optional[int] = None
    notes: Optional[str] = None

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
    trainer_feedback: Optional[str] = None
    created_at: str

# Check-In Models (3 niveles: daily, weekly, monthly) - portado de calmajp
class CheckInCreate(BaseModel):
    type: str  # "daily" | "weekly" | "monthly"
    # Daily (check-in de 10 segundos)
    mood: Optional[int] = None              # 1-5
    energy: Optional[int] = None            # 1-5 (o 1-10 en weekly)
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

# Message Models
class MessageCreate(BaseModel):
    receiver_id: str
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
    success_path: Optional[str] = "/onboarding?checkout=success"
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
