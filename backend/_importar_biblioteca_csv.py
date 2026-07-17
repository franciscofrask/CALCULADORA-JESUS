"""Importa la BIBLIOTECA DE MENÚS (CSV de 271k comidas reales) a db.meal_library.

Sustituye el contenido anterior de la colección (los 1.162 menús de la fase 1
de pruebas). Son menús REALES ya cuadrados con el método, minados de dietas de
clientes; el sugeridor los ofrece por cercanía al objetivo SIN reescalarlos.

Formato CSV: origen,tipo,P_metodo,H_metodo,G_metodo,P_real,H_real,G_real,veces,alimentos
  - tipo: "Comida 1".."Comida 4" | "Peri"
  - alimentos: "Nombre (Marca) (255 g) + Otro (2 ud) + ..." (cantidad SIEMPRE al final)

Reglas de importación:
  - Se excluyen filas con cantidades ilegibles (p.ej. "(.620 g)", ruido de registro).
  - Se excluyen menús con más de 9 alimentos (volcados de día entero, no comidas).
  - Cada alimento se matchea por NOMBRE exacto (normalizado) contra db.foods:
    si algún alimento del menú ya no existe en el catálogo, el menú se descarta.
  - "N ud" -> cantidad_g = N * racion del alimento (y se guarda unidades_n para mostrar).
  - Los macros método ('macros') se RECALCULAN con el motor actual de la app
    (calma_suggest: regla 25% + _ajuste), NO se copian del CSV: así el filtro, la
    tarjeta del sugeridor y lo que suma la comida al volcar coinciden SIEMPRE.
    Los del CSV se guardan en 'macros_csv' como referencia; los reales (etiqueta)
    en 'macros_reales'.
  - Campos compat con el flujo del coach (buscar_en_biblioteca): tipo comida/peri,
    alimento_ids, driver por alimento, usos.

Uso: ./venv/Scripts/python.exe _importar_biblioteca_csv.py [--apply] [--csv RUTA] [--min-veces N]
     (sin --apply: dry run con estadísticas, no escribe nada)

--min-veces N: importa solo menús de clientes usados N+ veces (las variantes tienen
veces=0 y quedan fuera). Para el Atlas dev (M0, 512MB) usar --min-veces 3 (~24k menús):
la biblioteca COMPLETA no cabe con el resto de datos. En prod (VPS, Mongo local sin
cuota) ejecutar sin --min-veces para importar los 266k.
"""
import asyncio
import csv
import hashlib
import os
import re
import sys
import unicodedata
from collections import Counter
from datetime import datetime, timezone

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

CSV_DEFAULT = os.path.join(os.path.dirname(__file__), "_biblioteca_menus_fuente.csv")
MAX_ALIMENTOS = 9
TIPOS_VALIDOS = {"Comida 1", "Comida 2", "Comida 3", "Comida 4", "Peri"}

# "Nombre lo que sea (con paréntesis) (255 g)" / "... (2 ud)" - cantidad al final
QTY_PAT = re.compile(r"^(.*\S)\s\((\d+(?:[.,]\d+)?)\s*(g|ud)\)$")


