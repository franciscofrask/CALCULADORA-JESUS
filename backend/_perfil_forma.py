# -*- coding: utf-8 -*-
"""Construye db.meal_shapes: de cuántas piezas se compone una comida real y con qué
combinaciones de familias, sacado de db.diets.

    ./venv/Scripts/python.exe _perfil_forma.py             # reconstruye
    ./venv/Scripts/python.exe _perfil_forma.py --ver       # enseña lo que hay, no escribe

Re-ejecutable: borra y rehace. De solo lectura sobre db.diets y db.foods.

Igual que `_perfil_companyia.py` y `_perfil_momento.py`, hay que ejecutarlo en CADA base
donde se use (dev y producción tienen dietas distintas). Sin la colección, el asistente
sigue funcionando como antes: el reparto por piezas se cae a su valor por defecto y la
composición por esqueletos se apaga sola.

Se saltan los días de bloque único (su C1 es el día entero, no un desayuno) y el peri,
que tiene su propio universo de alimentos y no es una comida.
"""
import argparse
import asyncio
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from motor.motor_asyncio import AsyncIOMotorClient

from meal_builder import classify_food_role, get_effective_macros_per_100g
from meal_moment import momento_de_comida, PERI
from meal_shape import COLECCION, MIN_APARICIONES, ROLES, TRAMO_KCAL, PerfilForma
from moment_profile import MOMENTOS_PERFIL, cat2_de


def _rol_de(food: dict) -> str:
    """Qué papel hace el alimento en el plato: P (proteína), H (hidrato), G (grasa) o V.

    Los mixtos van a su macro dominante para contarlos: un lácteo proteico (PH) es la
    proteína del desayuno, y unos huevos (PG) también. Es el mismo `classify_food_role`
    con el que el asistente monta las comidas, así que lo contado y lo compuesto hablan
    del mismo concepto.
    """
    rol = classify_food_role(food, get_effective_macros_per_100g(food))
    return {"P": "P", "PH": "P", "PG": "P", "H": "H", "G": "G", "V": "V"}.get(rol, "H")


def _kcal_de(alimento: dict, food: dict) -> float:
    """Las kcal que CUENTAN de un alimento de una dieta guardada.

    Se calculan desde el catálogo con el motor de siempre (`calma_suggest`), no se leen
    de la dieta: solo 433 de los 39.111 alimentos guardados traen sus macros dentro
    (el 1,1 %), así que fiarse del campo dejaba el reparto por kcal sin datos. Cuando sí
    están, se usan tal cual: son los que se le enseñaron al cliente ese día.
    """
    from calma_suggest import macros_efectivos

    ef = alimento.get("macros_efectivos") or {}
    kcal = ef.get("kcal")
    if isinstance(kcal, (int, float)) and kcal > 0:
        return float(kcal)
    if any(isinstance(ef.get(m), (int, float)) and ef.get(m) for m in ("P", "H", "G")):
        return (float(ef.get("P") or 0) * 4 + float(ef.get("H") or 0) * 4
                + float(ef.get("G") or 0) * 9)
    try:
        cantidad = float(alimento.get("cantidad_g") or alimento.get("cantidad") or 0)
    except (TypeError, ValueError):
        return 0.0
    if cantidad <= 0:
        return 0.0
    m = macros_efectivos(food, cantidad)
    return m["P"] * 4 + m["H"] * 4 + m["G"] * 9


