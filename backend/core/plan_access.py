"""
Enforcement de acceso por plan/suscripción (server-side).

Modelo de producto (decidido): **Stripe + alta manual admin**.
  - El acceso a las funciones de pago SOLO se concede si la suscripción está activa.
  - No hay auto-alta del cliente sin pago: el perfil se activa por webhook de Stripe
    (pago confirmado) o por asignación manual del admin (plan cortesía / comp_plan /
    clientes importados de Calma que ya estaban activos).

Regla de "acceso activo" (segura para la migración, sin bloquear a la base existente):
  - Estados de baja/cancelación/impago bloquean SIEMPRE.
  - Si el perfil está gestionado por Stripe (tiene stripe_subscription_id): exige que
    subscription_status ∈ ACTIVE_SUBSCRIPTION_STATES. Así un pago fallido / cancelación
    (past_due, canceled, unpaid, incomplete...) corta el acceso.
  - Si el perfil NO tiene suscripción Stripe (importado de Calma o alta manual/comp del
    admin): basta status == "activo". Los endpoints de bypass que ponían status "activo"
    sin cobrar fueron eliminados, así que este camino solo lo abren admin/webhook.

Las features se derivan del plan (PLAN_TYPES[plan].features, ver models/user.py). Un
endpoint premium exige acceso activo Y, si aplica, que el plan habilite su feature.
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException

from .database import db
from .security import get_current_user
from models.user import PLAN_TYPES

# Estados de suscripción de Stripe que conceden acceso. Para dar un periodo de gracia
# ante un primer cobro fallido, añade "past_due" (el backend ya da de baja automática a
# los 3 intentos). Por defecto, solo pagos al día.
ACTIVE_SUBSCRIPTION_STATES = {"active", "trialing"}

# ─────────────────────────────────────────────────────────────────────────────
# LA RUTINA, PARA EL CLIENTE.
#
# Se escondio el 19-07-2026 "hasta completar la funcionalidad" con una constante en el
# codigo, y su gemela en el front (CAP.RUTINA en lib/planAccess.js). Desde el doc 16-08
# (T3) ya no es una constante: manda el interruptor `t3_entreno` de db.app_settings, que
# se apaga y se enciende desde el panel sin desplegar. Los dos lados leen lo mismo: el
# front por `pantalla('t3_entreno')`, el backend por aqui.
#
# Lo que abre este interruptor es lo que el cliente VE y lo que se le DICE (la pantalla
# de la rutina, la de registro del entreno y el aviso de rutina nueva). El panel del
# entrenador no depende de el: sigue creando, generando y asignando rutinas.
async def rutina_visible_para_el_cliente() -> bool:
    """¿Puede el cliente ver la rutina y registrar sus entrenos?"""
    from routes.settings import pantalla_activa
    return await pantalla_activa("t3_entreno")

# Estados del perfil que bloquean el acceso pase lo que pase (baja, cancelación, impago).
BLOCKED_PROFILE_STATES = {
    "baja", "baja_automatica", "cancelado", "inactivo",
    "pago_pendiente", "pendiente_pago", "checkout_expirado", "pausado",
}


def has_active_access(profile: Optional[Dict[str, Any]]) -> bool:
    """True si el perfil tiene una membresía activa (pagada por Stripe o dada de alta
    por el admin / importada como activa). Ver la regla en el docstring del módulo."""
    if not profile:
        return False
    status = (profile.get("status") or "").lower()
    if status in BLOCKED_PROFILE_STATES:
        return False
    # Compra de pago único (p.ej. reto60): el acceso caduca al terminar el programa.
    # Solo el flujo de checkout one-time escribe access_until, así que no afecta a la
    # base existente (importados/alta manual no tienen este campo).
    access_until = profile.get("access_until")
    ahora = datetime.now(timezone.utc).isoformat()
    if access_until and access_until < ahora:
        return False
    # Perfil gestionado por Stripe: manda el estado real de la suscripción.
    if profile.get("stripe_subscription_id"):
        return (profile.get("subscription_status") or "").lower() in ACTIVE_SUBSCRIPTION_STATES

    # SIN STRIPE, SI SE SABE CUANDO ACABA, SE MIRA (punto 5.4). Aquí bastaba con que el perfil
    # dijera "activo", así que un ciclo terminado dejaba al cliente dentro para siempre: el
    # estado es una etiqueta que alguien puso una vez y no se entera de que pasa el tiempo.
    #
    # Solo `current_period_end`, que es cuando SE ACABA lo pagado. `next_payment` no vale para
    # esto: que un cobro se retrase no quiere decir que la membresía haya terminado, y cortarle
    # la app a alguien que paga por un cobro que no ha entrado todavía sería peor que el fallo.
    #
    # Medido en producción el 09-08: de 169 perfiles sin Stripe, 168 no tienen ninguna fecha de
    # fin, así que hoy esto no le quita el acceso a nadie. Es un cerrojo para el que la tenga y
    # para los que vengan.
    fin = str(profile.get("current_period_end") or "")
    if fin and fin[:10] < ahora[:10]:
        return False

    # Sin suscripción Stripe → alta manual/comp/legacy: basta que el perfil esté activo.
    return status == "activo"


def estado_de_acceso(profile: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Si tiene acceso y, si no lo tiene, POR QUE (punto 41 del doc del 07-08).

    Hasta ahora la app solo sabia decir "no tiene acceso", y por eso al cliente que llevaba
    un ano pagando y se le acababa el ciclo se le ensenaba la misma pantalla que al que
    acaba de registrarse: "Bienvenido a 12EN12, selecciona un plan". No es lo mismo no
    haber empezado que haber terminado, y el que termina merece que se le diga y a quien
    escribir.

    `motivo` es lo que decide el mensaje:
      sin_plan   - nunca contrato nada
      sin_pagar  - inicio un checkout y no lo termino
      caducado   - lo tuvo y se le acabo (baja, cancelacion, impago o fin de ciclo)
    """
    if not profile:
        return {"activo": False, "motivo": "sin_plan"}
    # Sin plan no hay acceso, aunque el perfil este "activo". `has_active_access` no mira
    # el plan -- solo el estado y la suscripcion -- asi que un perfil activo y sin plan le
    # daba el visto bueno. No es un cliente todavia: es alguien que se registro.
    if not profile.get("plan"):
        return {"activo": False, "motivo": "sin_plan"}
    if has_active_access(profile):
        return {"activo": True, "motivo": None}
    # Un checkout empezado y nunca pagado: no llego a ser cliente.
    if (profile.get("status") == "pendiente_pago"
            and profile.get("checkout_status") in ("draft", "created")):
        return {"activo": False, "motivo": "sin_pagar"}
    # Tenia plan y ya no tiene acceso: se le acabo.
    return {"activo": False, "motivo": "caducado"}


