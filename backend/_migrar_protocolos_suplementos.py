"""
Pasa los protocolos de suplementacion al formato versionado (punto 33 del doc del 07-08).

Antes cada cliente tenia UN documento con `actual`, `siguiente` y `siguiente_fecha`, que se
pisaba a si mismo en cada guardado. Ahora es una lista de versiones `{fecha, items, nota}`
que se resuelve por la mas reciente que no pase de hoy, igual que los macros.

Como se traduce lo que hay:

  actual      -> una version con la fecha de `updated_at` (cuando se guardo). Es lo mas
                 cercano a la verdad que tenemos: no se sabe desde cuando lo tomaba, pero
                 si desde cuando consta.
  siguiente   -> una version con `siguiente_fecha`, que es literalmente lo que significaba.

Los campos viejos se dejan en el documento: no estorban y si algo sale mal se puede volver.

  python _migrar_protocolos_suplementos.py             simula, no escribe
  python _migrar_protocolos_suplementos.py --escribir  escribe
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from core.database import db   # noqa: E402


async def main(escribir: bool):
    docs = await db.supplement_protocols.find({}, {"_id": 0}).to_list(5000)
    print(f"{len(docs)} protocolos")

    ya, migrados, vacios, muestra = 0, 0, 0, []
    for d in docs:
        if d.get("versiones"):
            ya += 1
            continue
        versiones = []
        cuando = str(d.get("updated_at") or "")[:10] or "2026-01-01"
        if d.get("actual"):
            versiones.append({"fecha": cuando, "items": d["actual"], "nota": d.get("nota"),
                              "guardado_por": None, "guardado_at": d.get("updated_at")})
        if d.get("siguiente") and d.get("siguiente_fecha"):
            versiones.append({"fecha": str(d["siguiente_fecha"])[:10], "items": d["siguiente"],
                              "nota": d.get("nota"), "guardado_por": None,
                              "guardado_at": d.get("updated_at")})
        if not versiones:
            vacios += 1
            continue
        versiones.sort(key=lambda v: v["fecha"])
        if escribir:
            await db.supplement_protocols.update_one(
                {"client_id": d["client_id"]}, {"$set": {"versiones": versiones}})
        migrados += 1
        if len(muestra) < 8:
            detalle = "  +  ".join(f"{v['fecha']}: {len(v['items'])} suplementos" for v in versiones)
            muestra.append(f"  {str(d.get('client_id'))[:8]}  {detalle}")

    print("\n".join(muestra) or "  (nada que migrar)")
    print(f"\n{migrados} migrados, {ya} ya estaban en el formato nuevo, {vacios} sin ningun suplemento")
    print("ESCRITO" if escribir else "SIMULACION: nada escrito (pasa --escribir)")


if __name__ == "__main__":
    asyncio.run(main("--escribir" in sys.argv))
