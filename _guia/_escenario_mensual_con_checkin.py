# -*- coding: utf-8 -*-
"""EL PASO 1 DEL MENSUAL, CON DATOS, para poder mirar la version larga.

El documento del 1-09 tiene DOS versiones del paso 1: la que ENSENA lo que ha hecho -- el
selector de periodo, el peso, «lo que has hecho en los ultimos 28 dias» y las sensaciones --
y la que lo PREGUNTA, para el que no tiene check-in. La app elige una u otra con
`hay_datos_suficientes`: hacen falta cierres en al menos la MITAD de los dias.

Ninguna de las dos cuentas de pruebas los tiene, asi que las dos caen en la version corta y
la larga no se puede mirar. Esto le pone al cliente de pruebas veinte cierres repartidos por
el mes, con sus sensaciones y su movimiento, y ya se puede.

SOLO EN DEV Y SOLO A LA CUENTA DE PRUEBAS. No toca a nadie mas y se puede deshacer:

    backend/venv/Scripts/python.exe _guia/_escenario_mensual_con_checkin.py            monta
    backend/venv/Scripts/python.exe _guia/_escenario_mensual_con_checkin.py --deshacer  quita
"""
import asyncio
import os
import sys
import uuid
from datetime import date, timedelta

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "backend"))

from core.database import db          # noqa: E402

CORREO = os.environ.get("CUENTA", "francisco@test.com")
#: De donde salen; se borran por aqui, para no llevarse por delante los de verdad.
MARCA = "escenario-mensual-0309"


async def main() -> None:
    deshacer = "--deshacer" in sys.argv
    user = await db.users.find_one({"email": CORREO}, {"_id": 0, "id": 1})
    if not user:
        print(f"no existe {CORREO}")
        return
    perfil = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0, "id": 1})
    if not perfil:
        print("esa cuenta no tiene ficha de cliente")
        return
    cid = perfil["id"]

    fuera = await db.checkins.delete_many({"client_id": cid, "origen": MARCA})
    print(f"quitados {fuera.deleted_count} cierres del escenario")
    if deshacer:
        return

    hoy = date.today()
    # Veinte de los ultimos veintiocho: por encima de la mitad, que es el liston.
    puestos = 0
    for i in range(1, 28):
        if puestos >= 20:
            break
        dia = hoy - timedelta(days=i)
        # Uno de cada cuatro se lo salta, que un mes perfecto no se parece a un mes.
        if i % 4 == 0:
            continue
        await db.checkins.insert_one({
            "id": str(uuid.uuid4()),
            "client_id": cid,
            "type": "daily",
            "created_at": dia.isoformat() + "T21:00:00",
            "origen": MARCA,
            "extras_respuesta": "si" if i % 5 == 0 else "no",
            "movimiento": ("mas" if i % 3 == 0 else "menos" if i % 7 == 0 else "igual"),
            "suplementos": {"respuesta": "si" if i % 6 else "no"},
            # Las tres sensaciones, en el rango que espera el reporte (1 a 5).
            "descanso": 3 + (i % 3) - 1,
            "energy": 3 + (i % 2),
            "hunger_anxiety": 2 + (i % 3),
        })
        puestos += 1
    print(f"puestos {puestos} cierres a {CORREO} entre {hoy - timedelta(days=27)} y {hoy}")


if __name__ == "__main__":
    asyncio.run(main())
