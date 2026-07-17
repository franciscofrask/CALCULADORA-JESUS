"""Fase 1 - Biblioteca de menús reales: mina db.diets y construye db.meal_library.

Extrae todas las comidas reales de los clientes, deduplica por combinación de
alimentos, puntúa por popularidad (usos y clientes distintos) y guarda los
menús validados por la práctica como biblioteca consultable.

Criterios acordados con el usuario (2026-07-12):
  - Entran combos con >= MIN_USOS usos y >= MIN_CLIENTES clientes distintos.
  - 2-9 alimentos, todos en gramos y existentes en el catálogo actual.
  - tipo: 'peri' (Intra/Post) o 'comida' (resto); sin momento desayuno/cena.
  - fuente: 'clientes' (separada de menu_templates, que es del admin/recetario).
  - Cantidades: mediana de los usos reales; macros con la lógica actual de la app.

Uso: ./venv/Scripts/python.exe _minar_biblioteca_menus.py [--apply]
     (sin --apply: dry run, muestra resumen y ejemplos, no escribe)
"""
import asyncio
import hashlib
import os
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

MIN_USOS = 3
MIN_CLIENTES = 2
PERI_KEYS = {"Intra", "Post", "Peri", "intra", "post"}


def clasificar_driver(ef: dict) -> str:
    """Driver de ajuste 'limpio' según los macros efectivos por 100g."""
    p, h, g = ef.get("P", 0) or 0, ef.get("H", 0) or 0, ef.get("G", 0) or 0
    if p >= 15 and g <= 2 and h <= 6:
        return "proteina_limpia"
    if h >= 15 and p <= 3 and g <= 2:
        return "hidrato_limpio"
    if g >= 50 and p <= 3 and h <= 5:
        return "grasa_limpia"
    return "mixto"


async def main():
    apply = "--apply" in sys.argv
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]

    from meal_builder import get_effective_macros_per_100g

    # Catálogo actual en memoria
    foods = {}
    async for f in db.foods.find({}, {"_id": 0}):
        if f.get("id") is not None:
            foods[int(f["id"])] = f
    print(f"catálogo: {len(foods)} alimentos | modo: {'APPLY' if apply else 'DRY RUN'}")

    # Minería: agrupar comidas por firma (set de alimento_ids)
    combos = defaultdict(lambda: {"usos": 0, "users": set(), "cantidades": defaultdict(list), "peri": 0})
    total_comidas = 0
    cursor = db.diets.find({}, {"_id": 0, "user_id": 1, "comidas": 1})
    async for d in cursor:
        uid = d.get("user_id")
        comidas = d.get("comidas")
        if not isinstance(comidas, dict):
            continue  # datos corruptos (p.ej. un Int64 en 'comidas'): se ignora la dieta
        for key, meal in comidas.items():
            if not isinstance(meal, dict):
                continue
            alimentos = meal.get("alimentos") or []
            if not (2 <= len(alimentos) <= 9):
                continue
            total_comidas += 1
            ids, cants, ok = [], {}, True
            for a in alimentos:
                aid = a.get("alimento_id")
                cant = a.get("cantidad_g") or a.get("cantidad") or 0
                if aid is None or cant <= 0 or int(aid) not in foods:
                    ok = False
                    break
                aid = int(aid)
                ids.append(aid)
                # si un alimento se repite en la comida, sumar cantidades
                cants[aid] = cants.get(aid, 0) + float(cant)
            if not ok or len(set(ids)) < 2:
                continue
            sig = tuple(sorted(set(ids)))
            c = combos[sig]
            c["usos"] += 1
            if uid:
                c["users"].add(uid)
            if key in PERI_KEYS:
                c["peri"] += 1
            for aid, cant in cants.items():
                c["cantidades"][aid].append(cant)

    print(f"comidas procesadas: {total_comidas} | combos únicos: {len(combos)}")

    # Selección y construcción de documentos
    docs = []
    for sig, c in combos.items():
        if c["usos"] < MIN_USOS or len(c["users"]) < MIN_CLIENTES:
            continue
        alimentos_doc, tot = [], {"P": 0.0, "H": 0.0, "G": 0.0}
        drivers = set()
        for aid in sig:
            food = foods[aid]
            ef = get_effective_macros_per_100g(food)
            cant = round(statistics.median(c["cantidades"][aid]))
            driver = clasificar_driver(ef)
            drivers.add(driver)
            fac = cant / 100.0
            tot["P"] += (ef.get("P", 0) or 0) * fac
            tot["H"] += (ef.get("H", 0) or 0) * fac
            tot["G"] += (ef.get("G", 0) or 0) * fac
            alimentos_doc.append({
                "alimento_id": aid,
                "nombre": food.get("nombre", ""),
                "cantidad_g": cant,
                "driver": driver,
            })
        macros = {m: round(v, 1) for m, v in tot.items()}
        macros["kcal"] = round(tot["P"] * 4 + tot["H"] * 4 + tot["G"] * 9)
        docs.append({
            "id": "L" + hashlib.sha1(",".join(map(str, sig)).encode()).hexdigest()[:10].upper(),
            "alimento_ids": list(sig),
            "alimentos": alimentos_doc,
            "macros": macros,
            "usos": c["usos"],
            "clientes": len(c["users"]),
            "tipo": "peri" if c["peri"] >= c["usos"] * 0.7 else "comida",
            "fuente": "clientes",
            "ajuste": {
                "p_limpia": "proteina_limpia" in drivers,
                "h_limpio": "hidrato_limpio" in drivers,
                "g_limpia": "grasa_limpia" in drivers,
            },
            "minado_at": datetime.now(timezone.utc).isoformat(),
        })

    docs.sort(key=lambda d: (-d["clientes"], -d["usos"]))
    n_comida = sum(1 for d in docs if d["tipo"] == "comida")
    n_peri = len(docs) - n_comida
    print(f"\nbiblioteca resultante: {len(docs)} menús ({n_comida} comidas, {n_peri} peri-entrenos)")
    print(f"con driver P limpio: {sum(1 for d in docs if d['ajuste']['p_limpia'])}")
    print(f"con driver H limpio: {sum(1 for d in docs if d['ajuste']['h_limpio'])}")
    print(f"con driver G limpia: {sum(1 for d in docs if d['ajuste']['g_limpia'])}")

    print("\ntop 8 (por clientes distintos):")
    for d in docs[:8]:
        comp = " + ".join(f"{a['nombre'][:24]} {a['cantidad_g']}g" for a in d["alimentos"])
        m = d["macros"]
        print(f"  [{d['tipo']:6}] x{d['usos']} usos/{d['clientes']} clientes | {m['P']}P {m['H']}H {m['G']}G | {comp[:110]}")

    print("\ntop 12 comidas de plato:")
    for d in [x for x in docs if x["tipo"] == "comida"][:12]:
        comp = " + ".join(f"{a['nombre'][:22]} {a['cantidad_g']}g" for a in d["alimentos"])
        m = d["macros"]
        print(f"  x{d['usos']}/{d['clientes']}cl | {m['P']}P {m['H']}H {m['G']}G | {comp[:120]}")

    if apply and docs:
        await db.meal_library.drop()
        await db.meal_library.insert_many([dict(d) for d in docs])
        await db.meal_library.create_index("alimento_ids")
        await db.meal_library.create_index([("tipo", 1), ("macros.P", 1)])
        print(f"\nINSERTADOS {len(docs)} en db.meal_library (colección recreada)")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
