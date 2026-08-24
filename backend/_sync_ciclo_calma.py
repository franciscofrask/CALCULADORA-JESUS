# -*- coding: utf-8 -*-
"""El ciclo de cada cliente arranca y termina el mismo dia que en Calma.

Francisco, 17-08-2026: «quiero que su ciclo haya arrancado el mismo dia que el de Calma y
termine el mismo dia que en Calma».

QUE ESTABA MAL
--------------
`core/cycle.compute_cycle` calcula la semana desde `cycle_start`, y si no lo hay, desde
`created_at`. Medido en produccion antes de tocar nada:

    perfiles activos ........................... 186
    con `cycle_start` puesto ....................  1
    con `created_at` = 2026-07-04 .............. 158   <- el dia de la importacion masiva
    en «semana 7» a la vez ..................... 161

O sea que la semana del ciclo no era la de cada cliente: era la de la importacion, la misma
para todos. Y de esa semana dependen las ventanas de reporte del doc del 16-08 y la pantalla
de renovacion de la semana 12.

DE DONDE SALE EL DATO BUENO
---------------------------
De la membresia de Calma (Firestore `usuarios/{email}.membresia`), que es un tramo por
contrato con su `inicio` y su `fin`. Se toma el que cubre HOY; si no hay ninguno (por
ejemplo el que renovo y su tramo nuevo empieza en unos dias), el que aun no ha vencido.

    inicio  ->  client_profiles.cycle_start
    fin     ->  client_profiles.current_period_end

NO se toca a quien tenga una suscripcion viva en Stripe: ahi manda Stripe y no Calma.

    python _sync_ciclo_calma.py             enseña lo que cambiaria y NO escribe
    python _sync_ciclo_calma.py --escribir  lo escribe
"""
import asyncio
import os
import sys
from collections import Counter
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import firebase_admin
from firebase_admin import credentials, firestore
from motor.motor_asyncio import AsyncIOMotorClient

from _destino_sync import destino, no_entra, rotulo, solo_correos   # --dev escribe en desarrollo
PROD, BASE_PROD = destino()
SOLO = solo_correos()   # --solo fichero.txt limita la pasada
BASE = BASE_PROD
ESCRIBIR = "--escribir" in sys.argv
HOY = datetime.now(timezone.utc)

if not firebase_admin._apps:
    firebase_admin.initialize_app(credentials.Certificate(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "serviceAccountKey.json")))
fs = firestore.client()


def tramo_vigente(doc: dict):
    """El tramo de membresia que vale hoy: el que cubre HOY y, si no, el que no ha vencido."""
    tramos = [m for m in (doc.get("membresia") or [])
              if isinstance(m, dict) and m.get("inicio") and m.get("fin")]
    cubren = [m for m in tramos if m["inicio"] <= HOY <= m["fin"]]
    if cubren:
        return max(cubren, key=lambda x: x["fin"])
    sin_vencer = [m for m in tramos if m["fin"] >= HOY]
    return max(sin_vencer, key=lambda x: x["fin"]) if sin_vencer else None


async def main():
    db = AsyncIOMotorClient(PROD, serverSelectionTimeoutMS=20000)[BASE]
    print(f"{'ENSAYO (no escribe)' if not ESCRIBIR else 'ESCRIBIENDO EN ' + rotulo()}\n")

    usuarios = {}
    async for u in db.users.find({}, {"_id": 0, "id": 1, "email": 1, "name": 1}):
        if no_entra(u.get("email"), SOLO):
            continue
        if u.get("email"):
            usuarios[u["email"].lower()] = u

    cambios, con_stripe, ya_estaban, sin_tramo = [], [], 0, 0

    for d in fs.collection("usuarios").stream():
        u = usuarios.get(d.id.lower())
        if not u:
            continue
        m = tramo_vigente(d.to_dict() or {})
        if not m:
            continue
        perfil = await db.client_profiles.find_one(
            {"user_id": u["id"]},
            {"_id": 0, "id": 1, "plan": 1, "cycle_start": 1, "current_period_end": 1,
             "stripe_subscription_id": 1, "subscription_status": 1})
        if not perfil:
            continue
        if perfil.get("stripe_subscription_id"):
            con_stripe.append(u["email"])
            continue

        inicio = m["inicio"].date().isoformat()
        fin = m["fin"].date().isoformat()
        ini_ahora = str(perfil.get("cycle_start") or "")[:10]
        fin_ahora = str(perfil.get("current_period_end") or "")[:10]
        if ini_ahora == inicio and fin_ahora == fin:
            ya_estaban += 1
            continue
        cambios.append((u.get("name"), u["email"], perfil["id"], perfil.get("plan"),
                        ini_ahora or "(vacio)", inicio, fin_ahora or "(vacio)", fin))

    print(f"clientes de Calma con cuenta aqui que se ponen al dia: {len(cambios)}")
    print(f"   ya cuadraban: {ya_estaban}")
    print(f"   con Stripe vivo (manda Stripe, no se tocan): {len(con_stripe)}")

    print(f"\n   {'nombre':24}{'plan':16}{'arranque':26}{'fin'}")
    distinto_fin = [c for c in cambios if c[6] != c[7]]
    print(f"   de esos, con el FIN distinto al de Calma: {len(distinto_fin)}")
    for n, _c, _pid, plan, ia, inuevo, fa, fnuevo in cambios[:25]:
        print(f"   {str(n)[:22]:24}{str(plan):16}{ia:12}-> {inuevo:12}{fa:12}-> {fnuevo}")
    if len(cambios) > 25:
        print(f"   ... y {len(cambios) - 25} mas")

    if not ESCRIBIR:
        print("\n(ensayo: no se ha escrito nada. Con --escribir se aplica)")
        return

    for _n, _c, pid, _plan, _ia, inicio, _fa, fin in cambios:
        await db.client_profiles.update_one(
            {"id": pid},
            {"$set": {"cycle_start": inicio,
                      "current_period_end": fin,
                      "ciclo_origen": "calma_membresia",
                      "ciclo_puesto_en": HOY.date().isoformat()}})
    print(f"\nescritos {len(cambios)} perfiles")


asyncio.run(main())
