"""Biblioteca de menús reales (db.meal_library): búsqueda por alimentos + macros
con ajuste automático "limpio".

Reglas de ajuste (acordadas 2026-07-12):
  - Solo se toca un alimento "driver limpio" (mono-macro):
      * proteína: fuente sin grasa (pechuga, claras, aislado...)  -> ±20 g de P
      * hidratos: fuente limpia (arroz, patata, crema de arroz...) -> ±30 g de H,
        solo si el menú tiene >= 50 g de hidratos
      * grasa: grasa pura (aceites)                                -> ±8 g de G
  - El driver se ajusta sin alterar (apenas) los otros dos macros.
  - Si tras el ajuste el menú queda a ±4 g de cada macro -> "cuadrada";
    a ±12 g -> se devuelve como aproximada; peor -> se descarta.
"""
from typing import Dict, List, Optional

from meal_builder import get_effective_macros_per_100g

# Umbrales de ajuste por macro (gramos de macro, no de alimento)
AJUSTE_MAX = {"P": 20.0, "H": 30.0, "G": 8.0}
H_MINIMO_PARA_AJUSTE = 50.0     # el menú debe tener >= 50 g de H para ajustar hidratos
DRIVER_POR_MACRO = {"P": "proteina_limpia", "H": "hidrato_limpio", "G": "grasa_limpia"}
MARGEN_CUADRADA = 4.0
MARGEN_APROX = 12.0
CANTIDAD_MIN_G = 10.0
CANTIDAD_MAX_G = 600.0


def _totales(items: List[dict]) -> Dict[str, float]:
    t = {"P": 0.0, "H": 0.0, "G": 0.0}
    for it in items:
        fac = it["cantidad_g"] / 100.0
        ef = it["_ef"]
        t["P"] += (ef.get("P", 0) or 0) * fac
        t["H"] += (ef.get("H", 0) or 0) * fac
        t["G"] += (ef.get("G", 0) or 0) * fac
    return t


def _ajustar_menu(items: List[dict], objetivo: Dict[str, float], macros_menu: Dict[str, float]) -> Optional[dict]:
    """Intenta ajustar el menú al objetivo tocando solo drivers limpios.
    Devuelve {items, totales, cuadrada} o None si queda fuera del margen aproximado."""
    # Orden P -> H -> G: la proteína limpia puede arrastrar algo de H, que
    # luego absorbe el driver de hidratos; la grasa pura no arrastra nada.
    for macro in ("P", "H", "G"):
        t = _totales(items)
        diff = objetivo[macro] - t[macro]
        if abs(diff) <= MARGEN_CUADRADA:
            continue
        if abs(diff) > AJUSTE_MAX[macro]:
            continue  # fuera del rango de ajuste permitido: se valorará al final
        if macro == "H" and macros_menu.get("H", 0) < H_MINIMO_PARA_AJUSTE:
            continue  # regla: hidratos solo se ajustan en menús de 50 g+ de H
        drivers = [it for it in items if it.get("driver") == DRIVER_POR_MACRO[macro]]
        if not drivers:
            continue
        # el driver con más cantidad tiene más recorrido en ambos sentidos
        drv = max(drivers, key=lambda it: it["cantidad_g"])
        por100 = drv["_ef"].get(macro, 0) or 0
        if por100 <= 1e-6:
            continue
        nueva = drv["cantidad_g"] + diff / (por100 / 100.0)
        nueva = round(nueva)
        if not (CANTIDAD_MIN_G <= nueva <= CANTIDAD_MAX_G):
            continue
        drv["cantidad_g"] = nueva

    t = _totales(items)
    if any(abs(objetivo[m] - t[m]) > MARGEN_APROX for m in ("P", "H", "G")):
        return None
    cuadrada = all(abs(objetivo[m] - t[m]) <= MARGEN_CUADRADA for m in ("P", "H", "G"))
    return {"items": items, "totales": t, "cuadrada": cuadrada}


