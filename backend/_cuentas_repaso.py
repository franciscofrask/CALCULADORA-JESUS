# -*- coding: utf-8 -*-
"""Las cuentas de prueba del repaso del 21-08 (doc 19-08 + doc 57), una por estado.

Francisco: «para las pruebas crearas cuentas correspondientes para poder ver cada
cambio funcionando». Cada cuenta deja un bloque a la vista:

  prueba.nivel1@test.com    nivel1 autogestion ACTIVO   -> 07 preferencias, 08 guia con
                                                           oferta, 09 Mis macros, 11 rapido
  prueba.bronze@test.com    bronze con coach ACTIVO     -> 09 oculto, 10 avisos, 11 rutina
                                                           del mes, audio NO
  prueba.porvencer@test.com nivel2 a 5 dias de vencer   -> 13 aviso «acaba en una semana»
  prueba.caducado@test.com  nivel1 vencido sin sub      -> 13 «Tu ciclo ha terminado»

Ya existian y se reutilizan: prueba.sinplan (13.1), prueba.legacy (silver 149,
renovar el mismo plan), clientedemo (gold, nutricion/doc 57), francisco admin.

Todas con password demo123. Registra por la API real (el flujo del alta de verdad)
y ajusta el perfil en Mongo. Idempotente.
"""
import os
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
API = "http://127.0.0.1:8000/api"
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
HOY = datetime.now(timezone.utc)

CUENTAS = [
    {"email": "prueba.nivel1@test.com", "name": "Prueba Nivel1", "plan": "nivel1",
     "fin": HOY + timedelta(weeks=9), "inicio": HOY - timedelta(weeks=3)},
    {"email": "prueba.bronze@test.com", "name": "Prueba Bronze", "plan": "bronze",
     "fin": HOY + timedelta(weeks=9), "inicio": HOY - timedelta(weeks=3)},
    {"email": "prueba.porvencer@test.com", "name": "Prueba Porvencer", "plan": "nivel2",
     "fin": HOY + timedelta(days=5), "inicio": HOY - timedelta(weeks=11)},
    {"email": "prueba.caducado@test.com", "name": "Prueba Caducado", "plan": "nivel1",
     "fin": HOY - timedelta(days=3), "inicio": HOY - timedelta(weeks=13)},
]

for c in CUENTAS:
    r = requests.post(f"{API}/auth/register", json={
        "email": c["email"], "password": "demo123", "name": c["name"], "phone": "600000000",
    }, timeout=30)
    creado = r.status_code in (200, 201)
    u = db.users.find_one({"email": c["email"]}, {"_id": 0, "id": 1})
    if not u:
        print(f"!! {c['email']}: no se pudo crear ({r.status_code} {r.text[:80]})")
        continue
    upd = {
        "plan": c["plan"], "status": "activo", "checkout_status": "completed",
        "plan_start": c["inicio"].isoformat(), "cycle_start": c["inicio"].date().isoformat(),
        "current_period_end": c["fin"].isoformat(),
        "price": 0, "cuenta_de_prueba": True,
    }
    db.client_profiles.update_one({"user_id": u["id"]}, {"$set": upd})
    db.users.update_one({"id": u["id"]}, {"$set": {"plan": c["plan"]}})
    print(f"ok {c['email']} · {c['plan']} · fin {c['fin'].date()} · {'creada' if creado else 'ya existia, ajustada'}")

print("\nlistas. password de todas: demo123")
