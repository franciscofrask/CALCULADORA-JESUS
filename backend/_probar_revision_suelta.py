"""
Revision de macros comprada suelta: que pasa cuando entra el pago.

No llama a Stripe (eso necesita el checkout real): simula el pago confirmado y comprueba el
circuito de dentro, que es lo que puede romperse.
"""
import asyncio
import uuid

from core.database import db
from core.revision_suelta import PRECIO_EUR, activar_tras_pago, descuento_vigente


async def main():
    coach = await db.users.find_one({"role": {"$in": ["trainer", "admin"]}}, {"_id": 0, "id": 1, "name": 1})
    cid, uid = str(uuid.uuid4()), str(uuid.uuid4())
    await db.client_profiles.insert_one({
        "id": cid, "user_id": uid, "name": "Cliente Revision", "email": "revision@test.com",
        "plan": "calculadora_jp", "price": 0, "status": "activo",
        "trainer_id": (coach or {}).get("id"), "created_at": "2026-07-30T00:00:00+00:00",
        "macros_training": {"protein": 200, "carbs": 180, "fat": 60},
        "ajustes_macros": {"actividad_diaria": "muy_activo"},
    })
    perfil = await db.client_profiles.find_one({"id": cid})

    print(f"precio de prueba: {PRECIO_EUR} EUR")
    print("coach asignado:", (coach or {}).get("name"))

    creada = await activar_tras_pago(perfil, PRECIO_EUR)
    print("\n1) entra el pago         ->", "revision creada" if creada else "NO se creo")
    p = await db.client_profiles.find_one({"id": cid}, {"_id": 0, "revision_suelta": 1})
    print("   estado en el perfil   ->", p["revision_suelta"]["estado"])
    print("   propuesta para el coach ->",
          await db.macro_sugerencias.count_documents({"client_id": cid, "origen": "revision_suelta"}))
    print("   avisos al staff       ->",
          await db.notifications.count_documents({"client_id": cid, "type": "revision_suelta_pagada"}))

    repetida = await activar_tras_pago(await db.client_profiles.find_one({"id": cid}), PRECIO_EUR)
    print("\n2) el webhook llega dos veces ->", "duplica (MAL)" if repetida else "no duplica (bien)")

    d = descuento_vigente(await db.client_profiles.find_one({"id": cid}))
    print("\n3) si sube de plan ahora ->", f"se le descuentan {d['importe_eur']} EUR "
          f"(le quedan {d['dias_restantes']} dias)" if d else "sin descuento")

    for col in ("client_profiles", "macro_sugerencias", "notifications"):
        await db[col].delete_many({"$or": [{"client_id": cid}, {"id": cid}, {"user_id": uid}]})
    print("\n(datos de prueba borrados)")

asyncio.run(main())
