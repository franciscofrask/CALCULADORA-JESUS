# -*- coding: utf-8 -*-
"""Punto 65: quien es el cliente «user» y que lleva colgando. SOLO MIRA."""
import asyncio, os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend", ".env"))

async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    print(f"base: {os.environ['DB_NAME']}\n")
    u = await db.users.find_one({"email": "user@user.com"}, {"_id": 0, "password": 0})
    if not u:
        print("no existe user@user.com"); return
    print("== la cuenta ==")
    print(json.dumps(u, ensure_ascii=False, indent=2, default=str)[:1400])
    uid = u["id"]
    p = await db.client_profiles.find_one({"user_id": uid}, {"_id": 0})
    print(f"\n== su ficha == {'existe' if p else 'NO tiene ficha'}")
    if p:
        interesa = {k: p.get(k) for k in ("id", "nombre", "apellidos", "plan", "status", "price",
                                          "access_until", "created_at", "trainer_id", "es_prueba",
                                          "stripe_customer_id", "stripe_subscription_id")}
        print(json.dumps(interesa, ensure_ascii=False, indent=2, default=str))
    cid = (p or {}).get("id")
    print("\n== que hay colgando de esa cuenta ==")
    por_user = ["diets", "diet_favorites", "checkins", "notifications", "messages", "chatbot_sessions",
                "macro_history", "food_favorites", "quiz_respuestas", "payments", "food_suggestions"]
    for c in por_user:
        try:
            n = await db[c].count_documents({"user_id": uid})
            if n: print(f"   {c:<20} {n}  (por user_id)")
        except Exception as e:
            print(f"   {c}: {e}")
    if cid:
        for c in ["routines", "reports", "coach_reports", "client_photos", "workout_logs",
                  "supplement_protocols", "client_supplementation", "alerts", "tareas", "macro_revisiones"]:
            try:
                n = await db[c].count_documents({"client_id": cid})
                if n: print(f"   {c:<20} {n}  (por client_id)")
            except Exception as e:
                print(f"   {c}: {e}")
    print("\n== y si ha entrado alguna vez ==")
    print(f"   last_login: {u.get('last_login')}   created_at: {u.get('created_at')}")
    n = await db.payments.count_documents({"user_id": uid})
    print(f"   cobros: {n}")

asyncio.run(main())
