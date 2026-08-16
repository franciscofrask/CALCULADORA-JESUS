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
from datetime import timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends

from core.database import db
from core.security import get_admin_user, get_current_user
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
    "t10_avisos_nuevos": False, # T10 · los 19 avisos del doc
}

router = APIRouter(tags=["settings"])
admin_router = APIRouter(prefix="/admin/settings", tags=["settings"])


def _mezclar_pantallas(guardadas: Optional[Dict[str, Any]]) -> Dict[str, bool]:
    """Los defaults del código con lo tocado en el panel por encima. Solo claves
    conocidas: una clave vieja que ya no exista en PANTALLAS deja de pintarse sola."""
    tocadas = guardadas or {}
    return {clave: bool(tocadas.get(clave, defecto)) for clave, defecto in PANTALLAS.items()}


async def ajustes_app() -> Dict[str, Any]:
    """Los ajustes vivos, para backend y para servir al front."""
    doc = await db.app_settings.find_one({"id": DOC_ID}, {"_id": 0}) or {}
    return {
        "pantallas": _mezclar_pantallas(doc.get("pantallas")),
        "frase_del_dia": doc.get("frase_del_dia"),
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
async def get_admin_settings(admin=Depends(get_admin_user)):
    return await ajustes_app()


@admin_router.put("")
async def update_admin_settings(payload: Dict[str, Any] = Body(...), admin=Depends(get_admin_user)):
    """Guarda interruptores y/o frase del día. Solo claves conocidas: un typo en el
    nombre de una pantalla no crea un interruptor fantasma que nadie lee."""
    cambios: Dict[str, Any] = {}

    pantallas = payload.get("pantallas")
    if isinstance(pantallas, dict):
        for clave, valor in pantallas.items():
            if clave in PANTALLAS:
                cambios[f"pantallas.{clave}"] = bool(valor)

    if "frase_del_dia" in payload:
        texto = str((payload.get("frase_del_dia") or {}).get("texto") or "").strip()
        if texto:
            cambios["frase_del_dia"] = {
                "texto": texto,
                # La fecha es la de España: la frase "de hoy" es la del día del cliente.
                "fecha": ahora_madrid().date().isoformat(),
                "puesta_por": admin.get("id"),
            }

    if cambios:
        await db.app_settings.update_one(
            {"id": DOC_ID},
            {"$set": {**cambios,
                      "updated_at": ahora_madrid().astimezone(timezone.utc).isoformat(),
                      "updated_by": admin.get("id")}},
            upsert=True,
        )
    return await ajustes_app()
