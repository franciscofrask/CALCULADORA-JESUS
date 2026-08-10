# -*- coding: utf-8 -*-
"""
Punto 10.1: que cambia en los 153 menus al dejar de pedirle a la guarnicion que tire de un
macro.

Cuadra CADA menu contra un objetivo, con el motor de antes y con el de ahora, y compara. Lo
que importa no es que cambien las cantidades -- van a cambiar -- sino:

    - que cuadren MAS menus, o al menos no menos
    - que el error contra el objetivo baje
    - que las verduras dejen de salir en cantidades de plato principal

    ./venv/Scripts/python.exe _medir_guarnicion.py --mongo mongodb://127.0.0.1:27018 --db jg12_restored
"""
import argparse
import asyncio
import io
import os
import sys

from motor.motor_asyncio import AsyncIOMotorClient

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import meal_templates
from meal_templates import MARGEN_MENU, _ajustar_plantilla

# Objetivos de comida. Con tres no bastaba: en los de hidratos bajos (10-20 g) los menus ya
# se pasan a cantidades minimas, asi que el paso 3 no reparte NADA y el cambio no puede verse.
# El reparto solo existe cuando faltan hidratos por cubrir, asi que hay que barrer tambien
# objetivos altos.
OBJETIVOS = [
    ("Comida 1   30P  20H 10G", {"P": 30, "H": 20, "G": 10}),
    ("Comida 3   24P  10H 15G", {"P": 24, "H": 10, "G": 15}),
    ("Comida 2   40P  60H 15G", {"P": 40, "H": 60, "G": 15}),
    ("Media      20P  35H  8G", {"P": 20, "H": 35, "G": 8}),
    ("Post       35P  80H 10G", {"P": 35, "H": 80, "G": 10}),
    ("Grande     45P 100H 20G", {"P": 45, "H": 100, "G": 20}),
]


def error(op, obj):
    if not op:
        return None
    # OJO: la clave es macros_totales, no macros. Con la clave mal todo salia a 0 y el
    # error era literalmente P+H+G del objetivo, identico antes y despues.
    m = op.get("macros_totales") or {}
    return round(sum(abs(float(m.get(k, 0)) - obj[k]) for k in ("P", "H", "G")), 1)


def cuadra(op, obj):
    if not op:
        return False
    m = op.get("macros_totales") or {}
    return all(abs(float(m.get(k, 0)) - obj[k]) <= MARGEN_MENU for k in ("P", "H", "G"))


async def precargar(db, menus):
    """Todos los alimentos de los 153 menus en UNA consulta.

    Sin esto cada item hacia su propio find_one contra Mongo a traves del tunel SSH:
    870 items x 3 objetivos x 2 motores = mas de 5.000 idas y vueltas, y de ahi que el
    script tardase tanto. Es la misma precarga que hace generar_opciones_menu en la app.
    """
    ids = set()
    for m in menus:
        for it in (m.get("items") or []):
            if it.get("alimento_id") not in (None, ""):
                try:
                    ids.add(int(it["alimento_id"]))
                except (TypeError, ValueError):
                    pass
    foods_by_id = {}
    async for f in db.foods.find({"id": {"$in": list(ids)}}, {"_id": 0}):
        foods_by_id[int(f["id"])] = f
    return foods_by_id


