"""
Rutas de facturación con Stripe (suscripciones, test mode).
- Cliente: crear sesión de checkout, sincronizar al volver, portal de facturación.
- Webhook: /api/stripe/webhooks (eventos de Stripe).
- Admin: sincronizar con Stripe, pagos próximos, incidencias de pago, alertas.
"""
import os
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends, Request, Body
from typing import Any, Dict, List
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from core.database import db
from core.security import get_current_user, get_admin_user
from models.common import (
    CheckoutSessionRequest, CheckoutSessionResponse, BillingPortalResponse,
    PaymentResponse, AlertResponse,
)
from models.user import PLAN_CATALOG
from core.stripe_billing import (
    get_stripe_module, stripe_api_call, require_stripe_test_mode,
    get_plan_info, get_stripe_price_id_for_plan, build_frontend_url,
    ensure_checkout_profile, get_or_create_stripe_customer,
    sync_profile_from_subscription, sync_profile_from_one_time_session,
    upsert_payment_from_invoice,
    update_profile_payment_method, get_payment_method_from_invoice,
    get_payment_method_status_from_error, find_client_profile, create_alert,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])
webhook_router = APIRouter(prefix="/stripe", tags=["stripe"])
admin_router = APIRouter(prefix="/admin/stripe", tags=["admin-stripe"])


# ==================== CLIENTE ====================

@router.post("/checkout-session", response_model=CheckoutSessionResponse)
async def create_checkout_session(data: CheckoutSessionRequest, user=Depends(get_current_user)):
    stripe_module = get_stripe_module()
    require_stripe_test_mode("La creación de checkout")
    plan_info = get_plan_info(data.plan)

    # Solo se venden online los planes comercialmente activos (los legacy se respetan
    # a quien ya los tiene, pero no se contratan de nuevo; especiales → alta manual).
    override = await db.plan_overrides.find_one({"code": plan_info["code"]}, {"_id": 0, "fields": 1})
    estado = ((override or {}).get("fields", {}).get("estado")
              or PLAN_CATALOG.get(plan_info["code"], {}).get("estado"))
    if estado != "activo":
        raise HTTPException(status_code=400, detail="Este plan ya no está disponible para nuevas contrataciones.")

    profile = await ensure_checkout_profile(user, plan_info["code"])
    customer_id = await get_or_create_stripe_customer(user, profile)

    success_url = build_frontend_url(data.success_path, include_session_placeholder=True)
    cancel_url = build_frontend_url(data.cancel_path)
    stripe_price_id = get_stripe_price_id_for_plan(plan_info["code"])

    checkout_metadata = {"user_id": user["id"], "profile_id": profile["id"], "plan": plan_info["code"]}
    session_kwargs = dict(
        customer=customer_id,
        client_reference_id=profile["id"],
        line_items=[{"price": stripe_price_id, "quantity": 1}],
        allow_promotion_codes=True,
        billing_address_collection="auto",
        customer_update={"address": "auto", "name": "auto"},
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=checkout_metadata,
    )
    if plan_info.get("one_time"):
        # Pago único (p.ej. reto60): un solo cobro, sin suscripción. La factura se genera
        # para que invoice.payment_succeeded registre el pago igual que en suscripciones.
        session_kwargs["mode"] = "payment"
        session_kwargs["invoice_creation"] = {"enabled": True}
        session_kwargs["payment_intent_data"] = {"metadata": checkout_metadata}
    else:
        session_kwargs["mode"] = "subscription"
        session_kwargs["subscription_data"] = {"metadata": checkout_metadata}
    session = await stripe_api_call(stripe_module.checkout.Session.create, **session_kwargs)

    await db.client_profiles.update_one(
        {"id": profile["id"]},
        {"$set": {"stripe_customer_id": customer_id, "stripe_price_id": stripe_price_id, "checkout_status": "created"}},
    )
    return CheckoutSessionResponse(checkout_url=session["url"], session_id=session["id"], profile_id=profile["id"])


