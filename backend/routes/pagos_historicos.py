# -*- coding: utf-8 -*-
"""El historial de cobros de un cliente, para el administrador.

Francisco, 13-08-2026: «algo que quiero es un log de pagos en la app que solo pueda verlo
un administrador».

QUE ES ESTO Y QUE NO ES
-----------------------
Esto NO es la facturacion viva: de cobrar hoy se encarga Stripe y eso vive en `routes/
billing.py`. Esto es el HISTORICO, lo que cada cliente ha pagado desde 2019, que estaba
repartido en tres sitios y no lo leia ni una linea de la app:

    holded      las facturas de verdad, con su numero y su importe
    thrivecart  los pedidos, renovaciones, cancelaciones y devoluciones
    stripe      los eventos de la pasarela, que sigue viva

`_sync_membresias_cobros.py` los unifica en `db.pagos_historicos` con un formato comun.
Aqui solo se leen.

POR QUE SOLO ADMIN, Y NO TRAINER
--------------------------------
El 21-07 se decidio que los entrenadores ven y gestionan a TODOS los clientes, y por eso
casi todo el panel usa `get_admin_user`, que deja pasar a los dos roles. Lo que alguien
ha pagado no es informacion de entrenamiento: es del negocio. Asi que esto usa
`get_admin_only_user`, el mismo que protege la pestana de Usuarios.
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query

from core.database import db
from core.security import get_admin_only_user

router = APIRouter(prefix="/admin/pagos", tags=["admin-pagos"])

# Cuantos se devuelven de una tacada. La pantalla pagina; el tope existe para que una
# consulta sin filtros no se traiga 3.000 cobros al navegador.
POR_PAGINA = 50

# EL MISMO DINERO LLEGA POR DOS CAMINOS, Y HAY QUE CONTARLO UNA VEZ (13-08-2026).
#
# Holded no es una pasarela: es la facturacion. Cada cobro de ThriveCart o de Stripe se
# factura ademas en Holded, asi que el mismo euro esta en las dos puntas. Medido al
# importar: de 1.611 filas, 353 son copias. Sumandolas todas salen 416.196 EUR; el dinero
# que entro de verdad son 332.022. Un panel que enseñe el bruto se equivoca en 84.174 EUR,
# que es justo el total de Holded entero.
#
# El importador marca la copia con `duplicado_de` (apuntando a la factura, que manda por
# ser el documento fiscal) y NO borra nada, para que se pueda auditar de donde sale cada
# cobro. Aqui se filtran siempre, salvo que se pidan a proposito.
SIN_COPIAS = {"duplicado_de": {"$exists": False}}

# Y hay eventos que no son dinero: cancelaciones, pausas y cobros fallidos. Cuentan la
# historia del cliente, asi que se guardan, pero no son un cobro y no pueden sumar. El
# importador los marca con `es_dinero: false`.
SOLO_DINERO = {"es_dinero": {"$ne": False}}


def _limpio(p: dict) -> dict:
    """Lo que sale al navegador. Nada de `_id` ni del volcado original del proveedor."""
    return {
        "id": p.get("id"),
        "fecha": p.get("fecha"),
        "email": p.get("email"),
        "nombre": p.get("nombre"),
        "client_id": p.get("client_id"),
        "importe": p.get("importe"),
        "moneda": p.get("moneda") or "EUR",
        "concepto": p.get("concepto"),
        "sku": p.get("sku"),
        "origen": p.get("origen"),
        "referencia": p.get("referencia"),
        "tipo": p.get("tipo"),
        # Un aviso sin dinero (cancelacion, pausa, cobro fallido) se pinta distinto y no
        # suma. `importe_evento` es lo que se intentaba cobrar: 2.859 EUR de cobros
        # fallidos y 4.165 EUR de suscripciones canceladas, que dicen algo aunque no
        # entraran en caja.
        "es_dinero": p.get("es_dinero") is not False,
        "importe_evento": p.get("importe_evento"),
    }


@router.get("")
async def listar_pagos(
    email: Optional[str] = Query(None, description="filtra por cliente"),
    origen: Optional[str] = Query(None, description="holded, thrivecart o stripe"),
    desde: Optional[str] = Query(None, description="fecha inicial, AAAA-MM-DD"),
    hasta: Optional[str] = Query(None, description="fecha final, AAAA-MM-DD"),
    pagina: int = Query(1, ge=1),
    incluir_eventos: bool = Query(False, description="ademas de los cobros, los avisos sin dinero (cancelaciones, pausas, cobros fallidos)"),
    ver_copias: bool = Query(False, description="para auditar: enseña tambien la copia de cada cobro facturado dos veces"),
    user=Depends(get_admin_only_user),
):
    """El historial de cobros, del mas reciente al mas antiguo.

    Devuelve tambien el total de lo filtrado, que es lo que se mira de verdad: la lista
    sirve para buscar un cobro concreto, y la suma para saber cuanto ha dejado un cliente.
    """
    filtro = {}
    if not ver_copias:
        filtro.update(SIN_COPIAS)
    if not incluir_eventos:
        filtro.update(SOLO_DINERO)
    if email:
        filtro["email"] = {"$regex": email.strip(), "$options": "i"}
    if origen:
        filtro["origen"] = origen
    if desde or hasta:
        rango = {}
        if desde:
            rango["$gte"] = desde
        if hasta:
            # Con la fecha final incluida: quien escribe "hasta el 31" espera el 31 dentro.
            rango["$lte"] = hasta + "T23:59:59"
        filtro["fecha"] = rango

    total = await db.pagos_historicos.count_documents(filtro)
    saltar = (pagina - 1) * POR_PAGINA
    cursor = db.pagos_historicos.find(filtro, {"_id": 0}).sort("fecha", -1).skip(saltar).limit(POR_PAGINA)
    pagos = [_limpio(p) async for p in cursor]

    # La suma se hace en la base, no sumando la pagina: el total de 3.000 cobros no cabe
    # en 50 filas, y un total que solo suma lo que se ve engaña más que no ponerlo.
    suma = await db.pagos_historicos.aggregate([
        {"$match": filtro},
        {"$group": {"_id": "$moneda", "total": {"$sum": "$importe"}, "n": {"$sum": 1}}},
    ]).to_list(10)

    return {
        "pagos": pagos,
        "total": total,
        "pagina": pagina,
        "por_pagina": POR_PAGINA,
        "paginas": max(1, (total + POR_PAGINA - 1) // POR_PAGINA),
        "sumas": [{"moneda": s["_id"] or "EUR", "total": round(s["total"] or 0, 2), "n": s["n"]}
                  for s in suma],
    }


@router.get("/resumen")
async def resumen(user=Depends(get_admin_only_user)):
    """Las cuatro cifras de arriba: cuánto hay, de dónde viene y desde cuándo.

    Si la coleccion todavia no existe -- la llena `_sync_membresias_cobros.py` --, esto
    responde con ceros y un aviso, en vez de romper la pantalla.
    """
    if not await db.pagos_historicos.count_documents({}):
        return {"hay_datos": False, "total": 0, "por_origen": [], "por_ano": [],
                "aviso": "Todavía no se ha importado el histórico de cobros."}

    # Todo lo de aqui abajo cuenta DINERO, asi que va sin copias y sin los avisos que no
    # son un cobro. Ver `SIN_COPIAS` arriba: la diferencia son 84.174 EUR.
    base = {**SIN_COPIAS, **SOLO_DINERO}
    total = await db.pagos_historicos.count_documents(base)

    por_origen = await db.pagos_historicos.aggregate([
        {"$match": base},
        {"$group": {"_id": "$origen", "n": {"$sum": 1}, "importe": {"$sum": "$importe"}}},
        {"$sort": {"importe": -1}},
    ]).to_list(10)

    por_ano = await db.pagos_historicos.aggregate([
        {"$match": base},
        {"$group": {"_id": {"$substr": ["$fecha", 0, 4]}, "n": {"$sum": 1},
                    "importe": {"$sum": "$importe"}}},
        {"$sort": {"_id": 1}},
    ]).to_list(20)

    clientes = await db.pagos_historicos.distinct("email", base)
    ultimo = await db.pagos_historicos.find_one(base, {"_id": 0, "fecha": 1}, sort=[("fecha", -1)])

    # Lo que se deja fuera, dicho en voz alta. Un panel que esconde filas sin explicarlo
    # obliga a fiarse; diciendo cuantas y por que, se puede comprobar.
    copias = await db.pagos_historicos.count_documents({"duplicado_de": {"$exists": True}})
    eventos = await db.pagos_historicos.count_documents({**SIN_COPIAS, "es_dinero": False})

    return {
        "hay_datos": True,
        "total": total,
        "clientes": len(clientes),
        "ultimo_cobro": (ultimo or {}).get("fecha"),
        "por_origen": [{"origen": o["_id"] or "?", "n": o["n"],
                        "importe": round(o["importe"] or 0, 2)} for o in por_origen],
        "por_ano": [{"ano": a["_id"], "n": a["n"], "importe": round(a["importe"] or 0, 2)}
                    for a in por_ano if a["_id"]],
        "fuera": {"copias": copias, "eventos_sin_dinero": eventos},
    }


@router.get("/cliente/{email}")
async def pagos_de_un_cliente(email: str, user=Depends(get_admin_only_user)):
    """Todo lo que ha pagado una persona, para abrirlo desde su ficha.

    Aqui van tambien los avisos sin dinero -- una cancelacion o un cobro fallido cuentan
    su historia --, pero el TOTAL solo suma cobros de verdad y sin copias.
    """
    filtro = {"email": email.lower().strip(), **SIN_COPIAS}
    cursor = db.pagos_historicos.find(filtro, {"_id": 0}).sort("fecha", -1)
    pagos = [_limpio(p) async for p in cursor]
    total = round(sum(float(p.get("importe") or 0) for p in pagos
                      if p.get("es_dinero") is not False), 2)
    return {"pagos": pagos, "n": len(pagos), "total": total,
            "primero": pagos[-1]["fecha"] if pagos else None,
            "ultimo": pagos[0]["fecha"] if pagos else None}
