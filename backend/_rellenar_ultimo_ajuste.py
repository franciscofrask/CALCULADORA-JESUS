"""Pone `client_profiles.ultimo_ajuste` en la fecha de VIGENCIA del ultimo ajuste real.

Por ese campo ordena el panel «esta semana te tocan estos», que es la primera pantalla que
mira Jesus los lunes. Medido el 12-08-2026 en produccion: **no coincidia con el historial en
184 de 185 perfiles**, y en la mayoria estaba vacio.

Por que estaba mal: los que escribian el campo pasaban `created_at` (el dia en que se guardo
la fila), y a los 159 clientes que vinieron de Calma se les importo todo el historial de una
tacada, asi que a unos les quedo la fecha de la importacion y a otros nada. El codigo ya usa
la fecha de vigencia desde el 12-08 (`core/seguimiento.fecha_de_vigencia`), pero eso solo
arregla los ajustes NUEVOS: lo que ya estaba escrito hay que rehacerlo, y es esto.

La fecha buena es el `effective_date` mas reciente que no sea futuro. Los ajustes programados
para dentro de tres semanas no cuentan: todavia no se le han hecho.

Uso:
    venv/Scripts/python.exe _rellenar_ultimo_ajuste.py                  # solo mira
    venv/Scripts/python.exe _rellenar_ultimo_ajuste.py --escribir       # lo deja escrito

Contra produccion, por el tunel:
    MONGO_URL="mongodb://localhost:27018" DB_NAME=jg12_prod \
      venv/Scripts/python.exe _rellenar_ultimo_ajuste.py --escribir
"""
import asyncio
import os
import sys
from datetime import date

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))


def _vigencia(fila: dict) -> str:
    return str(fila.get("effective_date") or fila.get("created_at") or "")[:10]


async def main() -> None:
    escribir = "--escribir" in sys.argv
    url = os.environ["MONGO_URL"]
    # La cadena de conexion, no el nombre de la base: dev y prod se llaman igual.
    print(f"CONEXION: {url[:32]}...")
    print("MODO:", "ESCRIBE" if escribir else "solo mira")
    db = AsyncIOMotorClient(url)[os.environ.get("DB_NAME", "jg12_restored")]

    hoy = date.today().isoformat()
    historial: dict = {}
    async for h in db.macro_history.find({}, {"_id": 0, "client_id": 1,
                                              "effective_date": 1, "created_at": 1}):
        d = _vigencia(h)
        if len(d) == 10 and d <= hoy:
            cid = h.get("client_id")
            if d > historial.get(cid, ""):
                historial[cid] = d

    cambian, iguales, sin_historial = [], 0, 0
    async for p in db.client_profiles.find({}, {"_id": 0, "id": 1, "ultimo_ajuste": 1}):
        real = historial.get(p["id"])
        if not real:
            sin_historial += 1
            continue
        actual = str(p.get("ultimo_ajuste") or "")[:10]
        if actual == real:
            iguales += 1
        else:
            cambian.append((p["id"], actual or "(vacio)", real))

    print(f"\nperfiles: {iguales + len(cambian) + sin_historial}")
    print(f"  ya estaban bien:        {iguales}")
    print(f"  sin historial (se dejan): {sin_historial}")
    print(f"  A CORREGIR:             {len(cambian)}")
    for cid, antes, ahora in cambian[:10]:
        print(f"    {cid[:12]}  {antes:12} -> {ahora}")
    if len(cambian) > 10:
        print(f"    ... y {len(cambian) - 10} mas")

    if not escribir:
        print("\nNo se ha escrito nada. Pasa --escribir para dejarlo puesto.")
        return

    for cid, _antes, ahora in cambian:
        await db.client_profiles.update_one({"id": cid}, {"$set": {"ultimo_ajuste": ahora}})
    print(f"\nescritos: {len(cambian)}")


if __name__ == "__main__":
    asyncio.run(main())