async def _leer(db):
    """Recorre las dietas y agrega, por momento: tamaños, familias, esqueletos y la
    relación entre kcal de la comida y número de piezas."""
    # El catálogo ENTERO (no solo id/nombre/categorías): las kcal de cada pieza se
    # calculan aquí desde sus macros, porque las dietas no las guardan.
    foods = {int(f["id"]): f async for f in db.foods.find({}, {"_id": 0})}

    tam = defaultdict(Counter)          # momento -> {piezas: veces}
    familias = defaultdict(Counter)     # momento -> {cat2: comidas en que aparece}
    esqueletos = defaultdict(Counter)   # momento -> {(cat2, ...): veces}
    por_kcal = defaultdict(lambda: defaultdict(Counter))   # momento -> tramo -> {piezas: veces}
    roles = defaultdict(lambda: defaultdict(Counter))      # momento -> rol -> {piezas: veces}
    kcal_pieza = defaultdict(Counter)   # momento -> {kcal de una pieza: veces}
    comidas = Counter()
    saltados = 0
    rol_de_id = {i: _rol_de(f) for i, f in foods.items()}

    async for d in db.diets.find({}, {"_id": 0, "comidas": 1, "num_comidas": 1}):
        com = d.get("comidas")
        if not isinstance(com, dict):
            continue
        try:
            n = int(d.get("num_comidas") or 0)
        except (TypeError, ValueError):
            n = 0
        # Bloque único: el día entero en una comida, no dice nada de la forma de comer.
        if n <= 1:
            saltados += 1
            continue
        for key, comida in com.items():
            if not isinstance(comida, dict) or not comida.get("alimentos"):
                continue
            momento = momento_de_comida(key, n)
            if momento == PERI or momento not in MOMENTOS_PERFIL:
                continue
            vistos, kcal = [], 0.0
            for a in comida["alimentos"]:
                aid = a.get("alimento_id")
                if not isinstance(aid, (int, float)) or int(aid) not in foods:
                    continue
                aid = int(aid)
                kcal += _kcal_de(a, foods[aid])
                if aid not in vistos:
                    vistos.append(aid)
            if not vistos:
                continue
            comidas[momento] += 1
            piezas = len(vistos)
            tam[momento][piezas] += 1
            # La familia cuenta una vez por comida: dos frutas distintas siguen siendo
            # «lleva fruta», que es lo que describe la forma del plato.
            fams = sorted({cat2_de(foods[i]) for i in vistos})
            for f in fams:
                familias[momento][f] += 1
            esqueletos[momento][tuple(fams)] += 1
            if kcal > 0:
                tramo = int(kcal // TRAMO_KCAL) * TRAMO_KCAL
                por_kcal[momento][tramo][piezas] += 1
                # Cuántas kcal pone UNA pieza. Es lo que impide repartir entre cinco un
                # hueco que da para una: sin esto, un remate de 93 kcal se trataba como
                # una comida de tres piezas y pedía 3 g de proteína a cada una.
                kcal_pieza[momento][int(round(kcal / piezas))] += 1
            # Cuántas piezas hace cada papel. El cero se cuenta también: si la mitad de
            # las cenas no llevan grasa aparte, la mediana tiene que poder decirlo.
            cuenta_rol = Counter(rol_de_id[i] for i in vistos)
            for rol in ROLES:
                roles[momento][rol][cuenta_rol.get(rol, 0)] += 1

    return comidas, tam, familias, esqueletos, por_kcal, roles, kcal_pieza, saltados


def _documentos(comidas, tam, familias, esqueletos, por_kcal, roles, kcal_pieza):
    docs = []
    for momento, n in comidas.items():
        docs.append({
            "tipo": "_momento", "clave": momento, "comidas": n,
            "tam": {str(k): v for k, v in tam[momento].items()},
            "familias": dict(familias[momento]),
            "por_kcal": {str(tramo): {str(p): v for p, v in cuenta.items()}
                         for tramo, cuenta in por_kcal[momento].items()},
            "roles": {rol: {str(p): v for p, v in cuenta.items()}
                      for rol, cuenta in roles[momento].items()},
            "kcal_pieza": {str(k): v for k, v in kcal_pieza[momento].items()},
        })
        for fams, veces in esqueletos[momento].items():
            if veces < MIN_APARICIONES:
                continue
            docs.append({"tipo": "esqueleto", "clave": momento,
                         "familias": list(fams), "n": veces})
    return docs


async def construir():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
    comidas, tam, familias, esqueletos, por_kcal, roles, kcal_pieza, saltados = await _leer(db)
    docs = _documentos(comidas, tam, familias, esqueletos, por_kcal, roles, kcal_pieza)

    await db[COLECCION].delete_many({})
    for i in range(0, len(docs), 500):
        await db[COLECCION].insert_many(docs[i:i + 500])
    await db[COLECCION].create_index([("tipo", 1), ("clave", 1)])

    n_esq = sum(1 for d in docs if d["tipo"] == "esqueleto")
    print(f"{COLECCION}: {sum(comidas.values())} comidas de {len(comidas)} momentos "
          f"-> {n_esq} esqueletos con al menos {MIN_APARICIONES} usos "
          f"({saltados} días de bloque único saltados)")
    for momento in sorted(comidas):
        print(f"  {momento:10} {comidas[momento]:6} comidas")


async def ver():
    """Lo que hay guardado, en palabras. No escribe nada."""
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
    foods = [f async for f in db.foods.find({}, {"_id": 0, "id": 1, "nombre": 1, "categorias": 1})]
    nombre_fam = {}
    for f in foods:
        nombre_fam.setdefault(cat2_de(f), f.get("nombre", ""))
    perfil = await PerfilForma.cargar(db)
    if not perfil.hay_datos:
        print("no hay perfil de forma: construye primero")
        return
    for momento in sorted(perfil.momentos):
        print(f"\n=== {momento} ({perfil.comidas(momento)} comidas) ===")
        print(f"  piezas típicas: {perfil.piezas_tipicas(momento)}")
        for kcal in (200, 400, 600, 800):
            print(f"    a {kcal} kcal: {perfil.piezas_tipicas(momento, kcal)} piezas")
        formas = perfil.formas(momento)
        print(f"  esqueletos con datos: {len(formas)}")
        for fams, n in formas[:8]:
            etiquetas = " + ".join(f"{c}({nombre_fam.get(c, '?')[:16]})" for c in fams)
            print(f"    {n:5}  {etiquetas}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ver", action="store_true", help="enseña lo guardado, no escribe")
    args = ap.parse_args()
    asyncio.run(ver() if args.ver else construir())
