"""
Rutas de Suplementación.

Espejo del patrón de rutinas:
- Cliente lee su protocolo (GET /supplements/current).
- Admin/entrenador gestiona el catálogo (CRUD) y asigna el protocolo por cliente.
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
from typing import List, Optional

from core.database import db
from core.security import get_current_user, get_admin_user, assert_client_access
from core.plan_access import require_access
from core.tiempo import hoy_madrid
from models.supplements import (
    SupplementCatalogItem, SupplementProtocolSave, SupplementProtocolResponse,
    ProtocolItem, VersionProtocolo,
)


# ── El protocolo, versionado por fecha (punto 33 del 07-08) ──────────────
# Antes habia UN protocolo por cliente que se pisaba a si mismo: se podia asignar pero no
# quedaba registro de que tomaba en cada momento, y lo de "siguiente + siguiente_fecha" era
# un apano para poder dejar uno preparado. Ahora es una lista de versiones con fecha y se
# resuelve por la mas reciente que no pase de hoy, exactamente igual que los macros.

def _hoy() -> str:
    """El día del CLIENTE, en hora de España (doc 16-08, regla 1). Con la fecha UTC, un
    protocolo con fecha de mañana entraba en vigor a las 23:00 de esta noche: el cliente
    veía lo nuevo antes de tiempo y lo de hoy desaparecía sin que nadie tocara nada."""
    return hoy_madrid().isoformat()


def _ordenadas(versiones) -> list:
    return sorted([v for v in (versiones or []) if v.get("fecha")], key=lambda v: str(v["fecha"])[:10])


def vigente_en(versiones, fecha: Optional[str] = None) -> Optional[dict]:
    """La version que aplica en `fecha`: la mas reciente que no la pase."""
    dia = (fecha or _hoy())[:10]
    previas = [v for v in _ordenadas(versiones) if str(v["fecha"])[:10] <= dia]
    return previas[-1] if previas else None


def proxima_desde(versiones, fecha: Optional[str] = None) -> Optional[dict]:
    """La siguiente version que entrara en vigor despues de `fecha`, si la hay."""
    dia = (fecha or _hoy())[:10]
    futuras = [v for v in _ordenadas(versiones) if str(v["fecha"])[:10] > dia]
    return futuras[0] if futuras else None


def _respuesta(doc: dict) -> dict:
    """El documento como lo espera quien lo consume: `actual` y `siguiente` RESUELTOS por
    fecha, mas el historico entero por si se quiere mirar."""
    versiones = _ordenadas(doc.get("versiones"))
    hoy = vigente_en(versiones)
    prox = proxima_desde(versiones)
    return {
        "client_id": doc.get("client_id"),
        "actual": (hoy or {}).get("items") or [],
        "actual_fecha": (hoy or {}).get("fecha"),
        "siguiente": (prox or {}).get("items") or [],
        "siguiente_fecha": (prox or {}).get("fecha"),
        "nota": (hoy or {}).get("nota"),
        "versiones": versiones,
        "updated_at": doc.get("updated_at"),
    }

# ── La suplementación general ────────────────────────────────────────────
# La que se le enseña a quien todavía no tiene la suya escrita. No es una lista aparte que
# haya que mantener: es el mismo arranque que el panel le propone al coach (`/suggest`),
# la base y el intra del catálogo con la variante que le toca por sexo. Así lo que ve el
# cliente y lo que el coach va a partir de ahí son la misma cosa.
#
# El quemador NO entra: eso es una decisión de coach para una persona concreta, no algo que
# se le pone delante a alguien porque su objetivo diga "definición".

def _sexo_de(profile: dict) -> str:
    """"hombre" o "mujer", tolerante con los nombres de campo que conviven en la base."""
    crudo = str(profile.get("sexo") or profile.get("sex") or profile.get("genero") or "").lower()
    es_mujer = "muj" in crudo or "fem" in crudo or crudo in ("f", "female")
    return "mujer" if es_mujer else "hombre"


async def protocolo_generico(profile: dict) -> list:
    """La base + el intra del catálogo, por orden y con la variante del sexo del cliente."""
    sexo = _sexo_de(profile)
    catalogo = await db.supplement_catalog.find(
        {"activo": True, "categoria": {"$in": ["base", "intra"]}}, {"_id": 0}
    ).sort("orden", 1).to_list(200)
    return [_catalog_to_protocol_item(c) for c in catalogo
            if c.get("sexo", "ambos") in (sexo, "ambos")]


# ==================== CLIENTE ====================
router = APIRouter(prefix="/supplements", tags=["supplements"])


@router.get("/current", response_model=Optional[SupplementProtocolResponse])
async def get_current_protocol(ctx=Depends(require_access("suplementacion"))):
    """Protocolo de suplementación del cliente (requiere plan con suplementación y suscripción activa).

    SIN PROTOCOLO PROPIO SE DEVUELVE LA GENERAL (Jesús, 18-08). Antes esto devolvía `None`
    y la pantalla contestaba "de momento no te hemos puesto nada", que es dejar sin nada al
    94 de cada 193 clientes que todavía no tienen el suyo escrito. Lo que él quiere es lo
    contrario: que siempre haya algo que tomar delante, la general, hasta que le pongamos
    la suya. Va marcada con `es_generica` para que nadie la confunda con una pauta personal.
    """
    profile = ctx["profile"]

    protocol = await db.supplement_protocols.find_one(
        {"client_id": profile["id"]}, {"_id": 0}
    )
    # Resuelto por fecha: el cliente ve el que le toca HOY, no el ultimo que se guardo. Un
    # protocolo dejado preparado para dentro de dos semanas no se le ensena todavia.
    resuelto = _respuesta(protocol) if protocol else {
        "client_id": profile["id"], "actual": [], "siguiente": [], "versiones": [],
    }

    # Sin nada vigente entra la general. Se mira `actual` y no si existe el documento: al
    # quitarle la suplementacion a alguien la version vigente se queda sin items, y ese
    # cliente esta igual de vacio que el que nunca tuvo una.
    if not resuelto.get("actual"):
        generica = await protocolo_generico(profile)
        if generica:
            resuelto["actual"] = generica
            resuelto["actual_fecha"] = None
            resuelto["es_generica"] = True

    return SupplementProtocolResponse(**resuelto)


# ==================== ADMIN ====================
admin_router = APIRouter(prefix="/admin/supplements", tags=["admin-supplements"])


# ── Catálogo (CRUD) ──────────────────────────────────────────────────────
@admin_router.get("/catalog")
async def list_catalog(include_inactive: bool = False, user=Depends(get_admin_user)):
    """Lista el catálogo de suplementos."""
    q = {} if include_inactive else {"activo": True}
    items = await db.supplement_catalog.find(q, {"_id": 0}).sort("orden", 1).to_list(500)
    return items


@admin_router.post("/catalog")
async def create_catalog_item(item: SupplementCatalogItem, user=Depends(get_admin_user)):
    """Crea un suplemento en el catálogo."""
    doc = item.model_dump()
    await db.supplement_catalog.insert_one(doc)
    return {"message": "Suplemento creado", "id": item.id}


@admin_router.put("/catalog/{item_id}")
async def update_catalog_item(item_id: str, item: SupplementCatalogItem, user=Depends(get_admin_user)):
    """Actualiza un suplemento del catálogo."""
    doc = item.model_dump()
    doc["id"] = item_id
    res = await db.supplement_catalog.update_one({"id": item_id}, {"$set": doc})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Suplemento no encontrado")
    return {"message": "Suplemento actualizado", "id": item_id}


@admin_router.delete("/catalog/{item_id}")
async def delete_catalog_item(item_id: str, user=Depends(get_admin_user)):
    """Borrado lógico (activo=false) de un suplemento del catálogo."""
    res = await db.supplement_catalog.update_one({"id": item_id}, {"$set": {"activo": False}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Suplemento no encontrado")
    return {"message": "Suplemento desactivado", "id": item_id}


# ── Asignación del protocolo por cliente ─────────────────────────────────
@admin_router.post("/save", response_model=SupplementProtocolResponse)
async def save_protocol(client_id: str, data: SupplementProtocolSave, user=Depends(get_admin_user)):
    """Asigna/actualiza el protocolo de un cliente (upsert por client_id)."""
    profile = await db.client_profiles.find_one({"id": client_id})
    assert_client_access(user, profile)

    previo = await db.supplement_protocols.find_one({"client_id": client_id}, {"_id": 0}) or {}
    versiones = _ordenadas(previo.get("versiones"))
    quien = user.get("name", user.get("email", "coach"))
    ahora = datetime.now(timezone.utc).isoformat()

    def _poner(fecha: str, items, nota):
        """Deja `items` como el protocolo que aplica desde `fecha`, pisando lo que hubiera
        ese dia. Las demas fechas del historico no se tocan."""
        nonlocal versiones
        dia = str(fecha)[:10]
        versiones = [v for v in versiones if str(v["fecha"])[:10] != dia]
        if items:
            versiones.append({"fecha": dia, "items": items, "nota": nota,
                              "guardado_por": quien, "guardado_at": ahora})
        versiones = _ordenadas(versiones)

    # El bloque "actual": si el coach no dice desde cuando, se respeta la fecha de la version
    # vigente. Corregir una dosis NO tiene por que abrir una version nueva; abrir una version
    # nueva es una decision, y para eso esta la fecha.
    vig = vigente_en(versiones)
    fecha_actual = (data.actual_fecha or (vig or {}).get("fecha") or _hoy())[:10]
    _poner(fecha_actual, [i.model_dump() for i in data.actual], data.nota)

    # El bloque "siguiente" es simplemente una version con fecha futura.
    if data.siguiente_fecha:
        _poner(data.siguiente_fecha, [i.model_dump() for i in data.siguiente], data.nota)

    doc = {"client_id": client_id, "versiones": versiones, "updated_at": ahora}
    await db.supplement_protocols.update_one(
        {"client_id": client_id}, {"$set": doc}, upsert=True
    )

    # SOLO SE AVISA SI HAY ALGO QUE VER (T2 del doc del 16-08: "si le cambias la
    # suplementación, le llega el aviso y AQUÍ LO VE").
    #
    # Guardar sin ningún suplemento borra la versión vigente -- es la forma de quitarle la
    # suplementación -- y aun así salía el aviso "tu protocolo se ha actualizado". El
    # cliente entraba y se encontraba "Todavía no tienes suplementación", que es
    # exactamente la queja de la que sale esta tarea. Sin nada pautado no hay novedad que
    # anunciar.
    resuelto = _respuesta(doc)
    if resuelto["actual"] or resuelto["siguiente"]:
        from routes.notifications import avisar_suplementos
        await avisar_suplementos(profile["user_id"], nota=data.nota)

    return SupplementProtocolResponse(**resuelto)


@admin_router.delete("/version/{fecha}")
async def borrar_version(client_id: str, fecha: str, user=Depends(get_admin_user)):
    """Borra una version del historico (una fecha concreta). El resto se queda."""
    profile = await db.client_profiles.find_one({"id": client_id})
    assert_client_access(user, profile)
    doc = await db.supplement_protocols.find_one({"client_id": client_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Este cliente no tiene protocolo")
    dia = str(fecha)[:10]
    versiones = [v for v in _ordenadas(doc.get("versiones")) if str(v["fecha"])[:10] != dia]
    doc = {"client_id": client_id, "versiones": versiones,
           "updated_at": datetime.now(timezone.utc).isoformat()}
    await db.supplement_protocols.update_one({"client_id": client_id}, {"$set": doc})
    return SupplementProtocolResponse(**_respuesta(doc))


def _catalog_to_protocol_item(c: dict) -> dict:
    """Snapshot de un ítem del catálogo para meterlo en el protocolo."""
    return {
        "catalog_id": c.get("id"),
        "titulo": c.get("titulo", ""),
        "imagen": c.get("imagen"),
        "enlaces": c.get("enlaces", []),
        "cuando": c.get("cuando", ""),
        "cuanto": c.get("cuanto", ""),
        "observaciones": c.get("observaciones"),
    }


@admin_router.post("/suggest")
async def suggest_protocol(client_id: str, user=Depends(get_admin_user)):
    """Propone un protocolo inicial según el perfil (sexo y objetivo).
    No guarda nada: el entrenador lo revisa/edita antes de guardar."""
    profile = await db.client_profiles.find_one({"id": client_id}, {"_id": 0})
    assert_client_access(user, profile)

    # Sexo y objetivo (tolerante a distintos nombres de campo)
    sexo = _sexo_de(profile)
    objetivo = str(profile.get("objetivo") or profile.get("goal") or "").lower()
    es_definicion = "defin" in objetivo or "cut" in objetivo or "perder" in objetivo

    catalog = await db.supplement_catalog.find({"activo": True}, {"_id": 0}).sort("orden", 1).to_list(500)

    def sexo_ok(c):
        return c.get("sexo", "ambos") in (sexo, "ambos")

    actual = []
    # Stack base + intra, con la variante de sexo correcta
    for c in catalog:
        if c.get("categoria") in ("base", "intra") and sexo_ok(c):
            actual.append(_catalog_to_protocol_item(c))
    # Definición → añadir un quemador
    if es_definicion:
        quemador = next((c for c in catalog if c.get("categoria") == "quemador" and sexo_ok(c)), None)
        if quemador:
            actual.append(_catalog_to_protocol_item(quemador))

    # Dedup por catalog_id conservando orden
    seen = set()
    dedup = []
    for it in actual:
        k = it.get("catalog_id")
        if k in seen:
            continue
        seen.add(k)
        dedup.append(it)

    return {
        "actual": dedup,
        "siguiente": [],
        "siguiente_fecha": None,
        "nota": None,
        "_meta": {"sexo": sexo, "objetivo": objetivo, "es_definicion": es_definicion},
    }
