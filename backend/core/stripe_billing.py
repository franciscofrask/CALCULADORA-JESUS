"""
Capa de facturación con Stripe (suscripciones, test mode).
Portado de calmajp: helpers de checkout, sincronización de suscripción, pagos y alertas.

Todo lee STRIPE_SECRET_KEY en vivo desde el entorno, así que basta añadir la key a .env
y reiniciar el backend. Por defecto solo permite test mode (sk_test_...).
"""
import os
import asyncio
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

from fastapi import HTTPException

from .config import (
    STRIPE_API_VERSION, STRIPE_ALLOW_LIVE_MODE, FRONTEND_URL, CORS_ORIGINS,
    DEFAULT_BILLING_CYCLE_DAYS,
)
from .database import db
from models.user import PLAN_TYPES

try:
    import stripe
except ImportError:  # pragma: no cover
    stripe = None

logger = logging.getLogger(__name__)

ALERT_TYPES = {
    "payment_failure", "baja_automatica", "card_expired",
    "report_overdue", "missed_checkin", "weight_jump", "low_adherence", "manual",
}
ALERT_SEVERITIES = {"info", "warning", "critical"}
ALERT_DEDUPE_DAYS = 7


# ==================== Stripe module / config ====================

# Mensaje genérico de cara al usuario: el detalle real (qué variable falta, qué
# módulo, qué excepción) va SOLO al log. Un error de configuración nunca debe
# exponer nombres de variables, scripts o internos del código en la respuesta.
PAGOS_NO_DISPONIBLES = "Los pagos no están disponibles en este momento. Inténtalo más tarde o contacta con soporte."


def get_stripe_module():
    if stripe is None:
        logger.error("Stripe no disponible: la dependencia 'stripe' no está instalada")
        raise HTTPException(status_code=503, detail=PAGOS_NO_DISPONIBLES)
    secret_key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    if not secret_key:
        logger.error("Stripe no disponible: falta STRIPE_SECRET_KEY en el entorno")
        raise HTTPException(status_code=503, detail=PAGOS_NO_DISPONIBLES)
    stripe.api_key = secret_key
    stripe.api_version = STRIPE_API_VERSION
    return stripe


async def stripe_api_call(callable_obj, *args, **kwargs):
    """Corre una llamada síncrona del SDK de Stripe en un hilo (no bloquea el event loop)."""
    return await asyncio.to_thread(callable_obj, *args, **kwargs)


def get_stripe_key_mode() -> str:
    secret_key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    if secret_key.startswith("sk_test_"):
        return "test"
    if secret_key.startswith("sk_live_"):
        return "live"
    return "missing"


def require_stripe_test_mode(action: str = "Esta operación"):
    mode = get_stripe_key_mode()
    if mode == "missing":
        logger.error("Stripe no disponible para pruebas: falta STRIPE_SECRET_KEY")
        raise HTTPException(status_code=503, detail=PAGOS_NO_DISPONIBLES)
    if mode != "test" and not STRIPE_ALLOW_LIVE_MODE:
        raise HTTPException(
            status_code=409,
            detail=f"{action} está bloqueada: el proyecto está configurado solo para Stripe test mode.",
        )


# ==================== Planes / precios ====================

def get_plan_info(plan: str) -> Dict[str, Any]:
    plan_key = (plan or "").lower().strip()
    plan_info = PLAN_TYPES.get(plan_key)
    if not plan_info:
        raise HTTPException(status_code=400, detail="Plan no válido")
    return {"code": plan_key, **plan_info}


def get_stripe_price_id_for_plan(plan: str) -> str:
    plan_info = get_plan_info(plan)
    env_name = plan_info["stripe_price_env"]
    price_id = os.environ.get(env_name, "").strip()
    if not price_id:
        logger.error(
            "Precio de Stripe sin configurar para el plan %s: falta %s (correr setup_stripe_products.py)",
            plan_info["name"], env_name,
        )
        raise HTTPException(
            status_code=503,
            detail=f"El plan {plan_info['name']} no está disponible para compra en este momento. "
                   "Inténtalo más tarde o contacta con soporte.",
        )
    return price_id


