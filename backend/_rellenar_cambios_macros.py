"""
Rellena `cambios` en los ajustes que ya estaban en el historial (punto 31 del doc del 07-08).

A partir de ahora lo escribe cada guardado, pero el historial que ya hay no lo trae, y es
justo el que tiene que leer el modelo: sin esto, "que palanca movio el coach" solo existiria
para los ajustes de esta semana en adelante.

Con que se compara cada entrada:

  - Con `previous_training` / `previous_rest`, que ya se guardaban en la propia entrada. Es
    lo mas fiel: son los macros que el cliente tenia justo antes de ese cambio.
  - El perientreno no tiene equivalente guardado, asi que va contra el peri de la entrada
    anterior en el tiempo.
  - Y si una entrada no trae `previous_*` (las importadas de Calma), contra la anterior.

  python _rellenar_cambios_macros.py             simula, no escribe
  python _rellenar_cambios_macros.py --escribir  escribe
"""
import asyncio
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from core.database import db                                      # noqa: E402
from core.cambios_macros import marcar_cambios, palancas          # noqa: E402


def _fecha(h):
    return (h.get("effective_date") or (h.get("created_at") or "")[:10] or "", h.get("created_at") or "")


async def main(escribir: bool):
    por_cliente = defaultdict(list)
    async for h in db.macro_history.find({}, {"_id": 0}):
        if h.get("client_id"):
            por_cliente[h["client_id"]].append(h)
    print(f"{len(por_cliente)} clientes con historial, "
          f"{sum(len(v) for v in por_cliente.values())} ajustes")

    con_cambios, sin_anterior, muestra = 0, 0, []
    reparto = defaultdict(int)

    for cid, entradas in por_cliente.items():
        entradas.sort(key=_fecha)          # de la mas antigua a la mas reciente
        for i, h in enumerate(entradas):
            anterior = entradas[i - 1] if i > 0 else None
            antes = {
                "entreno": h.get("previous_training") or (anterior or {}).get("training"),
                "descanso": h.get("previous_rest") or (anterior or {}).get("rest"),
                "perientreno": (anterior or {}).get("peri"),
            }
            cambios = marcar_cambios(antes, {
                "entreno": h.get("training"), "descanso": h.get("rest"), "perientreno": h.get("peri"),
            })
            if cambios is None:
                sin_anterior += 1
                continue
            con_cambios += 1
            for p in palancas(cambios):
                reparto[p] += 1
            if escribir:
                await db.macro_history.update_one({"id": h["id"]}, {"$set": {"cambios": cambios}})
            if len(muestra) < 6 and palancas(cambios):
                muestra.append(f"  {h.get('effective_date') or '?'}  {cid[:8]}  ->  {', '.join(palancas(cambios))}")

    print("\n".join(muestra) or "  (nada que ensenar)")
    print(f"\n{con_cambios} ajustes con `cambios` calculado, {sin_anterior} sin nada anterior con que comparar")
    print("\nQue palanca se mueve mas, en todo el historico:")
    for palanca, n in sorted(reparto.items(), key=lambda x: -x[1]):
        print(f"  {palanca:24s} {n}")
    print("\nESCRITO" if escribir else "\nSIMULACION: nada escrito (pasa --escribir)")


if __name__ == "__main__":
    asyncio.run(main("--escribir" in sys.argv))
