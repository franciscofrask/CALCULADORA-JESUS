"""
Rutas de pagos (MOCKED).
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
from typing import List
import uuid

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

@router.post("/simulate")
async def simulate_payment(amount: float, user = Depends(get_current_user)):
    """Simular un pago (para testing)."""
    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    
    payment = {
        "id": str(uuid.uuid4()),
        "client_id": profile["id"],
        "amount": amount,
        "status": "success",
        "method": "card",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.payments.insert_one(payment)
    
    return PaymentResponse(**payment)