def infer_plan_from_price_id(price_id: Optional[str]) -> Optional[str]:
    if not price_id:
        return None
    for plan_code, plan_info in PLAN_TYPES.items():
        if os.environ.get(plan_info["stripe_price_env"], "").strip() == price_id:
            return plan_code
    return None


# ==================== Frontend URLs ====================

def get_frontend_base_url() -> str:
    if FRONTEND_URL:
        return FRONTEND_URL.rstrip("/")
    origins = [o.strip() for o in CORS_ORIGINS if o.strip() and o.strip() != "*"]
    if origins:
        return origins[0].rstrip("/")
    return "http://localhost:3000"


def build_frontend_url(path: Optional[str], *, include_session_placeholder: bool = False) -> str:
    normalized = path or "/dashboard"
    if normalized.startswith("http://") or normalized.startswith("https://"):
        final_url = normalized
    else:
        if not normalized.startswith("/"):
            normalized = f"/{normalized}"
        final_url = f"{get_frontend_base_url()}{normalized}"
    if include_session_placeholder and "{CHECKOUT_SESSION_ID}" not in final_url:
        sep = "&" if "?" in final_url else "?"
        final_url = f"{final_url}{sep}session_id={{CHECKOUT_SESSION_ID}}"
    return final_url


# ==================== Conversores ====================

def stripe_timestamp_to_iso(ts: Optional[int]) -> Optional[str]:
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def cents_to_amount(cents: Optional[int]) -> float:
    return round((cents or 0) / 100, 2)


def map_subscription_status_to_profile_status(sub_status: Optional[str]) -> str:
    return {
        "trialing": "activo",
        "active": "activo",
        "past_due": "pago_pendiente",
        "unpaid": "baja_automatica",
        "canceled": "cancelado",
        "incomplete": "pendiente_pago",
        "incomplete_expired": "checkout_expirado",
        "paused": "pausado",
    }.get(sub_status or "", "pendiente_pago")


def get_payment_method_status_from_error(error_code: Optional[str]) -> str:
    if error_code == "expired_card":
        return "caducada"
    if error_code:
        return "actualizar_tarjeta"
    return "ok"


# ==================== Perfil / customer ====================

async def find_client_profile(*, profile_id=None, subscription_id=None, customer_id=None, user_id=None):
    if profile_id:
        p = await db.client_profiles.find_one({"id": profile_id})
        if p:
            return p
    if subscription_id:
        p = await db.client_profiles.find_one({"stripe_subscription_id": subscription_id})
        if p:
            return p
    if customer_id:
        p = await db.client_profiles.find_one({"stripe_customer_id": customer_id})
        if p:
            return p
    if user_id:
        return await db.client_profiles.find_one({"user_id": user_id})
    return None


