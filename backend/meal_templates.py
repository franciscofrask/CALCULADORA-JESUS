"""
Meal Templates - Menús preestablecidos de "Sugiéreme un menú".
Método Jesús Gallego - 12en12.

Los menús viven en db.menu_templates y se gestionan desde el panel de admin
(sección Menús). Ya NO hay plantillas hardcodeadas: aquí solo queda la lógica de
generación y autoajuste. Cada menú define sus alimentos por rol (proteína/hidrato/
grasa) y las cantidades se autoajustan a los macros del usuario.
"""

from typing import Dict, List, Optional
from calma_engine import calcular_macros_efectivos, _redondear_cantidad, parse_categories



# =========================================================
# FUNCIÓN: Generar 3 opciones A/B/C para una comida
# =========================================================

def _item_avoided_precheck(item: dict, avoided_prefixes: set, avoided_keywords: list) -> bool:
    """Pre-chequeo barato sobre el item del template (sin tocar BD)."""
    buscar = (item.get("buscar", "") or "").lower()
    for kw in (avoided_keywords or []):
        if kw in buscar:
            return True
    cat = str(item.get("categoria", ""))
    for p in (avoided_prefixes or set()):
        if cat == p or cat.startswith(p + "."):
            return True
    return False


async def load_menu_templates(db) -> list:
    """Carga las plantillas de menú desde db.menu_templates (fuente ÚNICA). Ya no hay
    plantillas hardcodeadas: los menús se gestionan desde el panel de admin (sección Menús)."""
    try:
        return await db.menu_templates.find({}, {"_id": 0}).to_list(2000)
    except Exception as e:
        print(f"[menu_templates] error leyendo de DB: {e}")
        return []


async def generar_opciones_menu(
    db,
    momento: str,
    macros_objetivo: Dict[str, float],
    es_vegano: bool = False,
    excluir_proteinas: list = None,
    avoided_prefixes: set = None,
    avoided_keywords: list = None,
) -> List[Dict]:
    """
    Genera hasta 3 opciones de menú (A, B, C) autoajustadas para un momento.

    REGLAS:
    1. Las 3 opciones usan PROTEÍNAS DIFERENTES
    2. Las cantidades se autoajustan (mínimo + escalar) a los macros exactos
    3. Solo se devuelven menús CUADRADOS donde TODOS los alimentos entran
    4. Se descartan menús con alimentos evitados por el usuario
    """
    avoided_prefixes = avoided_prefixes or set()
    avoided_keywords = avoided_keywords or []

    p_obj = float(macros_objetivo.get("P", macros_objetivo.get("proteina", 0)) or 0)
    h_obj = float(macros_objetivo.get("H", macros_objetivo.get("hidratos", 0)) or 0)
    g_obj = float(macros_objetivo.get("G", macros_objetivo.get("grasa", 0)) or 0)
    kcal_obj = p_obj * 4 + h_obj * 4 + g_obj * 9

    excluir = set(excluir_proteinas or [])

    # Plantillas desde la base (editables por admin/coaches); siembra la 1ª vez.
    plantillas = await load_menu_templates(db)

    # Filtrar plantillas por momento y rango de kcal
    candidatas = [
        p for p in plantillas
        if p.get("momento") == momento
        and p.get("min_kcal", 0) <= kcal_obj <= p.get("max_kcal", 999999)
    ]

    if not candidatas:
        # Si no hay en rango, usar todas del momento
        candidatas = [p for p in plantillas if p.get("momento") == momento]

    # Descartar plantillas con algún item evitado (pre-chequeo barato)
    if avoided_prefixes or avoided_keywords:
        candidatas = [
            p for p in candidatas
            if not any(_item_avoided_precheck(it, avoided_prefixes, avoided_keywords) for it in p["items"])
        ]

    # Priorizar: si alto calórico, preferir plantillas con tag alto_calorico
    if kcal_obj > 600:
        candidatas.sort(key=lambda p: ("alto_calorico" in p.get("tags", [])), reverse=True)

    # Ajustar TODAS las candidatas y quedarnos con las que entran (cuadradas o aproximadas).
    ajustadas = []
    for plantilla in candidatas:
        # Proteína principal (2 niveles: 2.2 aves / 2.3 vacuno / 3.1 pescado / 10.1 legumbre…)
        # para exigir variedad entre las 3 opciones.
        prot_principal = None
        for item in plantilla["items"]:
            if item["rol"] == "proteina":
                prot_principal = ".".join(item["categoria"].split(".")[:2])
                break

        if prot_principal in excluir:
            continue

        opcion = await _ajustar_plantilla(
            db, plantilla, macros_objetivo, es_vegano,
            avoided_prefixes, avoided_keywords,
        )
        if opcion:
            mt = opcion.get("macros_totales", {})
            err = (abs(float(mt.get("P", 0)) - p_obj)
                   + abs(float(mt.get("H", 0)) - h_obj)
                   + abs(float(mt.get("G", 0)) - g_obj))
            ajustadas.append((opcion, prot_principal, err))

    # Priorizar: primero las CUADRADAS exactas, luego las más cercanas al objetivo.
    ajustadas.sort(key=lambda x: (not x[0].get("cuadrada", False), x[2]))

    # Elegir hasta 3 con proteínas diferentes.
    opciones = []
    proteinas_usadas = set()
    for opcion, prot_principal, _ in ajustadas:
        if len(opciones) >= 3:
            break
        if prot_principal in proteinas_usadas:
            continue
        opciones.append(opcion)
        proteinas_usadas.add(prot_principal)

    # Etiquetar A, B, C
    letras = ["A", "B", "C"]
    for i, opcion in enumerate(opciones):
        opcion["letra"] = letras[i] if i < 3 else f"D{i-2}"

    return opciones[:3]


