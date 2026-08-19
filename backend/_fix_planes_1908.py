"""Los movimientos de clientes del bloque 03 del doc del 19-08 (Admin › Planes).

    FALLO 03  Los 9 de «premium» (especiales, 0 €) se mueven a `nivel3` -- el Premium de
              verdad -- con el precio que tiene cada uno. El plan cambia; su precio, sus
              fechas y su ciclo NO se tocan.
    FALLO 12  Los de «calculadora_jp» se migran a `mantenimiento`: «pueden editar sus
              macros pero sin ajuste», que es exactamente la ficha nueva de
              Mantenimiento. Su precio no se toca.
    FALLO 13  Los 3 sin plan y el que tiene la grafía «CalMa»: al que pone CalMa se le
              normaliza a `calma12` (el alias ya lo resolvía en caliente; escrito queda
              mejor). LOS 3 SIN PLAN NO SE TOCAN AQUÍ: «asignarles el que les toque» es
              una decisión por cliente, no un valor por defecto -- se listan y decide
              Francisco/Jesús.

    LO QUE ESTE SCRIPT NO HACE, A PROPÓSITO: los 15 del Reto 12en12 («a revisar uno a
    uno», con su tabla de precios de la hoja de pagos) y los 2 del Reto Gold («mover esos
    2») -- ¿a nivel3? el doc no dice el destino --, que esperan la revisión.

Se ejecuta contra produccion por el tunel (27018), con el OK de Francisco:

    MONGO_URL="mongodb://localhost:27018" DB_NAME=jg12_prod \
      ./venv/Scripts/python.exe _fix_planes_1908.py            # solo lista (dry run)
    ... _fix_planes_1908.py --aplicar                          # escribe, con backup
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient

APLICAR = "--aplicar" in sys.argv


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    backup, cambios = [], []

    async def mover(filtro, plan_nuevo, motivo):
        async for p in db.client_profiles.find(filtro, {"_id": 0}):
            backup.append(p)
            u = await db.users.find_one({"id": p.get("user_id")}, {"_id": 0, "name": 1, "email": 1})
            cambios.append((p.get("id"), (u or {}).get("name"), p.get("plan"), plan_nuevo,
                            p.get("price"), motivo))
            if APLICAR:
                await db.client_profiles.update_one(
                    {"id": p["id"]}, {"$set": {"plan": plan_nuevo}})

    # FALLO 03 · los 9 del premium especial → nivel3 (Premium). Solo cambia el plan.
    await mover({"plan": "premium"}, "nivel3", "fusion premium (fallo 03)")

    # FALLO 12 · Calculadora JP → Mantenimiento.
    await mover({"plan": "calculadora_jp"}, "mantenimiento", "migracion CalcJP (fallo 12)")

    # FALLO 13 · la grafía «CalMa» → calma12 (normalizar lo que el alias ya resolvía).
    await mover({"plan": "CalMa"}, "calma12", "grafia CalMa (fallo 13)")

    # EL OVERRIDE VIEJO DE ELM (guardado desde el panel antes del 19-08): pisa el
    # catálogo nuevo con «legacy» y el nombre antiguo. Se limpia conservando solo el
    # `que_incluye` escrito a mano, si lo hubiera.
    ov = await db.plan_overrides.find_one({"code": "elm"}, {"_id": 0})
    if ov:
        backup.append({"_tipo": "plan_override", **ov})
        conservar = {k: v for k, v in (ov.get("fields") or {}).items()
                     if k == "que_incluye" and v}
        cambios.append(("plan_overrides", "elm", "override viejo", "limpiado", None,
                        "pisa el catalogo del 19-08"))
        if APLICAR:
            if conservar:
                await db.plan_overrides.update_one({"code": "elm"},
                                                   {"$set": {"fields": conservar}})
            else:
                await db.plan_overrides.delete_one({"code": "elm"})

    # FALLO 13 · los sin plan: SE LISTAN, no se tocan.
    print("\n─ SIN PLAN (decidir uno a uno, no se tocan) ─")
    async for p in db.client_profiles.find({"plan": None}, {"_id": 0, "id": 1, "user_id": 1}):
        u = await db.users.find_one({"id": p.get("user_id")}, {"_id": 0, "name": 1, "email": 1})
        print("  ", (u or {}).get("name"), "·", (u or {}).get("email"), "·", p.get("id"))

    print(f"\n─ {'APLICADO' if APLICAR else 'DRY RUN (nada escrito)'} · {len(cambios)} movimientos ─")
    for c in cambios:
        print("  ", " · ".join(str(x) for x in c))

    if APLICAR and backup:
        sello = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        ruta = f"_backup_planes_1908_{sello}.json"
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(backup, f, ensure_ascii=False, indent=2, default=str)
        print(f"backup en {ruta}")


if __name__ == "__main__":
    asyncio.run(main())
