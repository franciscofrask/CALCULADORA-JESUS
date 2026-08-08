"""
Modelos Pydantic para usuarios y autenticación.
"""
import math

from pydantic import BaseModel, EmailStr, ConfigDict, Field, field_validator
from typing import Optional, Dict, List, Any, Union

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
    # ---------------- LOS TRES NIVELES (especificacion 31-07-2026, parte 1) ----------
    # Sustituyen a lo anterior como lo unico que se puede contratar. Ciclos de 12 semanas.
    # Al que ya tiene un plan viejo no se le cambia nada: sigue igual hasta que le toque
    # renovar, y entonces elige entre estos tres (ver RENOVACION_A y planes_contratables).
    #
    # OJO: no se pueden comprar hasta que existan sus productos en Stripe. Las variables
    # de .env de abajo estan vacias a proposito: hasta que se creen, el checkout devuelve
    # un 503 con un mensaje claro en vez de cobrar mal.
    "nivel1": {
        "name": "Nivel 1", "estado": "activo", "asignable": True,
        "ciclo": {"tipo": "trimestral", "semanas": 12},
        "precio": 297.0, "precio_nota": "297€ por ciclo de 12 semanas",
        "precios": [{"label": "Ciclo", "importe": 297.0, "periodo": "12 semanas"}],
        "responsable": "Operaciones",
        "habilitaciones": {"calculadora": "autogestion", "rutina": "ninguna",
                           "reportes": ["mensual"], "suplementacion": False, "harbiz": False,
                           "acompanamiento": "solo_app", "frecuencia_contacto": "ninguna"},
        "stripe_price_env": "STRIPE_PRICE_NIVEL1", "billing_cycle_weeks": 12,
        # Doc 03-08: PAGO UNICO del ciclo. No es una suscripcion: al llegar la
        # semana 12 se le habla y decide, nunca se le cobra solo.
        "pago_unico": True,
    },
    "nivel2": {
        "name": "Nivel 2", "estado": "activo", "asignable": True,
        "ciclo": {"tipo": "trimestral", "semanas": 12},
        "precio": 897.0, "precio_nota": "897€ por ciclo de 12 semanas",
        "precios": [{"label": "Ciclo", "importe": 897.0, "periodo": "12 semanas"}],
        "responsable": "CEO",
        "habilitaciones": {"calculadora": "personalizado", "rutina": "personalizada",
                           "reportes": ["quincenal", "mensual"], "suplementacion": True,
                           "harbiz": False, "acompanamiento": "con_entrenador",
                           "frecuencia_contacto": "quincenal"},
        "stripe_price_env": "STRIPE_PRICE_NIVEL2", "billing_cycle_weeks": 12,
        # Doc 03-08: PAGO UNICO del ciclo. No es una suscripcion: al llegar la
        # semana 12 se le habla y decide, nunca se le cobra solo.
        "pago_unico": True,
    },
    "nivel3": {
        # "Cómo se compra: por llamada". No lleva a un pago, lleva a agendar.
        "name": "Nivel 3", "estado": "activo", "asignable": True,
        "ciclo": {"tipo": "trimestral", "semanas": 12},
        "precio": 1500.0, "precio_nota": "1.500€ por ciclo de 12 semanas · se contrata por llamada",
        "precios": [{"label": "Ciclo", "importe": 1500.0, "periodo": "12 semanas"}],
        "responsable": "CEO",
        "habilitaciones": {"calculadora": "personalizado", "rutina": "personalizada",
                           "reportes": ["quincenal", "mensual"], "suplementacion": True,
                           "harbiz": False, "acompanamiento": "con_entrenador_y_llamadas",
                           "frecuencia_contacto": "semanal"},
        "stripe_price_env": "STRIPE_PRICE_NIVEL3", "billing_cycle_weeks": 12,
        # Doc 03-08: PAGO UNICO del ciclo. No es una suscripcion: al llegar la
        # semana 12 se le habla y decide, nunca se le cobra solo.
        "pago_unico": True,
    },
    "membresia": {
        # "Membresia 97 EUR/mes: ya no es la entrada, es la SALIDA para el que no renueva."
        # Nueva y separada de ELM a proposito, para que el de salida no arrastre las
        # condiciones antiguas (ELM tenia precios de 67 y 87 EUR, anual de 800 y Harbiz).
        #
        # `solo_salida` es lo que la distingue: no se ofrece al comprar -- ahi solo estan
        # los tres niveles -- pero si a quien acaba su ciclo y no renueva.
        "name": "Membresía", "estado": "activo", "asignable": True, "solo_salida": True,
        "ciclo": {"tipo": "mensual", "semanas": None},
        "precio": 97.0, "precio_nota": "97€/mes · para quien no renueva su ciclo",
        "precios": [{"label": "Mensual", "importe": 97.0, "periodo": "mes"}],
        "responsable": "Operaciones",
        "habilitaciones": {"calculadora": "autogestion", "rutina": "ninguna",
                           "reportes": [], "suplementacion": False, "harbiz": False,
                           "acompanamiento": "solo_app", "frecuencia_contacto": "ninguna"},
        "stripe_price_env": "STRIPE_PRICE_MEMBRESIA", "billing_cycle_weeks": 4,
    },
    # ---------------- ACTIVOS ----------------
    "elm": {
        # Legacy desde el 31-07-2026: deja de ser la entrada. El documento lo nombra entre
        # los que dejan de contratarse. Quien lo tiene sigue igual.
        "name": "ELM (El Lunes Empiezo)", "estado": "legacy", "asignable": True,
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
        # El "Reto de 1.500" del documento. Legacy desde el 31-07-2026.
        "name": "Reto 12en12 - Gold", "estado": "legacy", "asignable": True,
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
        # Misma familia que el Reto Gold: legacy desde el 31-07-2026.
        "name": "Reto 12en12 - Silver", "estado": "legacy", "asignable": True,
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
        # Legacy desde el 31-07-2026: los tres niveles son lo unico contratable.
        "name": "Reto 60 días", "estado": "legacy", "asignable": True,
        "ciclo": {"tipo": "bimestral", "semanas": 8},
        "precio": 547.0, "precio_nota": "547€ (pago único)",
        "precios": [{"label": "Único", "importe": 547.0, "periodo": "único"}],
        "responsable": "Operaciones",
        "habilitaciones": {"calculadora": "personalizado", "rutina": "del_mes",
                            "reportes": [], "suplementacion": False, "harbiz": True},
        "stripe_price_env": "STRIPE_PRICE_RETO60", "billing_cycle_weeks": 8,
    },
    "calculadora_jp": {
        # Legacy desde el 31-07-2026: se solapa con el Nivel 1.
        "name": "Calculadora JP", "estado": "legacy", "asignable": True,
        "ciclo": {"tipo": "mensual", "semanas": None},
        "precio": 60.0, "precio_nota": "60€/mes",
        "precios": [{"label": "Mensual", "importe": 60.0, "periodo": "mes"}],
        "responsable": "Ninguno (autogestión)",
        "habilitaciones": {"calculadora": "autogestion", "rutina": "ninguna",
                            "reportes": [], "suplementacion": False, "harbiz": False},
        "stripe_price_env": "STRIPE_PRICE_CALCULADORA_JP", "billing_cycle_weeks": 4,
    },
    "mantenimiento": {
        # Legacy desde el 31-07-2026: su sitio lo ocupa la Membresia de salida.
        "name": "Mantenimiento", "estado": "legacy", "asignable": True,
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
    "calma12": {
        # CALMA 12 sale en el catálogo del equipo (bloque E del doc del 07-08) con dos
        # clientes activos, y NO estaba aquí. En la base hay perfiles con el plan escrito
        # "CalMa" tal cual, que hasta ahora no casaba con ninguna entrada del catálogo: sin
        # entrada, `plan_grants_feature` no encuentra habilitaciones y el cliente se queda
        # sin nada (ni reportes, ni suplementación, ni cadencia), y en las listas sale como
        # plan desconocido. Es el caso exacto que avisa el punto 38: la app tiene que saber
        # representarlos, no convertirlos.
        #
        # Las habilitaciones son las de un plan con coach detrás, que es lo que era. El
        # precio va vacío a propósito: el catálogo del equipo tampoco lo trae, y el que
        # manda es el del contrato de cada cliente (punto 36).
        "name": "CALMA 12", "estado": "legacy", "asignable": True,
        "ciclo": {"tipo": "trimestral", "semanas": 12},
        "precio": 0.0, "precio_nota": "Sin precio de catálogo: manda el del contrato de cada cliente",
        "precios": [],
        "responsable": "CEO",
        "habilitaciones": {"calculadora": "personalizado", "rutina": "personalizada",
                           "reportes": ["mensual"], "suplementacion": True, "harbiz": False,
                           "acompanamiento": "con_entrenador", "frecuencia_contacto": "mensual"},
        "stripe_price_env": "", "billing_cycle_weeks": 12,
        # Los perfiles migrados lo traen escrito asi, sin normalizar.
        "alias": ["CalMa", "calma", "calma_12", "calma 12"],
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
        # Pago único: cobra una vez y el acceso dura el ciclo, sin renovar. Lo marca
        # `pago_unico` (los tres niveles, doc 03-08) o un precio de periodo "único"
        # (reto60 y compañía, que ya venían así).
        "one_time": bool(p.get("pago_unico")) or (p.get("precios") or [{}])[0].get("periodo") == "único",
        "features": derive_features(p.get("habilitaciones", {})),
    }
    for code, p in PLAN_CATALOG.items()
}


