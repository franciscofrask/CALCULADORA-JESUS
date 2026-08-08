"""Trae la foto de cada receta del recetario (bloque J del documento del 07-08-2026).

El documento lo dice en la sección «Las fotos»: «Las 103 del recetario ya vienen con
foto». Vienen, sí -- pero la importación de julio no se las trajo, así que en el
sugeridor cada receta salía como una lista de ingredientes en texto pelado.

De dónde salen: la REST de WordPress no da los macros ni los ingredientes, pero
**la foto sí**. Cada receta trae `featured_media`, y con ese id se pide
`/wp-json/wp/v2/media/<id>`, que devuelve la URL y los tamaños. Las dos peticiones
funcionan sin sesión, y las imágenes son públicas (HTTP 200 desde fuera).

Se guarda la URL, no el fichero. Son fotos de Jesús servidas por su web, ya están
en webp y pesan unos 90 KB: descargarlas serían 9 MB más dentro de Mongo, que es
justo el problema que ya tenemos con las fotos de los clientes.

Uso:
    venv/Scripts/python.exe _traer_fotos_recetario.py            # solo mira
    venv/Scripts/python.exe _traer_fotos_recetario.py --apply    # guarda
"""
import asyncio
import json
import os
import sys
import urllib.request

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

API = "https://noteconformesconmenos.com/wp-json/wp/v2"


def pedir(url: str):
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def slug_de(url: str) -> str:
    return (url or "").rstrip("/").rsplit("/", 1)[-1]


async def main():
    apply = "--apply" in sys.argv
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "jg12_restored")]

    recetas, pagina = [], 1
    while True:
        lote = pedir(f"{API}/recetas?per_page=100&page={pagina}")
        if not lote:
            break
        recetas += lote
        if len(lote) < 100:
            break
        pagina += 1
    print(f"recetas en la web: {len(recetas)}  |  modo: {'APPLY' if apply else 'SOLO MIRAR'}")

    # media_id -> urls, pidiendo cada foto una sola vez
    fotos, sin_foto = {}, []
    for r in recetas:
        mid = r.get("featured_media")
        if not mid:
            sin_foto.append(r["slug"])
            continue
        if mid in fotos:
            continue
        try:
            m = pedir(f"{API}/media/{mid}")
        except Exception as e:
            print(f"   !! no se pudo leer la foto {mid} de {r['slug']}: {e}")
            continue
        tam = (m.get("media_details") or {}).get("sizes") or {}
        fotos[mid] = {
            # 'medium' es la de las tarjetas del sugeridor; 'full' por si algún día
            # se abre la receta a pantalla completa.
            "foto": (tam.get("medium") or {}).get("source_url") or m.get("source_url"),
            "foto_grande": m.get("source_url"),
        }

    print(f"fotos distintas encontradas: {len(fotos)}")
    if sin_foto:
        print(f"recetas SIN foto en la web: {len(sin_foto)}")
        for s in sin_foto:
            print(f"   - {s}")

    por_slug = {r["slug"]: fotos.get(r.get("featured_media")) for r in recetas}
    plantillas = await db.menu_templates.find({}, {"_id": 0, "id": 1, "fuente": 1, "nombre": 1}).to_list(None)

    ops, sin_casar = [], []
    for p in plantillas:
        f = por_slug.get(slug_de(p.get("fuente")))
        if not f or not f.get("foto"):
            sin_casar.append(p["nombre"])
            continue
        ops.append((p["id"], f))

    print(f"\nplantillas: {len(plantillas)}")
    print(f"   se les pone foto : {len(ops)}")
    print(f"   se quedan sin ella: {len(sin_casar)}")
    for n in sin_casar[:10]:
        print(f"      - {n[:64]}")

    if not apply:
        print("\nNo se ha escrito nada. Pasa --apply para guardar.")
        return

    from pymongo import UpdateOne
    await db.menu_templates.bulk_write(
        [UpdateOne({"id": pid}, {"$set": f}) for pid, f in ops], ordered=False)
    con = await db.menu_templates.count_documents({"foto": {"$exists": True}})
    print(f"\nguardado. plantillas con foto: {con} de {len(plantillas)}")


if __name__ == "__main__":
    asyncio.run(main())
