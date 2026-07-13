"""
Modelos Pydantic para usuarios y autenticación.
"""
from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional, Dict, List, Any

# =========================================================
# CATÁLOGO DE PLANES (fuente única)
# =========================================================
# Refleja el documento "JG - Catálogo de Planes y Membresías".
#
# Campos de cada plan:
#   name           Nombre comercial.
#   estado         activo | legacy | especial | complemento.
#                    - activo:     se vende hoy.
#                    - legacy:     ya no se vende; se respeta a quien lo tenga.
#                    - especial:   personalizado, condiciones pactadas con el CEO.
#                    - complemento: producto suelto (no es una membresía asignable).
#   asignable      True si puede asignarse como plan/membresía de un cliente.
#   ciclo          tipo (mensual|trimestral|bimestral|semestral|unico|variable) y
#                  semanas (duración del ciclo; None si es mensual indefinido o variable).
#   precio         Importe de referencia (informativo; los pagos son mock).
#   precio_nota    Detalle textual del precio tal cual el catálogo.
#   precios        Opciones estructuradas [{label, importe, periodo}].
#   responsable    Quién gestiona el plan.
#   habilitaciones Qué habilita el plan al usuario:
#       calculadora     personalizado | autogestion | sin_ajuste
#       rutina          personalizada | del_mes | ninguna | opcional
#       reportes        lista de: quincenal, mensual, semanal
#       suplementacion  bool
#       harbiz          bool
#   stripe_price_env  Variable .env con el Price ID de Stripe ("" si no aplica).
#   billing_cycle_weeks  Longitud del ciclo de cobro recurrente (semanas).