# Como esta escrito el plan en los perfiles migrados -> el codigo del catalogo. Los datos
# vienen de sitios distintos y no siempre normalizados ("CalMa" tal cual, con esas mayusculas),
# y un plan que no casa con el catalogo deja al cliente SIN habilitaciones: ni reportes, ni
# suplementacion, ni cadencia. Es lo que avisa el punto 38 del 07-08 -- la app tiene que saber
# representar los planes viejos, no convertirlos.
ALIAS_DE_PLAN: Dict[str, str] = {
    alias.lower().strip(): code
    for code, p in PLAN_CATALOG.items()
    for alias in (p.get("alias") or [])
}


def codigo_de_plan(plan: Optional[str]) -> str:
    """El codigo del catalogo para el plan de un perfil, resolviendo alias y mayusculas."""
    v = (plan or "").lower().strip()
    return ALIAS_DE_PLAN.get(v, v)


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


# Los tres niveles son lo unico que se puede contratar desde el 31-07-2026.
NIVELES = ("nivel1", "nivel2", "nivel3")


def planes_contratables(catalogo: Optional[Dict[str, Dict[str, Any]]] = None,
                        incluir_salida: bool = False) -> List[str]:
    """Lo que alguien puede contratar HOY: los planes en estado 'activo'.

    Un plan legacy sigue funcionando para quien lo tiene -- eso no se toca nunca -- pero
    no se le puede vender a nadie mas, ni siquiera al que ya lo tenia: cuando le toque
    renovar elige entre los nuevos (`opciones_de_renovacion`).

    La Membresia queda fuera salvo que se pida `incluir_salida`: no es un plan que se
    compre, es donde cae el que no renueva.
    """
    cat = catalogo or PLAN_CATALOG
    return [code for code, p in cat.items()
            if p.get("estado") == "activo" and p.get("asignable")
            and (incluir_salida or not p.get("solo_salida"))]


