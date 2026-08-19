"""
Las tareas del equipo (doc del 19-08, apartado 05).

    «Hoy no hay forma de asignar nada: ni un cliente a un entrenador, ni una tarea a una
     persona. Todo lo que se manda hacer va por WhatsApp y no queda en ningún sitio.»

Una tarea son CUATRO CAMPOS Y NINGUNO MÁS (el formulario del doc): a quién, qué, para
cuándo y sobre quién (opcional, si va ligada a un cliente). Lo demás es rastro: quién la
creó, cuándo se hizo y quién la hizo — que es lo que deja registro en la ficha («el mes
que viene, al abrir esa ficha, se ve que se le contactó»).

`clave` es la deduplicación de las AUTOMÁTICAS: mientras exista una tarea con esa clave
(hecha o no), no se vuelve a crear. Por eso las claves llevan el periodo dentro cuando la
condición puede repetirse («se está cayendo» este mes y el que viene son dos tareas) y lo
omiten cuando no (una ficha sin plan es UNA tarea hasta que alguien la arregle).
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.avisos_equipo import avisar_al_equipo


async def crear_tarea(db, *, a_quien: str, que: str,
                      para_cuando: Optional[str] = None,
                      sobre_quien: Optional[str] = None,
                      sobre_quien_nombre: Optional[str] = None,
                      creada_por: Optional[str] = None,
                      creada_por_nombre: Optional[str] = None,
                      clave: Optional[str] = None,
                      origen: str = "manual",
                      avisar: bool = True) -> Optional[Dict[str, Any]]:
    """Crea una tarea y avisa al asignado. Devuelve la tarea, o None si la clave ya existe.

    El aviso va a la campanita del EQUIPO de esa persona («le aparece en su panel... y le
    llega un aviso»). Las automáticas avisan igual: una tarea que nadie ve es una lista,
    no un sistema.
    """
    que = (que or "").strip()
    if not que or not a_quien:
        return None
    if clave and await db.tareas.find_one({"clave": clave}, {"_id": 0, "id": 1}):
        return None

    tarea = {
        "id": str(uuid.uuid4()),
        "a_quien": a_quien,
        "que": que,
        "para_cuando": (str(para_cuando)[:10] or None) if para_cuando else None,
        "sobre_quien": sobre_quien,
        "sobre_quien_nombre": sobre_quien_nombre,
        "creada_por": creada_por,                 # None = la generó el sistema
        "creada_por_nombre": creada_por_nombre or ("sistema" if not creada_por else None),
        "origen": origen,                         # manual | auto:<tipo>
        "clave": clave,
        "hecha": False,
        "hecha_por": None,
        "hecha_por_nombre": None,
        "hecha_at": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.tareas.insert_one({**tarea})

    if avisar:
        detalle = f" · sobre {sobre_quien_nombre}" if sobre_quien_nombre else ""
        plazo = f" · para el {tarea['para_cuando']}" if tarea.get("para_cuando") else ""
        await avisar_al_equipo(
            db, tipo="tarea", titulo=f"Tarea nueva: {que[:80]}",
            mensaje=f"{que}{detalle}{plazo}",
            client_id=sobre_quien, trainer_id=a_quien,
            extra={"tarea_id": tarea["id"]},
        )
    return tarea


async def marcar_hecha(db, tarea_id: str, *, por: str, por_nombre: Optional[str] = None,
                       hecha: bool = True) -> bool:
    """Marca (o desmarca) una tarea. Devuelve si existía."""
    r = await db.tareas.update_one(
        {"id": tarea_id},
        {"$set": {"hecha": bool(hecha),
                  "hecha_por": por if hecha else None,
                  "hecha_por_nombre": (por_nombre or None) if hecha else None,
                  "hecha_at": datetime.now(timezone.utc).isoformat() if hecha else None}},
    )
    return r.matched_count > 0


def ordenar_para_panel(tareas: List[Dict[str, Any]], hoy_iso: str) -> Dict[str, List[Dict[str, Any]]]:
    """Las pendientes de una persona, partidas como las mira: vencidas, para hoy, y lo
    que viene. Una tarea sin fecha es «para hoy»: se pidió sin plazo, no para nunca."""
    vencidas, hoy, proximas = [], [], []
    for t in tareas:
        if t.get("hecha"):
            continue
        fecha = t.get("para_cuando")
        if fecha and fecha < hoy_iso:
            vencidas.append(t)
        elif not fecha or fecha == hoy_iso:
            hoy.append(t)
        else:
            proximas.append(t)
    vencidas.sort(key=lambda t: t.get("para_cuando") or "")
    proximas.sort(key=lambda t: t.get("para_cuando") or "")
    return {"vencidas": vencidas, "hoy": hoy, "proximas": proximas}
