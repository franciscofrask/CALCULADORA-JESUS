# -*- coding: utf-8 -*-
"""Pone el MOMENTO DEL DIA a cada menu de la biblioteca (db.meal_library).

EL FALLO QUE ARREGLA (video de Francisco, 29-08-2026). En «Sugiereme un menu» se filtra por
Meriendas y salen comidas: langostinos, pimientos asados, y una merienda con «conejo
contramuslo 16 g». Sus palabras: «en las recetas del recetario si, pero en los menus estos
que se cogen de la gente no cuadra».

La causa no era el filtro, era el dato. La ventana filtra por momento SOLO las recetas del
recetario (`LibraryMenusModal`), porque los menus de la gente no tienen momento: la
biblioteca guarda la POSICION (`tipo_comida`: Comida 1..4, Peri) y nada mas. Y la posicion no
dice el momento -- con 4 comidas la 3 es la merienda, con 3 comidas es la cena --, asi que al
pedir meriendas le llegaban las cenas de todo el mundo.

COMO SE DEDUCE. `meal_moment.momento_de_comida(meal_key, num_comidas)` ya lo resuelve, pero
necesita el numero de comidas del dia, que la biblioteca tampoco guarda. Si esta en
`db.diets`, que es de donde se cosecha: se recorren las dietas, se cuenta en que momento se
monto cada menu EN ESA POSICION, y se escribe el resultado.

Por (firma, posicion) y no solo por firma: 30.674 conjuntos de alimentos aparecen en varias
posiciones, y el mismo plato puede ser almuerzo en una y cena en otra. Son entradas distintas
de la biblioteca y cada una lleva su momento.

QUE SE ESCRIBE, en cada menu que tenga usos en db.diets:

    momentos            lista con los momentos que llegan al 25 % de sus usos
    momento_principal   el mas frecuente
    momentos_usos       el recuento entero, para poder revisarlo sin recalcular

Los que no aparecen en ninguna dieta se quedan SIN el campo y no se tocan: la mayoria vienen
del CSV de la calculadora antigua (su recuento vive en `usos_calma`) y ahi no hay a quien
preguntarle en que momento se lo comio. El endpoint decide que hacer con ellos; este guion no
inventa un momento que no consta.

Uso:
    venv/Scripts/python.exe _momentos_biblioteca.py            # dry run, no escribe
    venv/Scripts/python.exe _momentos_biblioteca.py --apply    # escribe

Idempotente: pasarlo dos veces deja lo mismo.
"""
import asyncio
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.cosecha_menus import firma  # noqa: E402
from meal_moment import momento_de_comida  # noqa: E402

# Un momento entra en `momentos` si es al menos este porcentaje de los usos del menu. Con
# el 25 % un menu que unos ponen de merienda y otros de cena sale en las dos, que es la
# verdad; y uno que solo una vez de cada veinte cayo en otro sitio, no.
UMBRAL = 0.25

# La posicion tal y como la guarda la biblioteca, desde la clave de la comida.
POSICION = {"C1": "Comida 1", "C2": "Comida 2", "C3": "Comida 3", "C4": "Comida 4",
            "C5": "Comida 5", "C6": "Comida 6",
            "Intra": "Peri", "Post": "Peri", "intra": "Peri", "post": "Peri"}


async def contar_momentos(db):
    """{(firma, posicion): Counter(momento -> veces)} recorriendo todas las dietas."""
    cuenta = defaultdict(Counter)
    sin_num_comidas = 0
    dietas = 0

    cursor = db.diets.find({}, {"_id": 0, "comidas": 1, "num_comidas": 1})
    async for dieta in cursor:
        dietas += 1
        comidas = dieta.get("comidas")
        if not isinstance(comidas, dict):
            continue  # dietas corruptas (un Int64 en 'comidas'), como en la cosecha
        num = dieta.get("num_comidas")
        if not num:
            # Sin saber cuantas comidas tenia el dia, la posicion no dice el momento.
            # No se supone: ese uso no cuenta.
            sin_num_comidas += 1
            continue
        for meal_key, meal in comidas.items():
            if not isinstance(meal, dict):
                continue
            pos = POSICION.get(meal_key)
            if not pos:
                continue
            ids = []
            for a in (meal.get("alimentos") or []):
                try:
                    ids.append(int(a.get("alimento_id")))
                except (TypeError, ValueError):
                    ids = []
                    break
            if len(set(ids)) < 2:      # MIN_ALIMENTOS de la cosecha
                continue
            momento = momento_de_comida(meal_key, int(num), single_meal=(int(num) == 1))
            cuenta[(firma(ids), pos)][momento] += 1

    return cuenta, dietas, sin_num_comidas


def momentos_de(contador: Counter):
    """Los momentos que llegan al umbral, el principal y el recuento."""
    total = sum(contador.values())
    if not total:
        return None
    momentos = [m for m, n in contador.most_common() if n >= total * UMBRAL]
    if not momentos:                      # todo muy repartido: al menos el mayoritario
        momentos = [contador.most_common(1)[0][0]]
    return momentos, contador.most_common(1)[0][0], dict(contador)


async def main(aplicar: bool):
    from core.database import db

    print("Contando momentos en db.diets...")
    cuenta, dietas, sin_num = await contar_momentos(db)
    print(f"  dietas recorridas: {dietas}   ·   sin num_comidas (no cuentan): {sin_num}")
    print(f"  combinaciones (menu, posicion) con momento: {len(cuenta)}")

    total_biblioteca = await db.meal_library.count_documents({})
    con_momento = 0
    sin_momento = 0
    reparto = Counter()
    escrituras = []

    cursor = db.meal_library.find({}, {"_id": 1, "alimento_ids": 1, "tipo_comida": 1})
    async for menu in cursor:
        ids = menu.get("alimento_ids") or []
        pos = (menu.get("tipo_comida") or "").strip()
        try:
            clave = (firma(ids), pos)
        except (TypeError, ValueError):
            sin_momento += 1
            continue
        contador = cuenta.get(clave)
        calculado = momentos_de(contador) if contador else None
        if not calculado:
            sin_momento += 1
            continue
        momentos, principal, usos = calculado
        con_momento += 1
        reparto[principal] += 1
        escrituras.append({"_id": menu["_id"], "momentos": momentos,
                           "momento_principal": principal, "momentos_usos": usos})

    print(f"\nBIBLIOTECA: {total_biblioteca}")
    print(f"  se les puede poner momento: {con_momento}  ({con_momento * 100 // max(1, total_biblioteca)} %)")
    print(f"  se quedan sin momento:      {sin_momento}")
    print("\n  por momento principal:")
    for m, n in reparto.most_common():
        print(f"    {m:>9}: {n}")

    if not aplicar:
        print("\n(dry run: no se ha escrito nada. Con --apply se escribe.)")
        return

    print(f"\nEscribiendo {len(escrituras)}...")
    from pymongo import UpdateOne
    lote = []
    hechas = 0
    for e in escrituras:
        lote.append(UpdateOne({"_id": e["_id"]}, {"$set": {
            "momentos": e["momentos"],
            "momento_principal": e["momento_principal"],
            "momentos_usos": e["momentos_usos"],
        }}))
        if len(lote) >= 1000:
            r = await db.meal_library.bulk_write(lote, ordered=False)
            hechas += r.modified_count
            lote = []
            print(f"  {hechas}...")
    if lote:
        r = await db.meal_library.bulk_write(lote, ordered=False)
        hechas += r.modified_count
    print(f"  modificados: {hechas}")


if __name__ == "__main__":
    asyncio.run(main("--apply" in sys.argv))
