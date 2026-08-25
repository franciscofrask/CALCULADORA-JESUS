"""
Rutas de facturación con Stripe (suscripciones, test mode).
- Cliente: crear sesión de checkout, sincronizar al volver, portal de facturación.
- Webhook: /api/stripe/webhooks (eventos de Stripe).
- Admin: sincronizar con Stripe, pagos próximos, incidencias de pago, alertas.
"""
import os
import logging
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Depends, Request, Body
from typing import Any, Dict, List
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from core.database import db
from core.sin_futuro import hasta_hoy
from core.security import get_current_user, get_admin_user
from models.common import (
    CheckoutSessionRequest, CheckoutSessionResponse, BillingPortalResponse,
    PaymentResponse, AlertResponse,
)
from models.user import (
    PLAN_CATALOG, codigo_de_plan, merged_catalog, puede_renovar_su_plan_legacy,
)
from core.calendario_arranque import plan_de_arranque
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
    #
    # LA UNICA PUERTA DEL PLAN ANTIGUO (Francisco, 16-08): si el admin ha encendido
    # `renovable_por_los_suyos` en un plan legacy, ese plan se puede cobrar SOLO al cliente
    # que ya lo tiene. Se mira su perfil ANTES de tocarlo, porque `ensure_checkout_profile`
    # le escribe el plan pedido encima y despues ya no habria con que comparar. Para
    # cualquier otro sigue siendo el 400 de siempre: no basta con encender el interruptor,
    # hay que ser de los suyos.
    override = await db.plan_overrides.find_one({"code": plan_info["code"]}, {"_id": 0, "fields": 1})
    campos = (override or {}).get("fields", {})
    base = PLAN_CATALOG.get(plan_info["code"], {})
    estado = campos.get("estado") or base.get("estado")
    renovacion_legacy = False
    precio_congelado = None
    if estado != "activo":
        from routes.plans import _overrides_by_code
        perfil_previo = await db.client_profiles.find_one(
            {"user_id": user["id"]}, {"_id": 0, "plan": 1, "price": 1, "precio_alta": 1})
        catalogo = merged_catalog(await _overrides_by_code())
        el_suyo = codigo_de_plan((perfil_previo or {}).get("plan"))
        if not (el_suyo == plan_info["code"] and puede_renovar_su_plan_legacy(el_suyo, catalogo)):
            raise HTTPException(status_code=400, detail="Este plan ya no está disponible para nuevas contrataciones.")
        # ES LA RENOVACIÓN DE SU PLAN ANTIGUO. Se cobra con SU precio congelado (parte 1:
        # «el precio se congela mientras no se dé de baja»), en línea y como pago único:
        # los legacy no tienen Price en Stripe -- se retiraron de la venta -- y su importe
        # es el de cada cliente, no uno de tarifa.
        #
        # SU PRECIO, O NINGUNO (24-08). La cascada tenía un tercer escalón -- «si no, su
        # último cobro real» -- y adivinar sale caro: ese cobro es el último de CUALQUIER
        # cosa que haya comprado. Medido sobre los diez clientes sin precio guardado, a
        # dos les habría cobrado 60 € por renovar un Reto 12en12, porque 60 € fue su
        # último recibo (un mes de Mantenimiento). Cobrar de menos sin que nadie se entere
        # es peor que no cobrar: ahora, si no se sabe su precio, sale el 400 humano de
        # abajo y lo resuelve el equipo, que es quien sabe lo que pagó.
        renovacion_legacy = True
        precio_congelado = (perfil_previo or {}).get("price") or (perfil_previo or {}).get("precio_alta")
        precio_congelado = float(precio_congelado or plan_info.get("price") or 0)
        if precio_congelado <= 0:
            raise HTTPException(status_code=400,
                                detail="No sabemos tu precio de renovación. Escríbenos y te lo dejamos listo.")

    # EL PREMIUM SE CONTRATA POR LLAMADA (doc 19-08, y era el rojo del caso 05): «nunca con
    # botón de pagar». La pantalla no lo ofrece, pero este endpoint devolvía una URL de
    # Stripe a cualquiera que lo pidiera a mano. El enlace de cobro del Premium lo genera
    # el equipo después de la llamada, por la ficha del lead (su propio endpoint).
    from core.renovacion import es_por_llamada
    if es_por_llamada(plan_info["code"]):
        raise HTTPException(
            status_code=400,
            detail="Este plan se contrata por llamada: agenda la tuya y te mandamos el enlace de pago.")

    # Con el precio congelado por delante: si no, la preparación del checkout le escribe
    # el del catálogo en la ficha (0,00 € en los planes antiguos) y le borra el suyo.
    profile = await ensure_checkout_profile(user, plan_info["code"], price_override=precio_congelado)
    customer_id = await get_or_create_stripe_customer(user, profile)

    success_url = build_frontend_url(data.success_path, include_session_placeholder=True)
    cancel_url = build_frontend_url(data.cancel_path)
    # La renovación del legacy va con precio EN LÍNEA (el congelado de este cliente), no
    # con un Price de catálogo: esos planes no tienen Price en Stripe y pedirlo daría 503.
    if renovacion_legacy:
        stripe_price_id = None
        linea = {"price_data": {"currency": "eur",
                                "unit_amount": int(round(precio_congelado * 100)),
                                "product_data": {"name": f"Renovación · {plan_info['name']}"}},
                 "quantity": 1}
    else:
        stripe_price_id = get_stripe_price_id_for_plan(plan_info["code"])
        linea = {"price": stripe_price_id, "quantity": 1}

    checkout_metadata = {"user_id": user["id"], "profile_id": profile["id"], "plan": plan_info["code"]}
    if renovacion_legacy:
        # SU PRECIO VIAJA CON LA SESIÓN (24-08). Es lo que se le cobra de verdad, y es lo
        # que tiene que quedar en su ficha cuando el pago vuelva: al confirmarlo se
        # escribía el del catálogo, que en los planes antiguos es 0,00 €, así que la
        # renovación SIGUIENTE moría en «No sabemos tu precio de renovación» y el cliente
        # tenía que escribir al equipo para poder seguir pagando.
        checkout_metadata["precio_congelado"] = f"{precio_congelado:.2f}"

    # Si pagó una revisión suelta hace menos de 30 días, ese importe se le descuenta al subir de
    # plan: es lo que hace que probar no le cueste nada. Se crea un cupón de un solo uso por el
    # importe exacto y se marca como aplicado para que no se lo pueda descontar dos veces.
    from core.revision_suelta import descuento_vigente
    descuento = descuento_vigente(profile)
    cupon_id = None
    if descuento:
        try:
            cupon = await stripe_api_call(
                stripe_module.Coupon.create,
                amount_off=int(round(descuento["importe_eur"] * 100)),
                currency="eur", duration="once",
                name="Revisión de macros ya pagada",
                max_redemptions=1,
            )
            cupon_id = cupon["id"]
        except Exception as e:   # noqa: BLE001 - si el cupón falla, el alta NO se bloquea
            logger.warning("No se pudo crear el cupón de la revisión suelta: %s", e)

    session_kwargs = dict(
        customer=customer_id,
        client_reference_id=profile["id"],
        line_items=[linea],
        billing_address_collection="auto",
        customer_update={"address": "auto", "name": "auto"},
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=checkout_metadata,
    )
    if plan_info.get("one_time") or renovacion_legacy:
        # Pago único: un solo cobro, sin suscripción. Desde el 20-08 es el modo de TODO
        # lo que se vende (ningún plan renueva solo: Francisco) y de la renovación del
        # legacy, cuyo precio va en línea. La factura se genera para que
        # invoice.payment_succeeded registre el pago igual que en suscripciones.
        session_kwargs["mode"] = "payment"
        session_kwargs["invoice_creation"] = {"enabled": True}
        session_kwargs["payment_intent_data"] = {"metadata": checkout_metadata}
    else:
        session_kwargs["mode"] = "subscription"
        subscription_data = {"metadata": checkout_metadata}

        # Todos arrancan en lunes (parte 2 de la especificacion). Se cobra el ciclo
        # completo HOY y se ancla la facturacion al lunes que le toca, de forma que el
        # cobro del ciclo siguiente cae el dia que acaba el suyo y no 84 dias despues
        # del pago. Asi el dinero entra ANTES de ponerse a preparar el ciclo que viene:
        # si no renueva, no se trabaja en balde.
        #
        # Esto es justo lo que hoy se hacia a mano cancelando la suscripcion y creando
        # otra, con el riesgo de cobrarle antes de tiempo que el propio SOP advierte. Y
        # ademas, recrear la suscripcion es lo que le rompia el precio congelado.
        #
        # Los dias de la Semana 0 se le REGALAN: proration_behavior="none".
        semanas = int(plan_info.get("billing_cycle_weeks") or 12)
        arranque = plan_de_arranque(semanas_ciclo=semanas)
        subscription_data["billing_cycle_anchor"] = arranque["anchor_timestamp"]
        subscription_data["proration_behavior"] = "none"

        session_kwargs["subscription_data"] = subscription_data
    # Con cupón no se pueden ofrecer códigos promocionales a la vez: Stripe no admite las dos cosas.
    if cupon_id:
        session_kwargs["discounts"] = [{"coupon": cupon_id}]
    else:
        session_kwargs["allow_promotion_codes"] = True

    try:
        session = await stripe_api_call(stripe_module.checkout.Session.create, **session_kwargs)
    except Exception as e:                                          # noqa: BLE001
        # EL PRICE NO CASA CON EL MODO. Pasa en dev con los planes mensuales: el price de
        # test es recurrente y aquí se cobra a pago único, y Stripe devuelve «payment mode
        # but passed a recurring price». Era un 500 seco en la cara del cliente; ahora
        # dice qué pasa (a él, en humano) y deja el detalle en el log para arreglarlo
        # donde toca, que es el price del entorno.
        # OJO (24-08): esta linea decia `plan_code`, que en esta funcion NO EXISTE. El
        # `except` que estaba para dar la cara petaba el mismo con un NameError, asi que
        # el cliente recibia el 500 seco que esto venia a evitar y el log que lo explicaba
        # no se escribia nunca. Se ve en cuanto Stripe rechaza una sesion por cualquier
        # motivo: aqui salio con «No such customer» al probar la renovacion en dev.
        detalle = str(e)
        logging.getLogger("uvicorn.error").error(
            "checkout: Stripe rechazó la sesión del plan %s (price %s, modo %s): %s",
            plan_info["code"], stripe_price_id, session_kwargs.get("mode"), detalle)
        if "recurring price" in detalle or "one-time price" in detalle:
            raise HTTPException(
                status_code=502,
                detail="Este plan no se puede pagar ahora mismo: su precio está mal "
                       "configurado en la pasarela. Ya lo estamos mirando.")
        raise HTTPException(
            status_code=502,
            detail="No hemos podido abrir el pago. Inténtalo en un momento.")

    cambios = {"stripe_customer_id": customer_id, "stripe_price_id": stripe_price_id,
               "checkout_status": "created"}

    if session_kwargs["mode"] == "subscription":
        # El precio de alta se congela mientras no se de de baja (parte 1). Stripe ya lo
        # respeta por si solo -- una suscripcion renueva con el price con el que se creo,
        # no con el del catalogo -- pero se guarda ademas aqui por dos motivos: para
        # poder enseñarselo y, sobre todo, para que se note si alguien recrea la
        # suscripcion y le cambia el precio sin querer.
        cambios["precio_alta"] = float(plan_info.get("price") or 0)
        cambios["precio_alta_at"] = datetime.now(timezone.utc).isoformat()
        cambios["arranque_lunes"] = arranque["arranque"].isoformat()
        cambios["fin_de_ciclo"] = arranque["fin_de_ciclo"].isoformat()
    if cupon_id:
        cambios["revision_suelta.descuento_aplicado"] = True
        cambios["revision_suelta.descuento_cupon"] = cupon_id
    await db.client_profiles.update_one({"id": profile["id"]}, {"$set": cambios})
    return CheckoutSessionResponse(checkout_url=session["url"], session_id=session["id"], profile_id=profile["id"])


