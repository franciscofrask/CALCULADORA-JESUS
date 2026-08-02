"""
Modelos Pydantic para usuarios y autenticación.
"""
import math

from pydantic import BaseModel, EmailStr, ConfigDict, Field, field_validator
from typing import Optional, Dict, List, Any

# Limites de cordura para los macros del perfil. Sin ellos cualquier PUT podia
# dejar guardado un valor absurdo (p. ej. protein=1e308) que luego se pintaba
# tal cual en la ficha del cliente.
MACRO_MAX_GRAMOS = 1500
MACRO_MAX_CALORIAS = 20000


def validar_dict_macros(v):
    """Valida un dict de macros suelto (protein/carbs/fat/calories y sus alias)."""
    if v is None:
        return v
    limpio = {}
    for k, val in v.items():
        if val is None:
            continue
        try:
            num = float(val)
        except (TypeError, ValueError):
            raise ValueError(f"Macro '{k}': valor no numerico")
        if not math.isfinite(num):
            raise ValueError(f"Macro '{k}': valor no finito")
        tope = MACRO_MAX_CALORIAS if k in ("calories", "calorias") else MACRO_MAX_GRAMOS
        if num < 0 or num > tope:
            raise ValueError(f"Macro '{k}': fuera de rango (0-{tope})")
        limpio[k] = num
    return limpio

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
#       acompanamiento  solo_app | con_entrenador | con_entrenador_y_llamadas
#       frecuencia_contacto  semanal | quincenal | mensual | ninguna
#
#   Los dos ultimos son de la especificacion del 31-07-2026 (parte 1). Sin ellos, dos
#   planes que solo se diferencian en si hay alguien detras y cada cuanto te escribe
#   quedaban identicos salvo el precio, y eso no habia donde configurarlo.
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
        "precio": 60.0, "precio_nota": "60€/mes",
        "precios": [{"label": "Mensual", "importe": 60.0, "periodo": "mes"}],
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
    if reportes:
        features.append("reportes")  # feature genérica: el plan incluye algún reporte/check-in
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


ACOMPANAMIENTO_OPCIONES = ("solo_app", "con_entrenador", "con_entrenador_y_llamadas")
FRECUENCIA_CONTACTO_OPCIONES = ("semanal", "quincenal", "mensual", "ninguna")


def completar_acompanamiento(hab: Dict[str, Any]) -> Dict[str, Any]:
    """Pone `acompanamiento` y `frecuencia_contacto` si el plan no los trae.

    Se añadieron con la especificacion del 31-07-2026, asi que ni los planes del
    catalogo ni los overrides que el admin ya tenia guardados los declaran. En vez de
    dejarlos vacios se deducen de algo que ya esta en el plan y es objetivo: la cadencia
    de reportes, que hoy ES la frecuencia con la que alguien mira a ese cliente.

    Es un punto de partida para que el panel tenga algo que enseñar, no una decision de
    negocio: en cuanto se repasen desde el panel manda lo que se ponga alli. Lo que NO
    se deduce de ningun dato existente es si el plan lleva llamadas; eso hay que
    marcarlo a mano (`con_entrenador_y_llamadas`).
    """
    hab = dict(hab or {})
    reportes = hab.get("reportes") or []

    if not hab.get("acompanamiento"):
        hab["acompanamiento"] = "con_entrenador" if reportes else "solo_app"

    if not hab.get("frecuencia_contacto"):
        for cadencia in ("semanal", "quincenal", "mensual"):
            if cadencia in reportes:
                hab["frecuencia_contacto"] = cadencia
                break
        else:
            hab["frecuencia_contacto"] = "ninguna"

    return hab


def get_plan(code: Optional[str]) -> Optional[Dict[str, Any]]:
    """Devuelve la entrada completa del catálogo (con code incluido) o None."""
    if not code:
        return None
    p = PLAN_CATALOG.get(code.lower().strip())
    if not p:
        return None
    hab = completar_acompanamiento(p.get("habilitaciones", {}))
    return {"code": code.lower().strip(), **p, "habilitaciones": hab,
            "features": derive_features(hab)}


def assignable_plan_codes() -> List[str]:
    """Códigos de planes que pueden asignarse como membresía de un cliente."""
    return [code for code, p in PLAN_CATALOG.items() if p.get("asignable")]


