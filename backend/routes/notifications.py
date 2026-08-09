"""
Notificaciones in-app del cliente ("campanita"): eventos que el coach genera y el
cliente debe conocer (rutina nueva, macros, feedback, suplementos, cambio de coach).
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid

from core.database import db
from core.sin_futuro import hasta_hoy
from core.security import get_current_user

router = APIRouter(prefix="/notifications", tags=["notifications"])


async def notify(user_id: str, type: str, title: str, link: Optional[str] = None, body: Optional[str] = None):
    """Crea una notificación para un usuario. Falla en silencio: un aviso nunca
    debe romper la operación principal (asignar coach, guardar macros...).

    `body` es el texto que escribe el coach (feedback al ajustar macros/suplementos):
    el cliente lo lee en el panel de novedades."""
    if not user_id:
        return
    try:
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "type": type,
            "title": title,
            "body": (body or "").strip() or None,
            "link": link,
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass


async def sincronizar_avisos(user_id: str) -> int:
    """Mira si al cliente le toca algún aviso de los de la parte 9 y lo crea.

    Se evalúa al entrar en la app en vez de con un cron: un aviso in-app solo se ve
    cuando entra, así que no gana nada existiendo antes. Cada aviso lleva una clave
    única del evento y no se repite mientras esa clave siga viva, así que da igual
    cuántas veces se llame aquí.

    Falla en silencio, como `notify`: quedarse sin un aviso no puede impedirle entrar.
    """
    try:
        from core.avisos_cliente import (
            avisos_condicionados, avisos_de_calendario, elegir_avisos)

        perfil = await db.client_profiles.find_one({"user_id": user_id}, {"_id": 0})
        if not perfil:
            return 0

        ahora = datetime.now(timezone.utc)
        datos = await _datos_para_avisos(perfil, ahora)

        calendario = avisos_de_calendario(
            perfil=perfil, ahora=ahora,
            proximo_ajuste=datos["proximo_ajuste"],
            semanas_ciclo=datos["semanas_ciclo"],
            macros_puestos_por_alguien=datos["macros_puestos_por_alguien"],
        )
        condicionados = avisos_condicionados(
            ahora=ahora,
            dias_sin_peso=datos["dias_sin_peso"],
            dias_sin_dieta=datos["dias_sin_dieta"],
            semanas_sin_ajustar=datos["semanas_sin_ajustar"],
            reporte_sin_fotos=datos["reporte_sin_fotos"],
        )

        # Lo ya enviado, para no repetir. Un mes cubre de sobra cualquier clave viva.
        desde = (ahora - timedelta(days=35)).isoformat()
        previas = await db.notifications.find(
            {"user_id": user_id, "created_at": {"$gte": desde}},
            {"_id": 0, "clave": 1, "created_at": 1, "condicionada": 1},
        ).to_list(200)
        claves = {p.get("clave") for p in previas if p.get("clave")}
        ultima_cond = max((p["created_at"] for p in previas if p.get("condicionada")), default=None)

        elegidos = elegir_avisos(calendario, condicionados, claves, ultima_cond, ahora)
        for aviso in elegidos:
            await db.notifications.insert_one({
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "type": aviso["tipo"],
                "title": aviso["titulo"],
                "body": aviso.get("cuerpo"),
                "link": aviso.get("link"),
                "read": False,
                "clave": aviso["clave"],
                "condicionada": not aviso.get("calendario"),
                "created_at": ahora.isoformat(),
            })
        return len(elegidos)
    except Exception:
        return 0


async def _datos_para_avisos(perfil: dict, ahora: datetime) -> dict:
    """Los datos que miran los disparadores. Consultas cortas y contadas."""
    from core.avisos_cliente import _dias_desde

    client_id, user_id = perfil.get("id"), perfil.get("user_id")

    # Hasta hoy (punto 22): un reporte fechado en 2028 hacia creer que se acababa de pesar,
    # y el aviso de "hace X que no te pesas" no salia nunca.
    ultimo_peso = await db.reports.find_one(
        hasta_hoy({"client_id": client_id, "weight": {"$ne": None}}),
        {"_id": 0, "created_at": 1, "photos": 1}, sort=[("created_at", -1)])
    ultima_dieta = await db.diets.find_one(
        {"user_id": user_id}, {"_id": 0, "fecha": 1}, sort=[("fecha", -1)])
    # `origen` y `changed_by` van en la proyeccion para saber si sus macros los puso ALGUIEN
    # o salieron del calculo del alta. De eso depende que se le diga o no que son
    # provisionales (punto 4.1): si se los puso su coach, no lo son.
    ultimos_macros = await db.macro_history.find_one(
        {"client_id": client_id},
        {"_id": 0, "created_at": 1, "origen": 1, "changed_by": 1},
        sort=[("created_at", -1)])

    dias_sin_ajustar = _dias_desde((ultimos_macros or {}).get("created_at"), ahora)
    dias_sin_dieta = None
    if ultima_dieta and ultima_dieta.get("fecha"):
        try:
            f = datetime.fromisoformat(str(ultima_dieta["fecha"])).replace(tzinfo=timezone.utc)
            dias_sin_dieta = max(0, (ahora - f).days)
        except (ValueError, TypeError):
            pass

    # Un reporte reciente sin fotos: sin ellas no se le puede generar el informe.
    sin_fotos = bool(ultimo_peso and not (ultimo_peso.get("photos") or [])
                     and (_dias_desde(ultimo_peso.get("created_at"), ahora) or 99) <= 7)

    semanas_ciclo = None
    proximo_ajuste = None
    try:
        from routes.plans import _overrides_by_code
        from models.user import merged_catalog
        plan = merged_catalog(await _overrides_by_code()).get(perfil.get("plan") or "", {})
        semanas_ciclo = (plan.get("ciclo") or {}).get("semanas")
    except Exception:
        pass

    # ¿Sus macros los puso alguien, o salieron del calculo del alta? (punto 4.1). La regla
    # vive en un solo sitio porque la usan dos pantallas -- los avisos y el Inicio -- y si
    # cada una tuviera la suya volveriamos a tener dos verdades.
    from core.macros_de_quien import de_una_persona

    return {
        "dias_sin_peso": _dias_desde((ultimo_peso or {}).get("created_at"), ahora),
        "dias_sin_dieta": dias_sin_dieta,
        "semanas_sin_ajustar": (dias_sin_ajustar // 7) if dias_sin_ajustar is not None else None,
        "reporte_sin_fotos": sin_fotos,
        "proximo_ajuste": proximo_ajuste,
        "semanas_ciclo": semanas_ciclo,
        "macros_puestos_por_alguien": de_una_persona(ultimos_macros),
    }


@router.get("")
async def list_notifications(user = Depends(get_current_user)):
    """Últimas notificaciones del usuario actual."""
    await sincronizar_avisos(user["id"])
    items = await db.notifications.find(
        {"user_id": user["id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(30)
    return {"notifications": items}


@router.get("/unread-count")
async def unread_count(user = Depends(get_current_user)):
    await sincronizar_avisos(user["id"])
    count = await db.notifications.count_documents({"user_id": user["id"], "read": False})
    return {"count": count}


@router.put("/read-all")
async def mark_all_read(user = Depends(get_current_user)):
    result = await db.notifications.update_many(
        {"user_id": user["id"], "read": False}, {"$set": {"read": True}}
    )
    return {"ok": True, "marked": result.modified_count}
