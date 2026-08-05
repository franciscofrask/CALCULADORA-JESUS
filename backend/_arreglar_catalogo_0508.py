# -*- coding: utf-8 -*-
"""Arreglos de catalogo que pidio Jesus el 05-08-2026 (documento "Lo que hay que corregir").

1. Cereales y panes PROTEICOS sin su categoria (7.1.3 / 8.8): el mismo producto calibraba
   o no segun como estuviera dado de alta. La 7.1.3 y la 8.8 saltan la calibracion y
   cuentan al 100 %, asi que faltarla cambia los macros que ve el cliente.
2. Genericos a 0 de proteina: con 0 no pasan el filtro de la calibracion y no cuentan
   nunca. El caso que trajo el: los pistachos genericos, a 0 teniendo ~20.
3. Duplicados marca/generico: se listan para decidir, NO se borra nada aqui.

Uso:
    python _arreglar_catalogo_0508.py            # solo mira y dice que haria
    python _arreglar_catalogo_0508.py --aplicar  # aplica (guarda backup antes)
"""
import asyncio
import json
import sys
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
from core.database import db

APLICAR = "--aplicar" in sys.argv

# Umbral del filtro de la calibracion: la proteina tiene que superar un tercio de los
# hidratos (cereales y panes). Un proteico de verdad lo supera de sobra; se usa aqui solo
# para no marcar como proteico algo que no lo es.
def es_proteico_de_verdad(a: dict) -> bool:
    p = float(a.get("proteinas") or 0)
    h = float(a.get("hidratos") or 0)
    return p >= 15 and (h == 0 or p > h / 3)


async def cereales_panes_proteicos():
    """Alimentos con 'proteic'/'protein' en el nombre, en categoria 7 u 8, sin 7.1.3 ni 8.8."""
    pendientes = []
    async for a in db.foods.find(
        {"nombre": {"$regex": "proteic|protein|whey", "$options": "i"}},
        {"_id": 0, "id": 1, "nombre": 1, "categorias": 1, "proteinas": 1, "hidratos": 1},
    ):
        cats = [c.strip() for c in str(a.get("categorias") or "").split("|")]
        raiz = cats[0].split(".")[0] if cats else ""
        if raiz not in ("7", "8"):
            continue
        if any(c.startswith("7.1.3") or c.startswith("8.8") for c in cats):
            continue
        if not es_proteico_de_verdad(a):
            continue
        nueva = "7.1.3" if raiz == "7" else "8.8"
        pendientes.append((a, nueva, [nueva if c == cats[0] else c for c in cats]))
    return pendientes


async def genericos_a_cero():
    """Genericos (sin marca = sin url) a 0 de proteina que SI deberian tener, tomando como
    referencia la mediana de los de marca de la misma categoria y palabra clave."""
    casos = []
    async for a in db.foods.find(
        {"proteinas": 0, "categorias": {"$regex": "^17.2|^7|^8|^10"}},
        {"_id": 0, "id": 1, "nombre": 1, "categorias": 1, "proteinas": 1, "url": 1},
    ):
        if a.get("url"):
            continue                      # tiene marca: no es un generico
        clave = a["nombre"].split("(")[0].strip().lower()
        if len(clave) < 4:
            continue
        # Los hermanos tienen que ser el MISMO tipo de alimento: si no, un bombon de
        # chocolate con pistachos entra a votar cuanta proteina tienen los pistachos.
        cat_a = str(a.get("categorias") or "").split("|")[0].strip()
        hermanos = []
        async for b in db.foods.find(
            {"nombre": {"$regex": clave, "$options": "i"}, "proteinas": {"$gt": 0}},
            {"_id": 0, "nombre": 1, "proteinas": 1, "categorias": 1},
        ):
            if str(b.get("categorias") or "").split("|")[0].strip() == cat_a:
                hermanos.append(b)
        if len(hermanos) >= 2:
            # El MAS BAJO de sus equivalentes, no la mediana: pasarse de proteina hace que
            # el alimento cruce el filtro y cuente lo que no lleva. Quedarse corto solo hace
            # que cuente menos, que es el lado seguro del error.
            vals = sorted(float(h["proteinas"]) for h in hermanos)
            casos.append((a, round(vals[0], 1), hermanos))
    return casos


async def duplicados():
    """Mismo alimento dado de alta con marca y sin ella (solo informativo)."""
    grupos = {}
    async for a in db.foods.find(
        {"categorias": {"$regex": "^17.2"}},
        {"_id": 0, "id": 1, "nombre": 1, "proteinas": 1, "url": 1},
    ):
        clave = a["nombre"].split("(")[0].strip().lower()
        grupos.setdefault(clave, []).append(a)
    return {k: v for k, v in grupos.items() if len(v) > 1}


async def main():
    print("=" * 70)
    print("1. CEREALES Y PANES PROTEICOS SIN SU CATEGORIA")
    print("=" * 70)
    prot = await cereales_panes_proteicos()
    for a, nueva, cats in prot:
        print(f"  [{a['id']}] {a['nombre']}")
        print(f"      {a['proteinas']}g proteina · {a['categorias']}  ->  {' | '.join(cats)}")
    if not prot:
        print("  (ninguno)")

    print()
    print("=" * 70)
    print("2. GENERICOS A 0 DE PROTEINA")
    print("=" * 70)
    ceros = await genericos_a_cero()
    for a, mediana, hermanos in ceros:
        print(f"  [{a['id']}] {a['nombre']} ({a['categorias']})  ->  {mediana}g")
        for h in hermanos[:3]:
            print(f"      referencia: {h['nombre']} = {h['proteinas']}g")
    if not ceros:
        print("  (ninguno)")

    print()
    print("=" * 70)
    print("3. DUPLICADOS marca/generico en frutos secos (solo informativo)")
    print("=" * 70)
    for clave, items in sorted((await duplicados()).items()):
        print(f"  {clave}:")
        for i in items:
            print(f"      [{i['id']}] {i['nombre']} · {i['proteinas']}g · {'marca' if i.get('url') else 'generico'}")

    if not APLICAR:
        print("\n(solo lectura: nada tocado. Con --aplicar se aplican 1 y 2, y 3 se deja como esta)")
        return

    sello = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup = f"_backup_catalogo_{sello}.json"
    tocados = [a for a, _, _ in prot] + [a for a, _, _ in ceros]
    with open(backup, "w", encoding="utf-8") as fh:
        json.dump(tocados, fh, ensure_ascii=False, indent=1)
    print(f"\nbackup de los {len(tocados)} documentos afectados -> {backup}")

    for a, nueva, cats in prot:
        await db.foods.update_one({"id": a["id"]}, {"$set": {"categorias": " | ".join(cats)}})
    for a, mediana, _ in ceros:
        await db.foods.update_one({"id": a["id"]}, {"$set": {"proteinas": mediana}})
    print(f"aplicado: {len(prot)} categorias corregidas, {len(ceros)} proteinas rellenadas")

asyncio.run(main())
