"""Mete en la biblioteca las comidas de los menús de ELM (punto 66 del 07-08-2026).

De dónde salen: los 15 menús de la Biblioteca de Menús de la membresía, en
`_menus_elm_pdf.json`. Cada «Comida N» del PDF es una comida autónoma con sus macros
y sus ingredientes, que es justo lo que pide el punto, así que cada una entra como un
menú independiente.

POR QUÉ NO SE PUDO AUTOMATIZAR DEL TODO
---------------------------------------
El documento dice que partir los PDF es mecánico. No lo es: **las tablas del PDF son
imágenes**. PyMuPDF encuentra 4 imágenes por página (el logo y las tablas) y como
texto solo saca los títulos -- «DIETA PROGRAMADA...», «Comida 1» --, ni un
ingrediente ni un macro. Se ven perfectamente en pantalla, pero no hay texto que
extraer porque nunca lo hubo. Se descargaron los 15 PDF, se renderizaron a PNG y se
transcribieron leyéndolos.

Estas comidas van por delante de las de los clientes: son material de Jesús, así que
entran sin pasar el filtro de calidad (que está pensado para lo que monta la gente).

Uso:
    venv/Scripts/python.exe _importar_menus_elm.py            # dry run
    venv/Scripts/python.exe _importar_menus_elm.py --apply
"""
import asyncio
import hashlib
import io
import json
import os
import re
import sys
import unicodedata

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from meal_builder import get_effective_macros_per_100g  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

FUENTE = os.path.join(os.path.dirname(__file__), "_menus_elm_pdf.json")

# Cómo se llama cada comida del PDF en la biblioteca. El intra y el post son «Peri»,
# igual que el resto de la app.
TIPO_COMIDA = {
    "Comida 1": "Comida 1", "Comida 2": "Comida 2",
    "Comida 3": "Comida 3", "Comida 4": "Comida 4",
    "Intraentreno": "Peri", "Postentreno": "Peri",
}

# Los ingredientes vienen en dos formatos:
#   "115g/ml Pan de barra"                          -> 115 g
#   "3ud (25 g/ml) Queso proteico ... (Carrefour)"  -> 3 x 25 = 75 g
RE_GRAMOS = re.compile(r"^([\d.,]+)\s*g/ml\s+(.+)$", re.I)
RE_UNIDADES = re.compile(r"^([\d.,]+)\s*ud\s*\(\s*([\d.,]+)\s*g/ml\s*\)\s*(.+)$", re.I)


def num(s: str) -> float:
    return float(s.replace(",", "."))


def parse_ingrediente(linea: str):
    """Devuelve (cantidad_en_gramos, nombre) o (None, None) si no se entiende."""
    m = RE_UNIDADES.match(linea.strip())
    if m:
        return num(m.group(1)) * num(m.group(2)), m.group(3).strip()
    m = RE_GRAMOS.match(linea.strip())
    if m:
        return num(m.group(1)), m.group(2).strip()
    return None, None


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9%\s]", " ", s)).strip()


PALABRAS_VACIAS = {"de", "del", "la", "el", "los", "las", "con", "y", "o", "al", "a",
                   "en", "un", "una", "por", "sin", "para", "ml", "g", "mas", "buena",
                   "calidad", "tipo"}


def fichas(s: str) -> set:
    return {t for t in norm(s).split() if t not in PALABRAS_VACIAS and len(t) > 2}


def puntuar(buscado: str, food: dict) -> float:
    """Cuánto se parece un alimento del catálogo a lo que pone el PDF."""
    tb, tf = fichas(buscado), fichas(food.get("nombre", ""))
    if not tb or not tf:
        return 0.0
    comunes = tb & tf
    if not comunes:
        return 0.0
    # que estén TODAS las palabras del PDF vale mucho más que compartir alguna
    cobertura = len(comunes) / len(tb)
    precision = len(comunes) / len(tf)
    s = 100 * cobertura + 40 * precision
    if norm(buscado) == norm(food.get("nombre", "")):
        s += 200
    return s


def clasificar_driver(ef: dict) -> str:
    p, h, g = (float(ef.get(k, 0) or 0) for k in ("P", "H", "G"))
    total = p + h + g
    if total <= 0:
        return "mixto"
    if p / total >= 0.8:
        return "proteina_limpia"
    if h / total >= 0.8:
        return "hidrato_limpio"
    if g / total >= 0.8:
        return "grasa_limpia"
    return "mixto"


