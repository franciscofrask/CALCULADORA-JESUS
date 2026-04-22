"""
Rutas del calculador de macros y búsqueda de alimentos.
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import uuid

from core.database import db
from core.security import get_current_user
from models.common import FoodSuggestion, FoodSuggestionResponse

# Import calculator functions
from calma_engine import (
    calcular_macros_efectivos_alimento as calcular_macros_efectivos, 
    que_macros_cuentan, 
    calcular_macros_brutos, 
    run_tests as calma_run_tests
)
from calculator import buscar_alimentos as buscar_alimentos_async, sugerir_alimentos, get_food_config
from target_calculator import calcular_targets, targets_to_profile_macros, run_tests as target_run_tests
from macro_distribution import distribuir_macros as dist_macros

router = APIRouter(prefix="/calculator", tags=["calculator"])

# ==================== FOODS ====================

@router.get("/foods")
async def get_foods(
    search: Optional[str] = None, 
    category: Optional[str] = None, 
    limit: int = 100, 
    user = Depends(get_current_user)
):
    """Obtiene la lista de alimentos desde MongoDB con filtros opcionales."""
    query = {}
    
    if search:
        query["nombre"] = {"$regex": search, "$options": "i"}
    
    if category:
        query["categorias"] = {"$regex": category}
    
    foods_cursor = db.foods.find(query, {"_id": 0}).limit(limit)
    foods = await foods_cursor.to_list(limit)
    return foods

@router.get("/foods/count")
async def get_foods_count(user = Depends(get_current_user)):
    """Retorna el conteo total de alimentos."""
    count = await db.foods.count_documents({})
    return {"total": count}

# ==================== CATEGORIES ====================

@router.get("/categories")
async def get_food_categories(user = Depends(get_current_user)):
    """Obtiene todas las categorías de alimentos."""
    categories_cursor = db.food_categories.find({}, {"_id": 0})
    categories = await categories_cursor.to_list(500)
    return categories

@router.get("/categories/count")
async def get_categories_count(user = Depends(get_current_user)):
    """Retorna el conteo total de categorías."""
    count = await db.food_categories.count_documents({})
    return {"total": count}

# ==================== MEAL CALCULATIONS ====================

@router.post("/meal")
async def calculate_meal(foods: List[Dict[str, Any]], user = Depends(get_current_user)):
    """Calcula macros totales de una comida."""
    total = {"calories": 0, "protein": 0, "carbs": 0, "fat": 0}
    
    for item in foods:
        quantity = item.get("quantity", 100) / 100
        total["calories"] += item.get("calories", 0) * quantity
        total["protein"] += item.get("protein", 0) * quantity
        total["carbs"] += item.get("carbs", 0) * quantity
        total["fat"] += item.get("fat", 0) * quantity
    
    return {k: round(v, 1) for k, v in total.items()}

# ==================== CALMA ENGINE ====================

@router.post("/macros-efectivos")
async def get_macros_efectivos(data: dict, user = Depends(get_current_user)):
    """Calcula los macros efectivos de un alimento."""
    alimento_id = data.get("alimento_id")
    cantidad_g = data.get("cantidad_g", 100)
    es_vegano = data.get("es_vegano", False)
    
    alimento = await db.foods.find_one({"id": alimento_id}, {"_id": 0})
    if not alimento:
        raise HTTPException(status_code=404, detail="Alimento no encontrado")
    
    efectivos = calcular_macros_efectivos(alimento, cantidad_g, es_vegano)
    brutos = calcular_macros_brutos(alimento, cantidad_g)
    cuenta = que_macros_cuentan(alimento, cantidad_g, es_vegano)
    
    return {
        "alimento": {
            "id": alimento.get("id"),
            "nombre": alimento.get("nombre"),
            "categorias": alimento.get("categorias"),
            "racion": alimento.get("racion")
        },
        "cantidad_g": cantidad_g,
        "efectivos": efectivos,
        "brutos": brutos,
        "que_cuenta": cuenta
    }

@router.post("/macros-comida")
async def get_macros_comida(data: dict, user = Depends(get_current_user)):
    """Calcula los macros totales de una comida completa."""
    alimentos_input = data.get("alimentos", [])
    es_vegano = data.get("es_vegano", False)
    
    total_P = total_H = total_G = 0.0
    total_P_bruto = total_H_bruto = total_G_bruto = 0.0
    detalle = []
    
    for item in alimentos_input:
        alimento = await db.foods.find_one({"id": item["alimento_id"]}, {"_id": 0})
        if not alimento:
            continue
        
        cantidad = item.get("cantidad_g", alimento.get("racion", 100))
        
        efectivos = calcular_macros_efectivos(alimento, cantidad, es_vegano)
        brutos = calcular_macros_brutos(alimento, cantidad)
        cuenta = que_macros_cuentan(alimento, cantidad, es_vegano)
        
        total_P += efectivos["P"]
        total_H += efectivos["H"]
        total_G += efectivos["G"]
        total_P_bruto += brutos["P"]
        total_H_bruto += brutos["H"]
        total_G_bruto += brutos["G"]
        
        detalle.append({
            "alimento_id": item["alimento_id"],
            "nombre": alimento.get("nombre", ""),
            "cantidad_g": cantidad,
            "efectivos": efectivos,
            "brutos": brutos,
            "que_cuenta": cuenta
        })
    
    return {
        "total_efectivos": {
            "P": round(total_P, 1),
            "H": round(total_H, 1),
            "G": round(total_G, 1),
            "kcal": round(total_P * 4 + total_H * 4 + total_G * 9, 1)
        },
        "total_brutos": {
            "P": round(total_P_bruto, 1),
            "H": round(total_H_bruto, 1),
            "G": round(total_G_bruto, 1),
            "kcal": round(total_P_bruto * 4 + total_H_bruto * 4 + total_G_bruto * 9, 1)
        },
        "detalle": detalle
    }

@router.get("/test-calma")
async def test_calma():
    """Ejecuta los tests del motor CALMA v2."""
    results = calma_run_tests()
    return results


# ==================== DISTRIBUTE MACROS ====================

@router.post("/distribute")
async def distribute_macros(data: dict, user = Depends(get_current_user)):
    """
    Distribuye los macros del usuario entre sus comidas del día.
    Los macros se obtienen del perfil del usuario.
    """
    profile = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil de cliente no encontrado")

    training = profile.get("macros_training", {})
    rest = profile.get("macros_rest", {})
    peri = profile.get("macros_periworkout") or profile.get("macros_peri") or {}

    if not training:
        raise HTTPException(status_code=400, detail="No tienes macros asignados")

    resultado = dist_macros(
        p_entreno=float(training.get("protein") or training.get("proteinas") or 0),
        h_entreno=float(training.get("carbs") or training.get("hidratos") or 0),
        g_entreno=float(training.get("fat") or training.get("grasas") or 0),
        p_peri=float(peri.get("protein") or peri.get("proteinas") or 35),
        h_peri=float(peri.get("carbs") or peri.get("hidratos") or 15),
        p_descanso=float(rest.get("protein") or rest.get("proteinas") or 0),
        h_descanso=float(rest.get("carbs") or rest.get("hidratos") or 0),
        g_descanso=float(rest.get("fat") or rest.get("grasas") or 0),
        tipo_dia=data.get("tipo_dia", "entrenamiento"),
        num_comidas=data.get("num_comidas", 4),
        momento_entreno=data.get("momento_entreno", 1),
        opcion_peri=data.get("opcion_peri", "intra_post")
    )

    return resultado


# ==================== SEARCH & SUGGEST ====================

@router.get("/search")
async def search_foods_endpoint(
    q: str = "",
    category: Optional[str] = None,
    tipo_comida: str = "normal",
    tag: Optional[str] = None,
    limit: int = 50,
    vegano: bool = False,
    user = Depends(get_current_user)
):
    """Búsqueda de alimentos con macros efectivos (CALMA), ordenados por frecuencia de uso."""
    alimentos = await buscar_alimentos_async(
        db=db,
        query=q,
        categoria=category or "",
        tipo_comida=tipo_comida,
        es_vegano=vegano,
        limit=limit,
        calcular_efectivos=True,
        tag_filter=tag or ""
    )

    # Sort by client's usage frequency
    food_freq = await _get_food_frequency(user["id"])
    if food_freq:
        alimentos.sort(key=lambda f: -food_freq.get(str(f.get("id", "")), 0))
    else:
        alimentos.sort(key=lambda f: f.get("nombre", ""))

    return {"alimentos": alimentos, "total": len(alimentos)}


async def _get_food_frequency(user_id: str) -> dict:
    """Count how many times each food appears in user's saved diets."""
    diets = await db.diets.find(
        {"user_id": user_id},
        {"_id": 0, "comidas": 1}
    ).to_list(100)

    if not diets:
        return {}

    freq = {}
    for diet in diets:
        for meal_data in (diet.get("comidas") or {}).values():
            for alimento in (meal_data.get("alimentos") or []):
                fid = str(alimento.get("id", alimento.get("alimento_id", "")))
                if fid:
                    freq[fid] = freq.get(fid, 0) + 1
    return freq