@router.post("/checkout-session/sync")
async def sync_checkout_session(payload: Dict[str, Any] = Body(...), user=Depends(get_current_user)):
    """Llamado por el frontend al volver de Stripe (?checkout=success&session_id=...),
    para no depender solo del webhook."""
    stripe_module = get_stripe_module()
    require_stripe_test_mode("La sincronización de checkout")

    session_id = payload.get("session_id") if isinstance(payload, dict) else None
    session_id = session_id.strip() if isinstance(session_id, str) else ""
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id es requerido")

    try:
        session = await stripe_api_call(
            stripe_module.checkout.Session.retrieve, session_id,
            expand=["subscription", "subscription.default_payment_method"],
        )
    except Exception as exc:
        logger.exception("Error recuperando checkout session %s", session_id)
        raise HTTPException(status_code=400, detail=f"No se pudo recuperar la sesión de Stripe: {exc}") from exc

    metadata = session.get("metadata") or {}
    profile_id = session.get("client_reference_id") or metadata.get("profile_id")
    # La sesión debe llevar el user_id del que sincroniza (todas las que crea la app lo
    # llevan). Sin esta exigencia, una sesión creada fuera de la app (sin metadata) podría
    # ser sincronizada por cualquier usuario y activarle el perfil con un pago ajeno.
    if metadata.get("user_id") != user["id"]:
        raise HTTPException(status_code=403, detail="La sesión no pertenece a este usuario")

    subscription = session.get("subscription")
    if isinstance(subscription, str):
        try:
            subscription = await stripe_api_call(
                stripe_module.Subscription.retrieve, subscription, expand=["default_payment_method"])
        except Exception:
            logger.exception("Error recuperando subscription de session %s", session_id)
            subscription = None

    synced_profile = None
    if subscription:
        synced_profile = await sync_profile_from_subscription(
            subscription, profile_id=profile_id, user_id=user["id"], customer_id=session.get("customer"))
        default_pm = subscription.get("default_payment_method") if isinstance(subscription, dict) else None
        if synced_profile and isinstance(default_pm, dict):
            card = default_pm.get("card") or {}
            await db.client_profiles.update_one(
                {"id": synced_profile["id"]},
                {"$set": {
                    "payment_method_status": "ok",
                    "payment_method_brand": card.get("brand"),
                    "payment_method_last4": card.get("last4"),
                    "payment_method_exp_month": card.get("exp_month"),
                    "payment_method_exp_year": card.get("exp_year"),
                }},
            )
            synced_profile = await db.client_profiles.find_one({"id": synced_profile["id"]}, {"_id": 0})

    if not synced_profile and session.get("mode") == "payment":
        # Checkout de pago único (p.ej. reto60): no hay suscripción que sincronizar.
        synced_profile = await sync_profile_from_one_time_session(session, user_id=user["id"])

    if not synced_profile and profile_id:
        synced_profile = await db.client_profiles.find_one({"id": profile_id}, {"_id": 0})

    return {
        "session_id": session_id,
        "payment_status": session.get("payment_status"),
        "subscription_status": (subscription or {}).get("status") if isinstance(subscription, dict) else None,
        "profile": synced_profile,
    }


@router.post("/portal", response_model=BillingPortalResponse)
async def create_billing_portal(user=Depends(get_current_user)):
    stripe_module = get_stripe_module()
    require_stripe_test_mode("La apertura del portal de facturación")
    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    customer_id = profile.get("stripe_customer_id")
    if not customer_id:
        raise HTTPException(status_code=400, detail="Este cliente todavía no tiene un customer de Stripe sincronizado.")
    session = await stripe_api_call(
        stripe_module.billing_portal.Session.create,
        customer=customer_id, return_url=build_frontend_url("/dashboard/profile"))
    return BillingPortalResponse(url=session["url"])


# ==================== WEBHOOK ====================

@webhook_router.post("/webhooks")
async def stripe_webhooks(request: Request):
    stripe_module = get_stripe_module()
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()
    if not webhook_secret:
        raise HTTPException(status_code=503, detail="Falta STRIPE_WEBHOOK_SECRET en el backend.")

    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    if not signature:
        raise HTTPException(status_code=400, detail="Falta Stripe-Signature")
    try:
        event = stripe_module.Webhook.construct_event(payload, signature, webhook_secret)
    except ValueError:
        raise HTTPException(status_code=400, detail="Payload de webhook inválido")
    except stripe_module.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Firma de webhook inválida")

    # Reclama el evento ANTES de procesarlo (insert con índice único): dos entregas
    # simultáneas del mismo evento no pueden procesarse dos veces. Si el procesado
    # falla, se libera la reclamación para que el reintento automático de Stripe
    # vuelva a intentarlo (marcarlo al final dejaría eventos a medio procesar).
    try:
        await db.stripe_events.insert_one(
            {"id": event["id"], "type": event["type"],
             "processed_at": datetime.now(timezone.utc).isoformat()})
    except DuplicateKeyError:
        return {"received": True, "duplicate": True}

    try:
        await _process_stripe_event(event)
    except Exception:
        await db.stripe_events.delete_one({"id": event["id"]})
        raise
    return {"received": True}