async def _dias_con_ajuste(client_id: str, desde, hasta=None) -> int:
    """Cuantas veces le han tocado los macros EN ESTE CICLO. Por dias y hasta hoy.

    Jesus, 12-08-2026: «En la renovacion sigue poniendo AJUSTES 176». Contaba filas de
    `macro_history` de toda la vida del cliente, en una tarjeta que resume el ciclo.

    LA FECHA BUENA ES `effective_date`, NO `created_at`. En las 3.446 filas que vinieron de
    Calma, `created_at` es el dia en que se importaron (todas el 05-08-2026, muchas en el
    mismo milisegundo) y `effective_date` es el dia en que el ajuste entro en vigor. En la
    cuenta de Jesus: 176 filas, 176 fechas de verdad repartidas entre 2022 y 2029, y por
    `created_at` una sola. O sea, los dos numeros que se pueden sacar de ahi -- 176 y 1 --
    son igual de falsos, cada uno por su lado.

    Contado como toca (dentro de su ciclo y hasta hoy): 11. El resto de clientes, entre 0 y 2,
    que es lo que cabe en doce semanas.

    Hasta hoy, ademas, porque hay ajustes programados con fecha por delante -- las de esa
    cuenta llegan a 2029 -- y un ajuste que aun no ha empezado no es algo que ya se le haya
    hecho. Es el mismo criterio que `core.sin_futuro.hasta_hoy` en el resto de la app.
    """
    filas = [f async for f in db.macro_history.find(
        {"client_id": client_id}, {"_id": 0, "effective_date": 1, "created_at": 1})]
    # Las 9 filas hechas en la app no traen `effective_date`; para esas, el dia en que se
    # guardaron ES el dia del ajuste.
    marcas = [f.get("effective_date") or f.get("created_at") for f in filas]
    # EL «HOY» ES EL DE ESPAÑA, no el del reloj del servidor (19-08). El servidor va en UTC,
    # asi que entre las 00:00 y las 02:00 de aqui se queda en el dia anterior y el ajuste de
    # hoy no se contaba: la tarjeta de renovacion decia 4 y «Mis macros» enseñaba 5. Es el
    # mismo fallo que se arreglo en la serie de peso, en otro sitio.
    #
    # `hasta` es el final del ciclo que se esta resumiendo, que no siempre es hoy: al
    # caducado hace meses hay que cortarle en el dia en que su ciclo acabo, o se le cuentan
    # como ajustes «de este ciclo» los de todo lo que lleva fuera.
    from core.tiempo import hoy_madrid
    return dias_distintos(marcas, desde, hasta or hoy_madrid())


