"""
Seccion 6 del doc: el mismo cuestionario, distinto comportamiento segun el plan.
  - plan con entrenador -> se calcula pero NO se aplica; queda propuesta y avisa al coach
  - plan que se autogestiona -> se aplica solo
"""
import asyncio
import uuid

import httpx

from core.database import db

BASE = "http://localhost:8000/api"


def m(macros):
    if not macros:
        return "sin macros"
    e = macros.get("training") or macros.get("macros_training") or {}
    return f"{e.get('proteinas', e.get('protein', '?'))}P {e.get('hidratos', e.get('carbs', '?'))}H"


async def un_caso(plan, etiqueta, coach_id=None):
    email = f"plan_{plan}_{uuid.uuid4().hex[:6]}@test.com"
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(f"{BASE}/auth/register", json={
            "email": email, "password": "Prueba1234", "name": f"Cliente {plan}", "phone": "600000000"})
        tok, uid = r.json()["access_token"], r.json()["user"]["id"]
        h = {"Authorization": f"Bearer {tok}"}
        cid = str(uuid.uuid4())
        await db.client_profiles.insert_one({
            "id": cid, "user_id": uid, "name": f"Cliente {plan}", "email": email,
            "plan": plan, "price": 0, "status": "activo", "week": 1,
            "trainer_id": coach_id, "created_at": "2026-07-29T00:00:00+00:00",
        })
        await c.post(f"{BASE}/clients/questionnaire", headers=h, json={
            "goal": "definicion", "sex": "hombre", "weight": 85, "body_fat": 18})
        perfil_antes = await db.client_profiles.find_one({"id": cid}, {"_id": 0, "macros_training": 1})

        r = await c.post(f"{BASE}/clients/ajustar-macros", headers=h, json={
            "actividad_diaria": "muy_activo", "deporte_extra": True,
            "facilidad_engordar": "normal", "sigue_dieta": False})
        entrega = (r.json() or {}).get("entrega") or {}
        propuesto = (r.json().get("resultado") or {}).get("macros", {}).get("entreno", {})
        perfil_despues = await db.client_profiles.find_one({"id": cid}, {"_id": 0, "macros_training": 1})

        propuestas = await db.macro_sugerencias.count_documents({"client_id": cid, "origen": "cuestionario_cliente"})
        avisos = await db.notifications.count_documents({"client_id": cid, "type": "macros_propuestos"}) if coach_id else 0

        print(f"\n{etiqueta}  (plan {plan})")
        print(f"   propuesto por el motor : {propuesto.get('proteina')}P {propuesto.get('hidratos')}H")
        print(f"   macros del perfil ANTES: {m(perfil_antes)}")
        print(f"   macros del perfil AHORA: {m(perfil_despues)}")
        print(f"   aplicado automaticamente: {entrega.get('aplicado')}")
        print(f"   propuesta para el coach : {propuestas}   aviso al coach: {avisos}")
        print(f"   coach que revisara     : {entrega.get('coach')}")

    for col in ("client_profiles", "macro_history", "quiz_respuestas", "macro_sugerencias",
                "macro_revisiones", "notifications"):
        await db[col].delete_many({"$or": [{"user_id": uid}, {"client_id": cid}]})
    await db.users.delete_one({"id": uid})


async def main():
    coach = await db.users.find_one({"role": {"$in": ["trainer", "admin"]}}, {"_id": 0, "id": 1, "name": 1})
    print("coach de la prueba:", (coach or {}).get("name"))
    await un_caso("elm", "CON ENTRENADOR", (coach or {}).get("id"))
    await un_caso("calculadora_jp", "SE AUTOGESTIONA")

asyncio.run(main())
