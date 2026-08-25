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
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ── PRECIO ────────────────────────────────────────────────────────────────────
# 57 EUR, del documento de Jesús del 16-08. Es el MISMO precio que el del catálogo
# (`rutina_mes` en models/user.py), que estaba a 55 y lo cerró Francisco el 16-08: son dos
# puertas al mismo producto -- la compra suelta y la del reporte -- y un cliente no puede
# verlo a un precio y pagar otro. Este es el número que se cobra; el del catálogo es el que
# se enseña, y `test_cobro_rutina_del_mes` no deja que se separen.
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
# No hay NADA preparado que entregar este mes (verificación 24-08, fallo 14).
SIN_RUTINA_PREPARADA = "sin_rutina_preparada"


def importe_centimos() -> int:
    return int(round(PRECIO_EUR * 100))


async def su_plan_ya_la_lleva(plan_code: Optional[str]) -> bool:
    """¿El plan de este cliente ya incluye la rutina? Entonces no se le vende.

    El criterio es el del catálogo (`habilitaciones.rutina`) y el mismo que usa la pantalla
    de Rutina para decidir si enseña la oferta: «ninguna» y «opcional» NO la llevan --
    opcional es justo eso, que se la puede comprar --, cualquier otro modo sí.
    """
    from core.plan_access import catalogo_vivo
    from models.user import codigo_de_plan

    catalogo = await catalogo_vivo()
    ficha = catalogo.get(codigo_de_plan(plan_code)) or {}
    modo = (ficha.get("habilitaciones") or {}).get("rutina")
    return bool(modo) and modo not in ("ninguna", "opcional")


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

    # MODO PRUEBAS: una cuenta de laboratorio NUNCA cobra de verdad, aunque Stripe esté en
    # vivo. Es el freno para que probar el envío de un reporte no acabe en un cargo real.
    # `es_pruebas` vive en el usuario; lo miramos por el contextvar de la petición.
    from core.contexto_pruebas import usuario_actual
    _u = usuario_actual()
    if (_u and _u.get("es_pruebas")) or profile.get("es_pruebas"):
        return {**salida, "motivo": "cuenta_de_pruebas"}

    if modalidad not in MODALIDADES:
        return {**salida, "motivo": "modalidad_desconocida"}

    # ¿POR QUÉ EL CANDADO DE «NO SE COBRA LO QUE NO SE PUEDE ENTREGAR» NO ESTÁ AQUÍ?
    #
    # (Verificación 24-08, fallo 14.) Este `cobrar` lo llaman DOS puertas: la pantalla de
    # Rutina (`routes/routines.quiero_la_rutina`) y el «Sí» del reporte mensual
    # (`routes/reports.py`). El candado -- `routines.hay_rutina_del_mes_que_entregar()` --
    # está puesto en las puertas y no aquí porque este `cobrar` está probado con una base
    # de mentira (tests/test_cobro_rutina_del_mes.py) y una consulta real a Mongo dentro lo
    # dejaría todo en rojo.
    #
    # QUEDA UN CABO, Y ES DE DINERO: `routes/reports.py` sigue cobrando 57 EUR aunque no
    # haya nada preparado. Ahí el circuito es a mano por diseño desde el 19-08 (se cobra y
    # se avisa al equipo para que la mande), así que no deja al cliente sin nada en
    # silencio, pero la línea buena es que reports.py llame también a
    # `hay_rutina_del_mes_que_entregar()` antes de cobrar. Ese fichero es de otro bloque.

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