def dias_distintos(marcas, desde=None, hasta=None) -> int:
    """Cuantos DIAS distintos hay en una lista de marcas de tiempo, entre `desde` y `hasta`.

    Una marca que no sea una fecha se descarta en vez de contarse: comprobar solo el largo
    dejaba pasar cualquier texto de diez letras.
    """
    inicio = desde.isoformat() if desde else None
    fin = hasta.isoformat() if hasta else None
    dias = set()
    for m in marcas:
        d = str(m or "")[:10]
        try:
            date.fromisoformat(d)
        except ValueError:
            continue
        if (inicio is None or d >= inicio) and (fin is None or d <= fin):
            dias.add(d)
    return len(dias)


@router.get("/renovacion")
async def get_renovacion(user=Depends(get_current_user)):
    """
    La pantalla de la semana 12 (especificacion 31-07-2026, parte 3).

    Primero lo que ha conseguido en el ciclo -- su foto del dia 1 al lado de la de hoy,
    el peso en porcentaje, su constancia -- y despues las tres salidas: seguir igual,
    cambiar de nivel o dejarlo en la membresia.

    No cobra nada ni cambia nada: solo cuenta. Cada salida lleva a su propio checkout.
    """
    from core.renovacion import (
        dias_de_ciclo, inicio_del_ciclo, montar_renovacion, resumen_del_ciclo,
    )
    from models.user import opciones_de_renovacion, merged_catalog
    from routes.plans import _overrides_by_code

    perfil = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not perfil:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")

    # El primer reporte con fotos es el "dia 1": la comparacion que de verdad enseña el
    # cambio, no la del mes pasado.
    primero = await db.reports.find_one(
        {"client_id": perfil["id"], "photos": {"$ne": []}}, {"_id": 0},
        sort=[("created_at", 1)])
    ultimo = await db.reports.find_one(
        hasta_hoy({"client_id": perfil["id"]}), {"_id": 0}, sort=[("created_at", -1)])

    # EL RESUMEN ES DE ESTE CICLO, no de toda su vida con nosotros: el arranque lo decide
    # `core.renovacion.inicio_del_ciclo` (ahi esta contado el caso). Y el «hoy» es el de
    # España, como en `_dias_con_ajuste`: en UTC, entre las 00:00 y las 02:00 de aqui, el
    # dia cuadrado de esta noche no entraba en la cuenta de dias y el ajuste si.
    from core.tiempo import hoy_madrid
    hoy = hoy_madrid()
    d0 = inicio_del_ciclo(perfil, hoy)
    # OJO CON EL NOMBRE: `ultimo` es EL ULTIMO REPORTE y viaja al resumen como tal. El
    # cierre de la ventana de la cuenta es otra cosa y se llama `cierre_ventana`; llamarlo
    # igual pisaba el reporte con una fecha y la pantalla entera respondia 500
    # («'datetime.date' object has no attribute 'get'»).
    dias_totales, dias_dieta, cierre_ventana = 84, 0, hoy
    if d0:
        # Y EL CICLO NO DURA MAS DE LO QUE DURA. La ventana se cerraba en «hoy», asi que al
        # que lleva medio año caducado -- su ultimo ciclo pagado empezo hace nueve meses --
        # le salia «X de 270 dias con el dia cuadrado» y los ajustes de esos nueve meses.
        # Es el mismo «45 de 730» por la tercera puerta: el ciclo que resume esta pantalla
        # termina cuando termino, no hoy.
        cierre_ventana = min(hoy, d0 + timedelta(days=dias_de_ciclo(perfil)))
        dias_totales = max(1, (cierre_ventana - d0).days)
        dias_dieta = await db.diets.count_documents({
            "user_id": user["id"],
            "fecha": {"$gte": d0.isoformat(), "$lte": cierre_ventana.isoformat()}})

    ajustes = await _dias_con_ajuste(perfil["id"], d0, cierre_ventana)
    catalogo = merged_catalog(await _overrides_by_code())

    # Los pesos que viajaron dentro de un ajuste. La mayoria de los clientes de Calma NO tienen
    # serie de peso -- se importaron antes de que existiera -- y sin esto su tarjeta de
    # renovacion salia sin peso y sin cambio mientras «Mis macros» le pintaba la curva entera.
    apuntes_de_peso = await db.macro_history.find(
        {"client_id": perfil["id"]},
        {"_id": 0, "effective_date": 1, "created_at": 1, "peso": 1, "client_weight": 1},
    ).sort([("effective_date", 1)]).to_list(2000)

    return montar_renovacion(
        perfil=perfil,
        catalogo=catalogo,
        opciones_catalogo=opciones_de_renovacion(perfil.get("plan"), catalogo),
        resumen=resumen_del_ciclo(
            reporte_primero=primero, reporte_ultimo=ultimo, perfil=perfil,
            dias_dieta=dias_dieta, dias_totales=dias_totales, ajustes_de_macros=ajustes,
            apuntes_de_peso=apuntes_de_peso),
    )