PLAN_CATALOG = {
    # ---------------- ACTIVOS ----------------
    "elm": {
        "name": "ELM (El Lunes Empiezo)", "estado": "activo", "asignable": True,
        "ciclo": {"tipo": "mensual", "semanas": None},
        "precio": 97.0, "precio_nota": "97€/mes (antiguos 67€ u 87€) · 800€/año",
        "precios": [{"label": "Mensual", "importe": 97.0, "periodo": "mes"},
                    {"label": "Anual", "importe": 800.0, "periodo": "año"}],
        "responsable": "Operaciones",
        "habilitaciones": {"calculadora": "personalizado", "rutina": "del_mes",
                            "reportes": [], "suplementacion": False, "harbiz": True},
        "stripe_price_env": "STRIPE_PRICE_ELM", "billing_cycle_weeks": 4,
    },
    "reto12en12_gold": {
        "name": "Reto 12en12 - Gold", "estado": "activo", "asignable": True,
        "ciclo": {"tipo": "trimestral", "semanas": 12},
        "precio": 1500.0, "precio_nota": "1.500€/trimestre o 600€/mes",
        "precios": [{"label": "Trimestral", "importe": 1500.0, "periodo": "trimestre"},
                    {"label": "Mensual", "importe": 600.0, "periodo": "mes"}],
        "responsable": "CEO",
        "habilitaciones": {"calculadora": "personalizado", "rutina": "personalizada",
                            "reportes": ["quincenal", "mensual"], "suplementacion": True, "harbiz": False},
        "stripe_price_env": "STRIPE_PRICE_RETO12EN12_GOLD", "billing_cycle_weeks": 12,
    },
    "reto12en12_silver": {
        "name": "Reto 12en12 - Silver", "estado": "activo", "asignable": True,
        "ciclo": {"tipo": "trimestral", "semanas": 12},
        "precio": 600.0, "precio_nota": "600€/trimestre o 250€/mes",
        "precios": [{"label": "Trimestral", "importe": 600.0, "periodo": "trimestre"},
                    {"label": "Mensual", "importe": 250.0, "periodo": "mes"}],
        "responsable": "CEO / José Luis",
        "habilitaciones": {"calculadora": "personalizado", "rutina": "del_mes",
                            "reportes": ["mensual"], "suplementacion": True, "harbiz": False},
        "stripe_price_env": "STRIPE_PRICE_RETO12EN12_SILVER", "billing_cycle_weeks": 12,
    },
    "reto60": {
        "name": "Reto 60 días", "estado": "activo", "asignable": True,
        "ciclo": {"tipo": "bimestral", "semanas": 8},
        "precio": 547.0, "precio_nota": "547€ (pago único)",
        "precios": [{"label": "Único", "importe": 547.0, "periodo": "único"}],
        "responsable": "Operaciones",
        "habilitaciones": {"calculadora": "personalizado", "rutina": "del_mes",
                            "reportes": [], "suplementacion": False, "harbiz": True},
        "stripe_price_env": "STRIPE_PRICE_RETO60", "billing_cycle_weeks": 8,
    },
    "calculadora_jp": {
        "name": "Calculadora JP", "estado": "activo", "asignable": True,
        "ciclo": {"tipo": "mensual", "semanas": None},
        "precio": 60.5, "precio_nota": "60,50€/mes",
        "precios": [{"label": "Mensual", "importe": 60.5, "periodo": "mes"}],
        "responsable": "Ninguno (autogestión)",
        "habilitaciones": {"calculadora": "autogestion", "rutina": "ninguna",
                            "reportes": [], "suplementacion": False, "harbiz": False},
        "stripe_price_env": "STRIPE_PRICE_CALCULADORA_JP", "billing_cycle_weeks": 4,
    },
    "mantenimiento": {
        "name": "Mantenimiento", "estado": "activo", "asignable": True,
        "ciclo": {"tipo": "mensual", "semanas": None},
        "precio": 60.0, "precio_nota": "60€/mes",
        "precios": [{"label": "Mensual", "importe": 60.0, "periodo": "mes"}],
        "responsable": "CEO",
        "habilitaciones": {"calculadora": "sin_ajuste", "rutina": "opcional",
                            "reportes": [], "suplementacion": False, "harbiz": False},
        "stripe_price_env": "STRIPE_PRICE_MANTENIMIENTO", "billing_cycle_weeks": 4,
    },
    # ---------------- LEGACY (inactivos, se respetan) ----------------
    "gold": {
        "name": "Gold (legacy)", "estado": "legacy", "asignable": True,
        "ciclo": {"tipo": "trimestral", "semanas": 12},
        "precio": 450.0, "precio_nota": "450-847€/trimestre (según antigüedad)",
        "precios": [{"label": "Trimestral", "importe": 450.0, "periodo": "trimestre"}],
        "responsable": "CEO",
        "habilitaciones": {"calculadora": "personalizado", "rutina": "personalizada",
                            "reportes": ["quincenal", "mensual"], "suplementacion": True, "harbiz": False},
        "stripe_price_env": "STRIPE_PRICE_GOLD", "billing_cycle_weeks": 12,
    },
    "silver": {
        "name": "Silver (legacy)", "estado": "legacy", "asignable": True,
        "ciclo": {"tipo": "trimestral", "semanas": 12},
        "precio": 267.0, "precio_nota": "267-435€/trimestre (según antigüedad)",
        "precios": [{"label": "Trimestral", "importe": 267.0, "periodo": "trimestre"}],
        "responsable": "CEO",
        "habilitaciones": {"calculadora": "personalizado", "rutina": "del_mes",
                            "reportes": ["mensual"], "suplementacion": True, "harbiz": False},
        "stripe_price_env": "STRIPE_PRICE_SILVER", "billing_cycle_weeks": 12,
    },
    "bronze": {
        "name": "Bronze (legacy)", "estado": "legacy", "asignable": True,
        "ciclo": {"tipo": "trimestral", "semanas": 12},
        "precio": 177.0, "precio_nota": "177-397€/trimestre (según antigüedad)",
        "precios": [{"label": "Trimestral", "importe": 177.0, "periodo": "trimestre"}],
        "responsable": "CEO",
        "habilitaciones": {"calculadora": "personalizado", "rutina": "opcional",
                            "reportes": [], "suplementacion": True, "harbiz": False},
        "stripe_price_env": "STRIPE_PRICE_BRONZE", "billing_cycle_weeks": 12,
    },
    # ---------------- ESPECIALES ----------------
    "premium": {
        "name": "Premium", "estado": "especial", "asignable": True,
        "ciclo": {"tipo": "variable", "semanas": None},
        "precio": 0.0, "precio_nota": "Variable (ej: 1.500€ cada dos semanas)",
        "precios": [],
        "responsable": "CEO",
        "habilitaciones": {"calculadora": "personalizado", "rutina": "personalizada",
                            "reportes": ["semanal", "mensual"], "suplementacion": True, "harbiz": False},
        "stripe_price_env": "", "billing_cycle_weeks": 4,
    },
    "plan_6m": {
        "name": "6M", "estado": "especial", "asignable": True,
        "ciclo": {"tipo": "semestral", "semanas": 26},
        "precio": 2500.0, "precio_nota": "2.500€ (6 meses); a veces 7 meses por 2.500€",
        "precios": [{"label": "Único", "importe": 2500.0, "periodo": "6 meses"}],
        "responsable": "CEO",
        "habilitaciones": {"calculadora": "personalizado", "rutina": "personalizada",
                            "reportes": ["semanal", "mensual"], "suplementacion": True, "harbiz": False},
        "stripe_price_env": "", "billing_cycle_weeks": 26,
    },
    # ---------------- COMPLEMENTOS (no asignables como membresía) ----------------
    "rutina_mes": {
        "name": "Rutina del Mes", "estado": "complemento", "asignable": False,
        "ciclo": {"tipo": "unico", "semanas": None},
        "precio": 55.0, "precio_nota": "55€ (pago único)",
        "precios": [{"label": "Único", "importe": 55.0, "periodo": "único"}],
        "responsable": "Operaciones",
        "habilitaciones": {"calculadora": "sin_ajuste", "rutina": "del_mes",
                            "reportes": [], "suplementacion": False, "harbiz": False},
        "stripe_price_env": "", "billing_cycle_weeks": 4,
    },
    "formaciones": {
        "name": "Formaciones / Lanzamientos", "estado": "complemento", "asignable": False,
        "ciclo": {"tipo": "unico", "semanas": None},
        "precio": 0.0, "precio_nota": "Variable (según cada lanzamiento)",
        "precios": [],
        "responsable": "CEO",
        "habilitaciones": {"calculadora": "sin_ajuste", "rutina": "ninguna",
                            "reportes": [], "suplementacion": False, "harbiz": False},
        "stripe_price_env": "", "billing_cycle_weeks": 4,
    },
}


