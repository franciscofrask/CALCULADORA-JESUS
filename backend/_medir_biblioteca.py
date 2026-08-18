"""Mide por que /api/calculator/library-menus devuelve CERO (punto 10.3 del 09-08).

Cuenta db.meal_library en dev (Atlas) y en produccion (tunel SSH a 127.0.0.1:27018)
y desglosa el embudo de filtros del endpoint, filtro a filtro, para los cinco casos
de la tabla de Jesus. Solo LEE: no escribe nada en ninguna de las dos bases.

Uso:
    backend/venv/Scripts/python.exe backend/_medir_biblioteca.py
"""
import asyncio
import os
import sys

from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

MARGEN_MAX = 15.0
AJUSTE_MAX = {"P": 20.0, "H": 30.0, "G": 8.0}

CASOS = [
    ("Comida 1", {"P": 30, "H": 20, "G": 10}, 5.0, "cuadrado"),
    ("Comida 1", {"P": 30, "H": 20, "G": 10}, 10.0, "cuadrado"),
    ("Peri", {"P": 30, "H": 30, "G": 0}, 5.0, "cuadrado"),
    ("Peri", {"P": 30, "H": 30, "G": 0}, 5.0, "usado"),
    ("Comida 3", {"P": 24, "H": 10, "G": 15}, 5.0, "cuadrado"),
]

ENTORNOS = [
    ("DEV  (Atlas)", os.environ.get("MONGO_DEV") or "", "jg12_restored"),
    ("PROD (tunel 27018)", "mongodb://127.0.0.1:27018", "jg12_prod"),
]


def _rango(obj):
    return {f"macros.{m}": {"$gte": obj[m] - MARGEN_MAX - AJUSTE_MAX[m],
                            "$lte": obj[m] + MARGEN_MAX + AJUSTE_MAX[m]}
            for m in ("P", "H", "G")}


async def medir(nombre, url, dbname):
    print("\n" + "=" * 78)
    print(nombre, "->", dbname)
    print("=" * 78)
    cli = AsyncIOMotorClient(url, serverSelectionTimeoutMS=15000)
    db = cli[dbname]
    col = db.meal_library
    total = await col.count_documents({})
    print(f"meal_library total .......... {total}")
    if not total:
        cli.close()
        return
    con_tipo = await col.count_documents({"tipo_comida": {"$exists": True}})
    con_calidad = await col.count_documents({"calidad": {"$exists": True}})
    calidad_pasa = await col.count_documents({"calidad.pasa": True})
    repetidos = await col.count_documents({"repetido_de": {"$exists": True}})
    con_clientes = await col.count_documents({"clientes": {"$exists": True}})
    elm = await col.count_documents({"fuente": "elm_menus"})
    print(f"con tipo_comida ............. {con_tipo}")
    print(f"con campo calidad ........... {con_calidad}")
    print(f"calidad.pasa == True ........ {calidad_pasa}")
    print(f"repetido_de presente ........ {repetidos}")
    print(f"con campo clientes .......... {con_clientes}")
    print(f"fuente=elm_menus ............ {elm}")

    tipos = await col.aggregate([
        {"$group": {"_id": "$tipo_comida", "n": {"$sum": 1}}},
        {"$sort": {"n": -1}},
    ]).to_list(50)
    print("tipo_comida:", ", ".join(f"{t['_id']!r}={t['n']}" for t in tipos))

    doc = await col.find_one({}, {"_id": 0})
    print("campos de un doc:", sorted(doc.keys()) if doc else "-")

    for tipo, obj, margen, orden in CASOS:
        print(f"\n-- {tipo} {obj['P']}P/{obj['H']}H/{obj['G']}G  +-{margen:g}  {orden}")
        pasos = [
            ("1 tipo_comida", {"tipo_comida": tipo}),
            ("2 + calidad.pasa", {"tipo_comida": tipo, "calidad.pasa": True}),
            ("3 + no repetido", {"tipo_comida": tipo, "calidad.pasa": True,
                                 "repetido_de": {"$exists": False}}),
        ]
        q4 = dict(pasos[2][1])
        q4.update(_rango(obj))
        pasos.append(("4 + rango macros", q4))
        # Sin los filtros del punto 67, para ver cuanto quita cada uno
        q5 = {"tipo_comida": tipo}
        q5.update(_rango(obj))
        pasos.append(("   (rango SIN 2 y 3)", q5))
        for etiqueta, q in pasos:
            print(f"   {etiqueta:24s} {await col.count_documents(q)}")
    cli.close()


