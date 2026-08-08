"""Mira qué recetas hay en el recetario web y da de alta las que nos falten.

Punto 65 del documento del 07-08-2026. El recetario se importó entero el 10-07 (99
de las 103), pero desde entonces Jesús ha publicado más y la app no se entera. Esto
lo compara y avisa.

CÓMO SE SACA EL CONTENIDO, Y POR QUÉ NO SALE SOLO
------------------------------------------------
La REST de WordPress sí da la LISTA (`/wp-json/wp/v2/recetas`, 103 con su id,
título, enlace y foto), y para eso se usa aquí. Lo que NO da son los macros ni los
ingredientes: son campos de JetEngine que no están marcados como visibles en REST.
Comprobado -- una receta de la API trae exactamente esto:

    ['author', 'date', 'dificultad', 'featured_media', 'id', 'link', 'slug',
     'status', 'template', 'tipo-de-comida', 'title', 'type']

Ni `meta`, ni `acf`, ni `content`. Y las páginas están detrás de la membresía, así
que pedirlas sin sesión devuelve vacío.

Mientras eso siga así, el contenido de las recetas nuevas se pega a mano en
`_recetario_nuevas.json` (se saca de la página con la sesión abierta). En cuanto
marquen esos campos como visibles en REST -- es un rato de trabajo en WordPress --,
este script puede tirar de la API y dejar de necesitar el fichero.

Uso:
    venv/Scripts/python.exe _sincronizar_recetario.py            # solo compara
    venv/Scripts/python.exe _sincronizar_recetario.py --apply    # da de alta
"""
import asyncio
import json
import os
import sys
import urllib.request
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from _importar_recetario import (  # noqa: E402
    MANUAL_MATCH, RE_SKIP, norm, parse_ing, rol_de, score_food, tokens_of,
)
from calculator import get_categoria_principal  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

API = "https://noteconformesconmenos.com/wp-json/wp/v2/recetas"
NUEVAS = os.path.join(os.path.dirname(__file__), "_recetario_nuevas.json")


def slug_de(url: str) -> str:
    return (url or "").rstrip("/").rsplit("/", 1)[-1]


def recetas_de_la_web():
    """La lista completa, paginando. Esto sí lo da la API sin sesión."""
    out, pagina = [], 1
    while True:
        with urllib.request.urlopen(f"{API}?per_page=100&page={pagina}", timeout=60) as r:
            lote = json.load(r)
        if not lote:
            break
        out += lote
        if len(lote) < 100:
            break
        pagina += 1
    return out


def resolver_items(rec: dict, foods: list) -> tuple:
    """Convierte los ingredientes escritos en alimentos del catálogo."""
    items, sin_match = [], []
    grasa_puesta = False
    for line in rec["ings"]:
        if RE_SKIP.search(line):
            continue  # condimento u opcional: no forma parte del menú
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
    return items, sin_match


async def main():
    apply = "--apply" in sys.argv
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "jg12_restored")]

    web = recetas_de_la_web()
    slugs_web = {r["slug"]: r for r in web}
    print(f"recetas en el recetario web: {len(web)}  |  modo: {'APPLY' if apply else 'SOLO COMPARAR'}")

    nuestras = await db.menu_templates.find({}, {"_id": 0, "fuente": 1, "nombre": 1}).to_list(None)
    slugs_nuestros = {slug_de(m.get("fuente")) for m in nuestras if m.get("fuente")}
    print(f"plantillas nuestras: {len(nuestras)} ({len(slugs_nuestros)} recetas distintas)")

    faltan = [s for s in slugs_web if s not in slugs_nuestros]
    sobran = [s for s in slugs_nuestros if s and s not in slugs_web]
    print(f"\nnos faltan {len(faltan)} recetas:")
    for s in faltan:
        print(f"   - {slugs_web[s]['title']['rendered'][:64]}  ({s})")
    if sobran:
        print(f"\ntenemos {len(sobran)} que ya no están en la web (¿borradas?):")
        for s in sobran:
            print(f"   - {s}")

    # Solo 4 de las 103 tienen puesta la taxonomía «tipo de comida» en WordPress. El
    # momento de las nuestras lo pusimos al importar y aquí se decide igual: por lo
    # que es el plato, siguiendo el criterio ya usado en las 99 (toda «tostada» y
    # todo «bol proteico» son desayuno; los platos de proteína, arroz y verdura van a
    # comida y cena).
    con_taxonomia = [r for r in web if r.get("tipo-de-comida")]
    print(f"\nrecetas con «tipo de comida» puesto en WordPress: {len(con_taxonomia)} de {len(web)}")

    if not faltan:
        print("\nNo falta ninguna receta.")
        return

    contenido = {}
    if os.path.exists(NUEVAS):
        for rec in json.load(open(NUEVAS, encoding="utf-8")):
            contenido[slug_de(rec["url"])] = rec

    sin_contenido = [s for s in faltan if s not in contenido]
    if sin_contenido:
        print(f"\nDe las que faltan, {len(sin_contenido)} no tienen contenido en "
              f"_recetario_nuevas.json y no se pueden dar de alta:")
        for s in sin_contenido:
            print(f"   - https://noteconformesconmenos.com/recetas/{s}/")

    foods = await db.foods.find({}, {"_id": 0}).to_list(5000)
    docs, avisos = [], []
    for s in faltan:
        rec = contenido.get(s)
        if not rec:
            continue
        items, sin_match = resolver_items(rec, foods)
        if not items:
            avisos.append(f"SIN ITEMS: {rec['titulo']}")
            continue
        print(f"\n{rec['titulo']}  ->  {' + '.join(rec['momentos'])}")
        for it in items:
            print("     ", it["_match"])
        for x in sin_match:
            print("      !! SIN MATCH:", x)
            avisos.append(f"{rec['titulo']}: sin match -> {x}")
        for momento in rec["momentos"]:
            docs.append({
                "id": "M" + uuid.uuid4().hex[:8].upper(),
                "nombre": rec["titulo"], "momento": momento,
                "min_kcal": 0.0, "max_kcal": 99999.0,
                "tags": ["recetario"],
                "items": [{k: v for k, v in it.items() if k != "_match"} for it in items],
                "origen": "custom",
                "created_by": "sincronizar_recetario",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "fuente": rec["url"],
                "macros_web": {"P": rec.get("P"), "H": rec.get("H"), "G": rec.get("G")},
                "ingredientes_web": rec.get("ings"),
            })

    print(f"\n{'=' * 70}\nplantillas a crear: {len(docs)}  |  avisos: {len(avisos)}")
    for a in avisos:
        print("   ", a)

    if not apply:
        print("\nNo se ha escrito nada. Pasa --apply para dar de alta.")
        return
    if docs:
        await db.menu_templates.insert_many(docs)
        print(f"\naltas hechas: {len(docs)}")
        print(f"plantillas ahora: {await db.menu_templates.count_documents({})}")


if __name__ == "__main__":
    asyncio.run(main())