def opciones_de_renovacion(plan_actual: Optional[str],
                           catalogo: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Que se le ofrece a un cliente cuando acaba su ciclo.

    Regla: al renovar se elige entre los planes que se venden hoy, venga de donde venga.
    Al que esta en un plan legacy no se le cambia nada mientras dure su ciclo, pero al
    renovar no puede quedarse en el suyo porque ya no se vende.

    Devuelve tambien `mantiene_precio`: el precio se congela mientras no se de de baja
    (parte 1), asi que si renueva en su MISMO plan paga lo que pagaba. Si cambia de
    plan, paga el precio del nuevo.
    """
    cat = catalogo or PLAN_CATALOG
    actual = (plan_actual or "").lower().strip()
    info = cat.get(actual) or {}
    es_legacy = info.get("estado") in ("legacy", None) and actual not in NIVELES

    return {
        "plan_actual": actual or None,
        "puede_seguir_igual": not es_legacy and info.get("estado") == "activo",
        "opciones": planes_contratables(cat),
        # La tercera salida del documento ("renovar, subir de nivel, o salir a la
        # membresia"): no es una opcion de compra, es donde cae el que no renueva.
        "salida": next((c for c, p in cat.items()
                        if p.get("solo_salida") and p.get("estado") == "activo"), None),
        "mantiene_precio": not es_legacy,
        "motivo": ("Tu plan ya no se ofrece: al renovar eliges entre los actuales"
                   if es_legacy else None),
    }


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
    """Crear cuenta: correo y contraseña, nada más.

    El nombre y el teléfono eran obligatorios. Pedirle el teléfono a alguien que viene a
    por un dato gratis espanta a la mitad, y el nombre se puede pedir después, cuando ya
    tiene algo suyo delante. Siguen aceptándose porque el registro del panel los manda.
    """
    email: EmailStr
    password: str
    name: Optional[str] = None
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
    # OJO: plan y price son opcionales A PROPOSITO. El perfil se crea en cuanto el
    # usuario guarda sus preferencias de comida, que puede hacer ANTES de contratar
    # nada; exigirlos hacia que GET /clients/profile devolviera 500 y el frontend se
    # quedara sin perfil (sin plan, sin cuestionario inicial y con el acceso cerrado
    # aunque hubiera pagado). Sin plan = plan no contratado, que es un estado real.
    plan: Optional[str] = None
    price: Optional[float] = None
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
    # Lo que este cliente tiene de particular y no cabe en ningun campo (punto 39 del
    # 07-08). Sale en su ficha y salta al cobrar o al generarle algo.
    excepcion: Optional[str] = None
    # Si tiene acceso y por que no, cuando no (punto 41). Lo calcula el servidor:
    # {"activo": bool, "motivo": "sin_plan"|"sin_pagar"|"caducado"|None}.
    acceso: Optional[Dict[str, Any]] = None
    # OJO con estos dos (punto 30 del 07-08): `weight` y `body_fat` son el ULTIMO valor de
    # sus series, calculado, no un dato que se guarde aparte. Los escribe solo
    # core/series_cliente.py; nadie mas debe ponerlos en un $set, o vuelven los dos pesos
    # distintos del punto 9. Las series llevan la fecha, que es lo que hay que ensenar al
    # lado del numero ("94 kg · hace 3 dias").
    weight: Optional[float] = None
    pesos: Optional[List[Dict[str, Any]]] = None                 # [{fecha, valor, origen}]
    height: Optional[float] = None
    age: Optional[int] = None
    sex: Optional[str] = None
    goal: Optional[str] = None
    body_fat: Optional[float] = None
    porcentajes_grasos: Optional[List[Dict[str, Any]]] = None    # [{fecha, valor, origen}]
    equipment: Optional[List[str]] = None
    injuries: Optional[List[str]] = None
    # Observaciones del coach sobre el ENTRENAMIENTO: van con la maquinaria y las lesiones
    # porque es lo que se actualiza al leer el reporte (Jesus 05-08, punto 2.5: "el
    # entrenamiento lo llevo aparte").
    training_notes: Optional[str] = None
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
    # Opcional por lo mismo que plan/price: hay perfiles creados por upsert (preferencias,
    # webhook de leads) que nunca lo escribieron.
    created_at: Optional[str] = None

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
    # Uso ACTUAL de farmacologia -> +10 g de proteina en descanso. Solo por la ruta de
    # admin: en PUT /users/clients/profile se descarta (el cliente no se lo marca solo).
    farmacologia: Optional[bool] = None
    weight: Optional[float] = None
    height: Optional[float] = None
    age: Optional[int] = None
    sex: Optional[str] = None
    goal: Optional[str] = None
    body_fat: Optional[float] = None
    equipment: Optional[List[str]] = None
    injuries: Optional[List[str]] = None
    # Observaciones del coach sobre el ENTRENAMIENTO: van con la maquinaria y las lesiones
    # porque es lo que se actualiza al leer el reporte (Jesus 05-08, punto 2.5: "el
    # entrenamiento lo llevo aparte").
    training_notes: Optional[str] = None
    training_days: Optional[int] = None
    # LA EXCEPCION de este cliente (punto 39 del doc del 07-08). Texto libre a proposito:
    # hay 17 clientes con una excepcion apuntada a mano en una hoja y no se parecen entre
    # si -- uno cuya membresia paga su marido, uno que paga en efectivo, uno al que no se
    # le genera rutina, uno que no paga nada y aun asi se le hace, uno con ciclo de 4
    # semanas, otro al que se le manda el reporte por WhatsApp. Modelarlas con casillas
    # seria inventarse las categorias antes de conocerlas, y la de la numero 18 no
    # entraria. Cadena vacia = quitar la excepcion (por eso este campo se trata aparte en
    # el PUT, que descarta los None pero no los vacios).
    excepcion: Optional[str] = None

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
    # sedentario (muy sedentario) | normal (ligeramente activo) | moderado | muy_activo.
    # CUATRO desde el documento de textos del 06-08; los dos primeros valores se conservan
    # tal cual para no romper lo que ya contestaron los clientes de antes. Solo `muy_activo`
    # sube hidratos: los otros tres no tocan nada (doc del 07-08).
    actividad_diaria: Optional[str] = None
    deporte_extra: Optional[bool] = None
    # Las dos preguntas de seguimiento del deporte (pantalla 6 del doc de textos). No mueven
    # macros: le dicen al entrenador que hace, cuando y si puede cuadrarlo con el descanso.
    deporte_cual: Optional[str] = None
    deporte_en_descanso: Optional[Union[bool, str]] = None   # True | False | "ya"
    facilidad_engordar: Optional[str] = None    # enseguida | normal | casi_no
    apetito: Optional[str] = None               # mucho | normal | poco (pantalla 7, no mueve macros)
    cuesta_definir: Optional[str] = None        # mucho | normal | poco (se guarda, no modifica)
    # Se pregunta en el test de entrada desde el doc de textos (pantalla 3): antes vivia en
    # el cuestionario largo, que solo ven los planes con entrenador.
    training_experience: Optional[str] = None   # cero | principiante | intermedio | avanzado
    # P6. Tres respuestas, no dos: True (la sigue y la mide), False (come lo que surge) y
    # "parecido" (come siempre parecido pero no lo tiene medido), que es el caso más común
    # y el que faltaba. El "parecido" cuenta como que trae dieta -- se le pide un día tipo
    # y se lee igual -- pero queda registrado que no venía medido.
    sigue_dieta: Optional[Union[bool, str]] = None
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
    # El biotipo y la altura se preguntan aqui desde el 06-08-2026: estaban en el perfil
    # largo, que solo ven los planes con coach, asi que el de 297 EUR no los daba nunca.
    # NO mueven macros -- el biotipo es una hipotesis de partida que el coach corrige
    # viendo como responde -- pero sin ellos no hay ni ficha ni caso parecido, y sin
    # altura no hay indice de muscularidad.
    biotype: Optional[str] = None
    height: Optional[float] = Field(default=None, ge=120, le=230)

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

    # Bloque 3 del documento del 06-08-2026. Lo que hace falta para montarle la rutina, y
    # que faltaba: entrenar AHORA no es lo mismo que llevar años (se puede llevar diez y
    # estar parado desde marzo), y lo que NO tiene pesa tanto como lo que tiene -- una
    # rutina con jaula de sentadilla no vale si en su gimnasio no hay.
    entrena_ahora: Optional[str] = None             # si | irregular | no
    maquinas_que_faltan: Optional[str] = None
    ejercicios_imposibles: Optional[str] = None

    # Bloque 5: su suplementacion. No existia, y sin esto se le pauta a ciegas: repitiendole
    # algo que ya toma o chocando con lo que lleva.
    suplementos_ahora: Optional[str] = None
    suplementos_antes: Optional[str] = None
    quiere_pauta_suplementos: Optional[str] = None  # si | lo_justo | no

    # Bloque 4: la intencion cuenta tanto como el uso. Hay que saberlo ANTES, no cuando ya
    # lo ha hecho.
    farmacologia_uso: Optional[str] = None          # uso | use | intencion | nunca

    # Bloque 6: su comida. Lo que decide si los menus le encajan en la vida o los abandona
    # en tres dias. Las 36 categorias y el momento del dia van aparte, en las preferencias.
    cocina_o_rapido: Optional[str] = None           # cocinar | normal | rapido
    conserva_o_fresco: Optional[str] = None         # conserva | ambos | fresco
    come_fuera: Optional[str] = None                # no | 1_2 | 3_4 | casi_todos
    que_le_apetece: Optional[str] = None
    favoritos_y_no_gustos: Optional[str] = None
    plato_imprescindible: Optional[str] = None
    # Las intolerancias, ESTRUCTURADAS y no en texto libre: de "soy intolerante a la
    # lactosa" no se puede sacar si puede comer yogur o queso curado, y de eso depende
    # media lista de la compra. Lo mismo con celiaquia contra sensibilidad.
    lactosa: Optional[str] = None                   # bien | tolera_algo | nada
    gluten: Optional[str] = None                    # bien | sensibilidad | celiaquia

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
    # LA FECHA DEL PESO, que NO es la del ajuste (punto 27 del 07-08). El coach ajusta hoy
    # leyendo un reporte de hace una semana: si ese peso se archiva con la fecha del ajuste,
    # la curva de peso queda corrida y el modelo aprende de un historico falso. Aqui viaja la
    # fecha del pesaje (la del reporte). Si no viene, se usa la del ajuste, como antes.
    peso_fecha: Optional[str] = None
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