async def pipeline():
    """Ejecuta el endpoint DE VERDAD (routes.calculator.library_menus) contra la base
    que diga MONGO_URL, y cuenta cuantos menus caen en cada paso de Python. Sirve para
    ver si el cero pasa en Mongo o mas adelante, en el bucle de las palancas."""
    from routes import calculator as C

    user = {"id": os.environ.get("USER_ID", "_medicion_")}
    for tipo, obj, margen, orden in CASOS:
        meal_key = "Post" if tipo == "Peri" else {"Comida 1": "C1", "Comida 3": "C3"}[tipo]
        data = {"mealKey": meal_key, "macros_objetivo": obj, "margen": margen,
                "orden": orden, "limit": 40, "momento_entreno": 1}
        r = await C.library_menus(data, user)
        print(f"{tipo:9s} {obj['P']}/{obj['H']}/{obj['G']} +-{margen:g} {orden:9s}"
              f" -> total={r['total']} devueltos={len(r['menus'])} filtros={r.get('filtros')}")


async def embudo_python():
    """El embudo DESPUES de Mongo: de los candidatos que trae la consulta, cuantos se
    caen porque un alimento del menu ya no esta en db.foods y cuantos por el margen."""
    from routes.calculator import (_LIBRARY_MARGEN_DEFAULT, _LIBRARY_MARGEN_MAX,
                                   _LIBRARY_TRABAJO_MAX, _redondear_para_el_cliente)
    from core.database import db
    from meal_library import _ajustar_menu
    from meal_builder import get_effective_macros_per_100g

    for tipo, obj, margen, orden in CASOS:
        q = {"tipo_comida": tipo, "calidad.pasa": True, "repetido_de": {"$exists": False}}
        q.update(_rango(obj))
        cand = await db.meal_library.find(q, {"_id": 0, "id": 1, "macros": 1, "alimentos": 1,
                                              "alimento_ids": 1, "clientes": 1, "usos": 1,
                                              "veces": 1, "fuente": 1}).to_list(4000)

        def desfase(c):
            mm = c.get("macros", {})
            return max(abs(obj[m] - float(mm.get(m, 0) or 0)) for m in ("P", "H", "G"))

        cand.sort(key=lambda c: (round(desfase(c)), -int(c.get("clientes") or 0)))
        trabajo = cand[:_LIBRARY_TRABAJO_MAX]
        ids = {a for c in trabajo for a in c.get("alimento_ids", [])}
        foods = {}
        async for f in db.foods.find({"id": {"$in": list(ids)}}, {"_id": 0}):
            foods[int(f["id"])] = f
        sin_food = sin_margen = ok = 0
        for c in trabajo:
            fl = [foods.get(int(a["alimento_id"])) for a in c.get("alimentos", [])]
            if not fl or any(f is None for f in fl):
                sin_food += 1
                continue
            items = [{"cantidad_g": float(a["cantidad_g"]),
                      "driver": "mixto" if (a.get("unidades_n") or f.get("unidades")) else a.get("driver", "mixto"),
                      "_ef": get_effective_macros_per_100g(f)}
                     for a, f in zip(c["alimentos"], fl)]
            aj = _ajustar_menu(items, obj, c.get("macros", {}))
            if aj:
                fin = [_redondear_para_el_cliente(f, it["cantidad_g"])
                       for f, it in zip(fl, aj["items"])]
                res = {m: sum((it["_ef"].get(m, 0) or 0) * g / 100.0
                              for it, g in zip(items, fin)) for m in ("P", "H", "G")}
            else:
                res = {m: float(c.get("macros", {}).get(m, 0) or 0) for m in ("P", "H", "G")}
            if any(abs(obj[m] - res[m]) > margen for m in ("P", "H", "G")):
                sin_margen += 1
            else:
                ok += 1
        print(f"{tipo:9s} {obj['P']}/{obj['H']}/{obj['G']} +-{margen:g}: mongo={len(cand)}"
              f" trabajo={len(trabajo)} caen_por_alimento={sin_food}"
              f" caen_por_margen={sin_margen} quedan={ok}")

    total = await db.meal_library.count_documents({})
    ids_lib = await db.meal_library.distinct("alimento_ids", {"calidad.pasa": True})
    presentes = await db.foods.count_documents({"id": {"$in": list(ids_lib)}})
    print(f"alimentos distintos en menus con calidad.pasa: {len(ids_lib)}; en db.foods: {presentes}")
    print(f"meal_library total: {total}")


async def main():
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
    if "--pipeline" in sys.argv:
        print("MONGO_URL =", os.environ.get("MONGO_URL"))
        await pipeline()
        return
    if "--embudo" in sys.argv:
        print("MONGO_URL =", os.environ.get("MONGO_URL"))
        await embudo_python()
        return
    for nombre, url, dbname in ENTORNOS:
        u = url or os.environ.get("MONGO_URL")
        try:
            await medir(nombre, u, dbname)
        except Exception as e:  # noqa: BLE001
            print(f"\n{nombre}: ERROR {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(main())