# Los cuatro motivos del doc del 23-08 (P56), cada uno con su salida en la pantalla:
#   caro           → se le enseña Mantenimiento (60 €/mes) como forma barata de seguir
#   sin_tiempo     → aplazar la decisión y que el equipo le escriba
#   sin_resultados → su entrenador le revisa el plan antes de irse (aviso con prioridad)
#   otra           → campo de texto libre
MOTIVOS_DE_BAJA = {
    "caro": "Es caro",
    "sin_tiempo": "No tengo tiempo ahora",
    "sin_resultados": "No estoy viendo resultados",
    "otra": "Otra cosa",
}

# Las claves del modal anterior (doc 19-08) se siguen aceptando: quien tenga la pantalla
# vieja cargada en el navegador no puede volver con un 400 por pedir la baja.
MOTIVOS_DE_BAJA_ANTIGUOS = {
    "no_consegui": "No he conseguido lo que quería",
    "no_lo_use": "No lo he usado",
    "consegui": "He conseguido lo que quería",
}

# Lo que el cliente eligió hacer con su motivo. "baja" es la única que marca `no_renovar`;
# las otras tres son quedarse (o al menos no irse todavía) y lo que hacen es avisar al
# equipo al momento y dejar la intención escrita en su ficha.
SALIDAS_DE_BAJA = ("baja", "mantenimiento", "aplazar", "revision")


@router.post("/no-renovar")
async def no_quiero_renovar(payload: Dict[str, Any] = Body(default={}),
                            user=Depends(get_current_user)):
    """El «no quiero renovar» de Mi plan (doc del 19-08).

    Lo que pasa al pedirla, tal cual el doc:
      1 · NO pierde el acceso: ha pagado su ciclo y lo termina. Lo único que se marca es
          que no se le va a volver a cobrar (si hay suscripción viva en Stripe, se le pone
          cancel_at_period_end; si no la hay, con la marca basta porque nada cobra solo).
      2 · Salta la tarea a soporte con su nombre y su motivo, con tiempo de sobra para
          hablar antes de que acabe el ciclo.
      3 · Cuando el ciclo acaba, la pantalla de caducado ya no le pide el correo.
    """
    perfil = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not perfil:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")

    motivo_clave = (payload.get("motivo") or "").strip()
    textos = {**MOTIVOS_DE_BAJA_ANTIGUOS, **MOTIVOS_DE_BAJA}
    if motivo_clave not in textos:
        raise HTTPException(status_code=400, detail="Dinos el motivo, aunque sea «otra cosa».")
    motivo = textos[motivo_clave]
    # El texto libre de «otra cosa» (y de quien quiera añadir algo): viaja al equipo tal
    # cual lo escribió, recortado para que un pegote no reviente la tarjeta de la tarea.
    detalle = (payload.get("detalle") or "").strip()[:500]
    if detalle:
        motivo = f"{motivo} · «{detalle}»" if motivo_clave != "otra" else detalle

    salida = (payload.get("salida") or "baja").strip()
    if salida not in SALIDAS_DE_BAJA:
        raise HTTPException(status_code=400, detail="Esa salida no existe.")

    ahora = datetime.now(timezone.utc).isoformat()
    nombre = user.get("name") or user.get("email") or "cliente"

    # LAS SALIDAS QUE NO SON IRSE (P56 del doc 23-08). No marcan `no_renovar` -- el
    # cliente ha elegido quedarse o esperar --, pero la intención queda escrita en su
    # ficha y el equipo se entera AL MOMENTO por el mismo canal de siempre: una tarea
    # con su aviso (core/tareas_automaticas), la que ya usaba la baja.
    if salida != "baja":
        await db.client_profiles.update_one(
            {"user_id": user["id"]},
            {"$set": {"baja_intencion": {"motivo": textos[motivo_clave],
                                         "motivo_clave": motivo_clave,
                                         "detalle": detalle or None,
                                         "salida": salida, "cuando": ahora}}})
        try:
            from core.tareas_automaticas import tarea_intencion_de_baja
            if salida == "revision":
                # «Que su entrenador le revise el plan antes de irse»: al suyo si lo
                # tiene, y para hoy: es la de prioridad.
                await tarea_intencion_de_baja(
                    db, client_id=perfil.get("id"), nombre=nombre,
                    que=(f"{nombre} no está viendo resultados y se planteaba no renovar. "
                         "Revisar su plan hoy y escribirle antes de que acabe su ciclo"),
                    trainer_id=perfil.get("trainer_id"), para_hoy=True)
            elif salida == "aplazar":
                await tarea_intencion_de_baja(
                    db, client_id=perfil.get("id"), nombre=nombre,
                    que=(f"{nombre} no tiene tiempo ahora y aplaza la decisión de renovar. "
                         "Escribirle estos días para verlo con calma"),
                    para_hoy=True)
            else:  # mantenimiento
                await tarea_intencion_de_baja(
                    db, client_id=perfil.get("id"), nombre=nombre,
                    que=(f"{nombre} dice que su plan le sale caro y se pasa a Mantenimiento. "
                         "Comprobar que termina el cambio"),
                    para_hoy=True)
        except Exception as e:
            logger.error(f"[baja] no se pudo crear la tarea de intención: {e}")
        # El precio de Mantenimiento sale del catálogo, no de un número escrito aquí.
        _precio_mant = (PLAN_CATALOG.get("mantenimiento") or {}).get("precio")
        mensajes = {
            "mantenimiento": ("Perfecto. Te llevamos al pago de Mantenimiento: "
                              + (f"{_precio_mant:.0f} € al mes y " if _precio_mant else "")
                              + "te quedas con la app y tus datos."),
            "aplazar": "Hecho, lo aplazamos. Te escribimos estos días y lo decides con calma.",
            "revision": "Hecho. Le pasamos tu plan a tu entrenador para que lo revise y te escriba.",
        }
        return {"ok": True, "salida": salida, "mensaje": mensajes[salida]}

    # La marca en su ficha: es lo que leen la renovación, el panel y los avisos.
    await db.client_profiles.update_one(
        {"user_id": user["id"]},
        {"$set": {"no_renovar": {"motivo": motivo, "motivo_clave": motivo_clave,
                                 "cuando": ahora}}})

    # Si Stripe le iba a cobrar solo, se le dice que no lo haga MÁS -- no que corte ahora:
    # `cancel_at_period_end` respeta el ciclo pagado, que es exactamente la promesa.
    sub_id = perfil.get("stripe_subscription_id")
    if sub_id and perfil.get("subscription_status") in ("active", "trialing"):
        try:
            stripe_module = get_stripe_module()
            await stripe_api_call(stripe_module.Subscription.modify, sub_id,
                                  cancel_at_period_end=True)
        except Exception as e:
            # La marca ya está puesta y la tarea va a salir: que Stripe esté caído no
            # puede tragarse la petición del cliente. El equipo lo verá en la tarea.
            logger.error(f"[baja] no se pudo marcar cancel_at_period_end en {sub_id}: {e}")

    # La tarea automática a soporte: «Nuria Garrido ha pedido la baja. Motivo: me sale
    # caro» — con tiempo de sobra para hablar con ella antes de que se acabe el ciclo.
    try:
        from core.tareas_automaticas import tarea_baja_pedida
        await tarea_baja_pedida(db, client_id=perfil.get("id"),
                                nombre=user.get("name") or user.get("email") or "cliente",
                                motivo=motivo)
    except Exception as e:
        logger.error(f"[baja] no se pudo crear la tarea: {e}")

    hasta = perfil.get("current_period_end") or perfil.get("access_until")
    return {"ok": True,
            "mensaje": "Hecho. No se te vuelve a cobrar y sigues teniendo acceso hasta el "
                       "final de tu ciclo.",
            "acceso_hasta": hasta}


