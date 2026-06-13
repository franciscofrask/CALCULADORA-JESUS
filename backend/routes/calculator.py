"""
Rutas del calculador de macros y búsqueda de alimentos.
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone, date
import math
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
    run_tests as calma_run_tests,
    parse_categories,
)
from calculator import buscar_alimentos as buscar_alimentos_async, sugerir_alimentos, get_food_config, calcular_cantidad_automatica, get_categoria_principal
from calma_suggest import (
    ajustar_cantidad as ajustar_cantidad_calma,
    macros_at as macros_at_calma,
    diferencia_de_macros as diferencia_de_macros_calma,
    aplicar_regla_macros as aplicar_regla_macros_calma,
    food_in_cat as food_in_cat_calma,
)
from target_calculator import calcular_targets, targets_to_profile_macros, run_tests as target_run_tests
from macro_distribution import distribuir_macros as dist_macros

router = APIRouter(prefix="/calculator", tags=["calculator"])

# ── Preparation filter helpers (mirrors Calma group-home-utils.js) ──────────
#
# Calma's $ function: new RegExp(`^((${code})[.]\d|(${code})$)`).test(token)
# → matches token if it EQUALS code exactly OR starts with "code.digit"
# → effectively a prefix match: "4" matches "4", "4.1", "4.1.1", "4.2", etc.

def _has_any_exact_cat(alimento, cat_codes: set) -> bool:
    """Mirror Calma's o(e, list) + $ function: prefix-aware category matching.
    'code' matches a token if token == code OR token starts with code+'.'
    """
    cats = str(alimento.get("categorias", "") or "")
    for t in cats.split("|"):
        t = t.strip()
        for code in cat_codes:
            if t == code or t.startswith(code + "."):
                return True
    return False

def _has_token(alimento, tag: str) -> bool:
    tag_up = tag.upper()
    cats = str(alimento.get("categorias", "") or "")
    raw_tags = alimento.get("tags", "") or ""
    if isinstance(raw_tags, list):
        tag_tokens = {str(t).strip().upper() for t in raw_tags}
    else:
        tag_tokens = {t.strip().upper() for t in str(raw_tags).split("|")}
    cat_tokens = {t.strip().upper() for t in cats.split("|")}
    return tag_up in cat_tokens or tag_up in tag_tokens

_LAT_CATS = {"2.2.8", "2.3.8", "2.4.8", "3.8", "3.9.8", "10.1.8", "11.8", "13.8"}
_FRE_CATS = {"FRE", "1.2.1", "2.2.1", "2.3.1", "2.4.1", "3.1", "3.9.1", "11.1", "13.1"}
_CGE_CATS = {"CGE", "2.2.4", "2.3.4", "2.4.4", "3.4", "3.9.4", "10.1.4", "11.4", "13.4"}
_PRE_CATS = {"PRE", "2.2.2", "2.3.2", "2.4.2", "3.2", "3.9.2", "11.5", "17.9.2"}
_YCO_CATS = {"YCO", "2.1", "2.2.3", "2.3.3", "2.4.3", "3.3", "3.9.3", "13.2", "17.9.3", "39"}

def _prep_lat(a):
    n = (a.get("nombre") or "").lower()
    return " lata" in n or "conserva" in n or _has_any_exact_cat(a, _LAT_CATS)

def _prep_fre(a):
    return _has_any_exact_cat(a, _FRE_CATS)

def _prep_cge(a):
    n = (a.get("nombre") or "").lower()
    return _has_any_exact_cat(a, _CGE_CATS) or "congelad" in n or "helad" in n

def _prep_pre(a):
    return _has_any_exact_cat(a, _PRE_CATS)

def _prep_yco(a):
    return _has_any_exact_cat(a, _YCO_CATS)

def _prep_ahu(a):
    n = (a.get("nombre") or "").lower()
    return _has_any_exact_cat(a, {"AHU", "3.7"}) or "ahumad" in n

def _prep_ya(a):
    # Original: o(e, ["YA", "2.1", "4", "11.5"]) || j.test(e)
    # "4" prefix matches all protein powders (4, 4.1, 4.1.1, etc.) → YA
    return _has_any_exact_cat(a, {"YA", "2.1", "4", "11.5"}) or _prep_ahu(a)

_PREP_TESTS = {
    "LAT": _prep_lat,
    "FRE": _prep_fre,
    "CGE": _prep_cge,
    "PRE": _prep_pre,
    "YCO": _prep_yco,
    "AHU": _prep_ahu,
    "YA":  _prep_ya,
    "HAM": lambda a: _has_token(a, "HAM"),
    "SNA": lambda a: _has_token(a, "SNA"),
    "SGL": lambda a: _has_token(a, "SGL"),
    "GEN": lambda a: not a.get("url"),
    "PRO": lambda a: _has_token(a, "PRO"),
    # Original: P(nombre,["polvo","harina"]) || o(e,["POL","4","7.1.2.6","16.5","18.3","27"]) || P(nombre,["crema","arroz"],AND)
    "POL": lambda a: (
        _has_any_exact_cat(a, {"POL", "4", "7.1.2.6", "16.5", "18.3", "27"}) or
        any(w in (a.get("nombre") or "").lower() for w in ("polvo", "harina")) or
        (("crema" in (a.get("nombre") or "").lower()) and ("arroz" in (a.get("nombre") or "").lower()))
    ),
    "MIN": lambda a: _has_token(a, "MIN"),
    "UNI": lambda a: bool(a.get("unidades") or a.get("por_unidad")),
}

_PREPS_ORDER = ["GEN", "PRO", "FRE", "CGE", "AHU", "LAT", "POL", "PRE", "HAM", "SNA", "MIN", "YCO", "UNI", "YA", "SGL"]

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
    p_rest: Optional[float] = None,
    h_rest: Optional[float] = None,
    g_rest: Optional[float] = None,
    frequent: bool = False,
    cuadrar: bool = False,
    peri: Optional[str] = None,
    user = Depends(get_current_user)
):
    """Búsqueda de alimentos con macros efectivos (CALMA).
    Si se pasan p_rest/h_rest/g_rest, ordena por aporte y calcula cantidad sugerida.
    Filtra alimentos que el usuario marcó como 'a evitar'.
    `frequent=true` -> el set de alimentos = top-20 frecuentes del usuario (como el
    filtro TOP de Calma); luego pasa por el mismo motor (cantidad + regla + diferencia).
    """
    if frequent:
        # Calma's "Alimentos frecuentes": top-20 by raw appearance count across all the
        # user's saved diets. They go through the SAME suggestion engine below.
        freq = await _get_food_frequency(user["id"])
        top_ids_str = sorted(freq, key=lambda k: freq[k], reverse=True)[:20]
        top_int = [int(f) for f in top_ids_str if str(f).lstrip("-").isdigit()]
        alimentos = await db.foods.find({"id": {"$in": top_int}}, {"_id": 0}).to_list(20) if top_int else []
        base_order = {fid: i for i, fid in enumerate(top_int)}
        alimentos.sort(key=lambda a: base_order.get(a.get("id"), 9999))
    else:
        # When browsing by category (no text query), fetch all — no artificial limit.
        fetch_limit = 4000 if (category and not q) else limit
        alimentos = await buscar_alimentos_async(
            db=db,
            query=q,
            categoria=category or "",
            tipo_comida=tipo_comida,
            es_vegano=vegano,
            limit=fetch_limit,
            calcular_efectivos=True,
            tag_filter=""  # tag filtering done below, after computing available_preps
        )

    # NOTE: Calma's "TOP/alimentos frecuentes" special filter (manejarAlimentos) is OFF by
    # default (filtrosActivacionPorDefecto = false). Frequent foods only appear when the user
    # explicitly opens the dedicated "Alimentos frecuentes" view, NOT injected into every
    # category browse. Injecting them here showed unrelated foods (Lomo, Arroz con pollo,
    # Crema de cacahuete) inside the Huevos category. Removed to match Calma.

    # Load user avoided preferences for filtering
    profile = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    avoided_categories = []
    avoided_keywords = []
    if profile:
        avoided_categories = profile.get("avoided_categories", [])
        avoided_keywords = [kw.lower() for kw in profile.get("avoided_keywords", [])]

    # Map avoided_category IDs to category prefixes (mirrors frontend PREFERENCE_CATEGORIES)
    AVOIDABLE_PREFIXES = {
        'grasas_buenas': ['42'], 'grasas_todo': ['17'], 'aperitivos': ['38'],
        'arroces': ['21'], 'aves': ['2.2'], 'barritas': ['47'],
        'bebidas': ['19'], 'isotonicas': ['18.1'], 'beb_vegetales': ['24'],
        'bolleria': ['31'], 'cacao': ['37'], 'casqueria': ['40'],
        'cerdo': ['2.4'], 'cereales': ['7'], 'chocolates': ['34'],
        'cocina_esp': ['39'], 'comida_rapida': ['49'], 'embutidos': ['2.1'],
        'fruta': ['11'], 'helados': ['44'], 'huevos': ['1'],
        'lacteos': ['5'], 'legumbres': ['10'], 'carnes_blancas': ['2.6'],
        'carnes_rojas': ['2.7'], 'panes': ['8'], 'pasta': ['22'],
        'pescados': ['3'], 'pizza': ['32'], 'proteina_polvo': ['4', '29', '30'],
        'proteina_vegetal': ['28'], 'salsas': ['16'], 'sopas': ['48'],
        'superalimentos': ['51'], 'tuberculos': ['9'], 'vacuno': ['2.3'],
        'verduras': ['13'],
    }
    avoided_prefixes = set()
    for cat_id in avoided_categories:
        for prefix in AVOIDABLE_PREFIXES.get(cat_id, []):
            avoided_prefixes.add(prefix)

    def is_avoided(alimento):
        nombre = alimento.get("nombre", "").lower()
        # Filter by keyword
        for kw in avoided_keywords:
            if kw in nombre:
                return True
        if not avoided_prefixes:
            return False
        # Parse numeric category parts and check against avoided prefixes
        food_cats = parse_categories(alimento.get("categorias", []))
        for food_cat in food_cats:
            for prefix in avoided_prefixes:
                if food_cat == prefix or food_cat.startswith(prefix + "."):
                    return True
        return False

    alimentos = [a for a in alimentos if not is_avoided(a)]

    # Collect available preparations using Calma-equivalent test functions (before filtering).
    available_preps = [p for p in _PREPS_ORDER if any(_PREP_TESTS[p](a) for a in alimentos)]

    # Apply preparation filter — supports comma-separated multiple tags (OR logic).
    if tag:
        tag_list = [t.strip().upper() for t in tag.split(',') if t.strip()]
        def matches_tag(alimento, tag_upper):
            test_fn = _PREP_TESTS.get(tag_upper)
            if test_fn:
                return test_fn(alimento)
            return _has_token(alimento, tag_upper)
        alimentos = [a for a in alimentos if any(matches_tag(a, t) for t in tag_list)]

    # When browsing by category, show all matching foods. Text searches keep the limit.
    if q:
        alimentos = alimentos[:limit]

    # Inject per-unit config so frontend can display "2 ud" vs "120g" correctly
    for a in alimentos:
        cfg = get_food_config(a)
        a["por_unidad"] = cfg.get("por_unidad", False)
        a["peso_unidad"] = cfg.get("peso_unidad", 0)

    has_macros_context = p_rest is not None or h_rest is not None or g_rest is not None
    # Calma's remaining uses raw-gram macros keyed proteinas/hidratos/grasas.
    # Unspecified macro -> inf (unconstrained); negatives clamped inside the engine.
    remaining = {
        "proteinas": float(p_rest) if p_rest is not None else float('inf'),
        "hidratos": float(h_rest) if h_rest is not None else float('inf'),
        "grasas": float(g_rest) if g_rest is not None else float('inf'),
    }

    if has_macros_context:
        # ── Calma manual-builder engine (calma_suggest) ──────────────────────
        # Suggested quantity = ajustarCantidadIngrediente (raw me, all 3 macros).
        # Ordering = diferenciaDeMacros ascending. NO "macros efectivos" here.
        procesados = []
        for a in alimentos:
            # Calma applies the macro-counting rule (ye) at food load: non-counting
            # macros are zeroed so they neither fill their target nor display. This
            # drives the ordering of mixed-macro prepared foods.
            aplicar_regla_macros_calma(a)
            cant = ajustar_cantidad_calma(a, remaining)  # units (unidades) or grams
            if cant <= 0 or math.isinf(cant):
                # 0 -> minimum portion already overshoots; exclude (matches Calma a>cant).
                # inf only for zero-macro foods, already resolved inside the engine.
                if cant <= 0:
                    continue
            contrib = macros_at_calma(a, cant)  # {proteinas,hidratos,grasas}
            es_unidad = bool(a.get("unidades"))
            racion = float(a.get("racion") or 100)
            # Frontend expects grams in _cantidad_sugerida + peso_unidad = g/unit.
            a["por_unidad"] = es_unidad
            a["peso_unidad"] = racion
            a["_cantidad_sugerida"] = (cant * racion) if es_unidad else cant
            a["_macros_sugeridos"] = {
                "P": round(contrib["proteinas"], 1),
                "H": round(contrib["hidratos"], 1),
                "G": round(contrib["grasas"], 1),
            }
            a["_diferencia"] = diferencia_de_macros_calma(contrib, remaining)
            a["_aporte_total"] = contrib["proteinas"] + contrib["hidratos"] + contrib["grasas"]
            procesados.append(a)
        alimentos = procesados

        # Get favorites to keep them first (our product feature, layered on top).
        fav_doc = await db.food_favorites.find_one({"user_id": user["id"]}, {"_id": 0})
        fav_ids = set(str(fid) for fid in (fav_doc.get("food_ids", []) if fav_doc else []))
        for a in alimentos:
            a["is_favorite"] = str(a.get("id", "")) in fav_ids

        # Calma ordenarIngredientesPorMacro: diferenciaDeMacros ascending, then name.
        # PLUS a marca-recomendada (PROMOCIONADO / "PRO") float: promoted brands
        # (FullGas, Fitness Burger, My Fitness Meals — tagged "PRO" in categorias)
        # surface to the TOP of their diferencia tier. Calma's UI shows e.g. FullGas
        # above Tarrina even though FullGas has a slightly worse diferencia. The float
        # is bucket-bounded (tier width = _PRO_TIER), so it ONLY moves promoted foods
        # within their own tier — non-PRO relative order is identical to pure
        # diferencia (the bucket key is monotonic in diferencia). Verified 15/15 vs
        # Calma's huevos reference (training day, C1).
        def _is_pro(f):
            return "PRO" in {t.strip().upper() for t in str(f.get("categorias", "") or "").split("|")}
        _PRO_TIER = 10.0
        def _diff(f):
            d = f.get("_diferencia")
            return d if d is not None else float('inf')
        def _bucket(f):
            d = _diff(f)
            return d if math.isinf(d) else round(d / _PRO_TIER) * _PRO_TIER
        # Calma cuadrarMacros phase (paso 3): after the diferencia order, a stable sort by
        # prioridad[fase] floats certain categories to the top after the diferencia order
        # (Calma's second sort in ordenarIngredientesPorMacro). de() = min matched index in
        # the fase's prioritarias list, PRO brands -0.5. Phases:
        #   cuadrarMacros (paso 3 normal meal): good fats 17.1.1 -> 17.1 -> 42
        #   intraentreno / postentreno (peri meals): their own prioritarias lists.
        _PRIOR_LISTS = {
            "cuadrar": ("17.1.1", "17.1", "42"),
            "intra": ("41", "18.1.1", "18.1.3", "18.1.2"),
            "post": ("4.1.1", "4.1.2", "4.1", "4.2", "5.4", "5.2.3", "5.2.2", "5.1", "4.3",
                     "27", "21.3", "7.1.1", "7.1.2.1", "18.3", "11.5", "11.2.1", "11.2.2",
                     "11.1", "11.4", "11.6", "11.7", "21.2", "7.3.1", "8", "24", "19.1",
                     "18.1", "18.2", "37", "16.5", "16.1"),
        }
        _prior_list = _PRIOR_LISTS.get(peri) if peri in ("intra", "post") else (_PRIOR_LISTS["cuadrar"] if cuadrar else None)
        def _prioridad(f):
            if not _prior_list:
                return 0
            for idx, code in enumerate(_prior_list):
                if food_in_cat_calma(f, code):
                    return (idx - 0.5) if _is_pro(f) else idx
            return float('inf')
        alimentos.sort(key=lambda f: (
            0 if f.get("is_favorite") else 1,
            _prioridad(f),
            _bucket(f),
            0 if _is_pro(f) else 1,
            _diff(f),
            f.get("nombre", "")
        ))
    else:
        # Default sort: favorites > frequency > alphabetical
        fav_doc = await db.food_favorites.find_one({"user_id": user["id"]}, {"_id": 0})
        fav_ids = set(str(fid) for fid in (fav_doc.get("food_ids", []) if fav_doc else []))
        food_freq = await _get_food_frequency(user["id"])

        for a in alimentos:
            a["is_favorite"] = str(a.get("id", "")) in fav_ids

        alimentos.sort(key=lambda f: (
            0 if f.get("is_favorite") else 1,
            -food_freq.get(str(f.get("id", "")), 0),
            f.get("nombre", "")
        ))

    return {"alimentos": alimentos, "total": len(alimentos), "available_preps": available_preps}


async def _get_food_frequency(user_id: str) -> dict:
    """Raw appearance count of each food across ALL the user's saved diets, mirroring
    Calma's `alimentosFrecuentes` = Ge(Pe(dietas).ingredientes): repeticiones++ per
    occurrence, no time decay. Returns {food_id_str: count}.
    """
    diets = await db.diets.find(
        {"user_id": user_id},
        {"_id": 0, "comidas": 1}
    ).to_list(2000)

    if not diets:
        return {}

    counts = {}
    for diet in diets:
        for meal_data in (diet.get("comidas") or {}).values():
            for alimento in (meal_data.get("alimentos") or []):
                fid = str(alimento.get("id", alimento.get("alimento_id", "")))
                if fid:
                    counts[fid] = counts.get(fid, 0) + 1
    return counts

@router.get("/frequent-foods")
async def get_frequent_foods(
    limit: int = 20,
    user = Depends(get_current_user)
):
    """Top alimentos más usados por el usuario en su historial de dietas."""
    freq = await _get_food_frequency(user["id"])
    if not freq:
        return {"alimentos": []}

    # Top IDs sorted by frequency
    top_ids_str = sorted(freq, key=lambda k: freq[k], reverse=True)[:limit]

    # Convert to int where possible (food IDs are numeric in this DB)
    top_ids = []
    for fid in top_ids_str:
        try:
            top_ids.append(int(fid))
        except (ValueError, TypeError):
            top_ids.append(fid)

    foods_cursor = db.foods.find({"id": {"$in": top_ids}}, {"_id": 0})
    foods_map = {}
    async for f in foods_cursor:
        foods_map[str(f["id"])] = f

    # Load user avoided preferences
    profile = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    avoided_categories = profile.get("avoided_categories", []) if profile else []
    avoided_keywords = [kw.lower() for kw in (profile.get("avoided_keywords", []) if profile else [])]
    AVOIDABLE_PREFIXES = {
        'grasas_buenas': ['42'], 'grasas_todo': ['17'], 'aperitivos': ['38'],
        'arroces': ['21'], 'aves': ['2.2'], 'barritas': ['47'],
        'bebidas': ['19'], 'isotonicas': ['18.1'], 'beb_vegetales': ['24'],
        'bolleria': ['31'], 'cacao': ['37'], 'casqueria': ['40'],
        'cerdo': ['2.4'], 'cereales': ['7'], 'chocolates': ['34'],
        'cocina_esp': ['39'], 'comida_rapida': ['49'], 'embutidos': ['2.1'],
        'fruta': ['11'], 'helados': ['44'], 'huevos': ['1'],
        'lacteos': ['5'], 'legumbres': ['10'], 'carnes_blancas': ['2.6'],
        'carnes_rojas': ['2.7'], 'panes': ['8'], 'pasta': ['22'],
        'pescados': ['3'], 'pizza': ['32'], 'proteina_polvo': ['4', '29', '30'],
        'proteina_vegetal': ['28'], 'salsas': ['16'], 'sopas': ['48'],
        'superalimentos': ['51'], 'tuberculos': ['9'], 'vacuno': ['2.3'],
        'verduras': ['13'],
    }
    avoided_prefixes = set()
    for cat_id in avoided_categories:
        for prefix in AVOIDABLE_PREFIXES.get(cat_id, []):
            avoided_prefixes.add(prefix)

    def is_avoided(alimento):
        nombre = alimento.get("nombre", "").lower()
        for kw in avoided_keywords:
            if kw in nombre:
                return True
        if not avoided_prefixes:
            return False
        food_cats = parse_categories(alimento.get("categorias", []))
        for food_cat in food_cats:
            for prefix in avoided_prefixes:
                if food_cat == prefix or food_cat.startswith(prefix + "."):
                    return True
        return False

    enriched = []
    for fid_str in top_ids_str:
        food = foods_map.get(fid_str)
        if not food or is_avoided(food):
            continue
        cfg = get_food_config(food)
        enriched.append({
            **food,
            "por_unidad": cfg.get("por_unidad", False),
            "peso_unidad": cfg.get("peso_unidad", 0),
            "usos": freq[fid_str],
        })

    return {"alimentos": enriched}


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
