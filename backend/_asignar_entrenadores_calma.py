"""El entrenador de cada cliente, sacado de CALMA (doc del 19-08, apartado 04).

    «CALMA lleva el entrenador escrito dentro del nombre del plan: "Bronze Trimestral
     (Jose Luis)", "Yaiza · Bronze (Montse)". O sea que el dato existe y no se migró. Se
     puede sacar de ahí en vez de asignarlo a mano cliente por cliente.»

Medido contra prod el 19-08: 23 clientes lo llevan escrito (22 de José Luis, 1 de
Montse). No son los 84 sin asignar -- el resto sí toca repartirlo a mano o desde el panel
-- pero son 23 que se asignan solos sin que nadie tenga que recordar de quién eran.

Regla: se mira la ÚLTIMA membresía del cliente que lleve «(Jose Luis)» o «(Montse)» en
el nombre, y solo se escribe si su ficha está SIN entrenador: esto rellena huecos, no
pisa lo que alguien asignó desde el panel.

    MONGO_URL="mongodb://localhost:27018" DB_NAME=jg12_prod \
      ./venv/Scripts/python.exe _asignar_entrenadores_calma.py            # dry run
    ... --aplicar                                                          # escribe
"""
import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient

APLICAR = "--aplicar" in sys.argv
PAT = re.compile(r"jose ?luis|montse", re.IGNORECASE)


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

    # Los usuarios del equipo, por nombre. Si no se encuentran, se para: mejor no asignar
    # que asignar a un id inventado.
    entrenadores = {}
    async for u in db.users.find({"role": {"$in": ["trainer", "admin"]}},
                                 {"_id": 0, "id": 1, "name": 1}):
        n = (u.get("name") or "").lower()
        if "jose luis" in n or "joseluis" in n or "josé luis" in n:
            entrenadores["jose luis"] = u["id"]
        if "montse" in n:
            entrenadores["montse"] = u["id"]
    print("entrenadores encontrados:", entrenadores)
    if not entrenadores:
        print("NINGUNO: no hay nada que asignar sin sus ids"); return

    backup, cambios, sin_hueco = [], [], 0
    async for d in db.calma_raw.find({}, {"_id": 0, "email": 1, "membresia": 1}):
        quien = None
        for m in (d.get("membresia") or []):     # la última que lo diga, gana
            mm = PAT.search(str(m.get("nombre") or ""))
            if mm:
                quien = "montse" if "montse" in mm.group(0).lower() else "jose luis"
        if not quien or quien not in entrenadores:
            continue
        u = await db.users.find_one({"email": (d.get("email") or "").lower()},
                                    {"_id": 0, "id": 1, "name": 1})
        if not u:
            continue
        p = await db.client_profiles.find_one({"user_id": u["id"]},
                                              {"_id": 0, "id": 1, "trainer_id": 1})
        if not p:
            continue
        if p.get("trainer_id"):
            sin_hueco += 1              # ya asignado desde el panel: no se pisa
            continue
        backup.append({"client_id": p["id"], "trainer_id_antes": None})
        cambios.append((u.get("name"), d.get("email"), quien))
        if APLICAR:
            await db.client_profiles.update_one(
                {"id": p["id"]}, {"$set": {"trainer_id": entrenadores[quien]}})

    print(f"\n{'APLICADO' if APLICAR else 'DRY RUN'} · {len(cambios)} asignados · "
          f"{sin_hueco} ya tenían entrenador (no se tocan)")
    for c in cambios:
        print("  ", " · ".join(str(x) for x in c))
    if APLICAR and backup:
        sello = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        with open(f"_backup_entrenadores_{sello}.json", "w", encoding="utf-8") as f:
            json.dump(backup, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    asyncio.run(main())