def _food_avoided(alimento: dict, avoided_prefixes: set, avoided_keywords: list) -> bool:
    """True si el alimento debe evitarse por keyword (en el nombre) o por categoría."""
    nombre = (alimento.get("nombre", "") or "").lower()
    for kw in (avoided_keywords or []):
        if kw in nombre:
            return True
    if not avoided_prefixes:
        return False
    for c in parse_categories(alimento.get("categorias", [])):
        for p in avoided_prefixes:
            if c == p or c.startswith(p + "."):
                return True
    return False


MARGEN_MENU = 4.0  # ±4 g por macro para considerar el menú "cuadrado" (badge "Cuadrada")
# Margen más laxo, SOLO para los menús preestablecidos (no toca la calculadora ni CALMA):
# se aceptan menús que se acercan aunque no cuadren perfecto, para no dejar al usuario sin
# opciones. Los que no cuadran a ±MARGEN_MENU se devuelven marcados como aproximados.
MARGEN_MENU_RELAX = 12.0


def _driver_macro(rol: str) -> Optional[str]:
    """Macro que ESE alimento escala según su rol en el menú."""
    return {"proteina": "P", "hidrato": "H", "grasa": "G"}.get(rol)


def _menu_max(rol: str, cat: str, maximo_base: float) -> float:
    """Tope superior generoso para el autoajuste de menús (el alimento de ajuste
    debe poder crecer; los topes del chatbot son demasiado estrictos aquí)."""
    if cat.startswith("17.1") or cat.startswith("42"):   # aceites / grasas buenas
        return 30.0
    if cat.startswith("17"):                             # frutos secos, aguacate, cremas
        return 60.0
    return max(maximo_base, 60.0)


