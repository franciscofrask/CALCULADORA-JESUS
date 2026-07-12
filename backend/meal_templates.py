"""
Meal Templates - Menús preestablecidos de "Sugiéreme un menú".
Método Jesús Gallego - 12en12.

Los menús viven en db.menu_templates y se gestionan desde el panel de admin
(sección Menús). Ya NO hay plantillas hardcodeadas: aquí solo queda la lógica de
generación y autoajuste. Cada menú define sus alimentos por rol (proteína/hidrato/
grasa) y las cantidades se autoajustan a los macros del usuario.
"""

import math

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
    required_food_ids: list = None,
    max_opciones: int = 3,
    variar_proteinas: bool = True,
    incluir_lejanas: bool = False,
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

    # Filtrar plantillas por momento (momento=None/'' = todos) y rango de kcal
    base = [p for p in plantillas if not momento or p.get("momento") == momento]
    candidatas = [
        p for p in base
        if p.get("min_kcal", 0) <= kcal_obj <= p.get("max_kcal", 999999)
    ]

    if not candidatas:
        # Si no hay en rango, usar todas del momento
        candidatas = base

    # Filtro "con estos alimentos" (buscador coach): la plantilla debe contener
    # todos los alimento_id pedidos entre sus items.
    if required_food_ids:
        req = {int(x) for x in required_food_ids}
        candidatas = [
            p for p in candidatas
            if req <= {int(it["alimento_id"]) for it in p.get("items", []) if it.get("alimento_id") not in (None, "")}
        ]

    # Descartar plantillas con algún item evitado (pre-chequeo barato)
    if avoided_prefixes or avoided_keywords:
        candidatas = [
            p for p in candidatas
            if not any(_item_avoided_precheck(it, avoided_prefixes, avoided_keywords) for it in p["items"])
        ]

    # Priorizar: si alto calórico, preferir plantillas con tag alto_calorico
    if kcal_obj > 600:
        candidatas.sort(key=lambda p: ("alto_calorico" in p.get("tags", [])), reverse=True)

    # PRECARGA (rendimiento): todos los alimento_id de las candidatas en UNA consulta.
    # Sin esto, cada item de cada plantilla hacía su propio find_one contra Atlas
    # (cientos de consultas en serie -> ~15-20 s de espera en "Sugiéreme un menú").
    ids_precarga = set()
    for p in candidatas:
        for it in p["items"]:
            if it.get("alimento_id") not in (None, ""):
                try:
                    ids_precarga.add(int(it["alimento_id"]))
                except (TypeError, ValueError):
                    pass
    foods_by_id = {}
    if ids_precarga:
        async for f in db.foods.find({"id": {"$in": list(ids_precarga)}}, {"_id": 0}):
            foods_by_id[int(f["id"])] = f
    generic_cache = {}  # (buscar, categoria) -> alimento, para items sin alimento_id

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
            foods_by_id=foods_by_id, generic_cache=generic_cache,
            best_effort=incluir_lejanas,
        )
        if opcion:
            mt = opcion.get("macros_totales", {})
            err = (abs(float(mt.get("P", 0)) - p_obj)
                   + abs(float(mt.get("H", 0)) - h_obj)
                   + abs(float(mt.get("G", 0)) - g_obj))
            ajustadas.append((opcion, prot_principal, err))

    # Priorizar: primero las CUADRADAS exactas, luego las más cercanas al objetivo.
    ajustadas.sort(key=lambda x: (not x[0].get("cuadrada", False), x[2]))

    # Selección: por defecto hasta max_opciones con proteínas diferentes (variedad);
    # con variar_proteinas=False se devuelven todas las que encajan, en orden.
    opciones = []
    proteinas_usadas = set()
    for opcion, prot_principal, _ in ajustadas:
        if len(opciones) >= max_opciones:
            break
        if variar_proteinas and prot_principal in proteinas_usadas:
            continue
        opciones.append(opcion)
        proteinas_usadas.add(prot_principal)

    # Etiquetar A, B, C...
    abc = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for i, opcion in enumerate(opciones):
        opcion["letra"] = abc[i] if i < len(abc) else str(i + 1)

    return opciones[:max_opciones]


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