async def _process_stripe_event(event: Dict[str, Any]) -> None:
    stripe_module = get_stripe_module()
    event_type = event["type"]
    obj = event["data"]["object"]

    if event_type == "checkout.session.completed":
        metadata = obj.get("metadata", {}) or {}
        base_update = {"checkout_status": "completed"}
        if obj.get("customer"):
            base_update["stripe_customer_id"] = obj["customer"]
        # Solo se escribe si existe: un checkout de pago único no debe pisar con None
        # la suscripción de un perfil.
        if obj.get("subscription"):
            base_update["stripe_subscription_id"] = obj["subscription"]
        await db.client_profiles.update_one({"id": metadata.get("profile_id")}, {"$set": base_update})
        if obj.get("subscription"):
            subscription = await stripe_api_call(stripe_module.Subscription.retrieve, obj["subscription"])
            await sync_profile_from_subscription(
                subscription, profile_id=metadata.get("profile_id"),
                user_id=metadata.get("user_id"), customer_id=obj.get("customer"))
        elif obj.get("mode") == "payment":
            # Pago único (p.ej. reto60): activa el perfil con acceso hasta fin de ciclo.
            await sync_profile_from_one_time_session(obj)

    elif event_type in {"customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"}:
        await sync_profile_from_subscription(obj)

    elif event_type == "invoice.payment_succeeded":
        profile = await find_client_profile(subscription_id=obj.get("subscription"), customer_id=obj.get("customer"))
        payment_method, _ = await get_payment_method_from_invoice(obj)
        await upsert_payment_from_invoice(obj, profile=profile, status_override="success")
        # El estado del perfil SOLO lo gobiernan las facturas de la suscripción. Una factura
        # suelta pagada (formaciones, rutina del mes, invoice_creation de un pago único) se
        # registra como pago pero no puede reactivar un perfil de baja ni simular membresía.
        if profile and obj.get("subscription"):
            await db.client_profiles.update_one(
                {"id": profile["id"]},
                {"$set": {
                    "status": "activo", "subscription_status": "active",
                    "payment_method_status": "ok", "last_payment_error": None,
                    "checkout_status": "completed", "payment_failure_count": 0,
                }},
            )
            await update_profile_payment_method(profile["id"], payment_method, payment_method_status="ok", last_payment_error=None)
            await db.alerts.update_many(
                {"client_id": profile["id"], "type": {"$in": ["payment_failure", "card_expired"]}, "resolved": False},
                {"$set": {"resolved": True, "resolved_at": datetime.now(timezone.utc).isoformat()}},
            )

    elif event_type == "invoice.payment_failed":
        profile = await find_client_profile(subscription_id=obj.get("subscription"), customer_id=obj.get("customer"))
        payment_method, payment_error = await get_payment_method_from_invoice(obj)
        error_code = (payment_error or {}).get("code")
        error_message = (payment_error or {}).get("message") or "Stripe no pudo cobrar esta factura."
        await upsert_payment_from_invoice(obj, profile=profile, status_override="failed",
                                          failure_code=error_code, failure_message=error_message)
        # Igual que en payment_succeeded: una factura suelta fallida (ajena a la suscripción)
        # no debe cortar el acceso ni disparar la baja automática de la membresía.
        if profile and obj.get("subscription"):
            # Contador atómico ($inc): reintentos concurrentes de Stripe no pierden
            # incrementos. Primero se normaliza a número (un null heredado rompería $inc).
            await db.client_profiles.update_one(
                {"id": profile["id"], "payment_failure_count": {"$not": {"$type": "number"}}},
                {"$set": {"payment_failure_count": 0}},
            )
            counted = await db.client_profiles.find_one_and_update(
                {"id": profile["id"]},
                {"$inc": {"payment_failure_count": 1}},
                return_document=ReturnDocument.AFTER,
                projection={"_id": 0, "payment_failure_count": 1},
            )
            failure_count = (counted or {}).get("payment_failure_count") or 1
            auto_baja = failure_count >= 3
            await db.client_profiles.update_one(
                {"id": profile["id"]},
                {"$set": {
                    "status": "baja_automatica" if auto_baja else "pago_pendiente",
                    "subscription_status": "canceled" if auto_baja else "past_due",
                    "checkout_status": "attention_required",
                    "payment_method_status": get_payment_method_status_from_error(error_code),
                    "last_payment_error": error_message,
                }},
            )
            await update_profile_payment_method(
                profile["id"], payment_method,
                payment_method_status=get_payment_method_status_from_error(error_code), last_payment_error=error_message)
            if auto_baja:
                sub_id = profile.get("stripe_subscription_id")
                if sub_id and not sub_id.startswith("sub_test_"):
                    try:
                        await stripe_api_call(stripe_module.Subscription.cancel, sub_id)
                    except Exception as exc:
                        logger.error("Error cancelando suscripción %s: %s", sub_id, exc)
                await create_alert(
                    profile["id"], "baja_automatica", "Baja automática por fallos de pago",
                    f"Cliente dado de baja tras {failure_count} cobros fallidos. Último error: {error_message}",
                    severity="critical", related_data={"failure_count": failure_count, "error_code": error_code})
            else:
                await create_alert(
                    profile["id"], "payment_failure", f"Cobro fallido ({failure_count}/3)",
                    f"Stripe no pudo cobrar la cuota. {error_message}",
                    severity="critical" if failure_count >= 2 else "warning",
                    related_data={"failure_count": failure_count, "error_code": error_code}, dedupe=False)

