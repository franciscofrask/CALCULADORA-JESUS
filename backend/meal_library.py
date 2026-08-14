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

# ¿Se ofrecen los menús sacados de las dietas de los clientes?
#
# SÍ, desde el 08-08-2026 (Francisco). Estuvieron apagados desde el 06-08, y el
# motivo era bueno: se ofrecían los 266.170 en crudo, sin filtro ninguno, y salían
# batidos y listas de botes.
#
# Lo que ha cambiado es que ya hay con qué filtrarlos, que es lo que pide el punto 67
# del documento del 07-08:
#
#   - pasan el filtro de calidad (verdura, sin carga de suplementos, número
#     razonable de ingredientes): 1.946 comidas de plato y 3.544 peri, de 23.681;
#   - se ordenan por cuánta GENTE DISTINTA los ha montado, no por usos;
#   - los repetidos (mismos alimentos, otras cantidades) no se ofrecen.
#
# Son de relleno y van detrás del recetario, que es el material terminado de Jesús.
#
# Afecta a los tres sitios que los usan: la pestaña "Biblioteca" del sugeridor de
# Nutrición, el momento mágico del final del cuestionario y el buscador de menús del
# coach en la ficha del cliente.
#
# Para apagarlos otra vez: poner esto en False y BIBLIOTECA_DE_CLIENTES en
# frontend/src/lib/menuFuentes.js también. Las dos.
BIBLIOTECA_DE_CLIENTES = True

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
    max_candidatos: int = 500,
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

    # Los menús de los clientes son de relleno y van SIEMPRE con filtro (punto 67):
    # solo los que llevan verdura, no son una lista de botes y tienen un número
    # razonable de ingredientes. Lo marca la cosecha (_cosechar_menus.py).
    q["calidad.pasa"] = True
    # Y sin repetir: 10.304 de los 23.681 llevan los mismos alimentos que otro y solo
    # cambian las cantidades, que aquí se reescalan igualmente. Al cliente le salía
    # tres veces la misma comida con otros gramos.
    q["repetido_de"] = {"$exists": False}
    # Preselección por macros: sin ajuste posible más allá de AJUSTE_MAX + margen,
    # todo lo que esté más lejos no puede cuadrar (ahorra evaluar 1000 menús).
    q["macros.P"] = {"$gte": objetivo["P"] - AJUSTE_MAX["P"] - MARGEN_APROX,
                     "$lte": objetivo["P"] + AJUSTE_MAX["P"] + MARGEN_APROX}
    q["macros.H"] = {"$gte": objetivo["H"] - AJUSTE_MAX["H"] - MARGEN_APROX,
                     "$lte": objetivo["H"] + AJUSTE_MAX["H"] + MARGEN_APROX}
    q["macros.G"] = {"$gte": objetivo["G"] - AJUSTE_MAX["G"] - MARGEN_APROX,
                     "$lte": objetivo["G"] + AJUSTE_MAX["G"] + MARGEN_APROX}

    # El tope viene de fuera: el flujo del coach quiere el barrido ancho (500), pero el
    # chat pide 3 opciones y traerse 500 menus enteros por la red eran 19 s medidos en
    # dev para luego tirar casi todos.
    candidatos = await db.meal_library.find(q, {"_id": 0}).to_list(max_candidatos)

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
            "popularidad": {"usos": c.get("usos", 0), "clientes": c.get("clientes", 0),
                            "usos_calma": c.get("usos_calma", 0)},
            "_err": err,
        })

    # Cuadradas primero y, dentro de ellas, la que más GENTE DISTINTA ha montado.
    # Ese es el criterio del punto 71, y no es lo mismo que la más usada: un menú que
    # han montado 30 personas es bueno; uno que una persona ha repetido 30 veces solo
    # dice que a esa persona le gusta.
    #
    # El error de macros NO va por delante de la gente cuando el menú ya cuadra. Si
    # los tres macros están dentro del margen válido, que uno se quede a 0,3 g y otro
    # a 0,9 no lo nota nadie -- pero ordenar por eso deja el criterio de la gente sin
    # estrenar, porque casi todos cuadran al decimal. Entre las que no cuadran sí
    # importa, y ahí se agrupa de dos en dos gramos para que tampoco mande el ruido.
    #
    # `usos_calma` va el último y a propósito: es lo que se sabía de la calculadora
    # antigua, donde no consta quién montó cada cosa. Sirve para desempatar entre
    # menús que aquí no ha tocado nadie, no para competir con la gente de verdad.
    def _orden(r):
        p = r["popularidad"]
        escalon = 0 if r["cuadrada"] else round(r["_err"] / 2)
        return (not r["cuadrada"], escalon,
                -p["clientes"], -p["usos"], -p["usos_calma"], r["_err"])

    resultados.sort(key=_orden)
    for r in resultados:
        r.pop("_err", None)
    return resultados[:limit]
