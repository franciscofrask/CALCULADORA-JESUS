# -*- coding: utf-8 -*-
"""
Alta y limpieza de los 20 usuarios simulados en la BD de PRUEBAS.
- registrar_y_preparar(): registra los 20 por la API real, promueve 10 a trainer
  (en la BD, como haría un admin: el registro público solo crea clientes) y reparte
  los 10 clientes entre los trainers (trainer_id), imitando la asignación del panel.
- limpiar(): borra TODO lo que hayan generado los usuarios @simulacion.test.
"""
import os
import sys
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from motor.motor_asyncio import AsyncIOMotorClient
from _simulacion._core import (
    Api, Persona, construir_personas, PASSWORD, DOMINIO, es_ok, hallazgo,
)


def _db():
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    return cli[os.environ.get("DB_NAME", "test_database")]


async def limpiar():
    """Borra los usuarios simulados y todos sus datos derivados."""
    db = _db()
    users = await db.users.find({"email": {"$regex": f"@{DOMINIO}$"}}, {"_id": 0, "id": 1}).to_list(100)
    ids = [u["id"] for u in users]
    if not ids:
        print("No hay usuarios simulados que limpiar.")
        return
    colecciones = ["client_profiles", "diets", "macro_history", "macro_logs", "reports",
                   "checkins", "messages", "notifications", "routines", "supplement_plans",
                   "payments", "alerts", "food_favorites"]
    total = 0
    for col in colecciones:
        for campo in ("user_id", "client_id", "trainer_id", "from_user_id", "to_user_id"):
            try:
                r = await db[col].delete_many({campo: {"$in": ids}})
                total += r.deleted_count
            except Exception:
                pass
    r = await db.users.delete_many({"id": {"$in": ids}})
    print(f"Limpieza: {r.deleted_count} usuarios + {total} documentos derivados borrados.")


async def registrar_y_preparar(personas: list):
    """Registra las 20 personas, promueve trainers y asigna clientes. Modifica las personas
    en sitio (rellena api/user_id/token/trainer_id)."""
    db = _db()

    # Por idempotencia: limpiar restos de una corrida anterior
    await limpiar()

    # 1) Registro por la API pública (todos entran como 'client')
    for p in personas:
        p.api = Api(etiqueta=f"{p.rol}{p.idx}")
        st, body = p.api.post("/auth/register", auth=False, json_body={
            "email": p.email, "password": PASSWORD, "name": p.nombre, "phone": p.telefono,
        })
        if not es_ok(st):
            hallazgo("BUG", "alta", f"No se pudo registrar {p.email}",
                     f"status={st} body={body}", endpoint="POST /auth/register")
            continue
        p.api.token = body.get("access_token")
        p.user_id = (body.get("user") or {}).get("id")

    # 2) Promover 10 a trainer (rol) directamente en la BD (no hay endpoint público)
    trainers = [p for p in personas if p.rol == "trainer"]
    clientes = [p for p in personas if p.rol == "client"]
    for p in trainers:
        if p.user_id:
            await db.users.update_one({"id": p.user_id}, {"$set": {"role": "trainer"}})
            # re-login para obtener un token con el rol nuevo
            st, body = p.api.post("/auth/login", auth=False,
                                  json_body={"email": p.email, "password": PASSWORD})
            if es_ok(st):
                p.api.token = body.get("access_token")

    # 3) Asignar cada cliente a un trainer (round-robin), como el panel del admin.
    #    Se hace en la BD del perfil; pero el perfil aún no existe (se crea al pagar el plan).
    #    Guardamos la intención en la persona; la asignación real se prueba en los flujos.
    for i, c in enumerate(clientes):
        c.trainer_id = trainers[i % len(trainers)].user_id

    ok_t = sum(1 for p in trainers if p.user_id)
    ok_c = sum(1 for p in clientes if p.user_id)
    print(f"Preparados: {ok_t}/10 entrenadores, {ok_c}/10 clientes.")
    return personas


# Planes variados para ejercitar el gating por plan (rutina/reportes/suplementos).
# El cliente 9 queda SIN plan a propósito (prueba del estado "sin plan / no pagado").
PLANES_CLIENTE = [
    "reto12en12_gold", "reto12en12_gold", "reto12en12_silver", "reto12en12_silver",
    "elm", "reto60", "mantenimiento", "calculadora_jp", "elm", None,
]


async def activar_planes(personas: list):
    """Crea perfiles ACTIVOS para los clientes (como un plan cortesía del admin), con
    planes variados y su trainer asignado. El self-service directo está bloqueado, así que
    esto imita el alta manual del panel. El cliente 9 queda sin plan."""
    import uuid
    from datetime import datetime, timezone, timedelta
    db = _db()
    clientes = [p for p in personas if p.rol == "client"]
    for i, c in enumerate(clientes):
        plan = PLANES_CLIENTE[i]
        if not plan or not c.user_id:
            continue
        now = datetime.now(timezone.utc)
        prof = {
            "id": str(uuid.uuid4()),
            "user_id": c.user_id,
            "plan": plan,
            "price": 100.0,
            "week": 1,
            "status": "activo",
            "trainer_id": c.trainer_id,
            "subscription_status": "active",
            "checkout_status": "completed",
            "comp_plan": True,
            "cycle_start": now.strftime("%Y-%m-%d"),
            "current_period_start": now.isoformat(),
            "current_period_end": (now + timedelta(days=84)).isoformat(),
            "next_payment": (now + timedelta(days=84)).isoformat(),
            "created_at": now.isoformat(),
        }
        await db.client_profiles.insert_one(prof)
        await db.users.update_one({"id": c.user_id}, {"$set": {"plan": plan, "trainer_id": c.trainer_id}})
        c.plan = plan
        c.profile_id = prof["id"]
    print("Planes activados:", {c.email.split('@')[0]: c.plan for c in clientes})


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--limpiar", action="store_true")
    args = ap.parse_args()
    if args.limpiar:
        asyncio.run(limpiar())
    else:
        asyncio.run(registrar_y_preparar(construir_personas()))
