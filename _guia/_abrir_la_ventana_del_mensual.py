# -*- coding: utf-8 -*-
"""ABRIR HOY LA VENTANA DEL REPORTE MENSUAL, PARA PODER LLEGAR AL PASO 4.

El paso 4 («Tu plan nuevo y mi feedback directo») solo aparece DESPUES de enviar el
reporte. Y en modo revision (`?ver=mensual`) el envio no funciona a proposito: es una
pantalla para mirar, no para escribir. Asi que el ultimo paso no hay forma de verlo sin
mandar uno de verdad, y para eso la ventana tiene que estar abierta.

QUIEN DECIDE LA VENTANA ES LA RUTINA, NO EL CICLO. En `routes/report_cadence.py`:

    semana_reporte = semana_rutina if semana_rutina is not None else cycle["week"]

o sea que al que tiene rutina cargada la ventana le vive en la SEMANA DE SU RUTINA («el
quincenal se abre en la semana 2 de la rutina, no de su ciclo»). Y el patron del plan pone
el mensual en las semanas 3, 7 y 11, los viernes.

Esto mueve el arranque de la rutina las semanas que hagan falta para que HOY caiga en una
semana de mensual. No toca el ciclo, ni los macros, ni ningun dato del cliente: solo la
fecha de su rutina, y se devuelve como estaba.

SOLO EN DEV Y SOLO A LA CUENTA DE PRUEBAS.

    backend/venv/Scripts/python.exe _guia/_abrir_la_ventana_del_mensual.py            abre
    backend/venv/Scripts/python.exe _guia/_abrir_la_ventana_del_mensual.py --quitar   cierra
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "backend"))

from core.database import db          # noqa: E402

CORREO = os.environ.get("CUENTA", "francisco@test.com")
#: Donde se guarda la fecha buena, para poder devolverla. En el propio documento, que asi
#: no hace falta acordarse de nada ni fiarse de un fichero suelto.
GUARDADA = "created_at_antes_de_abrir_la_ventana"


async def main() -> None:
    quitar = "--quitar" in sys.argv

    user = await db.users.find_one({"email": CORREO}, {"_id": 0, "id": 1})
    perfil = await db.client_profiles.find_one({"user_id": (user or {}).get("id")},
                                               {"_id": 0, "id": 1})
    if not perfil:
        print(f"no encuentro la ficha de {CORREO}")
        return

    rutina = await db.routines.find_one({"client_id": perfil["id"]},
                                        {"_id": 0, "id": 1, "created_at": 1, GUARDADA: 1},
                                        sort=[("created_at", -1)])
    if not rutina:
        print("esa cuenta no tiene rutina; sin rutina manda la semana del ciclo")
        return

    if quitar:
        antes = rutina.get(GUARDADA)
        if not antes:
            print("no estaba abierta: la rutina no tiene fecha guardada")
            return
        await db.routines.update_one({"id": rutina["id"]},
                                     {"$set": {"created_at": antes}, "$unset": {GUARDADA: ""}})
        print(f"la rutina vuelve a arrancar el {antes[:10]}; la ventana se cierra")
        return

    # DOS SEMANAS ATRAS: hoy pasa de ser la semana 1 de su rutina a ser la 3, que es la
    # primera que trae mensual en el patron. Si ya estaba movida, se respeta la original.
    original = rutina.get(GUARDADA) or rutina["created_at"]
    nueva = (datetime.fromisoformat(str(original).replace("Z", "+00:00"))
             - timedelta(days=14)).isoformat()
    await db.routines.update_one(
        {"id": rutina["id"]}, {"$set": {"created_at": nueva, GUARDADA: original}})

    print(f"la rutina arrancaba el {str(original)[:10]} y ahora arranca el {nueva[:10]}")
    print("hoy cae en la semana 3 de su rutina, que es semana de mensual")
    print()
    print("   Seguimiento -> el reporte sale vivo, SIN el ?ver=mensual")
    print("   los 4 pasos y, al enviar, el paso 4 con «Ver mi informe»")
    print()
    print("   para cerrarla otra vez:  --quitar")


if __name__ == "__main__":
    asyncio.run(main())
