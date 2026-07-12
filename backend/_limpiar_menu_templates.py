"""Vacía db.menu_templates (menús preestablecidos) dejando antes un backup JSON.

Uso: ./venv/Scripts/python.exe _limpiar_menu_templates.py
"""
import asyncio
import json
import os
from datetime import datetime

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


async def main():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ.get("DB_NAME", "test_database")]

    docs = await db.menu_templates.find({}, {"_id": 0}).to_list(5000)
    print(f"Menus encontrados: {len(docs)}")

    if docs:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = os.path.join(os.path.dirname(__file__), f"_backup_menu_templates_{stamp}.json")
        with open(backup, "w", encoding="utf-8") as f:
            json.dump(docs, f, ensure_ascii=False, indent=2)
        print(f"Backup guardado en: {backup}")

        result = await db.menu_templates.delete_many({})
        print(f"Eliminados: {result.deleted_count}")

    restantes = await db.menu_templates.count_documents({})
    print(f"Restantes en la coleccion: {restantes}")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
