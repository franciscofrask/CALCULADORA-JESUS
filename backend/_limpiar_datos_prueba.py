"""Limpieza de las cuentas de prueba (punto 8 del doc del 07-08).

Por defecto SIMULA: enseña qué borraría y no toca nada. Para borrar de verdad hay que
pasarle `--ejecutar` a mano.

    python _limpiar_datos_prueba.py              # simulación (no borra)
    python _limpiar_datos_prueba.py --ejecutar   # borra

`francisco@test.com` NO se borra nunca: es la cuenta de administrador que se usa a diario
(decisión de Francisco, 07-08). Está en la lista blanca de abajo junto con la cuenta demo,
que es con la que se prueba la app.

Antes de ejecutarlo en producción, comprobar que el backup del día está hecho:
`ls -lh /opt/jg12/backups/`. El cron lo deja a las 4:30.
"""
import asyncio
import sys

sys.path.insert(0, ".")
from core.database import db

# Cuentas que NO se tocan aunque encajen con los patrones.
LISTA_BLANCA = {
    "francisco@test.com",      # el admin que usa Francisco a diario
    "clientedemo@test.com",    # la cuenta con la que se prueba la app como cliente
}

# Con qué se reconoce una cuenta de prueba. Deliberadamente estrecho: es preferible dejarse
# una fuera y revisarla a mano que llevarse por delante a un cliente de verdad.
PATRONES = {"$or": [
    {"email": {"$regex": r"@test[.]com$", "$options": "i"}},
    {"email": {"$regex": r"@example", "$options": "i"}},
    {"email": {"$regex": r"^test[0-9]*@jg12", "$options": "i"}},
    {"email": {"$regex": r"jg12-sim", "$options": "i"}},
    {"email": {"$regex": r"^prueba@", "$options": "i"}},
]}

# Colecciones que cuelgan de un usuario y de qué campo.
POR_USER_ID = ["diets", "chatbot_sessions", "food_favorites", "quiz_respuestas",
               "diet_favorites", "user_preferences"]
POR_CLIENT_ID = ["reports", "checkins", "client_photos", "macro_history", "messages",
                 "supplements", "routines", "food_suggestions"]


async def cuentas_de_prueba():
    fuera = []
    for u in await db.users.find(PATRONES, {"_id": 0}).to_list(500):
        if (u.get("email") or "").lower() in LISTA_BLANCA:
            continue
        perfil = await db.client_profiles.find_one({"user_id": u["id"]}, {"_id": 0, "id": 1})
        fuera.append((u, perfil["id"] if perfil else None))
    return fuera


async def main(ejecutar: bool):
    cuentas = await cuentas_de_prueba()
    total_usuarios = await db.users.count_documents({})
    print(f"Usuarios en la base: {total_usuarios}")
    print(f"Cuentas de prueba que se borrarían: {len(cuentas)}")
    print(f"Intactas por lista blanca: {', '.join(sorted(LISTA_BLANCA))}\n")

    borrados_totales = {}
    for u, client_id in cuentas:
        detalle = []
        for col in POR_USER_ID:
            n = await db[col].count_documents({"user_id": u["id"]})
            if n:
                detalle.append(f"{col}:{n}")
        if client_id:
            for col in POR_CLIENT_ID:
                n = await db[col].count_documents({"client_id": client_id})
                if n:
                    detalle.append(f"{col}:{n}")
        print(f"  {str(u.get('email'))[:42]:44} {str(u.get('name'))[:20]:22} "
              f"{'perfil' if client_id else 'sin perfil':11} {' '.join(detalle) or '(sin datos)'}")

        if ejecutar:
            for col in POR_USER_ID:
                r = await db[col].delete_many({"user_id": u["id"]})
                borrados_totales[col] = borrados_totales.get(col, 0) + r.deleted_count
            if client_id:
                for col in POR_CLIENT_ID:
                    r = await db[col].delete_many({"client_id": client_id})
                    borrados_totales[col] = borrados_totales.get(col, 0) + r.deleted_count
                r = await db.client_profiles.delete_many({"id": client_id})
                borrados_totales["client_profiles"] = borrados_totales.get("client_profiles", 0) + r.deleted_count
            r = await db.users.delete_many({"id": u["id"]})
            borrados_totales["users"] = borrados_totales.get("users", 0) + r.deleted_count

    if ejecutar:
        print("\nBORRADO:")
        for col, n in sorted(borrados_totales.items()):
            print(f"  {col}: {n}")
        print(f"\nUsuarios que quedan: {await db.users.count_documents({})}")
    else:
        print("\n(SIMULACIÓN: no se ha borrado nada. Para borrar de verdad: --ejecutar)")


if __name__ == "__main__":
    asyncio.run(main("--ejecutar" in sys.argv))
