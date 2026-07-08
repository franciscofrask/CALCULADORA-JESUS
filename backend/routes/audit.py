"""
Registro de auditoría: quién hizo qué en las acciones sensibles del panel
(macros, coach, roles, contraseñas, bajas, leads).
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone
import uuid

from core.database import db
from core.security import get_admin_user

router = APIRouter(prefix="/admin/audit", tags=["audit"])


async def audit(actor: dict, action: str, detail: str = ""):
    """Registra una acción sensible. Falla en silencio: el log nunca debe
    romper la operación principal."""
    try:
        await db.audit_log.insert_one({
            "id": str(uuid.uuid4()),
            "actor_id": actor.get("id"),
            "actor_name": actor.get("name") or actor.get("email") or "staff",
            "action": action,
            "detail": detail,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass


@router.get("")
async def list_audit(limit: int = 100, user = Depends(get_admin_user)):
    """Últimas acciones del equipo, de más reciente a más antigua."""
    entries = await db.audit_log.find({}, {"_id": 0}).sort("created_at", -1).to_list(min(max(1, limit), 300))
    return {"entries": entries}