async def barrido(db, menus, umbrales, foods_by_id, generic_cache):
    """Cuadra los 153 menus con unos umbrales dados.

    umbrales=None reproduce el motor de antes (todo el mundo tira del macro de su rol)."""
    guardado = meal_templates.MINIMO_PARA_TIRAR
    meal_templates.MINIMO_PARA_TIRAR = umbrales or {"P": 0.0, "H": 0.0, "G": 0.0}
    try:
        out = {}
        for etiqueta, obj in OBJETIVOS:
            filas = []
            for men in menus:
                try:
                    op = await _ajustar_plantilla(
                        db, men, obj, best_effort=True,
                        foods_by_id=foods_by_id, generic_cache=generic_cache,
                    )
                except Exception:
                    op = None
                # La clave lleva el indice: hay menus del recetario que se llaman igual y,
                # metidos en un dict solo por nombre, 153 se quedaban en 99.
                filas.append(((len(filas), men.get("nombre")), op))
            out[etiqueta] = filas
        return out
    finally:
        meal_templates.MINIMO_PARA_TIRAR = guardado


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mongo", default=os.environ.get("MONGO_URL"))
    ap.add_argument("--db", default=os.environ.get("DB_NAME", "test_database"))
    ap.add_argument("--limite", type=int, default=0, help="solo los N primeros menus")
    ap.add_argument("--barrer-umbral", action="store_true",
                    help="prueba varios umbrales de hidrato en vez de comparar antes/ahora")
    ap.add_argument("--umbral-h", type=float, default=None,
                    help="fuerza el umbral de hidrato del informe detallado")
    args = ap.parse_args()

    cli = AsyncIOMotorClient(args.mongo, serverSelectionTimeoutMS=15000)
    db = cli[args.db]
    menus = await db.menu_templates.find({}, {"_id": 0}).to_list(None)
    if args.limite:
        menus = menus[:args.limite]
    print(f"menus: {len(menus)}")

    foods_by_id = await precargar(db, menus)
    generic_cache = {}
    print(f"alimentos precargados: {len(foods_by_id)}")

    if args.barrer_umbral:
        # El umbral de proteina y el de grasa no muerden: el alimento mas flojo que Jesus usa
        # con rol proteina da 8 g/100 g y el mas flojo con rol grasa da 13, asi que cualquier
        # corte por debajo de eso da exactamente el mismo resultado. El unico que decide algo
        # es el de hidratos, y es el que se barre aqui.
        print()
        print(f"{'umbral H':>9}  " + "  ".join(f"{e.split()[0]:>10}" for e, _ in OBJETIVOS))
        for u in (0.0, 4.0, 6.0, 7.0, 8.0, 9.0, 10.0, 12.0, 15.0):
            res = await barrido(db, menus, {"P": 6.0, "H": u, "G": 3.0},
                                foods_by_id, generic_cache)
            celdas = []
            for etiqueta, obj in OBJETIVOS:
                filas = res[etiqueta]
                c = sum(1 for _, op in filas if cuadra(op, obj))
                errs = [error(op, obj) for _, op in filas if op]
                celdas.append(f"{c:3} {sum(errs) / len(errs):6.2f}")
            print(f"{u:9.1f}  " + "  ".join(celdas))
        print("\n   (cada celda: cuantos cuadran  +  error medio en g)")
        print("   la fila 0.0 es el motor de antes: nadie se queda fuera del reparto")
        cli.close()
        return

    umbrales = dict(meal_templates.MINIMO_PARA_TIRAR)
    if args.umbral_h is not None:
        umbrales["H"] = args.umbral_h
    print(f"umbrales: {umbrales}")
    antes = await barrido(db, menus, None, foods_by_id, generic_cache)
    ahora = await barrido(db, menus, umbrales, foods_by_id, generic_cache)

    for etiqueta, obj in OBJETIVOS:
        fa, fh = dict(antes[etiqueta]), dict(ahora[etiqueta])
        ca = sum(1 for n, op in fa.items() if cuadra(op, obj))
        ch = sum(1 for n, op in fh.items() if cuadra(op, obj))
        ea = [error(op, obj) for op in fa.values() if op]
        eh = [error(op, obj) for op in fh.values() if op]
        print()
        print("=" * 78)
        print(f"{etiqueta}")
        print("=" * 78)
        print(f"   cuadran        antes {ca:4} / {len(fa)}      ahora {ch:4} / {len(fh)}")
        if ea and eh:
            print(f"   error medio    antes {sum(ea) / len(ea):6.1f} g      ahora {sum(eh) / len(eh):6.1f} g")
        rotos = [n for n in fa if cuadra(fa[n], obj) and not cuadra(fh.get(n), obj)]
        nuevos = [n for n in fa if not cuadra(fa[n], obj) and cuadra(fh.get(n), obj)]
        print(f"   cuadraban y ya no: {len(rotos)}   no cuadraban y ahora si: {len(nuevos)}")
        for n in rotos[:12]:
            print(f"      ROTO   {str(n[1])[:56]:56} err {error(fa[n], obj)} -> {error(fh.get(n), obj)}")
        for n in nuevos[:12]:
            print(f"      GANA   {str(n[1])[:56]:56} err {error(fa[n], obj)} -> {error(fh.get(n), obj)}")

    # Y lo que motivo el punto: cuanta verdura sale en el plato.
    print()
    print("=" * 78)
    # Con hidratos bajos no hay nada que repartir (a minimos ya sobran), asi que la
    # guarnicion no crece ni antes ni ahora: la foto hay que sacarla de un objetivo ALTO,
    # que es donde el reparto existe y donde el tomate se iba a 200 g.
    print("LAS GUARNICIONES, EN GRAMOS  (objetivo Post 35P 80H 10G, donde hay reparto)")
    print("=" * 78)
    etiqueta = OBJETIVOS[4][0]
    fa, fh = dict(antes[etiqueta]), dict(ahora[etiqueta])
    VERDURAS = ("lechuga", "tomate", "pepino", "calabacín", "champiñon", "espinac",
                "brócoli", "berenjena", "apio", "judías verdes", "pimiento")
    filas = []
    for clave, op in fh.items():
        prev = fa.get(clave)
        if not op or not prev:
            continue
        pa = {(i["nombre"] or "").lower(): i["cantidad_g"] for i in (prev.get("items") or [])}
        for i in (op.get("items") or []):
            nom = (i.get("nombre") or "").lower()
            if any(v in nom for v in VERDURAS) and nom in pa:
                if abs(pa[nom] - i["cantidad_g"]) >= 5:
                    filas.append((str(clave[1])[:34], i["nombre"][:26], pa[nom], i["cantidad_g"]))
    for men, nom, a, h in sorted(filas, key=lambda x: -(x[2] - x[3]))[:25]:
        print(f"   {men:34} {nom:26} {a:6.0f} g -> {h:6.0f} g")
    if not filas:
        print("   sin cambios apreciables")

    cli.close()


asyncio.run(main())
