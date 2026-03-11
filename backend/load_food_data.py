#!/usr/bin/env python3
"""
Script para cargar los datos de alimentos y categorías en MongoDB.
Uso: python load_food_data.py
"""

import asyncio
import json
import httpx
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path
import os

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# URLs de los archivos JSON
ALIMENTOS_URL = "https://customer-assets.emergentagent.com/job_f05fe051-b128-4de4-aae5-eef07210351c/artifacts/f5fk8e1c_alimentos_completos%20%281%29.json"
CATEGORIAS_URL = "https://customer-assets.emergentagent.com/job_f05fe051-b128-4de4-aae5-eef07210351c/artifacts/k8rt8bmx_categorias_completas%20%281%29.json"

async def download_json(url: str) -> list:
    """Descarga un archivo JSON desde una URL."""
    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=60.0)
        response.raise_for_status()
        return response.json()

async def load_data():
    """Carga los datos de alimentos y categorías en MongoDB."""
    # Conexión a MongoDB
    mongo_url = os.environ['MONGO_URL']
    db_name = os.environ['DB_NAME']
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    print("=" * 50)
    print("CARGA DE DATOS DE ALIMENTOS Y CATEGORÍAS")
    print("=" * 50)
    
    # Descargar datos
    print("\n📥 Descargando archivos JSON...")
    alimentos = await download_json(ALIMENTOS_URL)
    categorias = await download_json(CATEGORIAS_URL)
    
    print(f"   - Alimentos descargados: {len(alimentos)}")
    print(f"   - Categorías descargadas: {len(categorias)}")
    
    # Limpiar colecciones existentes
    print("\n🗑️  Limpiando colecciones existentes...")
    await db.foods.delete_many({})
    await db.food_categories.delete_many({})
    
    # Insertar categorías
    print("\n📁 Insertando categorías...")
    if categorias:
        await db.food_categories.insert_many(categorias)
    categories_count = await db.food_categories.count_documents({})
    print(f"   ✅ Categorías insertadas: {categories_count}")
    
    # Insertar alimentos
    print("\n🍎 Insertando alimentos...")
    if alimentos:
        await db.foods.insert_many(alimentos)
    foods_count = await db.foods.count_documents({})
    print(f"   ✅ Alimentos insertados: {foods_count}")
    
    # Crear índices para búsqueda eficiente
    print("\n🔍 Creando índices...")
    await db.foods.create_index("nombre")
    await db.foods.create_index("categorias")
    await db.foods.create_index("id", unique=True)
    await db.food_categories.create_index("id", unique=True)
    print("   ✅ Índices creados")
    
    # Verificación final
    print("\n" + "=" * 50)
    print("RESUMEN DE CARGA")
    print("=" * 50)
    print(f"✅ Total de ALIMENTOS cargados: {foods_count}")
    print(f"✅ Total de CATEGORÍAS cargadas: {categories_count}")
    print("=" * 50)
    
    # Mostrar ejemplos
    print("\n📋 Ejemplos de datos cargados:")
    print("\nPrimeros 3 alimentos:")
    async for food in db.foods.find().limit(3):
        food.pop('_id', None)
        print(f"   - {food['nombre']} (P:{food['proteinas']}g, H:{food['hidratos']}g, G:{food['grasas']}g)")
    
    print("\nPrimeras 3 categorías:")
    async for cat in db.food_categories.find().limit(3):
        cat.pop('_id', None)
        print(f"   - [{cat['id']}] {cat['nombre']}")
    
    client.close()
    return foods_count, categories_count

if __name__ == "__main__":
    foods, categories = asyncio.run(load_data())
    print(f"\n🎉 ¡Carga completada exitosamente!")