@router.post("/revision-suelta/checkout")
async def comprar_revision_suelta(payload: Dict[str, Any] = Body(default={}), user=Depends(get_current_user)):
    """
    Compra suelta de una revisión de macros por entrenador (sección 6 del doc).

    Para el cliente que se autogestiona: paga una vez y un entrenador le mira los números, sin
    cambiar de plan. Si sube de plan en los 30 días siguientes se le descuenta lo pagado.

    El precio es provisional hasta que Jesús lo cierre (core/revision_suelta.py).
    """
    from core.plan_access import tiene_entrenador_detras
    from core.revision_suelta import PRECIO_EUR, NOMBRE_PRODUCTO, importe_centimos

    stripe_module = get_stripe_module()
    require_stripe_test_mode("La compra de una revisión suelta")

    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    if tiene_entrenador_detras(profile.get("plan")):
        raise HTTPException(status_code=400,
                            detail="Tu plan ya incluye entrenador: tus macros los revisa él.")
    if (profile.get("revision_suelta") or {}).get("estado") == "pendiente":
        raise HTTPException(status_code=409, detail="Ya tienes una revisión pendiente de que la vea tu entrenador.")

    customer_id = await get_or_create_stripe_customer(user, profile)
    metadata = {"user_id": user["id"], "profile_id": profile["id"], "tipo": "revision_suelta"}
    # El precio va en linea (price_data) y no como producto de Stripe: siendo provisional, asi se
    # cambia tocando una constante y no hay que mantener un producto por cada precio de prueba.
    session = await stripe_api_call(
        stripe_module.checkout.Session.create,
        customer=customer_id,
        client_reference_id=profile["id"],
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": "eur",
                "unit_amount": importe_centimos(),
                "product_data": {"name": NOMBRE_PRODUCTO,
                                 "description": "Un entrenador revisa tus macros y te los ajusta."},
            },
            "quantity": 1,
        }],
        invoice_creation={"enabled": True},
        payment_intent_data={"metadata": metadata},
        success_url=build_frontend_url(payload.get("success_path") or "/dashboard?revision=ok",
                                       include_session_placeholder=True),
        cancel_url=build_frontend_url(payload.get("cancel_path") or "/dashboard"),
        metadata=metadata,
    )
    await db.client_profiles.update_one(
        {"id": profile["id"]},
        {"$set": {"revision_suelta": {"estado": "iniciada", "importe_eur": PRECIO_EUR,
                                      "session_id": session["id"],
                                      "creada_at": datetime.now(timezone.utc).isoformat()}}},
    )
    return {"checkout_url": session["url"], "session_id": session["id"], "importe_eur": PRECIO_EUR}