def plan_habilitaciones(code: Optional[str]) -> Dict[str, Any]:
    """Habilitaciones del plan (matriz). Vacío si el plan no existe."""
    p = PLAN_CATALOG.get((code or "").lower().strip())
    return completar_acompanamiento(p["habilitaciones"]) if p else {}


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
        entry["habilitaciones"] = completar_acompanamiento(entry.get("habilitaciones", {}))
        entry["features"] = derive_features(entry["habilitaciones"])
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
    # Motor v2: ultima version de las preguntas 5-8 (para precargar Ajustar macros).
    ajustes_macros: Optional[Dict[str, Any]] = None
    # Usa farmacos -> +10% proteina SOLO descanso. Lo fija el coach (o Nivel 1), nunca el cliente.
    farmacologia: Optional[bool] = None
    # Cuestionario Nivel 1 (perfil largo para el coach; no toca macros).
    nivel1: Optional[Dict[str, Any]] = None
    questionnaire_nivel1_completed: Optional[bool] = None
    # Cuestionario de ajuste (paso 2) hecho: hasta entonces sus macros son los provisionales
    # que salieron de las cuatro preguntas del alta.
    ajuste_macros_completado: Optional[bool] = None
    # Progreso del cuestionario de ajuste: {respuestas: {...}, paso: n}. Se guarda a cada
    # respuesta para que pueda salirse y volver donde lo dejo. Se borra al terminarlo.
    ajuste_macros_progreso: Optional[Dict[str, Any]] = None
    # Punto de partida (paso 3 del doc): fotos y medidas del dia 1, que son la unica forma de
    # comparar dentro de un mes.
    punto_de_partida_hecho: Optional[bool] = None
    medidas_inicio: Optional[Dict[str, Any]] = None
    # Revision de macros comprada suelta: {estado, importe_eur, pagada_at, descuento_aplicado}.
    # Solo para quien se autogestiona; el plan con coach ya la lleva incluida.
    revision_suelta: Optional[Dict[str, Any]] = None
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

    @field_validator("macros_training", "macros_rest", "macros_periworkout")
    @classmethod
    def _macros_en_rango(cls, v):
        return validar_dict_macros(v)

# Asignación de coach (trainer_id=None quita el coach)
class TrainerAssign(BaseModel):
    trainer_id: Optional[str] = None

# Onboarding guiado (tour de producto)
class OnboardingUpdate(BaseModel):
    step: Optional[str] = None          # id del paso actual donde quedó
    completed: Optional[bool] = None    # tour finalizado/omitido
    checklist_dismissed: Optional[bool] = None  # checklist "Primeros pasos" cerrado/completado

# Preguntas 5-8 del Nivel 0 ("Afina tus macros"): las que mueven el motor v2.
# Se guardan SIEMPRE (quiz_respuestas + perfil), se apliquen o no.
class AjustesMacros(BaseModel):
    actividad_diaria: Optional[str] = None      # P1: sedentario | normal | muy_activo
    deporte_extra: Optional[bool] = None        # P2
    facilidad_engordar: Optional[str] = None    # P3: enseguida | normal | casi_no
    cuesta_definir: Optional[str] = None        # P5: se guarda, no modifica
    sigue_dieta: Optional[bool] = None          # P6
    tiempo_dieta: Optional[str] = None          # P7: menos_1m | 1_3m | 3_6m | mas_6m (se guarda)
    # P8: decide que se hace con la dieta que trae (paso 4 del metodo). Definicion:
    # bien | lento | mantengo | cogiendo_peso. Volumen: bien | lento | mucha_grasa |
    # mantengo | bajando.
    como_va: Optional[str] = None
    # P9: no cambia el macro de arranque, marca el ritmo de los ajustes siguientes.
    # Definicion: mucho | normal | aguanto_mas. Volumen: no_puedo_mas | puedo_mas.
    hambre_saturacion: Optional[str] = None
    dieta_texto: Optional[str] = None           # P10: texto libre, se guarda tal cual
    dieta_hc_entreno: Optional[float] = None    # P10: HC totales del dia de entreno que come ahora
    dieta_grasa_entreno: Optional[float] = None # P10: grasa aproximada (opcional)
    dieta_confirmada: Optional[bool] = None     # P10: sin confirmar, la dieta NO se aplica
    historial_dietas: Optional[str] = None      # +-10%: guardar, NO aplicar (spec)

# Cuestionario inicial (ELM) - Nivel 0
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
    ajustes: Optional[AjustesMacros] = None  # preguntas 5-8 del quiz nuevo