async def buscar_en_biblioteca(
    db,
    macros_objetivo: Dict[str, float],
    alimento_ids: Optional[List[int]] = None,
    tipo: str = "comida",
    limit: int = 5,
    excluir_ids: Optional[set] = None,
) -> List[dict]:
    """Busca menús de la biblioteca real que contengan TODOS los alimentos pedidos
    y cuadren (o se ajusten) a los macros objetivo. Devuelve items listos para
    volcar a una comida (mismo formato que las opciones de menú)."""
    objetivo = {
        "P": float(macros_objetivo.get("P", 0) or 0),
        "H": float(macros_objetivo.get("H", 0) or 0),
        "G": float(macros_objetivo.get("G", 0) or 0),
    }

    q = {"tipo": tipo}
    if alimento_ids:
        q["alimento_ids"] = {"$all": [int(a) for a in alimento_ids]}
    # Preselección por macros: sin ajuste posible más allá de AJUSTE_MAX + margen,
    # todo lo que esté más lejos no puede cuadrar (ahorra evaluar 1000 menús).
    q["macros.P"] = {"$gte": objetivo["P"] - AJUSTE_MAX["P"] - MARGEN_APROX,
                     "$lte": objetivo["P"] + AJUSTE_MAX["P"] + MARGEN_APROX}
    q["macros.H"] = {"$gte": objetivo["H"] - AJUSTE_MAX["H"] - MARGEN_APROX,
                     "$lte": objetivo["H"] + AJUSTE_MAX["H"] + MARGEN_APROX}
    q["macros.G"] = {"$gte": objetivo["G"] - AJUSTE_MAX["G"] - MARGEN_APROX,
                     "$lte": objetivo["G"] + AJUSTE_MAX["G"] + MARGEN_APROX}

    candidatos = await db.meal_library.find(q, {"_id": 0}).to_list(500)

    # Cache de alimentos del catálogo para macros efectivos actuales
    ids_necesarios = {a["alimento_id"] for c in candidatos for a in c["alimentos"]}
    foods = {}
    if ids_necesarios:
        async for f in db.foods.find({"id": {"$in": list(ids_necesarios)}}, {"_id": 0}):
            foods[int(f["id"])] = f

    resultados = []
    for c in candidatos:
        if excluir_ids and c["id"] in excluir_ids:
            continue
        items = []
        ok = True
        for a in c["alimentos"]:
            food = foods.get(a["alimento_id"])
            if not food:
                ok = False
                break
            items.append({
                "alimento_id": a["alimento_id"],
                "nombre": food.get("nombre", a["nombre"]),
                "cantidad_g": float(a["cantidad_g"]),
                "driver": a.get("driver", "mixto"),
                "_ef": get_effective_macros_per_100g(food),
            })
        if not ok:
            continue
        ajuste = _ajustar_menu(items, objetivo, c.get("macros", {}))
        if not ajuste:
            continue
        err = sum(abs(objetivo[m] - ajuste["totales"][m]) for m in ("P", "H", "G"))
        items_out = []
        for it in ajuste["items"]:
            fac = it["cantidad_g"] / 100.0
            items_out.append({
                "alimento_id": it["alimento_id"],
                "nombre": it["nombre"],
                "cantidad_g": it["cantidad_g"],
                "macros_efectivos": {
                    "P": round((it["_ef"].get("P", 0) or 0) * fac, 1),
                    "H": round((it["_ef"].get("H", 0) or 0) * fac, 1),
                    "G": round((it["_ef"].get("G", 0) or 0) * fac, 1),
                },
            })
        t = ajuste["totales"]
        resultados.append({
            "biblioteca_id": c["id"],
            "nombre": " + ".join(i["nombre"].split(" (")[0] for i in items_out[:3]) + ("..." if len(items_out) > 3 else ""),
            "items": items_out,
            "macros_totales": {"P": round(t["P"], 1), "H": round(t["H"], 1), "G": round(t["G"], 1),
                               "kcal": round(t["P"] * 4 + t["H"] * 4 + t["G"] * 9)},
            "macros_objetivo": objetivo,
            "cuadrada": ajuste["cuadrada"],
            "fuente": "clientes",
            "popularidad": {"usos": c.get("usos", 0), "clientes": c.get("clientes", 0)},
            "_err": err,
        })

    # Cuadradas primero; luego menor error; luego más popular (clientes, usos)
    resultados.sort(key=lambda r: (not r["cuadrada"], r["_err"],
                                   -r["popularidad"]["clientes"], -r["popularidad"]["usos"]))
    for r in resultados:
        r.pop("_err", None)
    return resultados[:limit]
