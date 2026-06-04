
import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from pathlib import Path
from dotenv import load_dotenv
import json

async def inspect_diets():
    env_path = Path("backend/.env")
    load_dotenv(env_path)
    
    mongo_url = os.environ.get('MONGO_URL')
    db_name = os.environ.get('DB_NAME')
    
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    print(f"Checking diets in DB: {db_name}")
    
    try:
        # Get the 3 most recently updated diets
        cursor = db.diets.find().sort("updated_at", -1).limit(3)
        diets = await cursor.to_list(length=3)
        
        if not diets:
            print("No diets found in database.")
            return

        for diet in diets:
            print(f"\n--- Diet for Date: {diet.get('fecha')} (User: {diet.get('user_id')}) ---")
            print(f"Updated At: {diet.get('updated_at')}")
            print(f"Has distribution_targets: {'Yes' if 'distribution_targets' in diet and diet['distribution_targets'] else 'No'}")
            if 'distribution_targets' in diet and diet['distribution_targets']:
                print(f"distribution_targets content: {json.dumps(diet['distribution_targets'], indent=2)}")
            else:
                print("Field 'distribution_targets' is missing or null.")
            
            # Also check if it's in the profile? (Just in case)
            profile = await db.client_profiles.find_one({"user_id": diet.get('user_id')})
            if profile:
                 print(f"Profile has goal: {profile.get('goal')}")
                
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(inspect_diets())
