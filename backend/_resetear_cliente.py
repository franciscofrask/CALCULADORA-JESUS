"""
Deja a un cliente como recién registrado, para poder repetir el recorrido desde el principio.

Conserva su CUENTA (correo y contraseña) y su PLAN: sin plan no podría hacer nada. Borra todo lo
demás: el cuestionario, los macros, las dietas, las fotos, los reportes y las preferencias.

Uso:  venv/Scripts/python.exe _resetear_cliente.py correo@ejemplo.com [--aplicar] [--sin-plan]
Sin --aplicar solo enseña lo que borraría.
Con --sin-plan se le quita tambien el perfil entero: entra como quien no ha comprado nada.
"""
import asyncio
import sys

from core.database import db

# Lo que marca que ya ha pasado por el camino. Se quita del perfil, no se borra el perfil entero,
# para no perder su plan ni su fecha de alta.
CAMPOS_A_LIMPIAR = [
    "questionnaire_completed", "questionnaire_nivel1_completed", "nivel1",
    "ajuste_macros_completado", "ajuste_macros_progreso", "ajustes_macros",
    "macros_training", "macros_rest", "macros_periworkout", "macros_source",
    "macros_multiplicadores", "weight", "body_fat", "sex", "goal", "height", "birthdate", "age",
    "biotype", "training_experience", "activity_level", "farmacologia",
    "punto_de_partida_hecho", "medidas_inicio", "revision_suelta",
    "onboarding_step", "onboarding_completed", "checklist_dismissed",
    "peso_maximo", "peso_minimo", "peso_habitual", "peso_mejor_momento",
]

# Colecciones colgando del cliente: (coleccion, campo por el que se busca)
COLECCIONES = [
    ("diets", "user_id"), ("macro_history", "user_id"), ("quiz_respuestas", "user_id"),
    ("diet_favorites", "user_id"), ("food_favorites", "user_id"), ("chatbot_sessions", "user_id"),
    ("notifications", "user_id"), ("user_preferences", "user_id"),
    ("client_photos", "client_id"), ("checkins", "client_id"), ("reports", "client_id"),
    ("macro_sugerencias", "client_id"), ("macro_revisiones", "client_id"),
    ("supplements", "client_id"), ("client_supplementation", "client_id"),
    ("coach_reports", "client_id"), ("alerts", "client_id"),
]


async def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    correo = sys.argv[1].strip().lower()
    aplicar = "--aplicar" in sys.argv
    sin_plan = "--sin-plan" in sys.argv

    u = await db.users.find_one({"email": {"$regex": f"^{correo}$", "$options": "i"}}, {"_id": 0})
    if not u:
        print(f"No existe ningún usuario con el correo {correo}")
        return
    p = await db.client_profiles.find_one({"user_id": u["id"]}, {"_id": 0})

    print(f"{u['email']}  ({u.get('role')})")
    if sin_plan:
        print("  se CONSERVA: solo la cuenta (correo, contraseña, nombre y teléfono).")
        print(f"  se BORRA el perfil entero, incluido el plan {p.get('plan') if p else '-'}:")
        print("     al entrar verá lo mismo que quien acaba de registrarse y no ha comprado nada.")
    else:
        print(f"  se CONSERVAN: la cuenta, el nombre, el teléfono"
              + (f" y el plan {p.get('plan')}" if p else ""))
    print()

    if p and not sin_plan:
        tiene = [c for c in CAMPOS_A_LIMPIAR if p.get(c) not in (None, "", [], {})]
        print(f"  del perfil se limpian {len(tiene)} campos:")
        print("    " + ", ".join(tiene[:14]) + (" ..." if len(tiene) > 14 else ""))

    print("\n  se borra:")
    total = 0
    for col, campo in COLECCIONES:
        clave = p["id"] if campo == "client_id" and p else u["id"]
        n = await db[col].count_documents({campo: clave})
        if n:
            print(f"    {col}: {n}")
            total += n
    if not total:
        print("    (nada, ya estaba limpio)")

    if not aplicar:
        print("\n  ENSAYO. Para hacerlo de verdad, añade --aplicar")
        return

    for col, campo in COLECCIONES:
        clave = p["id"] if campo == "client_id" and p else u["id"]
        await db[col].delete_many({campo: clave})

    if p and sin_plan:
        await db.client_profiles.delete_one({"id": p["id"]})
        # Los pagos y las facturas se quedan: son historia contable, no progreso del cliente.
        print(f"\n  HECHO: {total} documentos borrados y el perfil eliminado (sin plan).")
        print("  Entra con su correo de siempre y verá lo mismo que alguien recién registrado.")
    elif p:
        await db.client_profiles.update_one(
            {"id": p["id"]}, {"$unset": {c: "" for c in CAMPOS_A_LIMPIAR}})
        print(f"\n  HECHO: {total} documentos borrados y el perfil limpio.")
        print("  Puede entrar con su correo y contraseña de siempre y empezar desde el alta.")

asyncio.run(main())
