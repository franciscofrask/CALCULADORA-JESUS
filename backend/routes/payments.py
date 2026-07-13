"""
Rutas de pagos: historial de pagos del cliente (solo lectura).

Los pagos reales los registra el circuito de Stripe (core/stripe_billing.py vía webhook).
El endpoint /simulate de creación de pagos falsos fue eliminado: permitía a cualquier
usuario autenticado insertar pagos "success" arbitrarios y falsear el historial.
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List

from core.database import db
from core.security import get_current_user
from models.common import PaymentResponse

router = APIRouter(prefix="/payments", tags=["payments"])

@router.get("", response_model=List[PaymentResponse])
async def get_payments(user = Depends(get_current_user)):
    """Obtener historial de pagos."""
    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")

    payments = await db.payments.find(
        {"client_id": profile["id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)

    return [PaymentResponse(**p) for p in payments]
