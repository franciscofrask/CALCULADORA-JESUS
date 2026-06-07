"""
Rutas de dietas: CRUD, calendario, copiar.
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from datetime import datetime, timezone
from typing import Optional
import calendar

from core.database import db
from core.security import get_current_user
from pdf_generator import generate_diet_pdf

router = APIRouter(prefix="/diets", tags=["diets"])

@router.post("")
async def save_diet(data: dict, user = Depends(get_current_user)):
    """Guardar la dieta completa de un día, o solo distribution_targets si targets_only=true."""
    fecha = data.get("fecha")
    if not fecha:
        raise HTTPException(status_code=400, detail="Fecha requerida")

    if data.get("targets_only"):
        await db.diets.update_one(
            {"user_id": user["id"], "fecha": fecha},
            {"$set": {
                "distribution_targets": data.get("distribution_targets"),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }},
            upsert=True
        )
        return {"message": "Targets actualizados", "fecha": fecha}

    diet_doc = {
        "user_id": user["id"],
        "fecha": fecha,
        "tipo_dia": data.get("tipo_dia", "entrenamiento"),
        "num_comidas": data.get("num_comidas", 4),
        "momento_entreno": data.get("momento_entreno", 1),
        "opcion_peri": data.get("opcion_peri", "intra_post"),
        "comidas": data.get("comidas", {}),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "macros_snapshot": data.get("macros_snapshot", None),
        "distribution_targets": data.get("distribution_targets", None),
        "is_cuadrado": data.get("is_cuadrado", False)
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
        {"_id": 0, "fecha": 1, "tipo_dia": 1, "num_comidas": 1, "comidas": 1, "distribution_targets": 1}
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
            "comidas": diet.get("comidas", {}),
            "distribution_targets": diet.get("distribution_targets", None)
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
        {"_id": 0, "fecha": 1, "tipo_dia": 1, "comidas": 1, "is_cuadrado": 1}
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
            "total_comidas": total_comidas,
            "is_cuadrado": diet.get("is_cuadrado", False)
        }
    
    return {"year": year, "month": month, "days": calendar_data}

@router.patch("/{fecha}/targets")
async def update_diet_targets(fecha: str, data: dict, user = Depends(get_current_user)):
    """Actualizar solo distribution_targets sin tocar comidas."""
    await db.diets.update_one(
        {"user_id": user["id"], "fecha": fecha},
        {"$set": {
            "distribution_targets": data.get("distribution_targets"),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }},
        upsert=True
    )
    return {"message": "Targets actualizados", "fecha": fecha}

@router.post("/copy-day")
async def copy_day(data: dict, user = Depends(get_current_user)):
    """Copiar el día completo (todas las comidas) de una fecha a otra."""
    source_date = data.get("fecha_origen")
    target_date = data.get("fecha_destino")
    if not source_date or not target_date:
        raise HTTPException(status_code=400, detail="Faltan fecha_origen y fecha_destino")

    source_diet = await db.diets.find_one({"user_id": user["id"], "fecha": source_date}, {"_id": 0})
    if not source_diet:
        raise HTTPException(status_code=404, detail="No hay dieta guardada para la fecha origen")

    copy_doc = {
        "user_id": user["id"],
        "fecha": target_date,
        "tipo_dia": source_diet.get("tipo_dia", "entrenamiento"),
        "num_comidas": source_diet.get("num_comidas", 4),
        "momento_entreno": source_diet.get("momento_entreno", 1),
        "opcion_peri": source_diet.get("opcion_peri", "intra_post"),
        "comidas": source_diet.get("comidas", {}),
        "macros_snapshot": source_diet.get("macros_snapshot"),
        "distribution_targets": source_diet.get("distribution_targets"),
        "is_cuadrado": source_diet.get("is_cuadrado", False),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    await db.diets.update_one(
        {"user_id": user["id"], "fecha": target_date},
        {"$set": copy_doc},
        upsert=True
    )
    return {"message": "Día copiado", "origen": source_date, "destino": target_date}

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
    
    # Also copy distribution target for that specific meal if it exists
    source_targets = source_diet.get("distribution_targets") or {}
    source_meal_target = source_targets.get(source_meal)

    update_payload = {
        f"comidas.{target_meal}": source_comida,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    if source_meal_target:
        update_payload[f"distribution_targets.{target_meal}"] = source_meal_target

    await db.diets.update_one(
        {"user_id": user["id"], "fecha": target_date},
        {
            "$set": update_payload
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


@router.get("/{fecha}/pdf")
async def export_diet_pdf(fecha: str, user = Depends(get_current_user)):
    """Genera PDF de la dieta de un día desde NutritionPage."""
    diet = await db.diets.find_one(
        {"user_id": user["id"], "fecha": fecha},
        {"_id": 0}
    )
    if not diet:
        raise HTTPException(status_code=404, detail="No hay dieta guardada para este día")

    comidas_raw = diet.get("comidas", {})
    if not comidas_raw:
        raise HTTPException(status_code=400, detail="La dieta está vacía")

    meal_names = {
        "C1": "Comida 1", "C2": "Comida 2", "C3": "Comida 3", "C4": "Comida 4",
        "Intra": "Intra-entreno", "Post": "Post-entreno"
    }

    # Build comidas list in the format pdf_generator expects
    comidas_list = []
    total_p, total_h, total_g = 0, 0, 0

    for key in ["C1", "Intra", "Post", "C2", "C3", "C4"]:
        meal_data = comidas_raw.get(key)
        if not meal_data:
            continue
        alimentos_raw = meal_data.get("alimentos", [])
        if not alimentos_raw:
            continue

        alimentos_pdf = []
        mp, mh, mg = 0, 0, 0
        for a in alimentos_raw:
            me = a.get("macros_efectivos", {})
            p = round(me.get("P", 0), 1)
            h = round(me.get("H", 0), 1)
            g = round(me.get("G", 0), 1)
            mp += p; mh += h; mg += g
            alimentos_pdf.append({
                "nombre": a.get("nombre", "?"),
                "cantidad": a.get("cantidad_g", 0),
                "unidad": "g",
                "macros": {"P": p, "H": h, "G": g},
            })

        total_p += mp; total_h += mh; total_g += mg
        comidas_list.append({
            "numero": meal_names.get(key, key),
            "alimentos": alimentos_pdf,
            "macros": {"P": round(mp, 1), "H": round(mh, 1), "G": round(mg, 1)},
            "objetivo": {},
        })

    summary = {
        "objetivo_total": {},
        "totales": {"P": round(total_p, 1), "H": round(total_h, 1), "G": round(total_g, 1)},
        "diferencia": {},
        "comidas": comidas_list,
    }

    user_name = user.get("name", "Cliente")
    pdf_buffer = generate_diet_pdf(summary, user_name, fecha)
    filename = f"dieta_jg12_{fecha}.pdf"

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
