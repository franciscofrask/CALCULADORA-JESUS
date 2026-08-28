# -*- coding: utf-8 -*-
"""Puntos 67 y 69: montar y desmontar PDF de rutina de prueba EN DEV.

En dev no hay PDF subidos (los datos no viajan), asi que para ver lo que pasa en
produccion hay que ponerlos a mano. Todos llevan el prefijo `PRUEBA-p67-` en el nombre,
y `--quitar` se los lleva todos, hayan salido de donde hayan salido.

  python _guia/_p67_pdfs_de_prueba.py --poner    a uno de cada cinco de los pendientes
  python _guia/_p67_pdfs_de_prueba.py --estado   cuantos hay y que dice el panel
  python _guia/_p67_pdfs_de_prueba.py --quitar   los borra todos
"""
import asyncio, os, sys, uuid, requests
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend", ".env"))
API = os.environ.get("API", "http://127.0.0.1:8000/api")
MARCA = "PRUEBA-p67-"


def panel():
    tok = requests.post(f"{API}/auth/login",
                        json={"email": "francisco@test.com", "password": "demo123"},
                        timeout=30).json()["access_token"]
    r = requests.get(f"{API}/admin/todo-semana",
                     headers={"Authorization": f"Bearer {tok}"}, timeout=180)
    r.raise_for_status()
    d = r.json()
    return (d.get("sin_rutina") or []), int(d.get("con_rutina_en_plan") or 0)


async def main():
    if os.environ.get("DB_NAME") == "jg12_prod":
        print("ESTO ES PRODUCCION: no se montan PDF de prueba aqui."); return
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    print(f"base: {os.environ['DB_NAME']}")

    if "--quitar" in sys.argv:
        r = await db.rutina_pdfs.delete_many({"filename": {"$regex": f"^{MARCA}"}})
        print(f"   PDF de prueba borrados: {r.deleted_count}")
    elif "--poner" in sys.argv:
        pend, total = panel()
        victimas = pend[::5][:40]
        ahora = datetime.now(timezone.utc).isoformat()
        for v in victimas:
            await db.rutina_pdfs.insert_one({
                "id": str(uuid.uuid4()), "client_id": v["client_id"],
                "filename": f"{MARCA}{v['client_id'][:8]}.pdf", "size": "10",
                "subido_por": "prueba-p67", "uploaded_at": ahora})
        print(f"   PDF puestos a {len(victimas)} de los {len(pend)} pendientes")

    n = await db.rutina_pdfs.count_documents({"filename": {"$regex": f"^{MARCA}"}})
    pend, total = panel()
    pct = (len(pend) / total * 100) if total else 0
    print(f"\n   PDF de prueba en la base: {n}")
    print(f"   el panel: {len(pend)} sin rutina de {total}  ({pct:.0f} %)"
          f"  ->  la columna {'SE ESCONDE' if pct >= 90 else 'SE VE'}")

asyncio.run(main())
