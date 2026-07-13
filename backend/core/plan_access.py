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
    if access_until and access_until < datetime.now(timezone.utc).isoformat():
        return False
    # Perfil gestionado por Stripe: manda el estado real de la suscripción.
    if profile.get("stripe_subscription_id"):
        return (profile.get("subscription_status") or "").lower() in ACTIVE_SUBSCRIPTION_STATES
    # Sin suscripción Stripe → alta manual/comp/legacy: basta que el perfil esté activo.
    return status == "activo"


def plan_features(plan_code: Optional[str]) -> list:
    """Lista de features que habilita el plan (['rutina','suplementacion',...])."""
    return PLAN_TYPES.get((plan_code or "").lower().strip(), {}).get("features", [])


def plan_grants_feature(plan_code: Optional[str], feature: Optional[str]) -> bool:
    """True si el plan habilita la feature (o si no se exige feature concreta)."""
    if not feature:
        return True
    return feature in plan_features(plan_code)


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
        if not plan_grants_feature(profile.get("plan"), feature):
            raise HTTPException(
                status_code=403,
                detail="Tu plan no incluye esta función. Cambia de plan para activarla.",
            )
        return {"user": user, "profile": profile}

    return _dep