# ==================== ADMIN ====================

@admin_router.post("/sync-client/{client_id}")
async def sync_client_with_stripe(client_id: str, user=Depends(get_admin_user)):
    stripe_module = get_stripe_module()
    profile = await db.client_profiles.find_one({"id": client_id}, {"_id": 0})
    if not profile:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    user_data = await db.users.find_one({"id": profile["user_id"]}, {"_id": 0, "password": 0})
    if not user_data:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if profile.get("stripe_customer_id"):
        customers = [await stripe_api_call(stripe_module.Customer.retrieve, profile["stripe_customer_id"])]
    else:
        customer_list = await stripe_api_call(stripe_module.Customer.list, email=user_data["email"], limit=10)
        customers = list(customer_list.data)
    if not customers:
        raise HTTPException(status_code=404, detail="No se encontró ningún customer en Stripe para este email.")

    selected_customer = customers[0]
    selected_subscription = None
    for customer in customers:
        subs = await stripe_api_call(stripe_module.Subscription.list, customer=customer["id"], status="all", limit=10)
        if subs.data:
            selected_customer = customer
            selected_subscription = sorted(subs.data, key=lambda s: s.get("created", 0), reverse=True)[0]
            break

    await db.client_profiles.update_one({"id": client_id}, {"$set": {"stripe_customer_id": selected_customer["id"]}})

    synced_payments = 0
    one_time_session_id = None
    if selected_subscription:
        await sync_profile_from_subscription(
            selected_subscription, profile_id=client_id, user_id=profile["user_id"], customer_id=selected_customer["id"])
        invoices = await stripe_api_call(
            stripe_module.Invoice.list, customer=selected_customer["id"], subscription=selected_subscription["id"], limit=24)
        for invoice in invoices.data:
            await upsert_payment_from_invoice(invoice, profile=profile)
            synced_payments += 1
    else:
        # Sin suscripción: puede ser un pago único (reto60) cuyo webhook/sync se perdió.
        # Se busca un checkout pagado en mode=payment que referencie a este perfil.
        sessions = await stripe_api_call(
            stripe_module.checkout.Session.list, customer=selected_customer["id"], limit=10)
        for s in sessions.data:
            refs = {s.get("client_reference_id"), (s.get("metadata") or {}).get("profile_id")}
            if s.get("mode") == "payment" and s.get("payment_status") == "paid" and client_id in refs:
                if await sync_profile_from_one_time_session(s):
                    one_time_session_id = s["id"]
                break

    updated = await db.client_profiles.find_one({"id": client_id}, {"_id": 0})
    return {
        "success": selected_subscription is not None or one_time_session_id is not None,
        "customer_id": selected_customer["id"],
        "subscription_id": selected_subscription["id"] if selected_subscription else None,
        "one_time_session_id": one_time_session_id,
        "synced_payments": synced_payments,
        "profile": updated,
    }