# ── YA ESTÁ PAGADA: QUE LA RECIBA (24-08) ─────────────────────────────────────────────
#
# «Que se compre directamente desde la app» (Jesús, 24-08). Hasta hoy comprar la rutina
# del mes solo dejaba un aviso en el panel para que alguien se la mandara a mano, y por
# eso hay clientes que la pagaron y siguen sin verla en su pantalla.
#
# Esto es lo que pasa cuando el pago entra, venga del webhook de Stripe o de la vuelta del
# checkout: se apunta en su ficha (que es lo que mira la pantalla para no volver a
# venderle lo mismo), se le pone la rutina del mes vigente, y se avisa al equipo. Si no hay
# nada preparado, la entrega sigue siendo a mano: eso lo dice el aviso con todas las letras
# para que nadie dé por hecho que ya la tiene.
#
# QUÉ SE ENTREGA (verificación 24-08, fallo 14): la plantilla estructurada marcada «la del
# mes» si la hay y, si no, EL PDF DEL MES, que es la entrega real del negocio. Antes solo
# sabía entregar la plantilla, y en producción no había ninguna: se cobraba y no llegaba
# nada. Desde el mismo arreglo, las dos puertas de compra que hay en la app no dejan
# cobrar cuando no hay nada preparado, así que este `None` ya casi no debería darse.
async def activar_tras_pago(profile: Dict[str, Any], importe_eur: Optional[float] = None,
                            modalidad: str = "basica",
                            session_id: Optional[str] = None,
                            cobrado: bool = True,
                            motivo: Optional[str] = None) -> bool:
    """El pago ha entrado: se apunta, se entrega y el equipo se entera.

    Devuelve si se ha activado ahora (False si ya estaba, para que el webhook y la vuelta
    del checkout -- que llegan los dos -- no la cobren ni la entreguen dos veces).
    """
    from core.avisos_equipo import avisar_al_equipo
    from core.database import db
    from core.tiempo import hoy_madrid

    pedida = (profile or {}).get("rutina_mes_pedida") or {}
    # La misma compra dos veces no: el webhook y el `sync` del navegador llegan los dos, y
    # sin esto la segunda vuelta le pondría la rutina otra vez y le sonaría otro aviso.
    # Esto es solo el atajo barato; el candado de verdad es el `$addToSet` de aquí abajo.
    if session_id and pedida.get("session_id") == session_id:
        return False

    # SE PIDE LA VEZ ANTES DE ENTREGAR NADA (repaso 24-08). El «¿ya está apuntada?» de arriba
    # LEE y luego ESCRIBE, y entre lo uno y lo otro cabe la otra llamada: el webhook de
    # Stripe y la vuelta del navegador llegan a la vez y los dos se traen la ficha limpia.
    # Medido con una compra de verdad en el modo prueba de Stripe: DOS filas en `rutina_pdfs`
    # con 32 ms de diferencia y DOS avisos «ha pagado la rutina del mes básica (57 €)» al
    # equipo por UN solo pago. Ese aviso cuenta como DINERO en el panel, o sea una venta
    # inventada en la caja del día.
    #
    # `$addToSet` porque es lo que Mongo resuelve de una pieza: el pago que ya está en la
    # lista no la cambia y vuelve con `modified_count: 0`, y de dos llamadas a la vez solo
    # una se lo lleva. La lista también deja el histórico de lo que se le ha cobrado por
    # esta puerta, que antes solo se sabía por el último `session_id` de la ficha.
    #
    # Sin `session_id` no hay carrera que ganar (la cuenta de laboratorio no pasa por
    # Stripe): se apunta y punto.
    if session_id:
        reclamo = await db.client_profiles.update_one(
            {"id": profile.get("id")}, {"$addToSet": {"rutina_mes_pagos": session_id}})
        # `getattr` con 1 por defecto, como en `routes/routines.retirar_el_pdf_del_mes`:
        # Motor siempre devuelve un `UpdateResult`, así que en la app el candado es real. El
        # 1 es para las bases de mentira de la batería, que no devuelven nada: si no se sabe
        # quién ganó la carrera, lo que manda es no dejar sin rutina a alguien que ha pagado.
        # Un aviso repetido se borra; un cliente que pagó 57 EUR y no recibió nada, no.
        if not getattr(reclamo, "modified_count", 1):
            return False

    modalidad = modalidad if modalidad in MODALIDADES else "basica"
    # Lo que se cobró de verdad. Solo se cae al precio de tarifa cuando no nos lo dicen
    # (`None`): un 0.0 es un 0.0, y hay que poder distinguirlo.
    importe = PRECIO_EUR if importe_eur is None else importe_eur
    puesta = await _entregarsela(profile.get("id"))

    await db.client_profiles.update_one(
        {"id": profile.get("id")},
        {"$set": {"rutina_mes_pedida": {
            "fecha": hoy_madrid().isoformat(),
            "cuando": datetime.now(timezone.utc).isoformat(),
            "modalidad": modalidad,
            "cobrado": bool(cobrado),
            # Por qué no se cobró, cuando no se cobró. Lo lee la pantalla para NO decirle
            # «el cobro se quedó pendiente» a una cuenta de laboratorio, que no lo está.
            "motivo": motivo,
            "importe_eur": importe,
            "session_id": session_id,
            "rutina_puesta": puesta,
            "origen": "checkout",
        }},
         # Igual que al contestar en el reporte (routes/reports.py): el que aplazó y luego
         # compró recibía igual el recordatorio «¿Te preparamos la rutina del mes?».
         "$unset": {"rutina_mes_aplazada_hasta": ""}},
    )

    etiqueta = "básica" if modalidad == "basica" else "avanzada"
    entrega = (f"Ya tiene puesta «{puesta}»." if puesta else
               "NO hay ninguna rutina del mes preparada (ni plantilla marcada ni PDF del "
               "mes): hay que entregársela a mano.")
    # EL AVISO DICE LO QUE HA PASADO DE VERDAD (24-08). Este tipo de aviso cuenta como
    # DINERO en el panel del equipo (`avisos_equipo.TIPOS_EQUIPO`), así que decir «ha pagado
    # 57 €» cuando la cuenta es de laboratorio -- o cuando el pago entró por otro importe --
    # le mete a Jesús una venta que no existe en la caja del día.
    cobro = (f"ha pagado la rutina del mes {etiqueta} ({importe:.0f} €)" if cobrado
             else f"tiene la rutina del mes {etiqueta} SIN COBRAR"
                  + (f" ({motivo})" if motivo else ""))
    await avisar_al_equipo(
        db, tipo="rutina_del_mes",
        titulo="Ha comprado la rutina del mes" if cobrado else "Rutina del mes sin cobrar",
        mensaje=f"{profile.get('name') or 'Un cliente'} {cobro}. {entrega}",
        client_id=profile.get("id"), trainer_id=profile.get("trainer_id"),
        extra={"modalidad": modalidad, "cobrado": bool(cobrado), "motivo": motivo,
               "importe_eur": importe, "rutina_puesta": puesta, "origen": "checkout"},
    )
    return True


async def _entregarsela(client_id: Optional[str]) -> Optional[str]:
    """Le pone la rutina del mes vigente: la plantilla marcada o, si no la hay, el PDF del
    mes (que es como se entrega de verdad).

    El import va aquí dentro y no arriba porque `routes.routines` arrastra medio backend
    (avisos, modelos, el cliente del LLM) y este módulo lo importa el reporte mensual.
    """
    if not client_id:
        return None
    try:
        from routes.routines import entregar_la_rutina_del_mes
        return await entregar_la_rutina_del_mes(client_id, origen="rutina_del_mes")
    except Exception:                            # noqa: BLE001
        # Que la entrega falle no puede tirar un pago que ya está cobrado: queda el aviso
        # al equipo y se la ponen a mano. El detalle, a la consola.
        logger.exception("No se pudo entregar la rutina del mes a %s", client_id)
        return None
