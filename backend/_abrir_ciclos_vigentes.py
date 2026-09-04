# -*- coding: utf-8 -*-
"""Apunta en el cuaderno de ciclos (`db.ciclos`, core/ciclos.py) el ciclo que cada cliente
tiene abierto hoy. Una sola vez, para arrancar el cuaderno.

POR QUE (doc de Jesus del 2-09, fase 1; Francisco, 4-09: «cuando renueva no podemos perder
el ciclo anterior; empezar a contar con las nuevas y dejar como pendiente las que ya
existen»). Desde el 4-09 cada renovacion por Stripe (core/stripe_billing.py) y cada alta
desde el panel (routes/admin.py) apuntan su ciclo en el cuaderno. De lo anterior solo
sabemos una cosa: el ciclo que el cliente tiene abierto AHORA, porque
`client_profiles.cycle_start` dice cuando arranco. Eso es lo unico que se apunta, con
motivo `registro_inicial`; los ciclos de antes no se escribieron nunca y no se inventan.

QUE HACE
    - recorre los perfiles con `cycle_start`
    - al que ya tiene algo en el cuaderno no lo toca (lo comprueba `registrar_ciclo_vigente`)
    - al resto le apunta el ciclo en curso: el inicio segun la misma cuenta que la semana
      viva (si el ancla es vieja y el plan ya dio la vuelta, el ciclo en curso es el que
      empezo N vueltas despues: `inicio_del_ciclo_vigente`), sus semanas segun el plan y
      su fin previsto
    - con --escribir crea antes los dos indices de `ciclos` si no estan (el unico por
      cliente y dia es el que cierra la carrera de los avisos repetidos de Stripe)

USO (desde backend/)
    venv/Scripts/python.exe _abrir_ciclos_vigentes.py               solo lee y enseña lo que haria
    venv/Scripts/python.exe _abrir_ciclos_vigentes.py --escribir    escribe

Va contra lo que diga backend/.env (MONGO_URL y DB_NAME): en local, la base de desarrollo.
Para produccion hace falta el tunel del 27018 con MONGO_URL y DB_NAME en el entorno (ver
_internos_proceso/tocar_datos_de_produccion.md), una copia antes, y pasar ademas
`--produccion`: sin esa palabra el script se niega a escribir en jg12_prod.

IDEMPOTENTE: una segunda pasada encuentra a todos con cuaderno y no escribe nada.
"""
import asyncio
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import DB_NAME, MONGO_URL                                   # noqa: E402
from core.database import db                                                 # noqa: E402
from core.ciclos import (COLECCION, dia_de_espana, inicio_del_ciclo_vigente,  # noqa: E402
                         registrar_ciclo_vigente, semanas_del_plan)

ESCRIBIR = "--escribir" in sys.argv
PRODUCCION = "--produccion" in sys.argv


def _fin_previsto(inicio, semanas):
    if not inicio or not semanas:
        return None
    return (datetime.fromisoformat(inicio) + timedelta(days=semanas * 7 - 1)).date().isoformat()


async def main():
    # Siempre en voz alta donde se esta, antes de nada (regla de la casa para todo lo que
    # escribe: _sync_membresias_cobros.py, _destino_sync.rotulo).
    print(f"conexion: {MONGO_URL[:25]}...   base: {DB_NAME}")
    print(f"modo: {'ESCRIBIR' if ESCRIBIR else 'solo lectura (pasa --escribir para escribir)'}")
    if ESCRIBIR and DB_NAME == "jg12_prod" and not PRODUCCION:
        raise SystemExit("La base es jg12_prod: para escribir en produccion hay que pasar --produccion "
                         "(y tener la copia hecha). No se ha escrito nada.")

    hoy = dia_de_espana(datetime.now(timezone.utc))
    total_perfiles = await db.client_profiles.count_documents({})
    perfiles = await db.client_profiles.find(
        {"cycle_start": {"$nin": [None, ""]}},
        {"_id": 0, "id": 1, "user_id": 1, "plan": 1, "status": 1, "cycle_start": 1, "created_at": 1},
    ).sort("created_at", 1).to_list(100000)
    con_cuaderno = set(await db[COLECCION].distinct("client_id"))

    filas, ya_apuntados = [], 0
    for p in perfiles:
        if p["id"] in con_cuaderno:
            ya_apuntados += 1
            continue
        inicio = inicio_del_ciclo_vigente(p)
        semanas = semanas_del_plan(p)
        filas.append({
            "id": p["id"], "plan": p.get("plan"), "status": p.get("status"),
            "cycle_start": p.get("cycle_start"), "inicio": inicio, "semanas": semanas,
            "fin_previsto": _fin_previsto(inicio, semanas),
            "ancla_vieja": bool(inicio) and inicio != dia_de_espana(p.get("cycle_start")),
        })

    print(f"\n  perfiles en la base:            {total_perfiles}")
    print(f"  con cycle_start:                {len(perfiles)}")
    print(f"  ya con cuaderno (no se tocan):  {ya_apuntados}")
    print(f"  a apuntar:                      {len(filas)}")
    if filas:
        print(f"    por status:  {dict(Counter(f['status'] for f in filas))}")
        print(f"    por plan:    {dict(Counter(f['plan'] for f in filas).most_common())}")
        print(f"    con el ancla vieja (se apunta la vuelta en curso, no el ancla): "
              f"{sum(1 for f in filas if f['ancla_vieja'])}")
        print(f"    sin semanas (plan sin ciclo fijo, sin fin previsto): "
              f"{sum(1 for f in filas if not f['semanas'])}")
        print(f"    con fin previsto anterior a hoy ({hoy}): "
              f"{sum(1 for f in filas if f['fin_previsto'] and f['fin_previsto'] < hoy)}")
        print(f"    con inicio en el futuro: {sum(1 for f in filas if f['inicio'] and f['inicio'] > hoy)}")
        print("\n  muestra (10 primeros):")
        print("    perfil        plan            status      cycle_start                 inicio      sem  fin previsto")
        for f in filas[:10]:
            marca = "  <- ancla vieja" if f["ancla_vieja"] else ""
            print(f"    {f['id'][:12]:<12}  {str(f['plan']):<14}  {str(f['status']):<10}  "
                  f"{str(f['cycle_start']):<26}  {f['inicio']}  {str(f['semanas']):>3}  "
                  f"{f['fin_previsto']}{marca}")

    if not ESCRIBIR:
        print(f"\n  SIMULACION: no se ha escrito nada. Se apuntarian {len(filas)} ciclos.")
        return

    # Los mismos dos indices que crea el arranque del backend (core/database.py); aqui por
    # si el script corre antes de que el backend con este codigo haya arrancado.
    await db[COLECCION].create_index([("client_id", 1), ("inicio", 1)], unique=True,
                                     name="un_ciclo_por_cliente_y_dia")
    await db[COLECCION].create_index([("client_id", 1), ("fin", 1)])

    escritos, saltados, fallos = 0, 0, 0
    por_perfil = {p["id"]: p for p in perfiles}
    for f in filas:
        try:
            ciclo = await registrar_ciclo_vigente(por_perfil[f["id"]])
        except Exception as exc:                                     # noqa: BLE001
            fallos += 1
            print(f"    FALLO {f['id']}: {exc}")
            continue
        if ciclo:
            escritos += 1
        else:
            saltados += 1
    print(f"\n  escritos: {escritos}   saltados (ya tenian cuaderno o sin con que): {saltados}   fallos: {fallos}")
    print(f"  ciclos en el cuaderno ahora: {await db[COLECCION].count_documents({})}")


if __name__ == "__main__":
    asyncio.run(main())