async def ensure_checkout_profile(user: Dict[str, Any], plan: str, *, price_override=None, trainer_id=None):
    """Crea/actualiza el perfil del cliente en estado 'pendiente_pago' antes del checkout.
    El webhook (o el sync de retorno) lo activa cuando el pago se confirma."""
    plan_info = get_plan_info(plan)
    profile = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    now_iso = datetime.now(timezone.utc).isoformat()
    stripe_price_id = get_stripe_price_id_for_plan(plan)
    profile_price = price_override if price_override is not None else plan_info["price"]

    if profile and profile.get("subscription_status") in {"active", "trialing", "past_due"}:
        raise HTTPException(status_code=400, detail="Este cliente ya tiene una suscripción activa o en cobro pendiente.")

    if profile:
        if "id" not in profile:
            profile["id"] = str(uuid.uuid4())
            await db.client_profiles.update_one({"user_id": user["id"]}, {"$set": {"id": profile["id"]}})
        update_data = {
            "plan": plan_info["code"],
            "price": profile_price,
            "status": "pendiente_pago",
            "subscription_status": "incomplete",
            "checkout_status": "draft",
            "stripe_price_id": stripe_price_id,
            "next_payment": None,
            "current_period_start": None,
            "current_period_end": None,
            "cancel_at_period_end": False,
            "billing_cycle_days": plan_info["billing_cycle_weeks"] * 7,
            "last_payment_error": None,
            # Limpia la caducidad de una compra única anterior (p.ej. reto60 → ELM).
            "access_until": None,
        }
        if trainer_id is not None:
            update_data["trainer_id"] = trainer_id
        await db.client_profiles.update_one({"id": profile["id"]}, {"$set": update_data})
        profile = await db.client_profiles.find_one({"id": profile["id"]}, {"_id": 0})
    else:
        profile = {
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "plan": plan_info["code"],
            "price": profile_price,
            "week": 1,
            "status": "pendiente_pago",
            "trainer_id": trainer_id,
            "next_payment": None,
            "macros_training": None,
            "macros_rest": None,
            "weight": None,
            "height": None,
            "age": None,
            "sex": None,
            "goal": None,
            # OJO: stripe_customer_id / stripe_subscription_id NO se ponen aquí: tienen índice
            # único parcial y escribir null explícito choca entre varios perfiles.
            "stripe_price_id": stripe_price_id,
            "subscription_status": "incomplete",
            "checkout_status": "draft",
            "current_period_start": None,
            "current_period_end": None,
            "cancel_at_period_end": False,
            "billing_cycle_days": plan_info["billing_cycle_weeks"] * 7,
            "payment_method_status": None,
            "last_payment_error": None,
            "created_at": now_iso,
        }
        await db.client_profiles.insert_one(profile)

    # OJO: NO se setea users.plan aquí. El plan del usuario (lo que la UI usa para mostrar
    # capacidades) solo debe reflejarse cuando el pago se confirma; lo hace
    # sync_profile_from_subscription al activarse la suscripción. Setearlo antes de pagar
    # concedía el plan por el mero hecho de iniciar (y abandonar) el checkout.
    return profile


async def get_or_create_stripe_customer(user: Dict[str, Any], profile: Dict[str, Any]) -> str:
    stripe_module = get_stripe_module()
    if profile.get("stripe_customer_id"):
        return profile["stripe_customer_id"]
    existing = await stripe_api_call(stripe_module.Customer.list, email=user["email"], limit=10)
    if existing.data:
        customer = existing.data[0]
    else:
        customer = await stripe_api_call(
            stripe_module.Customer.create,
            email=user["email"], name=user.get("name"), phone=user.get("phone"),
            metadata={"user_id": user["id"], "profile_id": profile["id"], "plan": profile["plan"]},
        )
    await db.client_profiles.update_one({"id": profile["id"]}, {"$set": {"stripe_customer_id": customer["id"]}})
    return customer["id"]


async def update_profile_payment_method(profile_id, payment_method, *, payment_method_status=None, last_payment_error=None):
    update: Dict[str, Any] = {}
    if payment_method is not None:
        card = payment_method.get("card", {}) or {}
        update.update({
            "payment_method_brand": card.get("brand"),
            "payment_method_last4": card.get("last4"),
            "payment_method_exp_month": card.get("exp_month"),
            "payment_method_exp_year": card.get("exp_year"),
        })
    if payment_method_status is not None:
        update["payment_method_status"] = payment_method_status
    if last_payment_error is not None:
        update["last_payment_error"] = last_payment_error
    if update:
        await db.client_profiles.update_one({"id": profile_id}, {"$set": update})


async def get_payment_method_from_invoice(invoice: Dict[str, Any]):
    stripe_module = get_stripe_module()
    pi_id = invoice.get("payment_intent")
    if not pi_id:
        return None, None
    try:
        pi = await stripe_api_call(stripe_module.PaymentIntent.retrieve, pi_id)
    except Exception as exc:
        logger.warning("No se pudo recuperar PaymentIntent %s: %s", pi_id, exc)
        return None, None
    pm_id = pi.get("payment_method")
    pm = None
    if pm_id:
        try:
            pm = await stripe_api_call(stripe_module.PaymentMethod.retrieve, pm_id)
        except Exception as exc:
            logger.warning("No se pudo recuperar PaymentMethod %s: %s", pm_id, exc)
    return pm, pi.get("last_payment_error")


