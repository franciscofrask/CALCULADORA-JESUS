"""
Rellena `ultimo_ajuste` y `ultimo_reporte` en los clientes que ya existen (punto 29 del
doc del 07-08). A partir de ahora las mantiene `core/seguimiento.py` al guardar, pero los
que ya estaban en la base no las tienen y saldrian todos como "nunca tocados".

De donde sale cada fecha, quedandose siempre con la mas reciente:

  ultimo_ajuste  - macro_history.created_at  +  calma_raw.macros_historial[].fecha
  ultimo_reporte - reports.created_at        +  calma_raw.formularios_mensuales[].fecha

Los de Calma cuentan: un cliente migrado al que Jesus ajusto en junio EN CALMA no lleva
sin tocar desde el principio de los tiempos, y si saliera asi taparia a los que de verdad
estan abandonados.

  python _rellenar_fechas_seguimiento.py            simula, no escribe
  python _rellenar_fechas_seguimiento.py --escribir escribe
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from core.database import db   # noqa: E402


def _dia(v):
    return str(v)[:10] if v else None


def _mayor(a, b):
    if not a:
        return b
    if not b:
        return a
    return a if a >= b else b


async def main(escribir: bool):
    perfiles = await db.client_profiles.find({}, {"_id": 0, "id": 1, "user_id": 1}).to_list(5000)
    print(f"{len(perfiles)} clientes")

    # Una consulta por coleccion, no una por cliente.
    ajuste, reporte = {}, {}
    async for h in db.macro_history.find({}, {"_id": 0, "client_id": 1, "created_at": 1, "effective_date": 1}):
        cid = h.get("client_id")
        f = _dia(h.get("created_at")) or _dia(h.get("effective_date"))
        if cid and f:
            ajuste[cid] = _mayor(ajuste.get(cid), f)
    async for r in db.reports.find({}, {"_id": 0, "client_id": 1, "created_at": 1}):
        cid, f = r.get("client_id"), _dia(r.get("created_at"))
        if cid and f:
            reporte[cid] = _mayor(reporte.get(cid), f)

    # Lo que traen de Calma, indexado por client_id y por user_id (calma_raw usa los dos).
    async for c in db.calma_raw.find({}, {"_id": 0, "client_id": 1, "user_id": 1,
                                          "macros_historial": 1, "formularios_mensuales": 1}):
        claves = [k for k in (c.get("client_id"), c.get("user_id")) if k]
        for h in (c.get("macros_historial") or []):
            f = _dia(h.get("fecha"))
            for k in claves:
                if f:
                    ajuste[k] = _mayor(ajuste.get(k), f)
        for r in (c.get("formularios_mensuales") or []):
            f = _dia(r.get("fecha"))
            for k in claves:
                if f:
                    reporte[k] = _mayor(reporte.get(k), f)

    tocados, sin_nada = 0, 0
    muestra = []
    for p in perfiles:
        cid, uid = p.get("id"), p.get("user_id")
        a = _mayor(ajuste.get(cid), ajuste.get(uid))
        r = _mayor(reporte.get(cid), reporte.get(uid))
        if not a and not r:
            sin_nada += 1
            continue
        cambios = {}
        if a:
            cambios["ultimo_ajuste"] = a
        if r:
            cambios["ultimo_reporte"] = r
        if escribir:
            await db.client_profiles.update_one({"id": cid}, {"$set": cambios})
        tocados += 1
        if len(muestra) < 8:
            muestra.append(f"  {cid[:8]}  ajuste {a or '-'}  reporte {r or '-'}")

    print("\n".join(muestra))
    print(f"\n{tocados} clientes con fecha, {sin_nada} sin ningun ajuste ni reporte")
    print("ESCRITO" if escribir else "SIMULACION: nada escrito (pasa --escribir)")


if __name__ == "__main__":
    asyncio.run(main("--escribir" in sys.argv))
