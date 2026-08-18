# -*- coding: utf-8 -*-
"""
Punto 10.1: alimentos que ocupan plaza en el reparto de un menu sin aportar el macro
que su rol dice que cubren.

Lo vio Jesus en un menu concreto: lechuga y tomate con rol «Hidrato» y proporcion 1, igual
que la pasta y el pan, cuando no dan hidratos (P0-H0-G0 y P0-H5-G0). En un menu de plantilla
las cantidades se reparten POR ROL, asi que una lechuga marcada como hidrato se lleva una
parte del cupo de hidratos que nadie va a cubrir: el resto de fuentes tienen que subir para
compensar, o el menu se queda corto.

Esto barre los menus enteros y saca la lista, ordenada por lo que mas se repite. No cambia
nada: la decision de que rol lleva cada alimento es de Jesus.

    ./venv/Scripts/python.exe _barrer_roles_menus.py
    ./venv/Scripts/python.exe _barrer_roles_menus.py --mongo mongodb://127.0.0.1:27018 --db jg12_prod
"""
import argparse
import asyncio
import io
import os
import sys

from motor.motor_asyncio import AsyncIOMotorClient

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Cuanto tiene que aportar por 100 g para que el rol se sostenga. Por debajo de esto el
# alimento no esta cubriendo ese macro: esta de acompañamiento.
MINIMO = {"proteina": 6.0, "hidrato": 8.0, "grasa": 3.0}

# El macro de cada rol.
MACRO_DE = {"proteina": "proteinas", "hidrato": "hidratos", "grasa": "grasas"}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mongo", default=os.environ.get("MONGO_URL"))
    ap.add_argument("--db", default=os.environ.get("DB_NAME", "test_database"))
    args = ap.parse_args()

    cli = AsyncIOMotorClient(args.mongo, serverSelectionTimeoutMS=15000)
    db = cli[args.db]

    foods = {int(f["id"]): f async for f in db.foods.find({}, {"_id": 0}) if f.get("id") is not None}
    por_nombre = {}
    for f in foods.values():
        por_nombre.setdefault((f.get("nombre") or "").strip().lower(), f)

    menus = await db.menu_templates.find({}, {"_id": 0}).to_list(None)
    print(f"menus: {len(menus)}   alimentos del catalogo: {len(foods)}")
    if not menus:
        print("no hay menus en esta base")
        return

    flojos = {}       # (nombre, rol) -> {"aporta": x, "menus": [..]}
    sin_alimento = {} # los que ni siquiera resuelven a un alimento del catalogo
    total_items = 0

    for m in menus:
        for it in (m.get("items") or []):
            total_items += 1
            rol = (it.get("rol") or "").strip().lower()
            if rol not in MACRO_DE:
                continue
            food = None
            if it.get("alimento_id") is not None:
                food = foods.get(int(it["alimento_id"]))
            if food is None:
                food = por_nombre.get((it.get("buscar") or "").strip().lower())
            nombre = (it.get("buscar") or "?").strip()
            if food is None:
                sin_alimento.setdefault(nombre, []).append(m.get("nombre"))
                continue
            # Por 100 g o por racion, segun como este guardado el alimento.
            racion = float(food.get("racion") or 100) or 100.0
            aporta_racion = float(food.get(MACRO_DE[rol]) or 0)
            por_100 = aporta_racion * (100.0 / racion) if food.get("unidades") else aporta_racion
            if por_100 < MINIMO[rol]:
                clave = (nombre, rol)
                d = flojos.setdefault(clave, {"aporta": round(por_100, 1), "menus": []})
                d["menus"].append(m.get("nombre"))

    print(f"items en total: {total_items}")
    print()
    print("=" * 86)
    print("ALIMENTOS QUE NO SOSTIENEN SU ROL  (aporta por 100 g < minimo del rol)")
    print("=" * 86)
    if not flojos:
        print("   ninguno")
    for (nombre, rol), d in sorted(flojos.items(), key=lambda x: -len(x[1]["menus"])):
        print(f"   {len(d['menus']):3} menus  rol={rol:9} {nombre[:42]:42} aporta {d['aporta']:5} g/100g "
              f"(minimo {MINIMO[rol]})")
    print()
    print(f"   {len(flojos)} combinaciones alimento+rol, "
          f"{sum(len(d['menus']) for d in flojos.values())} apariciones en menus")

    if sin_alimento:
        print()
        print("=" * 86)
        print("ITEMS QUE NO RESUELVEN A NINGUN ALIMENTO DEL CATALOGO")
        print("=" * 86)
        for nombre, ms in sorted(sin_alimento.items(), key=lambda x: -len(x[1]))[:25]:
            print(f"   {len(ms):3} menus  {nombre[:60]}")

    cli.close()


asyncio.run(main())