# ==================== Sincronización suscripción / pagos ====================

async def sync_profile_from_subscription(subscription, *, profile_id=None, user_id=None, customer_id=None):
    metadata = subscription.get("metadata", {}) or {}
    items = subscription.get("items", {}).get("data", [])
    first_item = items[0] if items else {}
    price_id = first_item.get("price", {}).get("id")
    plan_code = metadata.get("plan") or infer_plan_from_price_id(price_id)
    profile = await find_client_profile(
        profile_id=profile_id or metadata.get("profile_id"),
        subscription_id=subscription.get("id"),
        customer_id=customer_id or subscription.get("customer"),
        user_id=user_id or metadata.get("user_id"),
    )
    if not profile:
        logger.warning("No se encontró perfil para sincronizar suscripción %s", subscription.get("id"))
        return None

    status = subscription.get("status")
    update: Dict[str, Any] = {
        "stripe_customer_id": customer_id or subscription.get("customer"),
        "stripe_subscription_id": subscription.get("id"),
        "stripe_price_id": price_id or profile.get("stripe_price_id"),
        "subscription_status": status,
        "status": map_subscription_status_to_profile_status(status),
        "checkout_status": "completed" if status in {"active", "trialing", "past_due"} else profile.get("checkout_status"),
        "current_period_start": stripe_timestamp_to_iso(subscription.get("current_period_start")),
        "current_period_end": stripe_timestamp_to_iso(subscription.get("current_period_end")),
        "next_payment": stripe_timestamp_to_iso(subscription.get("current_period_end")),
        "cancel_at_period_end": bool(subscription.get("cancel_at_period_end")),
        "billing_cycle_days": profile.get("billing_cycle_days", DEFAULT_BILLING_CYCLE_DAYS),
        # Perfil gestionado por suscripción: no aplica la caducidad de compra única.
        "access_until": None,
    }
    if status in {"active", "trialing"}:
        update["last_payment_error"] = None
    if plan_code:
        plan_info = get_plan_info(plan_code)
        update["plan"] = plan_info["code"]
        update["price"] = plan_info["price"]
        # users.plan (capacidades en la UI) solo se refleja con la suscripción activa;
        # con incomplete/past_due/canceled el usuario no debe "tener" el plan.
        if status in {"active", "trialing"}:
            await db.users.update_one({"id": profile["user_id"]}, {"$set": {"plan": plan_info["code"]}})
        elif status in {"canceled", "unpaid", "incomplete_expired"}:
            await db.users.update_one({"id": profile["user_id"]}, {"$set": {"plan": None}})
    if status in {"canceled", "unpaid", "incomplete_expired"}:
        update["next_payment"] = None
        update["current_period_end"] = stripe_timestamp_to_iso(subscription.get("ended_at")) or update["current_period_end"]

    await db.client_profiles.update_one({"id": profile["id"]}, {"$set": update})
    return await db.client_profiles.find_one({"id": profile["id"]}, {"_id": 0})


