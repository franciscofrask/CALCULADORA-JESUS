"""
La rutina del mes que se compra desde el reporte mensual (T8 del doc del 16-08).

Al cliente cuyo plan no incluye rutina se le ofrece dentro de su reporte:

    TODOS LOS MESES · La rutina del mes
    Por estar en Bronze la tienes en 57 €. Te llega en unos días, junto con el ajuste
    nuevo de tus macros.
    [Sí · modalidad básica] [Sí · modalidad avanzada] [Ahora no]
    Al marcar «Sí» autorizas el cargo en tu tarjeta.

Esa última línea es la que manda aquí: **se cobra en la tarjeta que ya tiene puesta**, no
se le manda a una pantalla de pago a mitad del reporte. Si no se puede (no tiene tarjeta
guardada, o el banco pide autenticación), NO se le cobra a la fuerza: se deja constancia
para que el equipo lo resuelva, que es justo lo que ya hace el aviso de compra.

Como en la revisión suelta, el importe va en línea y NO como producto de Stripe: así el
precio se cambia tocando esta constante y no hay que mantener un producto por cada precio.

NADA DE ESTO COBRA SOLO SI NO ESTÁ CONFIGURADO: sin clave de Stripe, o con el modo live
bloqueado, `cobrar` devuelve que no se ha cobrado y el reporte se envía igual. Un cobro que
falla no puede impedirle al cliente mandar su reporte.
"""
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ── PRECIO ────────────────────────────────────────────────────────────────────
# 57 EUR, del documento de Jesús del 16-08. OJO: el catálogo de planes tiene la "Rutina del
# Mes" suelta a 55 EUR (`rutina_mes` en models/user.py); son dos cosas distintas -- aquella
# es la compra suelta y esta es la del reporte -- y hasta que Jesús diga lo contrario cada
# una mantiene su precio. Si se unifican, este número sale de allí.
PRECIO_EUR = 57.0
NOMBRE_PRODUCTO = "La rutina del mes"
DESCRIPCION = "Tu rutina del mes, con el ajuste nuevo de tus macros."

MODALIDADES = ("basica", "avanzada")

# Por qué no se pudo cobrar. Se guarda tal cual en el aviso del equipo para que quien lo
# atienda sepa si tiene que pedirle la tarjeta o solo esperar.
SIN_TARJETA = "sin_tarjeta"
REQUIERE_AUTENTICACION = "requiere_autenticacion"
RECHAZADA = "rechazada"
SIN_STRIPE = "sin_stripe"


def importe_centimos() -> int:
    return int(round(PRECIO_EUR * 100))


def _clave_de_idempotencia(profile_id: str, report_id: str) -> str:
    """La misma petición no cobra dos veces.

    Un reporte se puede reenviar -- el cliente le da dos veces, o se reintenta la petición --
    y sin esto cada intento sería un cargo nuevo de 57 EUR. La clave es del par cliente y
    reporte, así que Stripe devuelve el cobro original en vez de hacer otro.
    """
    return f"rutina_del_mes:{profile_id}:{report_id}"


async def cobrar(profile: Dict[str, Any], modalidad: str, report_id: str) -> Dict[str, Any]:
    """Cobra la rutina del mes en la tarjeta que el cliente ya tiene guardada.

    Devuelve siempre un diccionario, nunca levanta: esto se llama al enviar el reporte y el
    reporte tiene que salir aunque el cobro no entre.

        {"cobrado": True,  "importe_eur": 57.0, "payment_intent": "pi_...", "modalidad": ...}
        {"cobrado": False, "motivo": "sin_tarjeta" | "requiere_autenticacion" | ...}
    """
    salida = {"cobrado": False, "importe_eur": PRECIO_EUR, "modalidad": modalidad}

    if modalidad not in MODALIDADES:
        return {**salida, "motivo": "modalidad_desconocida"}

    from core.stripe_billing import (STRIPE_ALLOW_LIVE_MODE, get_stripe_key_mode,
                                     get_stripe_module, stripe_api_call)

    modo = get_stripe_key_mode()
    if modo == "missing" or (modo == "live" and not STRIPE_ALLOW_LIVE_MODE):
        # Sin Stripe configurado no se cobra y no se rompe nada: queda la petición para el
        # equipo, que es como funcionaba antes de que existiera este cobro.
        return {**salida, "motivo": SIN_STRIPE}

    customer_id = profile.get("stripe_customer_id")
    if not customer_id:
        return {**salida, "motivo": SIN_TARJETA}

    stripe_module = get_stripe_module()
    try:
        metodos = await stripe_api_call(
            stripe_module.PaymentMethod.list, customer=customer_id, type="card", limit=1)
        tarjetas = (metodos or {}).get("data") or []
        cliente = await stripe_api_call(stripe_module.Customer.retrieve, customer_id)
        por_defecto = ((cliente or {}).get("invoice_settings") or {}).get("default_payment_method")
        tarjeta = por_defecto or (tarjetas[0]["id"] if tarjetas else None)
        if not tarjeta:
            return {**salida, "motivo": SIN_TARJETA}

        intento = await stripe_api_call(
            stripe_module.PaymentIntent.create,
            amount=importe_centimos(),
            currency="eur",
            customer=customer_id,
            payment_method=tarjeta,
            off_session=True,      # no está delante de la pantalla: lo autorizó en el reporte
            confirm=True,
            description=f"{NOMBRE_PRODUCTO} ({modalidad})",
            metadata={"tipo": "rutina_del_mes", "modalidad": modalidad,
                      "profile_id": profile.get("id"), "report_id": report_id},
            idempotency_key=_clave_de_idempotencia(profile.get("id"), report_id),
        )
    except Exception as exc:                     # noqa: BLE001 - Stripe levanta de mil formas
        codigo = getattr(exc, "code", None) or ""
        motivo = REQUIERE_AUTENTICACION if "authentication_required" in str(codigo) else RECHAZADA
        # El detalle a la consola; al cliente y al equipo, el motivo en una palabra.
        logger.warning("No se pudo cobrar la rutina del mes a %s: %s", profile.get("id"), exc)
        return {**salida, "motivo": motivo}

    if (intento or {}).get("status") == "succeeded":
        return {"cobrado": True, "importe_eur": PRECIO_EUR, "modalidad": modalidad,
                "payment_intent": intento.get("id")}
    return {**salida, "motivo": (intento or {}).get("status") or RECHAZADA}