@router.post("/ajuste-a-medida/checkout")
async def comprar_ajuste_a_medida(payload: Dict[str, Any] = Body(default={}),
                                  user=Depends(get_current_user)):
    """La oferta de los 87 € del final del alta (bloque 6 del doc del 18-08).

    Se cobra por Stripe, entra en la cola de los lunes y se puede repetir. Lo único que no
    se permite es tener dos pendientes a la vez: pagar dos veces por el mismo trabajo que
    todavía no se ha hecho no es repetir, es cobrar de más.

    Al que ya lleva entrenador no se le vende: sus macros los revisa él y ya los paga.
    """
    from core.ajuste_a_medida import (
        DESCRIPCION, NOMBRE_PRODUCTO, PRECIO_EUR, hay_uno_pendiente, importe_centimos)
    from core.plan_access import tiene_entrenador_detras

    stripe_module = get_stripe_module()
    require_stripe_test_mode("La compra del ajuste a medida")

    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    if tiene_entrenador_detras(profile.get("plan")):
        raise HTTPException(status_code=400,
                            detail="Tu plan ya incluye entrenador: tus macros los ajusta él.")
    if hay_uno_pendiente(profile):
        raise HTTPException(status_code=409,
                            detail="Ya tienes un ajuste a medida pagado y pendiente de que lo preparemos.")

    customer_id = await get_or_create_stripe_customer(user, profile)
    metadata = {"user_id": user["id"], "profile_id": profile["id"], "tipo": "ajuste_a_medida"}
    session = await stripe_api_call(
        stripe_module.checkout.Session.create,
        customer=customer_id,
        client_reference_id=profile["id"],
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": "eur",
                "unit_amount": importe_centimos(),
                "product_data": {"name": NOMBRE_PRODUCTO, "description": DESCRIPCION},
            },
            "quantity": 1,
        }],
        invoice_creation={"enabled": True},
        payment_intent_data={"metadata": metadata},
        success_url=build_frontend_url(payload.get("success_path") or "/welcome?ajuste=ok",
                                       include_session_placeholder=True),
        cancel_url=build_frontend_url(payload.get("cancel_path") or "/welcome"),
        metadata=metadata,
    )
    await db.client_profiles.update_one(
        {"id": profile["id"]},
        {"$set": {"ajuste_a_medida": {
            **(profile.get("ajuste_a_medida") or {}),
            "quiere": True,
            "estado": "iniciado",
            "importe_eur": PRECIO_EUR,
            "session_id": session["id"],
            "creado_at": datetime.now(timezone.utc).isoformat(),
        }}},
    )
    return {"checkout_url": session["url"], "session_id": session["id"],
            "importe_eur": PRECIO_EUR}