async def sync_profile_from_one_time_session(session, *, user_id=None):
    """Activa el perfil tras un checkout de pago único (mode='payment', p.ej. reto60).
    No hay suscripción: el acceso dura el ciclo del plan (access_until) y no se renueva."""
    if session.get("payment_status") != "paid":
        return None
    metadata = session.get("metadata", {}) or {}
    profile = await find_client_profile(
        profile_id=session.get("client_reference_id") or metadata.get("profile_id"),
        customer_id=session.get("customer"),
        user_id=user_id or metadata.get("user_id"),
    )
    if not profile:
        logger.warning("No se encontró perfil para checkout de pago único %s", session.get("id"))
        return None

    plan_info = get_plan_info(metadata.get("plan") or profile.get("plan"))
    # El acceso se ancla a la FECHA DEL PAGO (created de la sesión), no a cuándo se
    # procesa: recuperar una sesión antigua vía admin sync no regala ciclo extra.
    created_ts = session.get("created")
    start = (datetime.fromtimestamp(created_ts, tz=timezone.utc)
             if created_ts else datetime.now(timezone.utc))
    end = start + timedelta(days=plan_info["billing_cycle_weeks"] * 7)
    await db.client_profiles.update_one(
        {"id": profile["id"]},
        {"$set": {
            "stripe_customer_id": session.get("customer") or profile.get("stripe_customer_id"),
            "plan": plan_info["code"],
            "price": plan_info["price"],
            "status": "activo",
            "subscription_status": None,
            "checkout_status": "completed",
            "current_period_start": start.isoformat(),
            "current_period_end": end.isoformat(),
            "access_until": end.isoformat(),
            "next_payment": None,
            "cancel_at_period_end": False,
            "billing_cycle_days": plan_info["billing_cycle_weeks"] * 7,
            "last_payment_error": None,
        }},
    )
    await db.users.update_one({"id": profile["user_id"]}, {"$set": {"plan": plan_info["code"]}})
    return await db.client_profiles.find_one({"id": profile["id"]}, {"_id": 0})


async def upsert_payment_from_invoice(invoice, *, profile=None, status_override=None, failure_code=None, failure_message=None):
    if profile is None:
        profile = await find_client_profile(
            subscription_id=invoice.get("subscription"), customer_id=invoice.get("customer"),
        )
    if not profile:
        logger.warning("No se encontró perfil para factura %s", invoice.get("id"))
        return None

    status = status_override
    if not status:
        if invoice.get("paid"):
            status = "success"
        elif invoice.get("status") in {"draft", "open"}:
            status = "pending"
        else:
            status = "failed"

    payment_doc = {
        "client_id": profile["id"],
        "user_id": profile["user_id"],
        "amount": cents_to_amount(invoice.get("amount_paid") or invoice.get("amount_due") or invoice.get("total")),
        "status": status,
        "method": "card",
        "currency": (invoice.get("currency") or "eur").upper(),
        "stripe_invoice_id": invoice.get("id"),
        "stripe_subscription_id": invoice.get("subscription"),
        "failure_code": failure_code,
        "failure_message": failure_message,
        "created_at": stripe_timestamp_to_iso(invoice.get("created")) or datetime.now(timezone.utc).isoformat(),
        "paid_at": stripe_timestamp_to_iso((invoice.get("status_transitions") or {}).get("paid_at")),
    }
    existing = await db.payments.find_one({"stripe_invoice_id": invoice.get("id")})
    if existing:
        await db.payments.update_one({"id": existing["id"]}, {"$set": payment_doc})
        payment_doc["id"] = existing["id"]
    else:
        payment_doc["id"] = str(uuid.uuid4())
        await db.payments.insert_one(payment_doc)
    return payment_doc


# ==================== Alertas ====================

async def create_alert(client_id, type_, title, message, severity="warning", related_data=None, dedupe=True):
    if type_ not in ALERT_TYPES:
        logger.warning("Tipo de alerta desconocido: %s", type_)
    if severity not in ALERT_SEVERITIES:
        severity = "warning"
    if dedupe:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=ALERT_DEDUPE_DAYS)).isoformat()
        existing = await db.alerts.find_one(
            {"client_id": client_id, "type": type_, "resolved": False, "created_at": {"$gte": cutoff}},
            {"_id": 0, "id": 1},
        )
        if existing:
            return None
    alert = {
        "id": str(uuid.uuid4()),
        "client_id": client_id,
        "type": type_,
        "severity": severity,
        "title": title,
        "message": message,
        "related_data": related_data,
        "acknowledged": False,
        "acknowledged_by": None,
        "acknowledged_at": None,
        "resolved": False,
        "resolved_at": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.alerts.insert_one(alert)
    return alert
