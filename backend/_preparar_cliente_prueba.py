"""
Prepara un cliente de prueba en dev para recorrer el cuestionario en el navegador.
Imprime el token para inyectarlo. Con --borrar, lo elimina todo.
"""
import asyncio
import sys
import uuid

import httpx

from core.database import db

BASE = "http://localhost:8000/api"
EMAIL = "recorrido_quiz@test.com"
PASS = "Recorrido1234"


async def borrar():
    u = await db.users.find_one({"email": EMAIL}, {"_id": 0, "id": 1})
    if not u:
        print("no habia nada que borrar")
        return
    for col in ("client_profiles", "macro_history", "quiz_respuestas", "diets"):
        r = await db[col].delete_many({"user_id": u["id"]})
        if r.deleted_count:
            print(f"  {col}: {r.deleted_count} borrados")
    await db.users.delete_one({"id": u["id"]})
    print("cliente de prueba borrado")


async def crear():
    await borrar()
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(f"{BASE}/auth/register", json={
            "email": EMAIL, "password": PASS, "name": "Recorrido Quiz", "phone": "600999888"})
        if r.status_code >= 300:
            print("ERROR en el registro:", r.status_code, r.text[:200])
            return
        tok = r.json()["access_token"]
        uid = r.json()["user"]["id"]

    await db.client_profiles.insert_one({
        "id": str(uuid.uuid4()), "user_id": uid, "name": "Recorrido Quiz", "email": EMAIL,
        "plan": "elm", "price": 0, "status": "activo", "week": 1,
        "start_date": "2026-07-29", "created_at": "2026-07-29T00:00:00+00:00",
    })
    print("cliente de prueba listo (sin alta hecha)")
    print("TOKEN:", tok)


if __name__ == "__main__":
    asyncio.run(borrar() if "--borrar" in sys.argv else crear())
