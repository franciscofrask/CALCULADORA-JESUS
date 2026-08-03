"""Que hay en el campo `tipo` de los menus de dev y si sirve para rellenar `tipo_comida`."""
import asyncio
from core.database import db


async def r():
    tipos = await db.meal_library.aggregate([
        {"$group": {"_id": "$tipo", "n": {"$sum": 1}}}, {"$sort": {"n": -1}},
    ]).to_list(20)
    print("valores de `tipo`:", tipos)
    uno = await db.meal_library.find_one({}, {"_id": 0, "tipo": 1, "macros": 1, "alimentos": 1, "fuente": 1})
    print("\nejemplo:")
    print("  tipo:", uno.get("tipo"), "| fuente:", uno.get("fuente"))
    print("  macros:", uno.get("macros"))
    print("  alimentos:", [a.get("nombre") for a in (uno.get("alimentos") or [])][:4])

asyncio.run(r())
