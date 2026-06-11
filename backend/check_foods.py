import asyncio, os, json
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path('.env'))

async def check():
    db = AsyncIOMotorClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]

    names = ['Fiambre de jam', 'Lomo cocido (Hacendado)', 'Lomo cocido']
    for name in names:
        foods = await db.foods.find({'nombre': {'$regex': name, '$options': 'i'}}, {'_id': 0}).to_list(3)
        for f in foods[:1]:
            racion = f.get('racion', 100) or 100
            p = f.get('proteinas', 0) or 0
            h = f.get('hidratos', 0) or 0
            g = f.get('grasas', 0) or 0
            p100 = p/racion*100
            h100 = h/racion*100
            g100 = g/racion*100
            print(f"[{f['nombre']}] racion={racion} P={p}({p100:.1f}/100g) H={h}({h100:.1f}/100g) G={g}({g100:.1f}/100g) cats={f.get('categorias','')}")

asyncio.run(check())