@admin_router.post("/sync-pending")
async def sync_pending_subscriptions(user=Depends(get_admin_user)):
    """Resincroniza perfiles en estado intermedio: suscripciones leyendo su estado real
    de Stripe, y checkouts de pago único ya pagados cuyo webhook/sync se perdió."""
    stripe_module = get_stripe_module()
    pending = await db.client_profiles.find(
        {"subscription_status": {"$in": ["incomplete", "past_due", "incomplete_expired", "unpaid"]},
         "stripe_subscription_id": {"$type": "string"}},
        {"_id": 0, "id": 1, "stripe_subscription_id": 1},
    ).to_list(200)
    synced = 0
    for p in pending:
        try:
            sub = await stripe_api_call(stripe_module.Subscription.retrieve, p["stripe_subscription_id"])
            await sync_profile_from_subscription(sub, profile_id=p["id"])
            synced += 1
        except Exception as exc:
            logger.warning("No se pudo sincronizar %s: %s", p.get("id"), exc)

    # Pagos únicos a medias: perfil quedó "incomplete" sin suscripción pero con customer;
    # si en Stripe hay un checkout mode=payment PAGADO que lo referencia, se activa.
    pending_one_time = await db.client_profiles.find(
        {"subscription_status": "incomplete",
         "stripe_subscription_id": {"$not": {"$type": "string"}},
         "stripe_customer_id": {"$type": "string"}},
        {"_id": 0, "id": 1, "stripe_customer_id": 1},
    ).to_list(200)
    recovered = 0
    for p in pending_one_time:
        try:
            sessions = await stripe_api_call(
                stripe_module.checkout.Session.list, customer=p["stripe_customer_id"], limit=10)
            for s in sessions.data:
                refs = {s.get("client_reference_id"), (s.get("metadata") or {}).get("profile_id")}
                if s.get("mode") == "payment" and s.get("payment_status") == "paid" and p["id"] in refs:
                    if await sync_profile_from_one_time_session(s):
                        recovered += 1
                    break
        except Exception as exc:
            logger.warning("No se pudo recuperar pago único de %s: %s", p.get("id"), exc)
    return {"synced": synced, "checked": len(pending),
            "one_time_recovered": recovered, "one_time_checked": len(pending_one_time)}


@admin_router.get("/upcoming-payments")
async def upcoming_payments(user=Depends(get_admin_user)):
    profiles = await db.client_profiles.find(
        {"next_payment": {"$type": "string"}, "subscription_status": {"$in": ["active", "trialing", "past_due"]}},
        {"_id": 0, "id": 1, "user_id": 1, "plan": 1, "price": 1, "next_payment": 1, "subscription_status": 1},
    ).sort("next_payment", 1).to_list(200)
    return {"upcoming": profiles}


@admin_router.get("/payment-issues")
async def payment_issues(user=Depends(get_admin_user)):
    profiles = await db.client_profiles.find(
        {"$or": [
            {"status": {"$in": ["pago_pendiente", "baja_automatica", "checkout_expirado"]}},
            {"payment_method_status": {"$in": ["caducada", "actualizar_tarjeta"]}},
            {"last_payment_error": {"$type": "string"}},
        ]},
        {"_id": 0, "id": 1, "user_id": 1, "plan": 1, "status": 1, "subscription_status": 1,
         "payment_method_status": 1, "last_payment_error": 1, "payment_failure_count": 1, "next_payment": 1},
    ).to_list(200)
    return {"issues": profiles}


@admin_router.get("/alerts", response_model=List[AlertResponse])
async def list_alerts(resolved: bool = False, user=Depends(get_admin_user)):
    alerts = await db.alerts.find({"resolved": resolved}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return [AlertResponse(**a) for a in alerts]


@admin_router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: str, user=Depends(get_admin_user)):
    r = await db.alerts.update_one(
        {"id": alert_id},
        {"$set": {"resolved": True, "resolved_at": datetime.now(timezone.utc).isoformat(),
                  "acknowledged": True, "acknowledged_by": user.get("id"),
                  "acknowledged_at": datetime.now(timezone.utc).isoformat()}})
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    return {"resolved": True}
