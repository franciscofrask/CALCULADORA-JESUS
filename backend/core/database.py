"""
Conexión a MongoDB y funciones de base de datos.
"""
from motor.motor_asyncio import AsyncIOMotorClient
from .config import MONGO_URL, DB_NAME

# MongoDB connection
client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

async def create_indexes():
    """Crear índices necesarios en MongoDB."""
    try:
        await db.foods.create_index([("nombre", "text")])
        await db.foods.create_index("id", unique=True)
        await db.foods.create_index("categorias")
        await db.diets.create_index([("user_id", 1), ("fecha", 1)], unique=True)
        await db.users.create_index("email", unique=True)
        await db.client_profiles.create_index("user_id", unique=True)
    except Exception as e:
        print(f"Error creating indexes: {e}")

async def close_connection():
    """Cerrar conexión a MongoDB."""
    client.close()