def afinar_cantidades(foods: list, obj: Dict[str, float], max_iter: int = 60) -> None:
    """Afinado fino GLOBAL de cantidades (muta `foods` in place).

    Dos problemas que el reparto proporcional clásico no resuelve:
      (a) el redondeo floor se come déficits pequeños (grasas 7.6/10);
      (b) los macros incidentales exigen INTERCAMBIOS (menos huevo + más boquerón
          para recortar grasa sin perder proteína).
    Optimizador voraz: prueba movimientos de ±1 paso de redondeo por alimento
    (los alimentos por unidades usan su peso real de unidad) y, si ninguno mejora
    solo, pares de movimientos (swaps), minimizando el error cuadrático total.

    `foods`: dicts con cantidad, minimo, maximo, ef {P,H,G}, cat y opcional paso_unidad.
    `obj`: {P,H,G}; los macros con objetivo None/inf se ignoran (p.ej. grasas en peri).
    """
    macros = [m for m in ("P", "H", "G")
              if obj.get(m) is not None and not math.isinf(float(obj[m]))]
    if not macros or not foods:
        return

    def _paso_redondeo(cat: str) -> float:
        # 55000 es múltiplo de todos los pasos usados (1, 5, 10, 25, 55)
        return max(1.0, 55000 - _redondear_cantidad(54999.99, cat))

    movimientos = []
    for f in foods:
        paso = f.get("paso_unidad") or _paso_redondeo(f.get("cat", ""))
        movimientos.append((f, paso))
        movimientos.append((f, -paso))

    def _totales():
        T = {m: 0.0 for m in macros}
        for f in foods:
            fac = f["cantidad"] / 100.0
            for m in macros:
                T[m] += (f["ef"].get(m, 0) or 0) * fac
        return T

    def _aplicable(f, delta):
        nueva = f["cantidad"] + delta
        return f["minimo"] <= nueva <= f["maximo"]

    def _err_sq(residuales):
        return sum(v * v for v in residuales.values())

    for _ in range(max_iter):
        T = _totales()
        res = {m: float(obj[m]) - T[m] for m in macros}
        if all(abs(v) <= 1.0 for v in res.values()):
            break
        e0 = _err_sq(res)
        mejor = None  # (err, [(food, delta), ...])
        for f, d in movimientos:
            if not _aplicable(f, d):
                continue
            e = _err_sq({m: res[m] - d * (f["ef"].get(m, 0) or 0) / 100.0 for m in macros})
            if e < e0 - 1e-9 and (mejor is None or e < mejor[0]):
                mejor = (e, [(f, d)])
        if mejor is None:
            for f1, d1 in movimientos:
                if not _aplicable(f1, d1):
                    continue
                for f2, d2 in movimientos:
                    if f2 is f1 or not _aplicable(f2, d2):
                        continue
                    e = _err_sq({m: res[m] - (d1 * (f1["ef"].get(m, 0) or 0) + d2 * (f2["ef"].get(m, 0) or 0)) / 100.0 for m in macros})
                    if e < e0 - 1e-9 and (mejor is None or e < mejor[0]):
                        mejor = (e, [(f1, d1), (f2, d2)])
        if mejor is None and len(foods) <= 12:
            # Tríos: necesarios cuando hay alimentos de paso grueso (latas, huevos)
            # que exigen compensar en dos frentes a la vez (+1 huevo -1 lata +fiambre).
            for f1, d1 in movimientos:
                if not _aplicable(f1, d1):
                    continue
                for f2, d2 in movimientos:
                    if f2 is f1 or not _aplicable(f2, d2):
                        continue
                    for f3, d3 in movimientos:
                        if f3 is f1 or f3 is f2 or not _aplicable(f3, d3):
                            continue
                        e = _err_sq({m: res[m] - (d1 * (f1["ef"].get(m, 0) or 0) + d2 * (f2["ef"].get(m, 0) or 0) + d3 * (f3["ef"].get(m, 0) or 0)) / 100.0 for m in macros})
                        if e < e0 - 1e-9 and (mejor is None or e < mejor[0]):
                            mejor = (e, [(f1, d1), (f2, d2), (f3, d3)])
        if mejor is None:
            break
        for f, d in mejor[1]:
            f["cantidad"] += d


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
    foods_by_id: dict = None,
    generic_cache: dict = None,
    best_effort: bool = False,
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
            aid = int(item["alimento_id"])
            if foods_by_id is not None:
                alimento = foods_by_id.get(aid)  # precargado en bloque (una sola consulta)
            else:
                alimento = await db.foods.find_one({"id": aid}, {"_id": 0})
        if not alimento:
            key = (item.get("buscar", ""), item.get("categoria", ""))
            if generic_cache is not None and key in generic_cache:
                alimento = generic_cache[key]
            else:
                alimento = await _buscar_alimento_generico(db, item["buscar"], item["categoria"])
                if generic_cache is not None:
                    generic_cache[key] = alimento
        if not alimento:
            return None
        if _food_avoided(alimento, avoided_prefixes, avoided_keywords):
            return None
        cfg = get_food_config(alimento)
        ef = get_effective_macros_per_100g(alimento)  # {P,H,G,cat,...} efectivos por 100g
        minimo = float(cfg.get("minimo", 5) or 5)
        _, maximo_base = get_food_limits(alimento, cfg)
        maximo = _menu_max(item["rol"], ef.get("cat", ""), maximo_base)
        # Alimentos por unidades (huevos, yogures...): se mueven en pasos de SU
        # peso real de unidad (huevo L = 63g), no del paso genérico de la categoría.
        peso_unidad = float(alimento.get("peso_unidad") or alimento.get("racion") or 0)
        es_unidad = bool(alimento.get("unidades") or alimento.get("por_unidad") or cfg.get("por_unidad"))
        foods.append({
            "item": item, "alimento": alimento, "ef": ef, "cat": ef.get("cat", ""),
            "minimo": minimo, "maximo": max(minimo, maximo),
            "driver": _driver_macro(item["rol"]), "cantidad": minimo,
            "paso_unidad": peso_unidad if (es_unidad and peso_unidad > 0) else None,
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
    if not best_effort:
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
            if f.get("paso_unidad"):
                # unidades enteras del alimento (huevo 63g, yogur 125g...)
                nueva = math.floor(nueva / f["paso_unidad"]) * f["paso_unidad"]
            else:
                nueva = _redondear_cantidad(nueva, f["cat"])
            if nueva < f["minimo"]:
                nueva = f["minimo"]
            f["cantidad"] = nueva

    # Paso 3.5: afinado fino GLOBAL (compartido con el botón "Cuadrar" del refit).
    afinar_cantidades(foods, obj)

    # Paso 4: validar. Se ACEPTA si está dentro del margen laxo; se marca "cuadrada" solo si
    # está dentro del margen estricto (±MARGEN_MENU). Así salen más opciones y el usuario ve
    # cuáles son exactas y cuáles aproximadas (para afinar a mano).
    T = totales()
    if not best_effort and any(abs(T[m] - obj[m]) > MARGEN_MENU_RELAX for m in ("P", "H", "G")):
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