@router.post("/suggest")
async def suggest_foods_endpoint(
    data: dict,
    user = Depends(get_current_user)
):
    """Sugerir alimentos para completar macros."""
    objetivo = data.get("objetivo", {"P": 40, "H": 15, "G": 8})
    restante = data.get("restante", objetivo)
    paso = data.get("paso")
    limit = data.get("limit", 5)
    
    foods_list = await db.foods.find({}, {"_id": 0}).to_list(3000)
    
    sugerencias = sugerir_alimentos(
        alimentos_disponibles=foods_list,
        macros_restantes=restante,
        max_resultados=limit,
        paso=paso
    )
    
    return {"suggestions": sugerencias, "count": len(sugerencias)}

# ==================== FOOD SUGGESTIONS (user submitted) ====================

@router.post("/suggest-food", response_model=FoodSuggestionResponse)
async def suggest_new_food(food: FoodSuggestion, user = Depends(get_current_user)):
    """Usuario sugiere añadir un nuevo alimento."""
    profile = await db.client_profiles.find_one({"user_id": user["id"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    
    suggestion = {
        "id": str(uuid.uuid4()),
        "client_id": profile["id"],
        "food": food.model_dump(),
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.food_suggestions.insert_one(suggestion)
    
    return FoodSuggestionResponse(**suggestion)

# ==================== MENU TEMPLATES ====================

@router.get("/menu-options")
async def get_menu_options(
    tipo_dia: str,
    num_comida: int,
    macros: Optional[str] = None,
    user = Depends(get_current_user)
):
    """Genera opciones de menú A/B/C para una comida."""
    from meal_templates import generar_opciones_menu
    
    target_macros = {"P": 40, "H": 15, "G": 8}
    if macros:
        parts = macros.split(",")
        if len(parts) == 3:
            target_macros = {"P": float(parts[0]), "H": float(parts[1]), "G": float(parts[2])}
    
    foods_list = await db.foods.find({}, {"_id": 0}).to_list(3000)
    options = generar_opciones_menu(tipo_dia, num_comida, target_macros, foods_list)
    
    return options

@router.get("/test-templates")
async def test_templates():
    """Test endpoint para verificar templates de menú."""
    from meal_templates import generar_opciones_menu
    
    foods_list = await db.foods.find({}, {"_id": 0}).to_list(3000)
    target = {"P": 40, "H": 15, "G": 8}
    
    return {
        "entrenamiento_c1": generar_opciones_menu("entrenamiento", 1, target, foods_list),
        "descanso_c1": generar_opciones_menu("descanso", 1, target, foods_list)
    }

# ==================== CONFIG ====================

@router.get("/food-config/{food_id}")
async def get_food_config_endpoint(food_id: int, user = Depends(get_current_user)):
    """Obtiene la configuración (min/max) de un alimento."""
    food = await db.foods.find_one({"id": food_id}, {"_id": 0})
    if not food:
        raise HTTPException(status_code=404, detail="Alimento no encontrado")
    
    config = get_food_config(food)
    return {
        "food_id": food_id,
        "nombre": food.get("nombre"),
        "config": config
    }


# ==================== TARGET CALCULATOR ====================

@router.post("/targets")
async def calculate_client_targets(data: dict, user = Depends(get_current_user)):
    """
    Calcula los macros objetivo del cliente basado en peso, sexo, %graso y objetivo.
    Usa las tablas de Jesús Gallego (macros_tables.json).
    
    Body: {"peso": 80, "sexo": "hombre", "porcentaje_graso": 20, "objetivo": "volumen"}
    """
    peso = data.get("peso")
    sexo = data.get("sexo")
    bf = data.get("porcentaje_graso")
    objetivo = data.get("objetivo")

    if not all([peso, sexo, bf is not None, objetivo]):
        raise HTTPException(status_code=400, detail="Faltan campos: peso, sexo, porcentaje_graso, objetivo")

    try:
        targets = calcular_targets(
            peso=float(peso),
            sexo=sexo,
            porcentaje_graso=float(bf),
            objetivo=objetivo
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return targets


@router.post("/targets/apply")
async def calculate_and_apply_targets(data: dict, user = Depends(get_current_user)):
    """
    Calcula targets Y los aplica al perfil del cliente automáticamente.
    Guarda macros_training, macros_rest y macros_periworkout en el perfil.
    
    Body: {"peso": 80, "sexo": "hombre", "porcentaje_graso": 20, "objetivo": "volumen"}
    """
    peso = data.get("peso")
    sexo = data.get("sexo")
    bf = data.get("porcentaje_graso")
    objetivo = data.get("objetivo")

    if not all([peso, sexo, bf is not None, objetivo]):
        raise HTTPException(status_code=400, detail="Faltan campos: peso, sexo, porcentaje_graso, objetivo")

    try:
        targets = calcular_targets(
            peso=float(peso),
            sexo=sexo,
            porcentaje_graso=float(bf),
            objetivo=objetivo
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    profile_macros = targets_to_profile_macros(targets)

    # Actualizar perfil del cliente
    update_data = {
        "weight": float(peso),
        "sex": sexo,
        "body_fat": float(bf),
        "goal": objetivo,
        "macros_training": profile_macros["macros_training"],
        "macros_rest": profile_macros["macros_rest"],
        "macros_periworkout": profile_macros["macros_periworkout"],
        "macros_source": "auto",
        "macros_multiplicadores": targets["multiplicadores"],
    }

    result = await db.client_profiles.update_one(
        {"user_id": user["id"]},
        {"$set": update_data},
        upsert=True
    )

    return {
        "applied": True,
        "targets": targets,
        "profile_macros": profile_macros,
    }


@router.get("/test-targets")
async def test_targets():
    """Ejecuta los tests del motor de targets."""
    return target_run_tests()