def plan_features(plan_code: Optional[str]) -> list:
    """Lista de features que habilita el plan (['rutina','suplementacion',...]).

    Pasa por `codigo_de_plan` para resolver los alias: hay perfiles migrados con el plan
    escrito sin normalizar ("CalMa"), y sin esto no casaban con ninguna entrada del
    catalogo y el cliente se quedaba sin ninguna habilitacion.
    """
    from models.user import codigo_de_plan
    return PLAN_TYPES.get(codigo_de_plan(plan_code), {}).get("features", [])


def plan_grants_feature(plan_code: Optional[str], feature: Optional[str]) -> bool:
    """True si el plan habilita la feature (o si no se exige feature concreta).

    Version SIN overrides: solo para los sitios que no pueden esperar a la base. El cerrojo
    de verdad es `plan_grants_feature_vivo`.
    """
    if not feature:
        return True
    return feature in plan_features(plan_code)


async def plan_features_vivo(plan_code: Optional[str]) -> list:
    """Las features del plan CON lo que el equipo haya editado en el panel.

    `PLAN_TYPES` se calcula una sola vez al importar `models/user.py`, desde el catalogo
    escrito en codigo. Los cambios del panel viven en `db.plan_overrides` y ahi no entraban
    nunca: quitarle la suplementacion a un plan hacia desaparecer la entrada del menu -- eso
    lo decide `GET /plans`, que si los lee -- mientras `GET /supplements/current` seguia
    devolviendo 200 con los datos. O sea que lo que editaba el equipo era cosmetico del lado
    del servidor (caso 69 de la lista del 12-08).
    """
    from models.user import codigo_de_plan, merged_catalog
    from routes.plans import _overrides_by_code
    try:
        catalogo = merged_catalog(await _overrides_by_code())
    except Exception:
        # Si la base no contesta, mejor el catalogo del codigo que dejar a todos fuera.
        return plan_features(plan_code)
    return (catalogo.get(codigo_de_plan(plan_code)) or {}).get("features", [])


