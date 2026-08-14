# -*- coding: utf-8 -*-
"""Escribe la fecha real de fin a los migrados cuya membresia de Calma ya vencio.

Francisco, 13-08-2026: «si la membresia se vencio se vencio y listo, no entran».

QUE PASA AL EJECUTAR ESTO
-------------------------
Hasta hoy `current_period_end` estaba a null en todos los migrados, asi que la app no
sabia cuando se les acababa el ciclo y entraban igual. El sincronizador de ciclos escribio
la fecha a los 127 con la membresia viva y dejo fuera a los 50 vencidos a proposito,
porque eso les cierra el acceso y es una decision de negocio, no tecnica. Ya esta tomada.

No es una puerta cerrada en la cara: `core/plan_access.py` distingue entre no haber
empezado nunca y haber terminado. A estos les sale el mensaje de «caducado», que dice que
se le acabo y a quien escribir, no el de bienvenida de un desconocido.

NO TOCA A NADIE QUE ESTE PAGANDO. Si el perfil tiene una suscripcion de Stripe viva
gestionada por la app, manda esa y aqui no se entra. Medido: de los 50, ninguno tiene
Stripe, pero la comprobacion se queda escrita porque manana puede haber uno.

    python _cerrar_membresias_vencidas.py             enseña a quien afecta, sin tocar nada
    python _cerrar_membresias_vencidas.py --escribir  lo hace
"""
import asyncio
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PROD = "mongodb://127.0.0.1:27018"
BASE = "jg12_restored"
ESCRIBIR = "--escribir" in sys.argv


async def main():
    from motor.motor_asyncio import AsyncIOMotorClient

    db = AsyncIOMotorClient(PROD, serverSelectionTimeoutMS=20000)[BASE]
    hoy = datetime.now(timezone.utc).isoformat()[:10]

    users = {}
    async for u in db.users.find({"deleted_at": None}, {"_id": 0, "id": 1, "email": 1, "name": 1}):
        if u.get("email"):
            users[u["email"].lower()] = u

    afectados, con_stripe, ya_puestos = [], [], 0
    async for c in db.calma_raw.find({}, {"_id": 0, "email": 1, "client_id": 1, "fin_membresia": 1}):
        email = (c.get("email") or "").lower()
        fin = c.get("fin_membresia") or ""
        if not (users.get(email) and fin and fin[:10] < hoy and c.get("client_id")):
            continue
        perfil = await db.client_profiles.find_one(
            {"id": c["client_id"]},
            {"_id": 0, "id": 1, "current_period_end": 1, "stripe_subscription_id": 1,
             "subscription_status": 1, "status": 1})
        if not perfil:
            continue
        if perfil.get("stripe_subscription_id"):
            con_stripe.append((email, perfil.get("subscription_status")))
            continue
        if (perfil.get("current_period_end") or "")[:10] == fin[:10]:
            ya_puestos += 1
            continue
        dias = (datetime.fromisoformat(hoy).date() - datetime.fromisoformat(fin[:10]).date()).days
        afectados.append({"email": email, "nombre": users[email].get("name"),
                          "client_id": c["client_id"], "fin": fin[:10], "dias": dias})

    afectados.sort(key=lambda x: -x["dias"])
    print(f"{'SE VA A ESCRIBIR' if ESCRIBIR else 'ENSAYO, no se toca nada'}\n")
    print(f"clientes a los que se les cierra el acceso: {len(afectados)}")
    print(f"respetados por tener suscripcion de Stripe viva: {len(con_stripe)}")
    print(f"ya tenian su fecha puesta: {ya_puestos}\n")
    for a in afectados:
        print(f"   vencio {a['fin']}  hace {a['dias']:4} dias   {a['email'][:40]}")

    if not ESCRIBIR:
        print("\nPara hacerlo: --escribir")
        return

    n = 0
    for a in afectados:
        r = await db.client_profiles.update_one(
            {"id": a["client_id"]},
            {"$set": {"current_period_end": a["fin"],
                      # Deja rastro de que esta fecha viene de la membresia de Calma y no
                      # de un cobro de la app, que si no dentro de un mes nadie sabe de
                      # donde salio.
                      "current_period_end_origen": "calma_fin_membresia",
                      "current_period_end_puesto_en": datetime.now(timezone.utc).isoformat()}})
        n += r.modified_count
    print(f"\nperfiles actualizados: {n}")

    # Y se comprueba con la funcion de verdad de la app, no con la teoria.
    from core.plan_access import can, estado_de_acceso
    sin_acceso = 0
    for a in afectados[:200]:
        p = await db.client_profiles.find_one({"id": a["client_id"]}, {"_id": 0})
        if not can(p, "nutricion") if False else True:
            estado = estado_de_acceso(p)
            if not estado.get("tiene_acceso", estado.get("acceso", True)):
                sin_acceso += 1
    print(f"comprobado con la funcion de la app: {sin_acceso} de {len(afectados)} se quedan sin acceso")

asyncio.run(main())