def derive_features(habilitaciones: Dict[str, Any]) -> List[str]:
    """Traduce la matriz de habilitaciones a la lista `features` que ya consume
    el resto del código (routines.py, frontend). Mantiene el vocabulario previo:
    rutina, macros, chat, reporte_quincenal, reporte_mensual, suplementacion, cardio, audio.
    """
    h = habilitaciones or {}
    reportes = h.get("reportes") or []
    features: List[str] = ["macros", "chat"]
    if h.get("rutina") in ("del_mes", "personalizada", "opcional"):
        features.append("rutina")
    if "quincenal" in reportes:
        features.append("reporte_quincenal")
    if "mensual" in reportes:
        features.append("reporte_mensual")
    if "semanal" in reportes:
        features.append("reporte_semanal")
    if h.get("suplementacion"):
        features.append("suplementacion")
    if h.get("rutina") == "personalizada":
        features.append("cardio")
    if "quincenal" in reportes:
        features.append("audio")
    return features


# PLAN_TYPES: vista compatible con el código previo (name, price, stripe_price_env,
# billing_cycle_weeks, features) derivada del catálogo. No editar a mano: cambia PLAN_CATALOG.
PLAN_TYPES = {
    code: {
        "name": p["name"],
        "price": p["precio"],
        "stripe_price_env": p.get("stripe_price_env", ""),
        "billing_cycle_weeks": p.get("billing_cycle_weeks", 4),
        # Pago único (p.ej. reto60): cobra una vez y el acceso dura el ciclo, sin renovar.
        "one_time": (p.get("precios") or [{}])[0].get("periodo") == "único",
        "features": derive_features(p.get("habilitaciones", {})),
    }
    for code, p in PLAN_CATALOG.items()
}


def get_plan(code: Optional[str]) -> Optional[Dict[str, Any]]:
    """Devuelve la entrada completa del catálogo (con code incluido) o None."""
    if not code:
        return None
    p = PLAN_CATALOG.get(code.lower().strip())
    if not p:
        return None
    return {"code": code.lower().strip(), **p, "features": derive_features(p.get("habilitaciones", {}))}


def assignable_plan_codes() -> List[str]:
    """Códigos de planes que pueden asignarse como membresía de un cliente."""
    return [code for code, p in PLAN_CATALOG.items() if p.get("asignable")]


def plan_habilitaciones(code: Optional[str]) -> Dict[str, Any]:
    """Habilitaciones del plan (matriz). Vacío si el plan no existe."""
    p = PLAN_CATALOG.get((code or "").lower().strip())
    return dict(p["habilitaciones"]) if p else {}


# Campos del catálogo que el admin puede sobrescribir desde el panel (guardados en
# db.plan_overrides). Lo demás (code, asignable, stripe_price_env) queda fijo por código.
PLAN_EDITABLE_FIELDS = {
    "name", "estado", "ciclo", "precio", "precio_nota", "precios",
    "responsable", "habilitaciones",
}


def merged_catalog(overrides_by_code: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Dict[str, Any]]:
    """Catálogo con los overrides del admin aplicados sobre los valores por defecto.
    `overrides_by_code`: {code: {campo: valor, ...}} (normalmente leído de db.plan_overrides).
    Devuelve {code: entrada completa con `code` y `features` recalculadas}.
    """
    overrides_by_code = overrides_by_code or {}
    out: Dict[str, Dict[str, Any]] = {}
    for code, base in PLAN_CATALOG.items():
        entry = {**base}
        ov = overrides_by_code.get(code) or {}
        for field, value in ov.items():
            if field in PLAN_EDITABLE_FIELDS:
                entry[field] = value
        entry["code"] = code
        entry["features"] = derive_features(entry.get("habilitaciones", {}))
        out[code] = entry
    return out

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
    # Ciclo calculado (ver core/cycle.py): inicio del ciclo y progreso derivado.
    cycle_start: Optional[str] = None
    cycle_number: Optional[int] = None
    cycle_total_weeks: Optional[int] = None
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
    # Checklist "Primeros pasos" del dashboard: cerrado/completado (no volver a mostrar).
    checklist_dismissed: Optional[bool] = None
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

# Asignación de coach (trainer_id=None quita el coach)
class TrainerAssign(BaseModel):
    trainer_id: Optional[str] = None

# Onboarding guiado (tour de producto)
class OnboardingUpdate(BaseModel):
    step: Optional[str] = None          # id del paso actual donde quedó
    completed: Optional[bool] = None    # tour finalizado/omitido
    checklist_dismissed: Optional[bool] = None  # checklist "Primeros pasos" cerrado/completado

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
