# -*- coding: utf-8 -*-
"""Pone `objetivo_actual` en las fichas que no lo tienen, LITERAL desde su `goal`, y el
objetivo del ciclo abierto en el cuaderno donde esta a null. Una sola vez, para arrancar la
fase 2 del doc de Jesus del 2-09.

POR QUE (doc de Jesus del 2-09, fase 2; decisiones de Francisco del 4-09). Jesus: «los
objetivos los pones tu, no el», de una lista cerrada de seis (core/objetivos.py). Hasta hoy
el objetivo era `goal`, que salia del cuestionario con dos valores («volumen» o
«definicion») y que el cliente reescribia desde el reporte. Francisco, 4-09: migracion
LITERAL: volumen pasa a ganar_volumen y definicion a perder_grasa (nunca a maxima
definicion, que eso no lo dijo nadie); el entrenador afina despues, ficha a ficha.

QUE HACE
    - cuenta las fichas por `goal` y cuantas no tienen `objetivo_actual`
    - a las que no lo tienen les pone `objetivo_actual = desde_goal(goal)` (core/objetivos);
      la que ya lo tiene NO se toca, aunque su goal diga otra cosa (lo puso el entrenador)
    - una ficha sin goal, o con un goal que no se reconoce, se queda sin objetivo (se cuenta)
    - al ciclo ABIERTO del cuaderno (db.ciclos, fin: null) con `objetivo` a null le pone el
      objetivo_actual de su ficha (el de despues de esta misma pasada)
    - `goal` no se toca: es la clave que entiende el motor de macros

USO (desde backend/)
    venv/Scripts/python.exe _objetivos_desde_goal.py               solo lee y enseña lo que haria
    venv/Scripts/python.exe _objetivos_desde_goal.py --escribir    escribe

Va contra lo que diga backend/.env (MONGO_URL y DB_NAME): en local, la base de desarrollo.
Para produccion hace falta el tunel del 27018 con MONGO_URL y DB_NAME en el entorno (ver
_internos_proceso/tocar_datos_de_produccion.md), una copia antes, y pasar ademas
`--produccion`: sin esa palabra el script se niega a escribir en jg12_prod.

IDEMPOTENTE: una segunda pasada no encuentra fichas sin objetivo ni ciclos sin el suyo.
"""
import asyncio
import os
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import DB_NAME, MONGO_URL                                   # noqa: E402
from core.database import db                                                 # noqa: E402
from core.ciclos import COLECCION                                            # noqa: E402
from core.objetivos import desde_goal, nombre_de                             # noqa: E402

ESCRIBIR = "--escribir" in sys.argv
PRODUCCION = "--produccion" in sys.argv

# «Sin objetivo» es no tenerlo, tenerlo a null o tenerlo vacio: las tres cosas se han visto
# en otros campos de la ficha y las tres son lo mismo aqui.
SIN_OBJETIVO = {"$in": [None, ""]}