@router.post("/rutina-del-mes/checkout")
async def comprar_la_rutina_del_mes(payload: Dict[str, Any] = Body(default={}),
                                    user=Depends(get_current_user)):
    """Comprar la rutina del mes desde la app (Jesús, 24-08: «que se compre directamente»).

    Hasta hoy la única forma de pagarla era el cargo a la tarjeta ya guardada
    (`POST /routines/quiero-la-rutina`), así que el que no tiene tarjeta -- el que viene de
    Calma, el de Calculadora -- no podía comprarla: se le apuntaba la petición y se le
    decía que el equipo le escribiría. Con el checkout puede pagar cualquiera, con la
    tarjeta que quiera y con factura, que es como ya se venden la revisión suelta y el
    ajuste a medida. Mismo patrón que ellos: precio EN LÍNEA, sin producto de Stripe.

    Al volver del pago, `sync_checkout_session` (y el webhook, el que llegue antes) llaman
    a `rutina_del_mes.activar_tras_pago`, que es quien se la ENTREGA.
    """
    from core.rutina_del_mes import (
        DESCRIPCION, NOMBRE_PRODUCTO, PRECIO_EUR, activar_tras_pago, importe_centimos,
        su_plan_ya_la_lleva)
    from routes.routines import _peticion_viva, hay_rutina_del_mes_que_entregar

    modalidad = str((payload or {}).get("modalidad") or "").strip()
    if modalidad not in ("basica", "avanzada"):
        raise HTTPException(status_code=400, detail="Dinos si la quieres básica o avanzada.")

    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    if await su_plan_ya_la_lleva(profile.get("plan")):
        raise HTTPException(status_code=400, detail="Tu plan ya incluye la rutina: no tienes que comprarla.")
    # El que YA tiene rutina activa no compra otra por error. LA QUE SE COMPRÓ ÉL NO CUENTA
    # (24-08): desde que el pago ENTREGA la rutina del mes, la compra de agosto le deja una
    # rutina activa y esta misma línea le cerraba la de septiembre para siempre. Y es «del
    # mes», así que se vende todos los meses. Lo que frena el segundo cargo del MISMO mes es
    # `_peticion_viva`, que es el candado de dinero y va justo debajo.
    if await db.routines.find_one({"client_id": profile["id"], "status": "active",
                                   "origen": {"$ne": "rutina_del_mes"}}, {"_id": 1}):
        raise HTTPException(status_code=400, detail="Ya tienes una rutina activa.")
    # Ni el que ya la pidió este mes, por cualquiera de las puertas (la pantalla de Rutina
    # o el «Sí» de su reporte mensual): el segundo cargo de 57 € es el fallo caro.
    from core.tiempo import hoy_madrid
    if await _peticion_viva(profile, hoy_madrid()):
        raise HTTPException(status_code=409,
                            detail="Ya nos pediste tu rutina y estamos con ella. Te llega en unos días.")

    # EL CANDADO DE LAS CUENTAS DE PRUEBA: una cuenta de laboratorio NUNCA llega a Stripe,
    # aunque el modo live esté abierto (es la misma regla que frena el cobro del reporte
    # mensual, `rutina_del_mes.cobrar`). Se le entrega la rutina igual, que es lo que se
    # está probando, y queda apuntado que no hubo cobro.
    if user.get("es_pruebas") or profile.get("es_pruebas"):
        await activar_tras_pago(profile, 0.0, modalidad, session_id=None, cobrado=False,
                                motivo="cuenta_de_pruebas")
        # «Ya tienes la rutina puesta» solo si de verdad se le ha puesto: sin nada preparado
        # no hay nada que entregar, y decir que sí es justo lo que hace que una prueba se dé
        # por buena sin serlo.
        puesto = await db.client_profiles.find_one({"id": profile["id"]},
                                                   {"_id": 0, "rutina_mes_pedida": 1})
        puesta = ((puesto or {}).get("rutina_mes_pedida") or {}).get("rutina_puesta")
        return {"sin_pago": True, "importe_eur": PRECIO_EUR, "rutina_puesta": puesta,
                "mensaje": ("Cuenta de pruebas: no se ha cobrado nada y ya tienes la rutina puesta."
                            if puesta else
                            "Cuenta de pruebas: no se ha cobrado nada. No hay ninguna rutina "
                            "del mes preparada, así que no se te ha puesto ninguna.")}

    # NO SE COBRA LO QUE NO SE PUEDE ENTREGAR (verificación 24-08, fallo 14).
    #
    # Esta puerta cobraba 57 € a ciegas: mandaba al checkout de Stripe, apuntaba la compra y
    # dejaba un aviso al equipo que decía con todas las letras «hay que entregársela a
    # mano». En producción, el 24-08, no había NADA que entregar -- cero plantillas marcadas
    # «la del mes» y ningún PDF del mes preparado --, así que cualquiera podía pagar 57 € y
    # no recibir nada automáticamente.
    #
    # Ahora la compra solo se abre cuando hay algo preparado: una plantilla marcada o el PDF
    # del mes (`routes/routines.hay_rutina_del_mes_que_entregar`). La pantalla de Rutina
    # pregunta esto mismo antes de enseñar el botón; esto es el cinturón, para el hueco entre
    # que se pinta el botón y se pulsa.
    #
    # VA JUSTO ANTES DE STRIPE Y DESPUÉS DEL CANDADO DE LAS CUENTAS DE PRUEBA: es un candado
    # de DINERO y una cuenta de laboratorio no llega a pagar nunca. Ahí arriba ya se le dice
    # al que prueba que no se le ha puesto ninguna rutina, que es la información que
    # necesita; cerrarle además la puerta solo le impediría probar el circuito.
    if not await hay_rutina_del_mes_que_entregar():
        # A la consola: cada uno de estos es una venta de 57 € que se cae por no tener la
        # rutina del mes subida.
        logger.warning("Rutina del mes: %s quiso comprarla y no hay ninguna preparada",
                       profile.get("id"))
        raise HTTPException(
            status_code=409,
            detail="La rutina de este mes todavía no está lista. En cuanto la tengamos "
                   "podrás comprarla desde aquí.")

    stripe_module = get_stripe_module()
    require_stripe_test_mode("La compra de la rutina del mes")

    customer_id = await get_or_create_stripe_customer(user, profile)
    metadata = {"user_id": user["id"], "profile_id": profile["id"],
                "tipo": "rutina_del_mes", "modalidad": modalidad}
    session = await stripe_api_call(
        stripe_module.checkout.Session.create,
        customer=customer_id,
        client_reference_id=profile["id"],
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": "eur",
                "unit_amount": importe_centimos(),
                "product_data": {"name": NOMBRE_PRODUCTO, "description": DESCRIPCION},
            },
            "quantity": 1,
        }],
        invoice_creation={"enabled": True},
        payment_intent_data={"metadata": metadata},
        success_url=build_frontend_url(payload.get("success_path") or "/dashboard/routine?rutina=ok",
                                       include_session_placeholder=True),
        cancel_url=build_frontend_url(payload.get("cancel_path") or "/dashboard/routine"),
        metadata=metadata,
    )
    return {"checkout_url": session["url"], "session_id": session["id"],
            "importe_eur": PRECIO_EUR}


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
        # El detalle de la excepción va SOLO al log: puede contener internos de Stripe.
        logger.exception("Error recuperando checkout session %s", session_id)
        raise HTTPException(status_code=400, detail="No se pudo verificar el pago. Inténtalo de nuevo en unos minutos.") from exc

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
        # NADA SE ENTREGA SIN QUE LA SESIÓN ESTÉ PAGADA. Vale para las tres ramas de abajo y la
        # razón está explicada entera en la de la rutina del mes: aquí se entra con un
        # `session_id` que manda el NAVEGADOR, y el endpoint de checkout se lo devuelve al
        # cliente antes de que pague, así que basta con abrir el pago, cerrar Stripe y llamar
        # aquí. En la rutina se cerró el 24-08; la revisión suelta (47 €) y el ajuste a medida
        # (87 €) tenían el mismo agujero y se cierran ahora, con la misma comprobación.
        pagada = session.get("payment_status") == "paid"
        tipo = (session.get("metadata") or {}).get("tipo")
        if tipo in ("revision_suelta", "ajuste_a_medida", "rutina_del_mes") and not pagada:
            logger.warning("%s: sync de la sesion %s con payment_status=%s; no se entrega nada",
                           tipo, session_id, session.get("payment_status"))
        elif tipo == "revision_suelta":
            # Revisión suelta: no cambia el plan. Se activa aquí también (además del webhook)
            # para que el cliente vuelva de Stripe y ya la vea en marcha; activar_tras_pago no
            # duplica si el webhook llegó antes.
            from core.revision_suelta import activar_tras_pago
            perfil = await db.client_profiles.find_one({"user_id": user["id"]})
            if perfil:
                await activar_tras_pago(perfil, (session.get("amount_total") or 0) / 100.0)
                synced_profile = await db.client_profiles.find_one({"id": perfil["id"]}, {"_id": 0})
        elif tipo == "ajuste_a_medida":
            # El ajuste a medida de 87 €, igual: no cambia el plan, entra en la cola del
            # lunes. Se activa aquí además de en el webhook para que al volver de Stripe ya
            # lo vea en marcha, y `activar_tras_pago` no duplica si el webhook llegó antes.
            from core.ajuste_a_medida import activar_tras_pago as activar_ajuste
            perfil = await db.client_profiles.find_one({"user_id": user["id"]})
            if perfil:
                await activar_ajuste(perfil, (session.get("amount_total") or 0) / 100.0)
                synced_profile = await db.client_profiles.find_one({"id": perfil["id"]}, {"_id": 0})
        elif tipo == "rutina_del_mes":
            # La rutina del mes comprada desde la pantalla de Rutina: tampoco toca el plan.
            # Se activa aquí además de en el webhook para que al volver de Stripe ya la
            # tenga puesta; `activar_tras_pago` no la entrega dos veces (mira el session_id).
            #
            # EL «SOLO SI ESTÁ PAGADA» YA LO HACE EL GUARDA DE ARRIBA, que cubre las tres. Lo
            # que pasó aquí el 24-08, y por lo que existe ese guarda: bastaba con abrir el
            # pago, cerrar Stripe y llamar con ese `session_id`; la sesión volvía con
            # `payment_status: unpaid` y aun así se entregaba el PDF, se apuntaba en la ficha
            # `cobrado: true, importe_eur: 57` y al equipo le sonaba «ha pagado la rutina del
            # mes básica (57 €)», o sea una venta que no existe metida en la caja del día.
            #
            # El webhook llega igual cuando el pago sí entra, así que no se pierde nada.
            from core.rutina_del_mes import activar_tras_pago as activar_rutina
            perfil = await db.client_profiles.find_one({"user_id": user["id"]})
            if perfil:
                await activar_rutina(perfil, (session.get("amount_total") or 0) / 100.0,
                                     (session.get("metadata") or {}).get("modalidad") or "basica",
                                     session_id=session_id)
                synced_profile = await db.client_profiles.find_one({"id": perfil["id"]}, {"_id": 0})
        else:
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
        logger.error("Webhook de Stripe rechazado: falta STRIPE_WEBHOOK_SECRET en el entorno")
        raise HTTPException(status_code=503, detail="Webhook no disponible")

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


