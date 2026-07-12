"""
Catálogo de planes y membresías.

Fuente única: PLAN_CATALOG (código) + overrides editables por el admin (db.plan_overrides).
El catálogo refleja el documento "JG - Catálogo de Planes y Membresías".
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from core.database import db
from core.security import get_admin_user
from models.user import PLAN_CATALOG, PLAN_EDITABLE_FIELDS, merged_catalog
from routes.audit import audit

router = APIRouter(tags=["plans"])


async def _overrides_by_code() -> Dict[str, Dict[str, Any]]:
    docs = await db.plan_overrides.find({}, {"_id": 0}).to_list(200)
    return {d["code"]: d.get("fields", {}) for d in docs if d.get("code")}


@router.get("/plans")
async def get_plans(estado: Optional[str] = None):
    """Catálogo público (con overrides del admin aplicados). Cada plan incluye estado,
    ciclo, precios, habilitaciones y `features`. Filtra por
    ?estado=activo|legacy|especial|complemento.
    """
    catalog = merged_catalog(await _overrides_by_code())
    if estado:
        return {c: p for c, p in catalog.items() if p.get("estado") == estado}
    return catalog


# ==================== ADMIN ====================

admin_router = APIRouter(prefix="/admin/plans", tags=["admin-plans"])


@admin_router.get("")
async def admin_list_plans(user=Depends(get_admin_user)):
    """Catálogo completo para el panel admin (con overrides aplicados). Marca qué
    planes tienen alguna edición respecto al valor por defecto del código."""
    overrides = await _overrides_by_code()
    catalog = merged_catalog(overrides)
    for code, p in catalog.items():
        p["has_override"] = bool(overrides.get(code))
    return catalog


@admin_router.put("/{code}")
async def admin_update_plan(code: str, data: dict, user=Depends(get_admin_user)):
    """Edita campos del catálogo de un plan (se guardan como override sobre el
    valor por defecto). Solo se aceptan campos editables."""
    code = (code or "").lower().strip()
    if code not in PLAN_CATALOG:
        raise HTTPException(status_code=404, detail="Plan no encontrado")

    fields = {k: v for k, v in (data or {}).items() if k in PLAN_EDITABLE_FIELDS}
    if not fields:
        raise HTTPException(
            status_code=400,
            detail=f"Nada que editar. Campos válidos: {', '.join(sorted(PLAN_EDITABLE_FIELDS))}",
        )

    existing = await db.plan_overrides.find_one({"code": code}, {"_id": 0, "fields": 1})
    merged_fields = {**(existing.get("fields") if existing else {}), **fields}
    await db.plan_overrides.update_one(
        {"code": code},
        {"$set": {"code": code, "fields": merged_fields,
                  "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    await audit(user, "plan", f"Editó el plan {code} ({', '.join(sorted(fields.keys()))})")
    return merged_catalog({code: merged_fields})[code]


@admin_router.delete("/{code}")
async def admin_reset_plan(code: str, user=Depends(get_admin_user)):
    """Elimina los overrides de un plan y lo restaura al valor por defecto del código."""
    code = (code or "").lower().strip()
    if code not in PLAN_CATALOG:
        raise HTTPException(status_code=404, detail="Plan no encontrado")
    await db.plan_overrides.delete_one({"code": code})
    await audit(user, "plan", f"Restauró el plan {code} a los valores por defecto")
    return merged_catalog()[code]
