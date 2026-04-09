"""
Rutas de dietas: CRUD, calendario, copiar.
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
from typing import Optional
import calendar

from core.database import db
from core.security import get_current_user

router = APIRouter(prefix="/diets", tags=["diets"])

@router.post("")
async def save_diet(data: dict, user = Depends(get_current_user)):
    """Guardar la dieta completa de un día."""
    fecha = data.get("fecha")
    if not fecha:
        raise HTTPException(status_code=400, detail="Fecha requerida")
    
    diet_doc = {
        "user_id": user["id"],
        "fecha": fecha,
        "tipo_dia": data.get("tipo_dia", "entrenamiento"),
        "num_comidas": data.get("num_comidas", 4),
        "momento_entreno": data.get("momento_entreno", 1),
        "opcion_peri": data.get("opcion_peri", "intra_post"),
        "comidas": data.get("comidas", {}),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "macros_snapshot": data.get("macros_snapshot", None)
    }
    
    await db.diets.update_one(
        {"user_id": user["id"], "fecha": fecha},
        {"$set": diet_doc},
        upsert=True
    )
    
    return {"message": "Dieta guardada", "fecha": fecha}

@router.get("/recent")
async def get_recent_diets(limit: int = 14, user = Depends(get_current_user)):
    """Lista los últimos días con dieta guardada."""
    cursor = db.diets.find(
        {"user_id": user["id"]},
        {"_id": 0, "fecha": 1, "tipo_dia": 1, "num_comidas": 1, "comidas": 1}
    ).sort("fecha", -1).limit(limit)
    
    diets = await cursor.to_list(length=limit)
    
    result = []
    for diet in diets:
        comidas_resumen = {}
        for key, meal_data in (diet.get("comidas") or {}).items():
            alimentos = meal_data.get("alimentos") or []
            if alimentos:
                nombres = [a.get("nombre", "?")[:20] for a in alimentos[:3]]
                comidas_resumen[key] = " + ".join(nombres)
                if len(alimentos) > 3:
                    comidas_resumen[key] += f" +{len(alimentos)-3}"
        
        result.append({
            "fecha": diet.get("fecha"),
            "tipo_dia": diet.get("tipo_dia", "entrenamiento"),
            "num_comidas": diet.get("num_comidas", 4),
            "comidas_resumen": comidas_resumen,
            "comidas": diet.get("comidas", {})
        })
    
    return {"diets": result, "count": len(result)}

@router.get("/calendar/{year}/{month}")
async def get_diet_calendar(year: int, month: int, user = Depends(get_current_user)):
    """Obtener calendario de dietas del mes."""
    start_date = f"{year}-{month:02d}-01"
    last_day = calendar.monthrange(year, month)[1]
    end_date = f"{year}-{month:02d}-{last_day}"
    
    diets = await db.diets.find(
        {
            "user_id": user["id"],
            "fecha": {"$gte": start_date, "$lte": end_date}
        },
        {"_id": 0, "fecha": 1, "tipo_dia": 1, "comidas": 1}
    ).to_list(31)
    
    calendar_data = {}
    for diet in diets:
        fecha = diet["fecha"]
        comidas = diet.get("comidas", {})
        
        total_foods = sum(len(m.get("alimentos", [])) for m in comidas.values())
        total_comidas = len([k for k, v in comidas.items() if v.get("alimentos")])
        
        status = "empty"
        if total_foods > 0:
            num_comidas = 4
            if total_comidas >= num_comidas:
                status = "complete"
            elif total_comidas > 0:
                status = "partial"
        
        calendar_data[fecha] = {
            "tipo_dia": diet.get("tipo_dia", "entrenamiento"),
            "status": status,
            "total_comidas": total_comidas
        }
    
    return {"year": year, "month": month, "days": calendar_data}

@router.get("/{fecha}")
async def get_diet(fecha: str, user = Depends(get_current_user)):
    """Obtener la dieta guardada para una fecha."""
    diet = await db.diets.find_one(
        {"user_id": user["id"], "fecha": fecha},
        {"_id": 0}
    )
    if not diet:
        return {"fecha": fecha, "exists": False}
    
    diet["exists"] = True
    return diet

@router.post("/copy")
async def copy_diet(data: dict, user = Depends(get_current_user)):
    """Copiar una comida de otro día."""
    source_date = data.get("source_date")
    source_meal = data.get("source_meal")
    target_date = data.get("target_date")
    target_meal = data.get("target_meal")
    
    if not all([source_date, source_meal, target_date, target_meal]):
        raise HTTPException(status_code=400, detail="Faltan parámetros")
    
    source_diet = await db.diets.find_one(
        {"user_id": user["id"], "fecha": source_date},
        {"_id": 0}
    )
    
    if not source_diet:
        raise HTTPException(status_code=404, detail="Dieta origen no encontrada")
    
    source_comida = source_diet.get("comidas", {}).get(source_meal)
    if not source_comida:
        raise HTTPException(status_code=404, detail="Comida origen no encontrada")
    
    await db.diets.update_one(
        {"user_id": user["id"], "fecha": target_date},
        {
            "$set": {
                f"comidas.{target_meal}": source_comida,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
        },
        upsert=True
    )
    
    return {
        "message": "Comida copiada",
        "source": f"{source_date}/{source_meal}",
        "target": f"{target_date}/{target_meal}"
    }

@router.delete("/{fecha}")
async def delete_diet(fecha: str, user = Depends(get_current_user)):
    """Eliminar una dieta."""
    result = await db.diets.delete_one({"user_id": user["id"], "fecha": fecha})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Dieta no encontrada")
    return {"message": "Dieta eliminada", "fecha": fecha}