async def _registrar_cobro_de_lead(session: Dict[str, Any], metadata: Dict[str, Any]) -> None:
    """Un lead ha pagado por el enlace que le mandó el equipo tras la llamada.

    No se le activa el plan solo: el Nivel 3 se vende hablando y puede que ni tenga
    cuenta todavía. Se marca el lead como convertido, se deja el pago registrado y se
    avisa al equipo para que le dé el alta desde el panel.
    """
    from core.avisos_equipo import avisar_al_equipo

    lead_id = metadata.get("lead_id")
    if not lead_id:
        return
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        logger.warning("Cobro de lead sin lead: %s", lead_id)
        return

    importe = (session.get("amount_total") or 0) / 100.0
    ahora = datetime.now(timezone.utc).isoformat()
    ya_estaba = (lead.get("enlace_pago") or {}).get("estado") == "pagado"
    await db.leads.update_one({"id": lead_id}, {"$set": {
        "enlace_pago.estado": "pagado",
        "enlace_pago.pagado_at": ahora,
        "enlace_pago.importe_pagado_eur": importe,
        "status": "convertido",
        "updated_at": ahora,
    }})
    if ya_estaba:
        return  # webhook repetido: no se duplica el aviso

    plan = metadata.get("plan") or "nivel3"
    nombre = lead.get("name") or lead.get("email") or "Un lead"
    await avisar_al_equipo(
        db,
        tipo="lead_pagado",
        titulo=f"{nombre} ha pagado el {plan}",
        mensaje=(f"{nombre} ha pagado {importe:.0f}€ por el enlace que se le mandó. "
                 f"Dale el alta del plan desde el panel. Teléfono: {lead.get('phone') or 'sin teléfono'}."),
        extra={"lead_id": lead_id, "plan": plan, "importe_eur": importe,
               "email": lead.get("email"), "phone": lead.get("phone")},
    )


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
            if metadata.get("tipo") == "cobro_lead":
                # Enlace de pago mandado a un lead tras la llamada (Nivel 3). Aqui no hay
                # perfil que activar todavia: el lead puede no tener ni cuenta. Se deja
                # cobrado y avisado, y el alta la hace el equipo desde el panel.
                await _registrar_cobro_de_lead(obj, metadata)
            elif metadata.get("tipo") == "revision_suelta":
                # Revisión de macros comprada suelta: NO toca el plan ni el acceso, solo deja la
                # revisión pendiente para el entrenador.
                from core.revision_suelta import activar_tras_pago
                perfil = await db.client_profiles.find_one({"id": metadata.get("profile_id")})
                if perfil:
                    await activar_tras_pago(perfil, (obj.get("amount_total") or 0) / 100.0)
            elif metadata.get("tipo") == "ajuste_a_medida":
                # El ajuste a medida de 87 €: tampoco toca el plan ni el acceso. Deja el
                # trabajo en la cola del lunes y le abre el cuestionario completo.
                from core.ajuste_a_medida import activar_tras_pago as activar_ajuste
                perfil = await db.client_profiles.find_one({"id": metadata.get("profile_id")})
                if perfil:
                    await activar_ajuste(perfil, (obj.get("amount_total") or 0) / 100.0)
            elif metadata.get("tipo") == "rutina_del_mes":
                # La rutina del mes: no toca el plan ni el acceso. Se le apunta la compra y
                # se le pone la rutina del mes vigente, si el equipo ha marcado alguna.
                #
                # El mismo cerrojo que en el `sync` de arriba (repaso 24-08). Con tarjeta,
                # `checkout.session.completed` ya llega pagada, así que esto no cambia nada
                # hoy; está por si algún día se abre un medio de pago diferido (Bizum,
                # transferencia), donde Stripe manda este evento SIN cobrar todavía y el
                # bueno es `checkout.session.async_payment_succeeded`, que este fichero no
                # escucha. Antes de abrir uno de esos hay que añadir ese evento.
                if obj.get("payment_status") != "paid":
                    logger.warning("Rutina del mes: %s llega con payment_status=%s; no se "
                                   "entrega nada", obj.get("id"), obj.get("payment_status"))
                else:
                    from core.rutina_del_mes import activar_tras_pago as activar_rutina
                    perfil = await db.client_profiles.find_one({"id": metadata.get("profile_id")})
                    if perfil:
                        await activar_rutina(perfil, (obj.get("amount_total") or 0) / 100.0,
                                             metadata.get("modalidad") or "basica",
                                             session_id=obj.get("id"))
            else:
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
    """Los avisos del sistema: cobros fallidos, bajas y reportes vencidos.

    UN ENTRENADOR SOLO VE LOS DE SUS CLIENTES (14-08-2026). Puede abrir y tocar la ficha de
    cualquiera -- eso no cambia --, pero los avisos son otra cosa: son la lista de lo que
    tiene que atender él. Con los de toda la casa dentro, la suya no se encuentra.

    El administrador los ve todos, que es su trabajo.
    """
    query = {"resolved": resolved}
    if user.get("role") == "trainer":
        mios = await db.client_profiles.find(
            {"trainer_id": user["id"]}, {"_id": 0, "id": 1}).to_list(2000)
        query["client_id"] = {"$in": [p["id"] for p in mios]}
    alerts = await db.alerts.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
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
