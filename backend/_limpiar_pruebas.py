"""Borra los usuarios de prueba que dejan los scripts de test si fallan a mitad."""
import asyncio
from core.database import db

PATRON = {"$regex": "^(prueba_alta_|recorrido_quiz)", "$options": "i"}
COLS = ["client_profiles", "macro_history", "quiz_respuestas", "diets", "macro_sugerencias",
        "macro_revisiones", "checkins", "reports", "chatbot_sessions", "notifications"]


async def r():
    usuarios = await db.users.find({"email": PATRON}, {"_id": 0, "id": 1, "email": 1}).to_list(200)
    if not usuarios:
        print("no hay usuarios de prueba")
        return
    for u in usuarios:
        print(f"borrando {u['email']}")
        for col in COLS:
            res = await db[col].delete_many({"user_id": u["id"]})
            if res.deleted_count:
                print(f"    {col}: {res.deleted_count}")
        await db.users.delete_one({"id": u["id"]})
    print(f"\n{len(usuarios)} usuarios de prueba borrados")

asyncio.run(r())
