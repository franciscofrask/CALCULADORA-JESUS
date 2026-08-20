"""
Ajustes globales de la app: db.app_settings, UN solo documento.

Nacen del doc 16-08: "que cada pantalla nueva se pueda apagar desde el panel sin
desplegar, por si algo no está fino". Hasta ahora apagar algo para todos era una
constante en el código y un deploy (así se apagó la Rutina el 19-07); esto es el
interruptor de verdad.

Dos cosas viven aquí:
  - `pantallas`: los interruptores de las pantallas nuevas del doc. PANTALLAS es la
    lista conocida con su valor por defecto; el documento de la base solo guarda lo
    que el panel haya tocado, así que añadir un interruptor nuevo es añadirlo al
    diccionario y ya tiene valor en todos los entornos.
  - `frase_del_dia`: la frase de Inicio (T1). La escribe el panel, es la misma para
    todos, y si un día no hay nueva se queda la del día anterior (por eso se guarda
    con su fecha: Inicio decide si la enseña con o sin estreno).
"""
from datetime import date, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException

from core.database import db
from core.security import get_admin_only_user, get_current_user
from core.tiempo import ahora_madrid

DOC_ID = "app"

# Los interruptores y su valor por defecto. Apagados hasta que cada tarea del doc
# 16-08 esté hecha y probada; `t2_suplementos` nace encendido porque esa pantalla ya
# existía y estaba en producción.
PANTALLAS = {
    "frase_del_dia": False,     # T1 · la frase en Inicio
    "t1_inicio_nuevo": False,   # T1 · el Inicio nuevo (Lo que toca hoy / Pendiente)
    "t2_suplementos": True,     # T2 · la pantalla de suplementos del cliente
    "t3_entreno": False,        # T3 · rutina visible + registro de sesión
    "t4_cierre_nuevo": False,   # T4 · el "¿Cómo fuiste hoy?" nuevo
    "t5_diario": False,         # T5 · el Diario en Seguimiento
    "t6_evolucion": False,      # T6 · Evolución completa (medidas + fotos) en cliente
    # T10 · los avisos del doc. Encendido de fábrica desde el bloque 10 del 19-08: la
    # tabla está completa (los dos de entrega, los once diseñados y las cuatro reglas),
    # así que el interruptor queda solo como freno de emergencia.
    "t10_avisos_nuevos": True,
}

router = APIRouter(tags=["settings"])

# SOLO ADMINISTRADORES: apagar una pantalla aquí se la quita a TODOS los clientes a la vez,
# y la frase del día la leen todos. Va con el mismo candado que el catálogo de planes, que
# es donde se edita.
admin_router = APIRouter(prefix="/admin/settings", tags=["settings"])


def _mezclar_pantallas(guardadas: Optional[Dict[str, Any]]) -> Dict[str, bool]:
    """Los defaults del código con lo tocado en el panel por encima. Solo claves
    conocidas: una clave vieja que ya no exista en PANTALLAS deja de pintarse sola."""
    tocadas = guardadas or {}
    return {clave: bool(tocadas.get(clave, defecto)) for clave, defecto in PANTALLAS.items()}


async def ajustes_app() -> Dict[str, Any]:
    """Los ajustes vivos, para backend y para servir al front."""
    doc = await db.app_settings.find_one({"id": DOC_ID}, {"_id": 0}) or {}

    # La cola de frases programadas (bloque 11 del 19-08): si a alguna le ha llegado su
    # día, pasa a ser LA frase y sale de la cola. Se resuelve al leer, sin cron, igual
    # que los avisos.
    frase = doc.get("frase_del_dia")
    cola = doc.get("frases_programadas") or []
    hoy = ahora_madrid().date().isoformat()
    vencidas = [f for f in cola if f.get("fecha") and f["fecha"] <= hoy]
    if vencidas:
        frase = max(vencidas, key=lambda f: f["fecha"])
        pendientes = [f for f in cola if f.get("fecha", "") > hoy]
        await db.app_settings.update_one(
            {"id": DOC_ID},
            {"$set": {"frase_del_dia": frase, "frases_programadas": pendientes}})
        cola = pendientes

    return {
        "pantallas": _mezclar_pantallas(doc.get("pantallas")),
        "frase_del_dia": frase,
        "frases_programadas": cola,
    }


async def pantalla_activa(nombre: str) -> bool:
    """El cerrojo que usan las rutas del backend. Si la base no contesta, manda el
    default del código: quedarse sin base no puede apagar lo que estaba encendido."""
    try:
        ajustes = await ajustes_app()
        return bool(ajustes["pantallas"].get(nombre, PANTALLAS.get(nombre, False)))
    except Exception:
        return bool(PANTALLAS.get(nombre, False))


@router.get("/settings/app")
async def get_app_settings(user=Depends(get_current_user)):
    """Lo que necesita el front al arrancar: interruptores y frase del día."""
    return await ajustes_app()


@admin_router.get("")
async def get_admin_settings(admin=Depends(get_admin_only_user)):
    return await ajustes_app()


@admin_router.put("")
async def update_admin_settings(payload: Dict[str, Any] = Body(...), admin=Depends(get_admin_only_user)):
    """Guarda interruptores y/o frase del día. Solo claves conocidas: un typo en el
    nombre de una pantalla no crea un interruptor fantasma que nadie lee."""
    cambios: Dict[str, Any] = {}

    pantallas = payload.get("pantallas")
    if isinstance(pantallas, dict):
        for clave, valor in pantallas.items():
            if clave in PANTALLAS:
                cambios[f"pantallas.{clave}"] = bool(valor)

    if "frase_del_dia" in payload:
        pedido = payload.get("frase_del_dia") or {}
        texto = str(pedido.get("texto") or "").strip()
        if texto:
            # PROGRAMABLE CON UNA SEMANA DE ANTELACIÓN (bloque 11 del doc 19-08). Sin
            # fecha (o con la de hoy) la frase entra ya, como siempre; con una fecha por
            # delante -- hasta 7 días -- se guarda en la cola y saldrá su día. La fecha
            # es la de España: la frase «de hoy» es la del día del cliente.
            hoy = ahora_madrid().date()
            fecha = str(pedido.get("fecha") or "").strip() or hoy.isoformat()
            try:
                d = date.fromisoformat(fecha)
            except ValueError:
                raise HTTPException(status_code=400, detail="La fecha de la frase no se entiende.")
            if d < hoy or (d - hoy).days > 7:
                raise HTTPException(
                    status_code=400,
                    detail="La frase se puede programar de hoy a una semana vista, no más allá.")
            frase = {"texto": texto, "fecha": d.isoformat(), "puesta_por": admin.get("id")}
            if d == hoy:
                cambios["frase_del_dia"] = frase
            else:
                doc = await db.app_settings.find_one({"id": DOC_ID}, {"_id": 0, "frases_programadas": 1}) or {}
                cola = [f for f in (doc.get("frases_programadas") or []) if f.get("fecha") != frase["fecha"]]
                cambios["frases_programadas"] = sorted(cola + [frase], key=lambda f: f["fecha"])

    if cambios:
        await db.app_settings.update_one(
            {"id": DOC_ID},
            {"$set": {**cambios,
                      "updated_at": ahora_madrid().astimezone(timezone.utc).isoformat(),
                      "updated_by": admin.get("id")}},
            upsert=True,
        )
    return await ajustes_app()
