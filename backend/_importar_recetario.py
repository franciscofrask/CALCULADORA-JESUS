"""Importa las recetas del recetario ELM (scrapeadas en _recetario_scrape.json)
como menus preestablecidos en db.menu_templates.

- Dry run (por defecto): imprime clasificacion, matching de ingredientes y avisos.
- Con --apply: inserta los menus en la base de datos.

Cada receta se convierte en: nombre, momento(s), items [{rol, buscar, categoria,
proporcion, alimento_id}]. Los platos principales se duplican en comida y cena
(decision del usuario 2026-07-10). Las cantidades exactas de la web no se guardan
como gramos: el motor de "Sugiéreme un menú" autoajusta cantidades a los macros
del usuario; se guarda la receta original en `fuente` y `ingredientes_web`.
"""
import asyncio
import json
import os
import re
import sys
import unicodedata
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from calculator import get_categoria_principal  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

SCRAPE = os.path.join(os.path.dirname(__file__), "_recetario_scrape.json")

# ---- Clasificacion por momento (indice en _recetario_scrape.json) ----
DESAYUNO = {1, 16, 20, 21, 23, 26, 30, 34, 39, 43, 46, 48, 53, 57, 59, 61, 63,
            68, 70, 71, 74, 75, 78, 79, 84, 96, 97, 98}
MERIENDA = {15, 22, 27, 29, 33, 35, 38, 40, 41, 44, 55, 66, 69, 72, 80, 88, 92}
# El resto: plato principal -> se duplica en comida y cena


def momentos_de(idx: int) -> list:
    if idx in DESAYUNO:
        return ["desayuno"]
    if idx in MERIENDA:
        return ["merienda"]
    return ["comida", "cena"]


# ---- Normalizacion / parsing de ingredientes ----
STOP = {"de", "del", "la", "el", "los", "las", "con", "y", "o", "al", "a", "en",
        "un", "una", "unos", "unas", "para", "tipo", "estilo", "sabor"}

UNIDADES = (r"g|gr|kg|ml|l|cl|ud|uds|unidad(?:es)?|rebanada(?:s)?|lata(?:s)?|"
            r"cucharada(?:s)?(?:\s+sopera(?:s)?)?|cucharadita(?:s)?|"
            r"puñado(?:s)?|scoop(?:s)?|sobre(?:s)?|loncha(?:s)?|filete(?:s)?|"
            r"perla(?:s)?|bote(?:s)?|vaso(?:s)?|taza(?:s)?|barrita(?:s)?|"
            r"tortita(?:s)?|hoja(?:s)?|dado(?:s)?|pieza(?:s)?|tarrina(?:s)?|"
            r"yogur(?:es)?|hamburguesa(?:s)?|huevo(?:s)?|tostada(?:s)?|wrap(?:s)?")

RE_QTY = re.compile(
    r"^\s*(?:media|medio|½|\d+[\d.,/]*)\s*(?:(" + UNIDADES + r")\b\.?)?\s*(?:de\s+)?",
    re.IGNORECASE,
)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s.lower()).strip()


def singular(tok: str) -> str:
    if len(tok) > 4 and tok.endswith("es") and not tok.endswith("les"):
        return tok[:-2]
    if len(tok) > 3 and tok.endswith("s"):
        return tok[:-1]
    return tok


def tokens_of(s: str) -> set:
    return {singular(t) for t in re.findall(r"[a-z0-9%]+", norm(s)) if t not in STOP and len(t) > 1}


def parse_ing(line: str):
    """'180g de patata natural' -> (nombre_limpio, marca, texto_original)"""
    original = line.strip()
    # marca / nota entre parentesis (puede haber varias)
    parens = re.findall(r"\(([^)]*)\)", original)
    marca = parens[-1].strip() if parens else ""
    if re.match(r"talla\s", marca, re.IGNORECASE):
        marca = ""
    base = re.sub(r"\([^)]*\)", " ", original)
    m = RE_QTY.match(base)
    unidad_como_nombre = ""
    if m:
        # si la "unidad" era en realidad el alimento (2 huevos, 1 yogur, 3 tortitas)
        u = (m.group(1) or "").lower()
        if u and singular(u) in {"huevo", "yogur", "hamburguesa", "tostada", "wrap", "tortita", "barrita"}:
            unidad_como_nombre = u
        base = base[m.end():]
    nombre = re.sub(r"\s+", " ", base).strip(" .,-")
    if unidad_como_nombre and unidad_como_nombre not in norm(nombre):
        nombre = (unidad_como_nombre + " " + nombre).strip()
    return nombre, marca, original


# ---- Rol por categoria (top-level) con fallback por macros ----
CAT_ROL = {
    # nota: lacteos (5) NO se fuerzan a proteina; se decide por macros
    # (nata/queso graso -> grasa, yogur/queso fresco -> proteina, leche -> hidrato)
    "1": "proteina", "2": "proteina", "3": "proteina", "4": "proteina",
    "6": "proteina", "40": "proteina", "45": "proteina",
    "7": "hidrato", "8": "hidrato", "9": "hidrato", "10": "hidrato",
    "11": "hidrato", "13": "hidrato", "14": "hidrato", "15": "hidrato",
    "18": "hidrato", "21": "hidrato", "22": "hidrato", "25": "hidrato",
    "26": "hidrato", "37": "hidrato", "46": "hidrato",
    "17": "grasa", "38": "grasa", "42": "grasa",
}


