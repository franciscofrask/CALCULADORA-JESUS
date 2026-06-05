
import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from pathlib import Path
from dotenv import load_dotenv
import json

async def monitor_save():
    env_path = Path("backend/.env")
    load_dotenv(env_path)
    
    mongo_url = os.environ.get('MONGO_URL')
    db_name = os.environ.get('DB_NAME')
    
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    print(f"Buscando el volcado más reciente en la DB: {db_name}...")
    
    try:
        # Buscamos la dieta más reciente modificada hace pocos segundos/minutos
        cursor = db.diets.find().sort("updated_at", -1).limit(1)
        diets = await cursor.to_list(length=1)
        
        if not diets:
            print("No se encontraron dietas.")
            return

        diet = diets[0]
        print(f"\n--- ÚLTIMA DIETA GUARDADA ---")
        print(f"Fecha: {diet.get('fecha')}")
        print(f"Usuario ID: {diet.get('user_id')}")
        print(f"Actualizada el: {diet.get('updated_at')}")
        
        targets = diet.get('distribution_targets')
        if targets:
            print("✅ VOLCADO ENCONTRADO EN BASE DE DATOS:")
            print(json.dumps(targets, indent=2))
        else:
            print("❌ ERROR: El campo 'distribution_targets' está VACÍO o es NULO en la DB.")
            print("Contenido completo del documento (sin comidas para brevedad):")
            # Mostrar todo menos las comidas que son muy largas
            summary_diet = {k: v for k, v in diet.items() if k != 'comidas'}
            print(json.dumps(summary_diet, indent=2, default=str))

    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(monitor_save())
