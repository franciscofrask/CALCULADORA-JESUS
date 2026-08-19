"""
Asignar tareas (doc del 19-08, apartado 05).

    «Tres sitios de donde sale el botón: la ficha de un cliente, una lista a varios de
     golpe, y suelto desde el panel. Cuatro campos y ninguno más.»

Aquí viven las cuatro operaciones: crear (una o a varios de golpe), listar (las mías y
las que asigné), marcar hecha y el registro por cliente que se ve en su ficha. Las
automáticas se generan al consultar la lista, con su freno (core/tareas_automaticas).
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException

from core.database import db
from core.security import get_admin_user
from core.tareas import crear_tarea, marcar_hecha, ordenar_para_panel
from core.tareas_automaticas import generar_tareas_automaticas
from core.tiempo import hoy_madrid

router = APIRouter(prefix="/admin/tareas", tags=["tareas"])


@router.post("")
async def asignar_tarea(data: Dict[str, Any] = Body(...), user=Depends(get_admin_user)):
    """Crea una tarea (o la misma para varios clientes de golpe: `sobre_quienes`).

    «Los nueve que renuevan el 21 de septiembre: los marcas, "contactar", a Jenny, y ya
    está» — eso llega aquí como una lista de client_ids y sale como una tarea por cliente,
    porque cada una se marca hecha por su cuenta.
    """
    a_quien = (data.get("a_quien") or "").strip()
    que = (data.get("que") or "").strip()
    para_cuando = data.get("para_cuando") or None
    if not a_quien or not que:
        raise HTTPException(status_code=400, detail="Faltan el quién o el qué de la tarea.")
    destinatario = await db.users.find_one(
        {"id": a_quien, "role": {"$in": ["admin", "trainer"]}}, {"_id": 0, "id": 1, "name": 1})
    if not destinatario:
        raise HTTPException(status_code=400, detail="Esa persona no está en el equipo.")

    sobre = [s for s in (data.get("sobre_quienes") or []) if s]
    if data.get("sobre_quien"):
        sobre.append(data["sobre_quien"])

    creadas: List[Dict[str, Any]] = []
    if sobre:
        perfiles = await db.client_profiles.find(
            {"id": {"$in": sobre}}, {"_id": 0, "id": 1, "user_id": 1}).to_list(len(sobre))
        nombres = {u["id"]: u.get("name") async for u in db.users.find(
            {"id": {"$in": [p["user_id"] for p in perfiles]}}, {"_id": 0, "id": 1, "name": 1})}
        for p in perfiles:
            t = await crear_tarea(db, a_quien=a_quien, que=que, para_cuando=para_cuando,
                                  sobre_quien=p["id"],
                                  sobre_quien_nombre=nombres.get(p["user_id"]),
                                  creada_por=user["id"], creada_por_nombre=user.get("name"))
            if t:
                creadas.append(t)
    else:
        t = await crear_tarea(db, a_quien=a_quien, que=que, para_cuando=para_cuando,
                              creada_por=user["id"], creada_por_nombre=user.get("name"))
        if t:
            creadas.append(t)

    if not creadas:
        raise HTTPException(status_code=400, detail="No se creó ninguna tarea.")
    return {"creadas": len(creadas), "tareas": creadas}


@router.get("")
async def mis_tareas(user=Depends(get_admin_user)):
    """Lo que esta persona tiene (vencidas, hoy, próximas), lo que asignó y sigue
    pendiente, y lo hecho reciente. Genera las automáticas de camino (con freno)."""
    await generar_tareas_automaticas(db)
    hoy = hoy_madrid().isoformat()

    mias = await db.tareas.find({"a_quien": user["id"], "hecha": False},
                                {"_id": 0}).to_list(500)
    hechas = await db.tareas.find({"a_quien": user["id"], "hecha": True},
                                  {"_id": 0}).sort("hecha_at", -1).to_list(30)
    # Lo que YO asigné y sigue vivo: «el que la asignó ve lo pendiente y lo que se ha
    # pasado de fecha, sin preguntar a nadie».
    asignadas = await db.tareas.find({"creada_por": user["id"], "hecha": False,
                                      "a_quien": {"$ne": user["id"]}},
                                     {"_id": 0}).to_list(500)

    nombres = {u["id"]: u.get("name") async for u in db.users.find(
        {"role": {"$in": ["admin", "trainer"]}}, {"_id": 0, "id": 1, "name": 1})}
    for t in asignadas:
        t["a_quien_nombre"] = nombres.get(t.get("a_quien"))

    return {**ordenar_para_panel(mias, hoy),
            "hechas": hechas,
            "asignadas": ordenar_para_panel(asignadas, hoy),
            "hoy_es": hoy}


@router.get("/equipo")
async def el_equipo(user=Depends(get_admin_user)):
    """Para el desplegable de «a quién»: el staff, con su nombre."""
    fuera = []
    async for u in db.users.find({"role": {"$in": ["admin", "trainer"]}},
                                 {"_id": 0, "id": 1, "name": 1, "role": 1}).sort("name", 1):
        fuera.append(u)
    return fuera


@router.put("/{tarea_id}/hecha")
async def hecha(tarea_id: str, data: Dict[str, Any] = Body(default={}),
                user=Depends(get_admin_user)):
    """Marcar hecha (o deshacer con {hecha: false}). La puede marcar el asignado o quien
    la creó; un tercero del equipo también — aquí nadie esconde trabajo a nadie."""
    ok = await marcar_hecha(db, tarea_id, por=user["id"], por_nombre=user.get("name"),
                            hecha=bool(data.get("hecha", True)))
    if not ok:
        raise HTTPException(status_code=404, detail="Esa tarea no existe.")
    return {"ok": True}


@router.delete("/{tarea_id}")
async def borrar(tarea_id: str, user=Depends(get_admin_user)):
    """Borrar una tarea creada por error. Solo quien la creó o un admin; las automáticas
    no se borran, se marcan hechas (borrarlas haría que el sistema las volviera a crear)."""
    t = await db.tareas.find_one({"id": tarea_id}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Esa tarea no existe.")
    if t.get("origen") != "manual":
        raise HTTPException(status_code=400,
                            detail="Las automáticas no se borran: márcala hecha y no vuelve.")
    if t.get("creada_por") != user["id"] and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo quien la creó puede borrarla.")
    await db.tareas.delete_one({"id": tarea_id})
    return {"ok": True}


@router.get("/de-cliente/{client_id}")
async def registro_del_cliente(client_id: str, user=Depends(get_admin_user)):
    """El registro que queda en la ficha: «qué se le pidió, quién lo hizo y cuándo. Así
    el mes que viene, al abrir esa ficha, se ve que se le contactó»."""
    tareas = await db.tareas.find({"sobre_quien": client_id},
                                  {"_id": 0}).sort("created_at", -1).to_list(100)
    nombres = {u["id"]: u.get("name") async for u in db.users.find(
        {"role": {"$in": ["admin", "trainer"]}}, {"_id": 0, "id": 1, "name": 1})}
    for t in tareas:
        t["a_quien_nombre"] = nombres.get(t.get("a_quien"))
    return {"pendientes": [t for t in tareas if not t.get("hecha")],
            "hechas": [t for t in tareas if t.get("hecha")]}