def rol_de(food: dict, categoria: str) -> str:
    top = (categoria or "").split(".")[0]
    if top in CAT_ROL:
        return CAT_ROL[top]
    p = float(food.get("proteinas") or 0)
    h = float(food.get("hidratos") or 0)
    g = float(food.get("grasas") or 0)
    if g >= 12 and p < 10:
        return "grasa"
    if p >= 8 and p >= h:
        return "proteina"
    return "hidrato"


# Lineas de condimentos / opcionales que no aportan macros relevantes: se omiten.
RE_SKIP = re.compile(r"\bal gusto\b|\bopcional(es)?\b|^\s*(sal|pimienta|vinagre|especias|agua|hielo)\b",
                     re.IGNORECASE)

# Overrides manuales: ingrediente (normalizado, contiene) -> nombre exacto en db.foods
MANUAL_MATCH = {
    "aceite de oliva": "Aceite de oliva virgen extra una cucharadita de café",
    "queso mozzarella bajo en grasa": "Mozzarella light (Hacendado)",
    "espaguetis de konjac": "Spaguetis de konjac (Clean Foods)",
}


# ---- Matching contra db.foods ----
def score_food(ing_norm: str, ing_toks: set, marca: str, food: dict) -> float:
    fname = norm(food.get("nombre") or "")
    ftoks = tokens_of(fname)
    if not ftoks or not ing_toks:
        return 0
    inter = ing_toks & ftoks
    if not inter:
        return 0
    s = 0.0
    s += 40 * len(inter)
    s -= 20 * len(ing_toks - ftoks)          # tokens del ingrediente que faltan
    s -= 4 * len(ftoks - ing_toks)           # ruido extra en el nombre del alimento
    if ing_norm and ing_norm in fname:
        s += 90
    if ing_norm and fname.startswith(ing_norm):
        s += 70                              # 'aceite de oliva...' gana a 'caballa en aceite de oliva'
    if fname.split(" (")[0] in ing_norm:
        s += 60
    if marca and norm(marca) in fname:
        s += 50
    tags = food.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    if "GEN" in tags:
        s += 15
    return s


async def main():
    apply = "--apply" in sys.argv
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]

    foods = await db.foods.find({}, {"_id": 0}).to_list(5000)
    print(f"foods en db: {len(foods)}  |  modo: {'APPLY' if apply else 'DRY RUN'}\n")

    recetas = json.load(open(SCRAPE, encoding="utf-8"))
    docs, avisos = [], []

    for idx, rec in enumerate(recetas):
        titulo = rec["titulo"].strip()
        items, sin_match = [], []
        grasa_puesta = False
        for line in rec["ings"]:
            if RE_SKIP.search(line):
                continue  # condimento / opcional: no forma parte del menu
            nombre, marca, original = parse_ing(line)
            if not nombre:
                sin_match.append(original)
                continue
            ing_norm, ing_toks = norm(nombre), tokens_of(nombre)
            best, best_s = None, 0.0
            override = next((v for k, v in MANUAL_MATCH.items() if k in ing_norm), None)
            if override:
                best = next((f for f in foods if f.get("nombre") == override), None)
                best_s = 999
            if not best:
                for f in foods:
                    s = score_food(ing_norm, ing_toks, marca, f)
                    if s > best_s:
                        best, best_s = f, s
            if not best or best_s < 55:
                sin_match.append(original)
                continue
            categoria = get_categoria_principal(best) or ""
            rol = rol_de(best, categoria)
            prop = 1.0
            if rol == "grasa" and not grasa_puesta:
                prop, grasa_puesta = "ajuste", True
            items.append({
                "rol": rol, "buscar": best.get("nombre", nombre), "categoria": categoria,
                "proporcion": prop, "alimento_id": best.get("id"),
                "_match": f"{original}  ->  {best.get('nombre')} [{best_s:.0f}] rol={rol}",
            })
        if not items:
            avisos.append(f"SIN ITEMS: {titulo}")
            continue
        for momento in momentos_de(idx):
            docs.append({
                "id": "M" + uuid.uuid4().hex[:8].upper(),
                "nombre": titulo, "momento": momento,
                "min_kcal": 0.0, "max_kcal": 99999.0,
                "tags": ["recetario"],
                "items": [{k: v for k, v in it.items() if k != "_match"} for it in items],
                "origen": "custom",
                "created_by": "import_recetario",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "fuente": rec.get("url"),
                "macros_web": {"P": rec.get("P"), "H": rec.get("H"), "G": rec.get("G")},
                "ingredientes_web": rec.get("ings"),
            })
        print(f"[{idx}] {titulo}  ->  {'+'.join(momentos_de(idx))}")
        for it in items:
            print("     ", it["_match"])
        for s in sin_match:
            print("      !! SIN MATCH:", s)
            avisos.append(f"{titulo}: sin match -> {s}")
        print()

    print("=" * 70)
    print(f"menus a crear: {len(docs)}  (recetas: {len(recetas)})")
    print(f"avisos: {len(avisos)}")
    for a in avisos:
        print("  -", a)

    if apply and docs:
        res = await db.menu_templates.insert_many([dict(d) for d in docs])
        print(f"\nINSERTADOS: {len(res.inserted_ids)}")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
