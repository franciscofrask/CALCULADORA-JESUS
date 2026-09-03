# -*- coding: utf-8 -*-
"""LOS DOS EJERCICIOS DE SU MAQUETA, para poder mirar la pregunta 5.

Su documento dibuja la pregunta con dos etiquetas ya puestas -- `Press militar ×` y
`Sentadilla profunda ×` -- porque el texto es «estos son los que me diste». Sin nada puesto
la pregunta sale en blanco y no se puede comprobar lo que dice la maqueta.

Van a `client_profiles.injuries`, que es el campo que lee el generador de rutinas y el que
la pregunta 5 escribe desde el 3-09. No hay endpoint para que el cliente se lo escriba a si
mismo -- lo escriben el alta y el panel --, de ahi este guion.

Y LE PRESTA UN PLAN CON QUINCENAL. La pregunta 5 vive en el bloque de lesiones, y ese
bloque solo lo lleva el perfil «completo», que es quien tiene reporte quincenal. La cuenta
del equipo -- la unica que puede abrir el formulario fuera de su ventana, con `?ver=` -- no
lo tiene, asi que se le pone «gold» mientras dure la prueba y se le devuelve el suyo.

SOLO EN DEV Y SOLO A LA CUENTA DE PRUEBAS. Guarda lo que habia para poder devolverlo:

    backend/venv/Scripts/python.exe _guia/_escenario_molestias.py            monta
    backend/venv/Scripts/python.exe _guia/_escenario_molestias.py --deshacer devuelve
"""
import asyncio
import io
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "backend"))

from core.database import db          # noqa: E402

CORREO = os.environ.get("CUENTA", "francisco@test.com")
LOS_DOS = ["Press militar", "Sentadilla profunda"]
COPIA = os.path.join(RAIZ, "_guia", "_escenario_molestias_antes.json")


async def main() -> None:
    deshacer = "--deshacer" in sys.argv
    user = await db.users.find_one({"email": CORREO}, {"_id": 0, "id": 1})
    if not user:
        print(f"no existe {CORREO}")
        return
    perfil = await db.client_profiles.find_one({"user_id": user["id"]},
                                               {"_id": 0, "id": 1, "injuries": 1, "plan": 1})
    if not perfil:
        print("esa cuenta no tiene ficha de cliente")
        return

    if deshacer:
        antes = {"injuries": [], "plan": perfil.get("plan")}
        if os.path.exists(COPIA):
            antes = json.load(io.open(COPIA, encoding="utf-8"))
            os.remove(COPIA)
        await db.client_profiles.update_one(
            {"id": perfil["id"]},
            {"$set": {"injuries": antes.get("injuries") or [],
                      "plan": antes.get("plan")}})
        print(f"devuelto: injuries = {antes.get('injuries')} · plan = {antes.get('plan')}")
        return

    # La copia solo se escribe la primera vez: correrlo dos veces no puede guardar como
    # «lo que habia» lo que puso el propio escenario.
    if not os.path.exists(COPIA):
        io.open(COPIA, "w", encoding="utf-8").write(json.dumps(
            {"injuries": perfil.get("injuries") or [], "plan": perfil.get("plan")},
            ensure_ascii=False))
    await db.client_profiles.update_one(
        {"id": perfil["id"]},
        {"$set": {"injuries": list(LOS_DOS), "plan": "gold"}})
    print(f"puesto en {CORREO}: injuries = {LOS_DOS} · plan = gold (era {perfil.get('plan')})")
    print(f"(lo que habia queda en {os.path.basename(COPIA)})")


if __name__ == "__main__":
    asyncio.run(main())
