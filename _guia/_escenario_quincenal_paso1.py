# -*- coding: utf-8 -*-
"""EL ESCENARIO DEL PASO 1 DEL QUINCENAL, para poder VERLO en la app de dev.

La pantalla del paso 1 con datos no se puede mirar cualquier dia: el peso semanal sale de la
pareja de dias seguidos desde el miercoles, asi que en martes no hay pareja que enseñar
porque el miercoles todavia no ha pasado. Y el bloque «lo que has hecho» necesita cierres
del dia, que la cuenta del equipo no tiene.

Asi que se le monta a `francisco@test.com` -- cuenta de PRUEBAS y solo en DEV -- la quincena
del documento: los dos pesajes de la maqueta (78,6 el miercoles y 78,2 el jueves, que dan
78,4 de media) y cierres suficientes para que el paso 1 enseñe datos en vez de preguntarlos.

Luego la pantalla se abre con `?ver=quincenal&dia=2026-08-27`, que es el modo revision del
equipo. NO SE TOCA NINGUN DATO DE PRODUCCION y no se escribe ningun texto de los que se
comprueban: lo que se monta son los NUMEROS de partida.

    backend/venv/Scripts/python.exe _guia/_escenario_quincenal_paso1.py
"""
import asyncio
import os
import sys
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

CORREO = "francisco@test.com"
#: El jueves de la maqueta. La quincena son los 14 dias que acaban ahi.
JUEVES = date(2026, 8, 27)
#: Los dos pesajes de la maqueta: «78,6 Miercoles · 78,2 Jueves» -> «Peso semanal 78,4 kg».
PESAJES = {date(2026, 8, 26): 78.6, JUEVES: 78.2}


async def main():
    from core.database import db

    if "12en12app" in (os.environ.get("MONGO_URL") or ""):
        print("Esto es dev. No se ejecuta contra produccion.")
        return

    user = await db.users.find_one({"email": CORREO}, {"_id": 0, "id": 1})
    if not user:
        print(f"No existe {CORREO}")
        return
    perfil = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0, "id": 1, "pesos": 1})
    if not perfil:
        print("Esa cuenta no tiene ficha de cliente")
        return

    # ── Los dos pesajes ──
    pesos = [p for p in (perfil.get("pesos") or [])
             if str(p.get("fecha") or "")[:10] not in {d.isoformat() for d in PESAJES}]
    for dia, valor in PESAJES.items():
        pesos.append({"fecha": dia.isoformat(), "valor": valor,
                      "origen": "escenario de pruebas del paso 1"})
    pesos.sort(key=lambda p: str(p.get("fecha")))
    await db.client_profiles.update_one({"user_id": user["id"]}, {"$set": {"pesos": pesos}})

    # ── Los cierres del dia: uno de cada dos, que es lo que hace que HAYA datos ──
    # Los numeros van variados a proposito: si los tres fueran iguales, las medias de
    # «como te has sentido» saldrian planas y no se veria la linea.
    creados = 0
    for i in range(0, 14, 2):
        dia = (JUEVES - timedelta(days=i)).isoformat()
        if await db.checkins.find_one({"client_id": perfil["id"], "type": "daily", "dia": dia}):
            continue
        await db.checkins.insert_one({
            "id": f"escenario-{dia}",
            "client_id": perfil["id"],
            "type": "daily",
            "dia": dia,
            "descanso": 3 - (i % 3 == 0),
            "energy": 3 + (i % 3 == 0),
            "hunger_anxiety": 3 + (i % 4 == 0),
            "movimiento": ["igual", "mas", "menos"][i % 3],
            "extras_respuesta": "si" if i % 6 == 0 else "no",
            "created_at": f"{dia}T21:00:00+00:00",
            "escenario_de_pruebas": True,
        })
        creados += 1

    print(f"Listo. {creados} cierres nuevos y los pesajes del {list(PESAJES)[0]} y el {JUEVES}.")
    print("Ahora: /dashboard/reports?ver=quincenal&dia=2026-08-27")


if __name__ == "__main__":
    asyncio.run(main())
