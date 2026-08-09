# -*- coding: utf-8 -*-
"""
Trae a DEV los datos de PRODUCCION con los que hace falta reproducir cosas.

Por que existe: la biblioteca de menus tiene 266.170 comidas en produccion y 23.902 en dev,
asi que el sugeridor da resultados distintos en cada sitio y los fallos que reporta Jesus no
se pueden reproducir aqui. Igual con el recetario y con las dietas.

    Necesita el tunel abierto (ver _internos_proceso/tocar_datos_de_produccion.md):
    ssh -i ~/.ssh/id_ed25519_jg12 -N -L 27018:127.0.0.1:27017 root@s1.jesusgallegopt.com

    python _traer_datos_de_prod.py            # solo dice lo que haria
    python _traer_datos_de_prod.py --hazlo    # lo hace

LA DIRECCION IMPORTA Y SOLO VA EN UN SENTIDO: PRODUCCION -> DEV.

El origen se lee de `PROD_MONGO_URL` (el tunel) y el destino de `MONGO_URL` (el .env de
dev, que apunta a Atlas). Antes de escribir nada se comprueba que no son la misma base y que
el destino NO es el tunel, porque el accidente que hay que evitar aqui no es equivocarse de
coleccion: es escribir en produccion creyendo que escribes en dev.

QUE SE TRAE Y QUE NO

Se trae lo que hace falta para reproducir, y nada mas:

    meal_library     la biblioteca de comidas de clientes (el motivo de todo esto)
    menu_templates   el recetario de Jesus
    foods            el catalogo
    diets            las dietas guardadas

NO se traen `users`, `client_profiles`, `payments` ni `client_photos`. Las dos primeras
porque dev ya tiene su copia y son la identidad de la gente; las fotos porque son 902 MB y
no hacen falta para nada de esto.

Las dietas SI llevan datos de clientes reales (que comio quien y que dia). Vienen porque son
la unica forma de reproducir lo de las cantidades y lo del dia compartido, y porque las pidio
Francisco el 09-08. Van sin nombre ni correo: lo unico que las identifica es un `user_id` que
en dev ya existe.
"""
import asyncio
import os
import sys

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

# El destino sale del .env de dev. Se carga aqui a proposito y NO se toca `PROD_MONGO_URL`,
# que tiene que venir del entorno: asi el origen hay que ponerlo a mano cada vez y no puede
# quedarse escrito en ningun fichero.
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

HAZLO = "--hazlo" in sys.argv

COLECCIONES = [
    ("meal_library", "la biblioteca de comidas de clientes"),
    ("menu_templates", "el recetario de Jesus"),
    ("foods", "el catalogo de alimentos"),
    ("diets", "las dietas guardadas"),
]

# De 1.000 en 1.000: por el tunel, lotes mas grandes se quedan colgados.
LOTE = 1000


async def main():
    origen_url = os.environ.get("PROD_MONGO_URL") or "mongodb://localhost:27018"
    destino_url = os.environ.get("MONGO_URL")
    base = os.environ.get("DB_NAME", "jg12_restored")

    if not destino_url:
        print("Falta MONGO_URL (el destino, dev). Sale del .env.")
        return
    if "27018" in destino_url:
        print("EL DESTINO ES EL TUNEL. Eso es produccion. No se escribe nada.")
        return
    if origen_url == destino_url:
        print("Origen y destino son la misma base. No se escribe nada.")
        return

    prod = AsyncIOMotorClient(origen_url, serverSelectionTimeoutMS=15000)[base]
    dev = AsyncIOMotorClient(destino_url, serverSelectionTimeoutMS=30000)[base]

    # Que cada uno es quien dice ser: produccion tiene 266k menus y dev no.
    n_prod = await prod.meal_library.count_documents({})
    n_dev = await dev.meal_library.count_documents({})
    print(f"{'HACIENDOLO' if HAZLO else 'ENSAYO (nada se escribe)'}\n")
    print(f"ORIGEN  (produccion, por el tunel): meal_library = {n_prod}")
    print(f"DESTINO (dev, Atlas):               meal_library = {n_dev}")
    if n_prod < n_dev:
        print("\nEl origen tiene MENOS que el destino. Eso huele a que estan al reves. Se para.")
        return
    print()

    for nombre, que_es in COLECCIONES:
        de = await prod[nombre].count_documents({})
        a = await dev[nombre].count_documents({})
        print(f"   {nombre:16} {a:7} -> {de:7}   ({que_es})")
        if not HAZLO:
            continue

        # Se vacia y se vuelve a llenar: mezclar dos versiones de la misma coleccion deja
        # documentos viejos que ya no existen en produccion y que luego no se sabe de donde
        # salieron.
        await dev[nombre].delete_many({})
        lote, copiados = [], 0
        async for doc in prod[nombre].find({}, {"_id": 0}):
            lote.append(doc)
            if len(lote) >= LOTE:
                await dev[nombre].insert_many(lote, ordered=False)
                copiados += len(lote)
                lote = []
                print(f"      {copiados}/{de}", end="\r")
        if lote:
            await dev[nombre].insert_many(lote, ordered=False)
            copiados += len(lote)
        print(f"      copiados {copiados}/{de}      ")

    if not HAZLO:
        print("\nENSAYO: no se ha escrito nada. Pasa --hazlo para copiar.")
        return

    print("\nComo queda dev:")
    for nombre, _ in COLECCIONES:
        print(f"   {nombre:16} {await dev[nombre].count_documents({})}")
    pasan = await dev.meal_library.count_documents({"calidad.pasa": True})
    print(f"   de la biblioteca, pasan el filtro de calidad: {pasan}")


if __name__ == "__main__":
    asyncio.run(main())