async def plan_grants_feature_vivo(plan_code: Optional[str], feature: Optional[str]) -> bool:
    """True si el plan habilita la feature, mirando tambien los overrides del panel."""
    if not feature:
        return True
    return feature in await plan_features_vivo(plan_code)


def modo_calculadora(plan_code: Optional[str]) -> str:
    """
    Como trabaja la calculadora en este plan: 'personalizado' (hay un coach detras que revisa),
    'autogestion' (el cliente se lo lleva solo) o 'sin_ajuste'.

    Es el eje que separa los dos comportamientos del doc del 29-07: en el plan con entrenador los
    macros del cuestionario se calculan pero NO se aplican solos, se le presentan como propuesta y
    esperan a que el coach los valide.
    """
    from models.user import PLAN_CATALOG
    plan = PLAN_CATALOG.get((plan_code or "").lower().strip()) or {}
    return (plan.get("habilitaciones") or {}).get("calculadora") or "sin_ajuste"


def tiene_entrenador_detras(plan_code: Optional[str]) -> bool:
    """True si el plan incluye coach que revisa los macros."""
    return modo_calculadora(plan_code) == "personalizado"


def dias_hasta_la_revision(plan_code: Optional[str]) -> int:
    """
    Cada cuanto le toca revision de macros segun su plan: quincenal si el plan la incluye,
    mensual en el resto. Es lo que hay que decirle al terminar el cuestionario ("tu proxima
    revision automatica sera el ..."), porque un numero sin fecha de repaso no dice cuando
    volver.
    """
    from models.user import PLAN_CATALOG
    plan = PLAN_CATALOG.get((plan_code or "").lower().strip()) or {}
    reportes = (plan.get("habilitaciones") or {}).get("reportes") or []
    if "semanal" in reportes:
        return 7
    if "quincenal" in reportes:
        return 14
    return 28


def require_access(feature: Optional[str] = None):
    """Dependencia FastAPI: exige perfil con acceso activo y, opcionalmente, que el plan
    habilite `feature`. Devuelve {'user', 'profile'} para reutilizar el perfil ya leído.

    - 404 si no hay perfil (aún no ha completado el alta).
    - 402 si el perfil existe pero la suscripción no está activa (impago/baja).
    - 403 si el plan no incluye la feature pedida.
    """
    async def _dep(user: dict = Depends(get_current_user)) -> Dict[str, Any]:
        profile = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
        if not profile:
            raise HTTPException(status_code=404, detail="Perfil no encontrado")
        if not has_active_access(profile):
            raise HTTPException(
                status_code=402,
                detail="Tu suscripción no está activa. Regulariza el pago para acceder a esta función.",
            )
        if not await plan_grants_feature_vivo(profile.get("plan"), feature):
            raise HTTPException(
                status_code=403,
                detail="Tu plan no incluye esta función. Cambia de plan para activarla.",
            )
        return {"user": user, "profile": profile}

    return _dep
