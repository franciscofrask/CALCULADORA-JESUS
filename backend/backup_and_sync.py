"""
Backup foods collection to Desktop, then sync with Calma (3110 base + Firestore approved).
"""
import asyncio
import json
import urllib.request
import os
from pathlib import Path
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

MONGO_URL = os.environ['MONGO_URL']
DB_NAME = os.environ['DB_NAME']

BASE_JSON_URL = "https://customer-assets.emergentagent.com/job_f05fe051-b128-4de4-aae5-eef07210351c/artifacts/f5fk8e1c_alimentos_completos%20%281%29.json"

FIRESTORE_URL = (
    "https://firestore.googleapis.com/v1/projects/jesusgallegopt"
    "/databases/calma-alimentos/documents/alimentos_aprobados"
    "?key=AIzaSyCDeFM3SpZBxrAFQzhnZkm5LtnREjg_KTs&pageSize=300"
)

DESKTOP = Path.home() / "Desktop"


def fs_get_value(field):
    if field is None:
        return None
    for vtype in ['stringValue', 'integerValue', 'doubleValue', 'booleanValue']:
        if vtype in field:
            val = field[vtype]
            return int(val) if vtype == 'integerValue' else val
    if 'arrayValue' in field:
        return [fs_get_value(v) for v in field['arrayValue'].get('values', [])]
    return None


def fetch_json_url(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def fetch_firestore_all():
    all_docs = []
    url = FIRESTORE_URL
    page = 0
    while url:
        data = fetch_json_url(url)
        docs = data.get('documents', [])
        all_docs.extend(docs)
        page += 1
        token = data.get('nextPageToken')
        url = FIRESTORE_URL + f"&pageToken={token}" if token else None
        print(f"  Firestore page {page}: {len(docs)} docs")
    return all_docs


def transform_firestore(docs):
    alimentos = []
    for doc in docs:
        f = doc.get('fields', {})
        categorias_arr = fs_get_value(f.get('categorias')) or []
        minimo_raw = f.get('minimo')
        minimo = None
        if minimo_raw and 'nullValue' not in minimo_raw:
            minimo = fs_get_value(minimo_raw)
        a = {
            'id': fs_get_value(f.get('alimentoId')),
            'nombre': fs_get_value(f.get('nombre')),
            'categorias': ' | '.join(str(c) for c in categorias_arr if c is not None),
            'racion': fs_get_value(f.get('racion')) or 100,
            'proteinas': float(fs_get_value(f.get('proteinas')) or 0),
            'hidratos': float(fs_get_value(f.get('hidratos')) or 0),
            'grasas': float(fs_get_value(f.get('grasas')) or 0),
            'unidades': fs_get_value(f.get('unidades')) or False,
            'minimo': minimo,
            'url': fs_get_value(f.get('url')),
        }
        foto_frente = fs_get_value(f.get('fotoFrente'))
        foto_reverso = fs_get_value(f.get('fotoReverso'))
        if foto_frente:
            a['foto_frente'] = foto_frente
        if foto_reverso:
            a['foto_reverso'] = foto_reverso
        alimentos.append(a)
    return alimentos


async def main():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # ── 1. BACKUP ─────────────────────────────────────────────────────────────
    print("\n=== BACKUP ===")
    current_foods = await db.foods.find({}, {"_id": 0}).to_list(length=None)
    print(f"  Foods actuales en DB: {len(current_foods)}")

    backup_path = DESKTOP / "backup_foods_calculadora.json"
    with open(backup_path, 'w', encoding='utf-8') as f:
        json.dump(current_foods, f, ensure_ascii=False, indent=2, default=str)
    print(f"  Backup guardado: {backup_path}")

    # ── 2. DESCARGAR FUENTES ──────────────────────────────────────────────────
    print("\n=== DESCARGANDO FUENTES ===")
    print("  Bajando JSON base (3110 alimentos)...")
    base = fetch_json_url(BASE_JSON_URL)
    print(f"  JSON base: {len(base)} alimentos")

    print("  Bajando Firestore alimentos_aprobados...")
    fs_docs = fetch_firestore_all()
    fs_foods = transform_firestore(fs_docs)
    print(f"  Firestore aprobados: {len(fs_foods)} alimentos")

    # ── 3. MERGE ──────────────────────────────────────────────────────────────
    print("\n=== MERGE ===")
    by_id = {}
    for a in base:
        by_id[a['id']] = a
    for a in fs_foods:
        by_id[a['id']] = a  # approved overrides base if same id

    merged = sorted(by_id.values(), key=lambda x: x.get('id') or 0)
    print(f"  Total merged: {len(merged)} alimentos")

    # ── 4. SYNC MONGODB ───────────────────────────────────────────────────────
    print("\n=== SYNC MONGODB ===")
    await db.foods.delete_many({})
    print("  Colección foods vaciada")

    batch = 500
    for i in range(0, len(merged), batch):
        await db.foods.insert_many(merged[i:i+batch])
        print(f"  Insertados {min(i+batch, len(merged))}/{len(merged)}")

    # recreate indexes
    await db.foods.create_index("nombre")
    await db.foods.create_index("categorias")
    await db.foods.create_index("id", unique=True)
    print("  Índices recreados")

    final = await db.foods.count_documents({})
    print(f"\n✅ LISTO: {final} alimentos en DB")
    print(f"   Backup en: {backup_path}")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
