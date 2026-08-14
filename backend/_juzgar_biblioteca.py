# -*- coding: utf-8 -*-
"""Juzga la biblioteca de comidas ENTERA de una vez: el "entrenamiento" en bloque.

Francisco, 14-08-2026: «te lo voy a repetir de nuevo: quiero que lo entrenemos con los
menus de produccion». Y tiene razon en el como: el juez de coherencia funciona, pero a
4 juicios por peticion la biblioteca se limpia gota a gota y mientras tanto el compositor
sigue saliendo. Esto la pasa entera UNA vez, veredicto guardado en `db.menu_juicios`
para siempre; a partir de ahi, ofrecer un menu real es una lectura de cache.

No toca la biblioteca: solo escribe veredictos. Es reanudable (lo ya juzgado se salta) y
se puede parar cuando sea sin perder nada.

    python _juzgar_biblioteca.py --limite 20        prueba corta
    python _juzgar_biblioteca.py                    todo el tipo "comida"
    python _juzgar_biblioteca.py --tipo peri        el peri, si algun dia hace falta

Coste, medido con la prueba corta antes de lanzar el total: ~200 tokens por juicio con
el modelo del chat. La biblioteca entera son unos pocos euros, una sola vez.
"""
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

TIPO = "peri" if "--tipo" in sys.argv and "peri" in sys.argv else "comida"
LIMITE = 0
if "--limite" in sys.argv:
    LIMITE = int(sys.argv[sys.argv.index("--limite") + 1])
PARALELO = 8      # llamadas a la vez; con mas, el limite de la API empieza a devolver 429


async def main():
    from motor.motor_asyncio import AsyncIOMotorClient
    from core.juez_menus import firma_de, juzgar, veredicto_cacheado

    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]

    # Los mismos criterios con los que la app los ofrece: calidad de la cosecha y sin
    # repetidos. Los de 2+ clientes pasan solos y no gastan juicio.
    filtro = {"tipo": TIPO, "calidad.pasa": True, "repetido_de": {"$exists": False}}
    total = await db.meal_library.count_documents(filtro)
    autos = await db.meal_library.count_documents({**filtro, "clientes": {"$gte": 2}})
    print(f"biblioteca tipo '{TIPO}': {total} menus con calidad "
          f"({autos} pasan solos por 2+ clientes; a juzgar: {total - autos})", flush=True)

    sem = asyncio.Semaphore(PARALELO)
    hechos = {"juzgados": 0, "pasan": 0, "fuera": 0, "cacheados": 0, "errores": 0}
    arranque = time.time()

    async def uno(doc):
        ids = [int(a["alimento_id"]) for a in (doc.get("alimentos") or [])]
        firma = firma_de(TIPO, ids)
        if await veredicto_cacheado(db, firma) is not None:
            hechos["cacheados"] += 1
            return
        etiqueta = [f"{a.get('nombre')} ({float(a.get('cantidad_g') or 0):.0f} g)"
                    for a in (doc.get("alimentos") or [])]
        async with sem:
            vale = await juzgar(db, TIPO, etiqueta, firma)
        # `juzgar` devuelve False tanto si el menu no vale como si la API fallo; el fallo
        # no se cachea, asi que se distingue mirando si quedo veredicto guardado.
        if await veredicto_cacheado(db, firma) is None:
            hechos["errores"] += 1
        else:
            hechos["juzgados"] += 1
            hechos["pasan" if vale else "fuera"] += 1

    lote, n = [], 0
    cursor = db.meal_library.find({**filtro, "clientes": {"$lt": 2}},
                                  {"_id": 0, "alimentos": 1})
    async for doc in cursor:
        n += 1
        if LIMITE and n > LIMITE:
            break
        lote.append(asyncio.create_task(uno(doc)))
        if len(lote) >= PARALELO * 4:
            await asyncio.gather(*lote)
            lote = []
            if hechos["juzgados"] and hechos["juzgados"] % 200 < PARALELO * 4:
                ritmo = hechos["juzgados"] / max(time.time() - arranque, 1)
                print(f"   {hechos['juzgados']} juzgados "
                      f"({hechos['pasan']} pasan, {hechos['fuera']} fuera, "
                      f"{hechos['cacheados']} ya estaban) ~{ritmo:.1f}/s", flush=True)
    if lote:
        await asyncio.gather(*lote)

    print(f"\nFIN en {time.time() - arranque:,.0f} s: "
          f"{hechos['juzgados']} juzgados ({hechos['pasan']} pasan, {hechos['fuera']} fuera), "
          f"{hechos['cacheados']} ya estaban, {hechos['errores']} errores de API "
          f"(se reintentan al volver a lanzar)", flush=True)
    print("veredictos totales en la base:", await db.menu_juicios.count_documents({}), flush=True)

asyncio.run(main())
