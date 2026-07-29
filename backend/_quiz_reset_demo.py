# -*- coding: utf-8 -*-
"""DEV: inspecciona y (con --reset) resetea el cuestionario del cliente demo para
poder recorrer el quiz desde el principio, incluido Nivel 1 (plan con coach)."""
import asyncio, sys
sys.stdout.reconfigure(encoding="utf-8")
from core.database import db as mdb

EMAIL = "clientedemo@test.com"

async def main():
    reset = "--reset" in sys.argv
    u = await mdb.users.find_one({"email": EMAIL}, {"_id": 0})
    if not u:
        print("no existe", EMAIL); return
    prof = await mdb.client_profiles.find_one({"user_id": u["id"]}, {"_id": 0})
    campos = ["plan", "calculadora", "questionnaire_completed", "status",
              "goal", "sex", "weight", "body_fat", "nivel1", "week"]
    print("=== ANTES ===")
    print("user:", {k: u.get(k) for k in ("id", "email", "name", "role", "plan")})
    print("profile:", {k: (prof or {}).get(k) for k in campos})

    if reset:
        await mdb.client_profiles.update_one({"user_id": u["id"]}, {"$set": {
            "questionnaire_completed": False,
            "calculadora": "personalizado",  # para que aparezca Nivel 1 (coach)
            "status": "activo",
        }})
        prof2 = await mdb.client_profiles.find_one({"user_id": u["id"]}, {"_id": 0})
        print("\n=== DESPUES (reset) ===")
        print("profile:", {k: prof2.get(k) for k in campos})

asyncio.run(main())
