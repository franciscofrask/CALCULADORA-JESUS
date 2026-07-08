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
from core.security import get_current_user, get_admin_user
from models.supplements import (
    SupplementCatalogItem, SupplementProtocolSave, SupplementProtocolResponse,
    ProtocolItem,
)

# ==================== CLIENTE ====================
router = APIRouter(prefix="/supplements", tags=["supplements"])


@router.get("/current", response_model=Optional[SupplementProtocolResponse])
async def get_current_protocol(user=Depends(get_current_user)):
    """Protocolo de suplementación asignado al cliente (actual + siguiente + nota)."""
    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")

    protocol = await db.supplement_protocols.find_one(
        {"client_id": profile["id"]}, {"_id": 0}
    )
    if not protocol:
        return None
    return SupplementProtocolResponse(**protocol)


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
    if not profile:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    doc = {
        "client_id": client_id,
        "actual": [i.model_dump() for i in data.actual],
        "siguiente": [i.model_dump() for i in data.siguiente],
        "siguiente_fecha": data.siguiente_fecha,
        "nota": data.nota,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.supplement_protocols.update_one(
        {"client_id": client_id}, {"$set": doc}, upsert=True
    )

    from routes.notifications import notify
    await notify(profile["user_id"], "suplementos", "Tu protocolo de suplementos se ha actualizado", "/dashboard/supplements")

    return SupplementProtocolResponse(**doc)


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
    if not profile:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    # Sexo y objetivo (tolerante a distintos nombres de campo)
    sexo_raw = str(profile.get("sexo") or profile.get("sex") or profile.get("genero") or "").lower()
    sexo = "mujer" if ("muj" in sexo_raw or "fem" in sexo_raw or sexo_raw in ("f", "female")) else "hombre"
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