async def _ajustar_plantilla(
    db,
    plantilla: dict,
    macros_objetivo: Dict[str, float],
    es_vegano: bool = False,
    avoided_prefixes: set = None,
    avoided_keywords: list = None,
) -> Optional[Dict]:
    """
    Autoajuste de una plantilla a los macros de la comida.

    Criterio: TODOS los alimentos del menú tienen que entrar. Se parte de la
    cantidad MÍNIMA de cada alimento y se escalan las cantidades hasta cuadrar
    P/H/G (±MARGEN). Si algún alimento no se puede sourcear, está evitado, o el
    menú no cuadra (a mínimos ya se pasa, o no se llega) -> se descarta (None).
    """
    from meal_builder import get_effective_macros_per_100g, get_food_limits
    from calculator import get_food_config

    avoided_prefixes = avoided_prefixes or set()
    avoided_keywords = avoided_keywords or []

    obj = {
        "P": float(macros_objetivo.get("P", macros_objetivo.get("proteina", 0)) or 0),
        "H": float(macros_objetivo.get("H", macros_objetivo.get("hidratos", 0)) or 0),
        "G": float(macros_objetivo.get("G", macros_objetivo.get("grasa", 0)) or 0),
    }

    # Paso 1: resolver TODOS los alimentos (gate: todos deben existir).
    # Si el item trae alimento_id (elegido con el buscador), se usa ese alimento exacto;
    # si no (los 60 originales), se busca uno genérico por nombre + categoría.
    foods = []
    for item in plantilla["items"]:
        alimento = None
        if item.get("alimento_id") not in (None, ""):
            alimento = await db.foods.find_one({"id": int(item["alimento_id"])}, {"_id": 0})
        if not alimento:
            alimento = await _buscar_alimento_generico(db, item["buscar"], item["categoria"])
        if not alimento:
            return None
        if _food_avoided(alimento, avoided_prefixes, avoided_keywords):
            return None
        cfg = get_food_config(alimento)
        ef = get_effective_macros_per_100g(alimento)  # {P,H,G,cat,...} efectivos por 100g
        minimo = float(cfg.get("minimo", 5) or 5)
        _, maximo_base = get_food_limits(alimento, cfg)
        maximo = _menu_max(item["rol"], ef.get("cat", ""), maximo_base)
        foods.append({
            "item": item, "alimento": alimento, "ef": ef, "cat": ef.get("cat", ""),
            "minimo": minimo, "maximo": max(minimo, maximo),
            "driver": _driver_macro(item["rol"]), "cantidad": minimo,
        })

    def totales():
        T = {"P": 0.0, "H": 0.0, "G": 0.0}
        for f in foods:
            fac = f["cantidad"] / 100.0
            T["P"] += f["ef"]["P"] * fac
            T["H"] += f["ef"]["H"] * fac
            T["G"] += f["ef"]["G"] * fac
        return T

    # Paso 2: gate de overshoot a mínimos (solo se puede escalar hacia arriba). Usa el margen
    # laxo para no descartar menús que a mínimos se pasan un poco.
    T = totales()
    for m in ("P", "H", "G"):
        if T[m] > obj[m] + MARGEN_MENU_RELAX:
            return None

    # Paso 3: escalar cada macro con sus alimentos motor (grasa al final: absorbe
    # la grasa incidental de proteínas)
    for m in ("H", "P", "G"):
        drivers = [f for f in foods if f["driver"] == m and f["ef"][m] > 1e-6]
        if not drivers:
            continue
        T = totales()
        needed = obj[m] - T[m]
        if needed <= 0:
            continue
        per = needed / len(drivers)
        for f in drivers:
            extra_g = per / (f["ef"][m] / 100.0)
            nueva = min(f["maximo"], f["cantidad"] + extra_g)
            nueva = _redondear_cantidad(nueva, f["cat"])
            if nueva < f["minimo"]:
                nueva = f["minimo"]
            f["cantidad"] = nueva

    # Paso 4: validar. Se ACEPTA si está dentro del margen laxo; se marca "cuadrada" solo si
    # está dentro del margen estricto (±MARGEN_MENU). Así salen más opciones y el usuario ve
    # cuáles son exactas y cuáles aproximadas (para afinar a mano).
    T = totales()
    if any(abs(T[m] - obj[m]) > MARGEN_MENU_RELAX for m in ("P", "H", "G")):
        return None
    es_cuadrada = all(abs(T[m] - obj[m]) <= MARGEN_MENU for m in ("P", "H", "G"))

    # Paso 5: construir items en la forma que consume el front
    items_resultado = []
    for f in foods:
        fac = f["cantidad"] / 100.0
        items_resultado.append({
            "alimento_id": f["alimento"].get("id"),
            "nombre": f["alimento"].get("nombre", f["item"]["buscar"]),
            "cantidad_g": f["cantidad"],
            "macros_efectivos": {
                "P": round(f["ef"]["P"] * fac, 1),
                "H": round(f["ef"]["H"] * fac, 1),
                "G": round(f["ef"]["G"] * fac, 1),
            },
            "rol": f["item"]["rol"],
        })

    return {
        "plantilla_id": plantilla["id"],
        "nombre": plantilla["nombre"],
        "items": items_resultado,
        "macros_totales": {
            "P": round(T["P"], 1),
            "H": round(T["H"], 1),
            "G": round(T["G"], 1),
            "kcal": round(T["P"] * 4 + T["H"] * 4 + T["G"] * 9, 1),
        },
        "macros_objetivo": obj,
        "cuadrada": es_cuadrada,
        "tags": plantilla.get("tags", []),
    }


async def _buscar_alimento_generico(db, nombre: str, categoria: str) -> Optional[dict]:
    """
    Busca un alimento genérico en MongoDB por nombre y categoría.
    Prioriza: 1) coincidencia exacta de categoría + nombre
              2) categoría padre + nombre
              3) solo nombre
    Prefiere alimentos con tag GEN (genérico).
    """
    import re
    
    # Intentar búsqueda por categoría exacta + nombre
    filtro = {
        "nombre": {"$regex": re.escape(nombre), "$options": "i"},
        "$or": [
            {"categorias": {"$regex": f"(^|\\|)\\s*{re.escape(categoria)}", "$options": "i"}},
            {"categorias": categoria}
        ]
    }
    
    resultados = await db.foods.find(filtro, {"_id": 0}).limit(20).to_list(20)
    
    if not resultados:
        # Solo por nombre
        filtro = {"nombre": {"$regex": re.escape(nombre), "$options": "i"}}
        resultados = await db.foods.find(filtro, {"_id": 0}).limit(20).to_list(20)
    
    if not resultados:
        return None
    
    # Priorizar genéricos (tag GEN)
    for r in resultados:
        tags = r.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]
        if "GEN" in tags:
            return r
    
    # Si no hay genérico, devolver el primero
    return resultados[0]