def norm_name(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip().lower()


def clasificar_driver(ef: dict) -> str:
    """Mismo criterio que la fase 1 (_minar_biblioteca_menus): driver de ajuste limpio."""
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
    csv_path = CSV_DEFAULT
    if "--csv" in sys.argv:
        csv_path = sys.argv[sys.argv.index("--csv") + 1]
    min_veces = 0
    if "--min-veces" in sys.argv:
        min_veces = int(sys.argv[sys.argv.index("--min-veces") + 1])

    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]

    import copy as _copy

    from calma_suggest import aplicar_regla_macros, macros_at
    from meal_builder import get_effective_macros_per_100g

    # Motor de la app: copia del alimento con la regla de macros aplicada (cacheada
    # por id; macros_at aplica el _ajuste dependiente de cantidad en cada llamada)
    regla_cache = {}

    def macros_efectivos_item(food: dict, cantidad_g: float) -> dict:
        fid = int(food["id"])
        if fid not in regla_cache:
            fc = _copy.deepcopy(food)
            aplicar_regla_macros(fc)
            regla_cache[fid] = fc
        fc = regla_cache[fid]
        es_unidad = bool(food.get("unidades"))
        racion = float(food.get("racion") or 100) or 100.0
        cant = (cantidad_g / racion) if es_unidad else cantidad_g
        return macros_at(fc, cant)  # {proteinas, hidratos, grasas}

    # Catálogo por nombre normalizado
    foods_by_name = {}
    duplicados = 0
    async for f in db.foods.find({}, {"_id": 0}):
        if f.get("id") is None or not f.get("nombre"):
            continue
        key = norm_name(f["nombre"])
        if key in foods_by_name:
            duplicados += 1
            continue  # nombre duplicado: se queda el primero (determinista por orden natural)
        foods_by_name[key] = f
    print(f"catálogo: {len(foods_by_name)} nombres únicos ({duplicados} duplicados) | modo: {'APPLY' if apply else 'DRY RUN'}")

    drivers_cache = {}  # alimento_id -> driver

    stats = Counter()
    unmatched = Counter()
    docs = []
    vistos = set()

    with open(csv_path, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            stats["filas"] += 1
            tipo_comida = (row.get("tipo") or "").strip()
            if tipo_comida not in TIPOS_VALIDOS:
                stats["tipo_invalido"] += 1
                continue
            if min_veces and int(float(row.get("veces") or 0)) < min_veces:
                stats["bajo_min_veces"] += 1
                continue

            piezas = [p.strip() for p in (row.get("alimentos") or "").split(" + ") if p.strip()]
            if not piezas:
                stats["sin_alimentos"] += 1
                continue
            if len(piezas) > MAX_ALIMENTOS:
                stats["demasiados_alimentos"] += 1
                continue

            alimentos, ok = [], True
            tot = {"P": 0.0, "H": 0.0, "G": 0.0}
            for pieza in piezas:
                m = QTY_PAT.match(pieza)
                if not m:
                    stats["cantidad_ilegible"] += 1
                    ok = False
                    break
                nombre, cant_str, unidad = m.group(1), m.group(2).replace(",", "."), m.group(3)
                food = foods_by_name.get(norm_name(nombre))
                if not food:
                    unmatched[nombre] += 1
                    ok = False
                    break
                cant = float(cant_str)
                item = {"alimento_id": int(food["id"]), "nombre": food["nombre"]}
                if unidad == "ud":
                    racion = float(food.get("racion") or 100) or 100.0
                    item["cantidad_g"] = round(cant * racion, 1)
                    item["unidades_n"] = cant if cant % 1 else int(cant)
                else:
                    item["cantidad_g"] = round(cant, 1)
                if item["cantidad_g"] <= 0:
                    stats["cantidad_cero"] += 1
                    ok = False
                    break
                fid = item["alimento_id"]
                if fid not in drivers_cache:
                    drivers_cache[fid] = clasificar_driver(get_effective_macros_per_100g(food))
                item["driver"] = drivers_cache[fid]
                ef = macros_efectivos_item(food, item["cantidad_g"])
                tot["P"] += ef["proteinas"]
                tot["H"] += ef["hidratos"]
                tot["G"] += ef["grasas"]
                alimentos.append(item)
            if not ok:
                stats["menus_descartados"] += 1
                continue

            firma = "|".join(f"{a['alimento_id']}:{a['cantidad_g']}" for a in
                             sorted(alimentos, key=lambda x: x["alimento_id"])) + "|" + tipo_comida
            mid = hashlib.sha1(firma.encode()).hexdigest()[:16]
            if mid in vistos:
                stats["duplicado_exacto"] += 1
                continue
            vistos.add(mid)

            docs.append({
                "id": mid,
                "tipo_comida": tipo_comida,
                "tipo": "peri" if tipo_comida == "Peri" else "comida",  # compat coach
                "origen": (row.get("origen") or "cliente").strip(),
                "veces": int(float(row.get("veces") or 0)),
                "usos": int(float(row.get("veces") or 0)),  # compat coach
                "clientes": 0,  # el CSV no trae clientes distintos
                # macros método RECALCULADOS con el motor actual (fuente de verdad)
                "macros": {"P": round(tot["P"], 1), "H": round(tot["H"], 1), "G": round(tot["G"], 1)},
                # macros método tal cual venían en el CSV (solo referencia)
                "macros_csv": {"P": float(row["P_metodo"]), "H": float(row["H_metodo"]), "G": float(row["G_metodo"])},
                "macros_reales": {"P": float(row["P_real"]), "H": float(row["H_real"]), "G": float(row["G_real"])},
                "alimentos": alimentos,
                "alimento_ids": sorted({a["alimento_id"] for a in alimentos}),
                "n_alimentos": len(alimentos),
                "fuente": "clientes",
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            stats["importables"] += 1
            drift = max(abs(tot["P"] - float(row["P_metodo"])),
                        abs(tot["H"] - float(row["H_metodo"])),
                        abs(tot["G"] - float(row["G_metodo"])))
            if drift <= 1.0:
                stats["motor_coincide_csv_1g"] += 1
            elif drift > 5.0:
                stats["motor_difiere_csv_5g"] += 1

    print("\n== Estadísticas ==")
    for k, v in stats.most_common():
        print(f"  {k}: {v}")
    print(f"  alimentos no encontrados (nombres distintos): {len(unmatched)}")
    for nombre, n in unmatched.most_common(15):
        print(f"    {n:>6}x  {nombre}")

    por_tipo = Counter(d["tipo_comida"] for d in docs)
    print(f"\n  por tipo: {dict(por_tipo)}")

    if not apply:
        print("\nDRY RUN: no se ha escrito nada. Ejecuta con --apply para importar.")
        return

    print(f"\nBorrando meal_library actual y escribiendo {len(docs)} menús...")
    await db.meal_library.delete_many({})
    BATCH = 5000
    for i in range(0, len(docs), BATCH):
        await db.meal_library.insert_many(docs[i:i + BATCH])
        print(f"  {min(i + BATCH, len(docs))}/{len(docs)}")

    await db.meal_library.create_index([("tipo_comida", 1), ("macros.P", 1), ("macros.H", 1), ("macros.G", 1)])
    await db.meal_library.create_index([("tipo", 1), ("macros.P", 1), ("macros.H", 1), ("macros.G", 1)])
    await db.meal_library.create_index([("alimento_ids", 1)])
    await db.meal_library.create_index([("id", 1)], unique=True)
    total = await db.meal_library.count_documents({})
    print(f"HECHO: {total} menús en db.meal_library con índices.")


if __name__ == "__main__":
    asyncio.run(main())
