"""
Modelos Pydantic para usuarios y autenticación.
"""
from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional, Dict, List, Any

# Plan Types
# stripe_price_env: nombre de la variable .env que guarda el Price ID de Stripe (lo escribe setup_stripe_products.py).
# billing_cycle_weeks: longitud del ciclo de cobro recurrente (12 = 84 días, como calmajp).
PLAN_TYPES = {
    "gold": {"name": "Gold", "price": 149, "stripe_price_env": "STRIPE_PRICE_GOLD", "billing_cycle_weeks": 12, "features": ["rutina", "macros", "chat", "reporte_quincenal", "suplementacion", "cardio", "audio"]},
    "silver": {"name": "Silver", "price": 99, "stripe_price_env": "STRIPE_PRICE_SILVER", "billing_cycle_weeks": 12, "features": ["rutina", "macros", "chat", "reporte_mensual"]},
    "bronze": {"name": "Bronze", "price": 69, "stripe_price_env": "STRIPE_PRICE_BRONZE", "billing_cycle_weeks": 12, "features": ["rutina", "macros", "chat", "reporte_mensual"]},
    "elm": {"name": "ELM", "price": 39, "stripe_price_env": "STRIPE_PRICE_ELM", "billing_cycle_weeks": 12, "features": ["macros", "chat"]}
}

# Auth Models
class UserRegister(BaseModel):
    email: EmailStr
    password: str
    name: str
    phone: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    email: str
    name: str
    phone: Optional[str] = None
    role: str
    plan: Optional[str] = None
    trainer_id: Optional[str] = None
    created_at: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

# Client Profile Models
class ClientProfile(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    user_id: str
    plan: str
    price: float
    week: int = 1
    status: str = "activo"
    trainer_id: Optional[str] = None
    next_payment: Optional[str] = None
    macros_training: Optional[Dict[str, float]] = None
    macros_rest: Optional[Dict[str, float]] = None
    macros_periworkout: Optional[Dict[str, float]] = None
    macros_source: Optional[str] = None
    macros_multiplicadores: Optional[Dict[str, float]] = None
    # Coach-set (Calma quiereRepartoDeComidas=false): the whole day's macros go to ONE comida.
    single_meal_mode: Optional[bool] = None
    weight: Optional[float] = None
    height: Optional[float] = None
    age: Optional[int] = None
    sex: Optional[str] = None
    goal: Optional[str] = None
    body_fat: Optional[float] = None
    equipment: Optional[List[str]] = None
    injuries: Optional[List[str]] = None
    training_days: Optional[int] = None
    # Cuestionario inicial obligatorio (ELM): respuestas y flag de completado.
    questionnaire_completed: Optional[bool] = None
    birthdate: Optional[str] = None
    training_experience: Optional[str] = None
    activity_level: Optional[str] = None
    biotype: Optional[str] = None
    # Onboarding guiado (tour de producto): progreso por usuario.
    onboarding_completed: Optional[bool] = None
    onboarding_step: Optional[str] = None
    # ---- Stripe billing (suscripción) ----
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    stripe_price_id: Optional[str] = None
    subscription_status: Optional[str] = None        # active|trialing|past_due|canceled|incomplete|...
    checkout_status: Optional[str] = None            # draft|created|completed|attention_required
    current_period_start: Optional[str] = None
    current_period_end: Optional[str] = None
    cancel_at_period_end: Optional[bool] = None
    billing_cycle_days: Optional[int] = None
    payment_method_status: Optional[str] = None      # ok|caducada|actualizar_tarjeta
    payment_method_brand: Optional[str] = None
    payment_method_last4: Optional[str] = None
    payment_method_exp_month: Optional[int] = None
    payment_method_exp_year: Optional[int] = None
    payment_failure_count: Optional[int] = None
    last_payment_error: Optional[str] = None
    created_at: str

class ClientProfileCreate(BaseModel):
    plan: str
    price: Optional[float] = None
    trainer_id: Optional[str] = None

class ClientProfileUpdate(BaseModel):
    plan: Optional[str] = None
    price: Optional[float] = None
    week: Optional[int] = None
    status: Optional[str] = None
    trainer_id: Optional[str] = None
    macros_training: Optional[Dict[str, float]] = None
    macros_rest: Optional[Dict[str, float]] = None
    macros_periworkout: Optional[Dict[str, float]] = None
    macros_source: Optional[str] = None
    single_meal_mode: Optional[bool] = None
    weight: Optional[float] = None
    height: Optional[float] = None
    age: Optional[int] = None
    sex: Optional[str] = None
    goal: Optional[str] = None
    body_fat: Optional[float] = None
    equipment: Optional[List[str]] = None
    injuries: Optional[List[str]] = None
    training_days: Optional[int] = None

# Onboarding guiado (tour de producto)
class OnboardingUpdate(BaseModel):
    step: Optional[str] = None          # id del paso actual donde quedó
    completed: Optional[bool] = None    # tour finalizado/omitido

# Cuestionario inicial (ELM)
class QuestionnaireSubmit(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    goal: str  # "volumen" | "definicion"
    sex: Optional[str] = None  # "hombre" | "mujer"
    training_experience: Optional[str] = None  # cero | principiante | intermedio | avanzado
    birthdate: Optional[str] = None  # YYYY-MM-DD
    height: Optional[float] = None  # cm
    weight: float  # kg
    activity_level: Optional[str] = None  # sedentario | ligero | moderado | activo
    biotype: Optional[str] = None
    body_fat: float  # %

# Macros Models
class MacrosData(BaseModel):
    protein: float
    carbs: float
    fat: float
    calories: Optional[float] = None

class PeriMacrosData(BaseModel):
    protein: float
    carbs: float

class MacrosUpdate(BaseModel):
    training: MacrosData
    rest: MacrosData
    peri: Optional[PeriMacrosData] = None
    note: Optional[str] = None
    # Date-versioned macros (Calma todosLosMacros): these macros apply to diet days on/after
    # this date. Default = today. Diets before it keep the prior version.
    effective_date: Optional[str] = None
    # Calc inputs stored per change for traceability (history of how the macros were derived).
    peso: Optional[float] = None
    porcentaje_graso: Optional[float] = None
    sexo: Optional[str] = None
    objetivo: Optional[str] = None
