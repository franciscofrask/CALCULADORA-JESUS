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


async def variante_para(user_id: str, familia: str, variantes: list) -> dict:
    """La variante que toca de un aviso con varios textos (regla 6 del doc 16-08:
    nunca el mismo dos veces seguidas).

    `familia` es la clave ESTABLE del aviso, sin fechas ("cierra_dia",
    "quincenal_abierto"...): la `clave` de deduplicación lleva la fecha dentro y
    cambia cada vez, así que no sirve para saber qué texto se usó la última vez.
    Devuelve el texto elegido con `familia` y `variante` dentro, para que el insert
    los persista y la rueda siga girando.
    """
    from core.avisos_cliente import rotar_variante
    ultimo = await db.notifications.find_one(
        {"user_id": user_id, "familia": familia},
        {"_id": 0, "variante": 1}, sort=[("created_at", -1)])
    return {**rotar_variante(variantes, (ultimo or {}).get("variante")), "familia": familia}


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

        # Antes de mirar si le toca una nueva, se retiran las que ya no tocan: si no, se
        # acumulan y el cliente lee tres condicionadas a la vez cuando la regla es UNA cada
        # siete dias (#52 del 15-08).
        await _caducar_condicionadas(user_id, {a["clave"] for a in condicionados})

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
            doc = {
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
            }
            # Avisos con textos que rotan (regla 6 del doc 16-08): se guarda qué
            # variante salió para que `variante_para` no repita la misma dos veces.
            if aviso.get("familia") is not None:
                doc["familia"] = aviso["familia"]
                doc["variante"] = aviso.get("variante")
            await db.notifications.insert_one(doc)
        return len(elegidos)
    except Exception:
        return 0


async def _caducar_condicionadas(user_id: str, claves_vivas: set) -> None:
    """Retira de la campanita las condicionadas que ya no vienen a cuento.

    Dos cosas, las dos de las pruebas del 15-08:

      - un aviso que dejo de ser verdad -- «llevas 4 semanas con los mismos macros» dos dias
        despues de ajustarlos -- se quedaba en la lista para siempre (#51),
      - y como cada semana puede entrar una nueva, se acumulaban: Jesus vio tres a la vez
        cuando la regla del documento es UNA condicionada cada siete dias (#52).

    Se queda viva la mas reciente que siga cumpliendose; el resto se marcan. NO se borran:
    el registro es lo que sostiene el tope semanal, y borrandolo le llegaria otra al dia
    siguiente. Se marcan tambien como leidas para que no dejen la campanita encendida.
    """
    pendientes = await db.notifications.find(
        {"user_id": user_id, "condicionada": True, "read": False, "caducada": {"$ne": True}},
        {"_id": 0, "id": 1, "clave": 1, "created_at": 1},
    ).sort("created_at", -1).to_list(50)

    fuera, ya_hay_viva = [], False
    for n in pendientes:            # de la mas nueva a la mas vieja
        if not ya_hay_viva and n.get("clave") in claves_vivas:
            ya_hay_viva = True
            continue
        fuera.append(n["id"])

    if fuera:
        await db.notifications.update_many(
            {"user_id": user_id, "id": {"$in": fuera}},
            {"$set": {"caducada": True, "read": True}})


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
    # Por `effective_date`, no por `created_at`: ver `macros_por_fecha.ultima_vigente`. Aqui
    # importaba el doble, porque de la fecha sale «lleva X dias sin ajustar»: con la fecha de
    # importacion, los 185 clientes migrados salian ajustados el 05-08 y el aviso no podia
    # saltar nunca.
    from macros_por_fecha import ultima_vigente, ultimo_cambio
    ultimos_macros = await ultima_vigente(db, client_id)

    # «LLEVAS 4 SEMANAS CON LOS MISMOS MACROS» A LOS DOS DIAS DE AJUSTARLOS (#51 del 15-08).
    #
    # La cuenta salia de la entrada VIGENTE HOY, y esa se corta en hoy a proposito. Si el
    # ajuste se guarda con efecto manana -- que es un cambio ya hecho, solo que programado --
    # la vigente sigue siendo la vieja y el aviso le decia al cliente que lleva un mes igual
    # justo despues de que le tocaran los macros. Se cuenta desde el ultimo cambio
    # REGISTRADO, y como `_dias_desde` no devuelve negativos, un ajuste con fecha futura da
    # cero dias: no hay nada de lo que avisarle.
    cambio = await ultimo_cambio(db, client_id)
    dias_sin_ajustar = _dias_desde(
        (cambio or {}).get("effective_date") or (cambio or {}).get("created_at"),
        ahora)
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
    # Las caducadas no se pintan: son avisos que dejaron de ser verdad (ver
    # `_caducar_condicionadas`). Se conservan en la base, solo que fuera de la vista.
    items = await db.notifications.find(
        {"user_id": user["id"], "caducada": {"$ne": True}}, {"_id": 0}
    ).sort("created_at", -1).to_list(30)
    return {"notifications": items}


@router.get("/unread-count")
async def unread_count(user = Depends(get_current_user)):
    await sincronizar_avisos(user["id"])
    count = await db.notifications.count_documents(
        {"user_id": user["id"], "read": False, "caducada": {"$ne": True}})
    return {"count": count}


@router.put("/read-all")
async def mark_all_read(user = Depends(get_current_user)):
    result = await db.notifications.update_many(
        {"user_id": user["id"], "read": False}, {"$set": {"read": True}}
    )
    return {"ok": True, "marked": result.modified_count}