async def main():
    apply = "--apply" in sys.argv
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "jg12_restored")]
    foods = await db.foods.find({}, {"_id": 0}).to_list(5000)
    print(f"catálogo: {len(foods)} alimentos  |  modo: {'APPLY' if apply else 'DRY RUN'}")

    datos = json.load(io.open(FUENTE, encoding="utf-8"))
    docs, sin_match, flojos = [], [], []

    for menu in datos["menus"]:
        for comida in menu["comidas"]:
            alimentos, tot = [], {"P": 0.0, "H": 0.0, "G": 0.0}
            completa = True
            for linea in comida["ingredientes"]:
                cant, nombre = parse_ingrediente(linea)
                if cant is None:
                    sin_match.append((menu["id"], comida["comida"], linea, "no se entiende"))
                    completa = False
                    continue
                mejor, punt = None, 0.0
                for f in foods:
                    s = puntuar(nombre, f)
                    if s > punt:
                        mejor, punt = f, s
                if not mejor or punt < 60:
                    sin_match.append((menu["id"], comida["comida"], nombre,
                                      f"lo más parecido: {mejor.get('nombre') if mejor else '-'} ({punt:.0f})"))
                    completa = False
                    continue
                if punt < 110:
                    flojos.append((nombre, mejor.get("nombre"), punt))
                ef = get_effective_macros_per_100g(mejor)
                fac = cant / 100.0
                for m in tot:
                    tot[m] += (float(ef.get(m, 0) or 0)) * fac
                alimentos.append({
                    "alimento_id": int(mejor["id"]),
                    "nombre": mejor.get("nombre", nombre),
                    "cantidad_g": round(cant, 1),
                    "driver": clasificar_driver(ef),
                })
            if not completa or len(alimentos) < 2:
                continue
            macros = {m: round(v, 1) for m, v in tot.items()}
            macros["kcal"] = round(tot["P"] * 4 + tot["H"] * 4 + tot["G"] * 9)
            sig = ",".join(str(a["alimento_id"]) for a in sorted(alimentos, key=lambda x: x["alimento_id"]))
            docs.append({
                "id": "ELM" + hashlib.sha1(f"{menu['id']}|{comida['comida']}|{sig}".encode()).hexdigest()[:9].upper(),
                "alimento_ids": sorted({a["alimento_id"] for a in alimentos}),
                "alimentos": alimentos,
                "macros": macros,
                # Lo que dice el PDF, para poder comparar con lo que sale del motor.
                "macros_pdf": comida.get("macros"),
                "tipo_comida": TIPO_COMIDA.get(comida["comida"], "Comida 2"),
                "tipo": "peri" if TIPO_COMIDA.get(comida["comida"]) == "Peri" else "comida",
                "n_alimentos": len(alimentos),
                "fuente": "elm_menus",
                "origen": "jesus",
                # Material de Jesús: entra sin pasar el filtro de calidad, que está
                # pensado para lo que montan los clientes.
                "calidad": {"pasa": True, "motivo": "menu_de_jesus"},
                "usos": 0, "clientes": 0, "usos_calma": 0,
                "menu": {"id": menu["id"], "nombre": menu["nombre"],
                         "comida": comida["comida"], "tipo_dia": menu["tipo_dia"],
                         "fuente": menu["fuente"]},
            })

    print(f"\ncomidas en el fichero: {sum(len(m['comidas']) for m in datos['menus'])}")
    print(f"comidas listas para entrar: {len(docs)}")
    print(f"ingredientes que no casan: {len(sin_match)}")
    for mid, com, ing, motivo in sin_match:
        print(f"   [{mid} {com}] {ing[:52]:52} -> {motivo}")
    if flojos:
        print(f"\nmatches flojos ({len(flojos)}), conviene mirarlos:")
        for buscado, encontrado, s in sorted(flojos, key=lambda x: x[2])[:15]:
            print(f"   {buscado[:44]:44} -> {encontrado[:44]:44} ({s:.0f})")

    # ¿Cuadran los macros del PDF con los que calcula nuestro motor?
    print("\ncomparación de macros (PDF vs motor):")
    desviados = 0
    for d in docs:
        pdf = d.get("macros_pdf") or {}
        if not pdf.get("P"):
            continue
        dif = max(abs(float(str(pdf.get(m, 0)).replace(",", ".")) - d["macros"][m])
                  for m in ("P", "H", "G") if pdf.get(m) is not None)
        if dif > 8:
            desviados += 1
    print(f"   se desvían más de 8 g en algún macro: {desviados} de {len(docs)}")

    if not apply:
        print("\nDRY RUN: no se ha escrito nada. Pasa --apply para meterlos.")
        return

    await db.meal_library.delete_many({"fuente": "elm_menus"})
    if docs:
        await db.meal_library.insert_many(docs)
    print(f"\nmetidos: {len(docs)}")
    print(f"biblioteca ahora: {await db.meal_library.count_documents({})}")


if __name__ == "__main__":
    asyncio.run(main())