# Cuestionario Nivel 1 (solo planes con coach: calculadora == 'personalizado').
# Alimenta perfil, caso gemelo y estrategia; NO toca los macros.
class Nivel1Submit(BaseModel):
    biotype: Optional[str] = None
    height: Optional[float] = None              # cm
    birthdate: Optional[str] = None             # YYYY-MM-DD
    training_experience: Optional[str] = None
    peso_maximo: Optional[float] = None
    peso_minimo: Optional[float] = None
    peso_habitual: Optional[float] = None
    peso_mejor_momento: Optional[float] = None
    salud: Optional[Dict[str, Any]] = None      # {sueno, estres, medicacion, hormonal, lesiones}
    dietas_previas: Optional[str] = None
    entrenador_anterior: Optional[str] = None
    dias_entreno: Optional[int] = None
    hora_entreno: Optional[str] = None
    material: Optional[List[str]] = None
    cardio: Optional[str] = None
    alimentos_evitados: Optional[List[str]] = None
    alergias: Optional[str] = None
    num_comidas: Optional[int] = None
    # Bloque 4 del doc del 29-07. Ninguna toca los macros: son las que permiten emparejar al
    # cliente con los que ya han pasado por aqui.
    trt: Optional[str] = None                   # P14: si | no | antes  (la regla, pendiente de Jesus)
    zona_grasa: Optional[str] = None            # P15: abdomen | cintura | espalda_baja | pecho | piernas | reparto
    peso_maximo_cuando: Optional[str] = None    # P18
    foto_peso_maximo: Optional[str] = None      # P19 (opcional)
    mejor_definicion_cuando: Optional[str] = None   # P20; "nunca" si nunca estuvo definido
    hasta_donde: Optional[str] = None           # P21
    vario_peso_3m: Optional[str] = None         # P22
    tiempo_intentandolo: Optional[str] = None   # P23
    dieta_que_funciona: Optional[str] = None    # P24
    por_que_fallaron: Optional[str] = None      # P25
    motivo_apuntarse: Optional[str] = None      # P26

# Macros Models
class MacrosData(BaseModel):
    protein: float = Field(ge=0, le=MACRO_MAX_GRAMOS)
    carbs: float = Field(ge=0, le=MACRO_MAX_GRAMOS)
    fat: float = Field(ge=0, le=MACRO_MAX_GRAMOS)
    calories: Optional[float] = Field(default=None, ge=0, le=MACRO_MAX_CALORIAS)

class PeriMacrosData(BaseModel):
    protein: float = Field(ge=0, le=MACRO_MAX_GRAMOS)
    carbs: float = Field(ge=0, le=MACRO_MAX_GRAMOS)

class MacrosUpdate(BaseModel):
    training: MacrosData
    rest: MacrosData
    peri: Optional[PeriMacrosData] = None
    note: Optional[str] = None
    # Date-versioned macros (Calma todosLosMacros): these macros apply to diet days on/after
    # this date. Default = today. Diets before it keep the prior version.
    effective_date: Optional[str] = None
    # Calc inputs stored per change for traceability (history of how the macros were derived).
    peso: Optional[float] = Field(default=None, ge=25, le=300)
    porcentaje_graso: Optional[float] = Field(default=None, ge=3, le=60)
    sexo: Optional[str] = None
    objetivo: Optional[str] = None
    # Motor v2: preguntas 5-8 y desglose del calculo que origino estos macros
    # (se versionan en macro_history.motor; la revision se recalcula en servidor).
    ajustes: Optional[AjustesMacros] = None
    desglose: Optional[List[Dict[str, Any]]] = None
    # Modelo predictivo (paso 1): el POR QUE del ajuste, interno del coach. Es
    # distinto de `note`, que es el feedback que le llega al cliente.
    criterio: Optional[str] = None
    # Si este ajuste sale de una sugerencia de la IA: su id. Sirve para medir cuanto
    # la corrigio el coach (la senal de aprendizaje mas valiosa que hay).
    sugerencia_id: Optional[str] = None


class MacroEvaluacion(BaseModel):
    """Modelo predictivo (paso 1): como salio la fase que abrio un ajuste. Se
    rellena a toro pasado, cuando llega el reporte siguiente."""
    resultado: str            # buena | mala
    causa: Optional[str] = None   # ajuste (fallo del coach) | cliente (no cumplio) | otro
    nota: Optional[str] = None

    @field_validator("resultado")
    @classmethod
    def _resultado_valido(cls, v):
        if v not in ("buena", "mala"):
            raise ValueError("resultado debe ser 'buena' o 'mala'")
        return v

    @field_validator("causa")
    @classmethod
    def _causa_valida(cls, v):
        if v is not None and v not in ("ajuste", "cliente", "otro"):
            raise ValueError("causa debe ser 'ajuste', 'cliente' u 'otro'")
        return v