async def main():
    # Siempre en voz alta donde se esta, antes de nada (regla de la casa para todo lo que
    # escribe: _abrir_ciclos_vigentes.py, _sync_membresias_cobros.py).
    print(f"conexion: {MONGO_URL[:25]}...   base: {DB_NAME}")
    print(f"modo: {'ESCRIBIR' if ESCRIBIR else 'solo lectura (pasa --escribir para escribir)'}")
    if ESCRIBIR and DB_NAME == "jg12_prod" and not PRODUCCION:
        raise SystemExit("La base es jg12_prod: para escribir en produccion hay que pasar --produccion "
                         "(y tener la copia hecha). No se ha escrito nada.")

    perfiles = await db.client_profiles.find(
        {}, {"_id": 0, "id": 1, "goal": 1, "objetivo_actual": 1, "status": 1, "plan": 1},
    ).to_list(100000)
    por_goal = Counter((p.get("goal") or "(sin goal)") for p in perfiles)
    con_objetivo = [p for p in perfiles if p.get("objetivo_actual")]
    sin_objetivo = [p for p in perfiles if not p.get("objetivo_actual")]
    con_destino = [(p, desde_goal(p.get("goal"))) for p in sin_objetivo]
    sin_destino = [p for p, o in con_destino if not o]
    con_destino = [(p, o) for p, o in con_destino if o]

    print(f"\n  fichas en la base:                        {len(perfiles)}")
    print(f"  por goal:                                 {dict(por_goal.most_common())}")
    print(f"  ya con objetivo_actual (no se tocan):     {len(con_objetivo)}")
    if con_objetivo:
        print(f"    por objetivo: {dict(Counter(p['objetivo_actual'] for p in con_objetivo).most_common())}")
    print(f"  sin objetivo_actual:                      {len(sin_objetivo)}")
    print(f"    con goal reconocible (se les pone):     {len(con_destino)}")
    print(f"      por destino: {dict(Counter(o for _, o in con_destino).most_common())}")
    print(f"    sin goal o con goal raro (se quedan sin): {len(sin_destino)}")
    if sin_destino:
        print(f"      por goal: {dict(Counter((p.get('goal') or '(sin goal)') for p in sin_destino).most_common())}")
        print(f"      por status: {dict(Counter(p.get('status') for p in sin_destino).most_common())}")

    # Los ciclos abiertos sin objetivo, con el que tendra su ficha DESPUES de esta pasada.
    objetivo_por_ficha = {p["id"]: p.get("objetivo_actual") for p in perfiles}
    objetivo_por_ficha.update({p["id"]: o for p, o in con_destino})
    abiertos = await db[COLECCION].find(
        {"fin": None, "objetivo": SIN_OBJETIVO},
        {"_id": 0, "id": 1, "client_id": 1, "numero": 1, "inicio": 1},
    ).to_list(100000)
    ciclos_con = [(c, objetivo_por_ficha.get(c["client_id"])) for c in abiertos]
    ciclos_con = [(c, o) for c, o in ciclos_con if o]
    print(f"\n  ciclos abiertos sin objetivo:             {len(abiertos)}")
    print(f"    con ficha con objetivo (se les pone):   {len(ciclos_con)}")
    print(f"      por objetivo: {dict(Counter(o for _, o in ciclos_con).most_common())}")
    print(f"    sin objetivo en la ficha (se quedan):   {len(abiertos) - len(ciclos_con)}")

    print("\n  muestra (10 primeras fichas a las que se les pone):")
    print("    perfil        plan            status      goal           -> objetivo_actual")
    for p, o in con_destino[:10]:
        print(f"    {p['id'][:12]:<12}  {str(p.get('plan')):<14}  {str(p.get('status')):<10}  "
              f"{str(p.get('goal')):<13}  -> {o} ({nombre_de(o)})")

    if not ESCRIBIR:
        print(f"\n  SIMULACION: no se ha escrito nada. Se pondria objetivo_actual a {len(con_destino)} "
              f"fichas y objetivo a {len(ciclos_con)} ciclos abiertos.")
        return

    fichas, ciclos, fallos = 0, 0, 0
    for p, o in con_destino:
        try:
            # El filtro repite «sin objetivo»: si alguien se lo puso entre la lectura y la
            # escritura, lo suyo manda.
            r = await db.client_profiles.update_one(
                {"id": p["id"], "objetivo_actual": SIN_OBJETIVO}, {"$set": {"objetivo_actual": o}})
            fichas += r.modified_count
        except Exception as exc:                                     # noqa: BLE001
            fallos += 1
            print(f"    FALLO ficha {p['id']}: {exc}")
    for c, o in ciclos_con:
        try:
            r = await db[COLECCION].update_one(
                {"id": c["id"], "objetivo": SIN_OBJETIVO}, {"$set": {"objetivo": o}})
            ciclos += r.modified_count
        except Exception as exc:                                     # noqa: BLE001
            fallos += 1
            print(f"    FALLO ciclo {c['id']}: {exc}")
    print(f"\n  fichas escritas: {fichas}   ciclos escritos: {ciclos}   fallos: {fallos}")
    print(f"  fichas sin objetivo_actual ahora:   "
          f"{await db.client_profiles.count_documents({'objetivo_actual': SIN_OBJETIVO})}")
    print(f"  ciclos abiertos sin objetivo ahora: "
          f"{await db[COLECCION].count_documents({'fin': None, 'objetivo': SIN_OBJETIVO})}")


if __name__ == "__main__":
    asyncio.run(main())
