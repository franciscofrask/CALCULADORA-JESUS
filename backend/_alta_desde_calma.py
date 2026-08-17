# -*- coding: utf-8 -*-
"""Da de alta en la app a los que estan al dia en Calma y aqui no tienen cuenta.

Francisco, 17-08-2026: «¿por que no trajiste los que no tienen cuenta, con su mail y
contraseña, para que tambien tengan acceso?».

CON SU CONTRASEÑA DE VERDAD
---------------------------
No se les inventa una: se copia el hash de Firebase Auth (`password_hash` + `password_salt`)
igual que hizo la migracion de julio. `routes/auth.py` sabe validar contra ese hash scrypt y
lo cambia por bcrypt en el primer acceso, asi que entran con la misma contraseña que usaban
en Calma y no hay que decirles nada.

Si alguien no tiene hash en Auth (entro con Google, o su cuenta se creo de otra forma), se
crea igual con una contraseña inservible y se avisa aqui: ese tiene que usar «he olvidado mi
contraseña», que funciona desde el 13-08.

QUE SE CREA
-----------
El usuario y su ficha con lo que Calma sabe de el: plan (el de su membresia vigente), fecha
de fin del ciclo, sexo, ultimo peso y % graso, macros del ultimo ajuste, preferencias y
alergias. El resto -- dietas, reportes, medidas, fotos, historico de macros -- lo traen los
`_sync_*` de siempre, que cruzan por email y a partir de ahora ya le encuentran.

    python _alta_desde_calma.py             enseña a quien daria de alta y NO escribe
    python _alta_desde_calma.py --escribir  lo hace
"""
import asyncio
import os
import sys
import unicodedata
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bcrypt
import firebase_admin
from firebase_admin import auth, credentials, firestore
from motor.motor_asyncio import AsyncIOMotorClient

PROD = "mongodb://127.0.0.1:27018"
BASE = "jg12_restored"
ESCRIBIR = "--escribir" in sys.argv
HOY = datetime.now(timezone.utc)

if not firebase_admin._apps:
    firebase_admin.initialize_app(credentials.Certificate(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "serviceAccountKey.json")))
fs = firestore.client()

from _sync_planes_calma import codigo_de_calma, membresia_vigente  # noqa: E402


def _ultimo(d: dict):
    """La clave mas reciente de un diccionario con fechas por clave ('2026-8-14')."""
    def orden(k):
        try:
            y, m, dd = (int(x) for x in str(k).split("-"))
            return (y, m, dd)
        except Exception:
            return (0, 0, 0)
    return max(d, key=orden) if d else None


def _macros(cadena):
    """'200 120 50 40 30 200 80 50' -> los tres bloques de la app."""
    partes = str(cadena or "").split()
    if len(partes) < 8:
        return {}, {}, {}
    try:
        v = [float(x) for x in partes[:8]]
    except ValueError:
        return {}, {}, {}
    def bloque(p, h, g=None):
        b = {"protein": p, "carbs": h, "proteinas": p, "hidratos": h}
        if g is not None:
            b["fat"] = g
            b["grasas"] = g
        b["calories"] = round(p * 4 + h * 4 + (g or 0) * 9, 1)
        return b
    return bloque(v[0], v[1], v[2]), bloque(v[3], v[4]), bloque(v[5], v[6], v[7])


async def main():
    db = AsyncIOMotorClient(PROD, serverSelectionTimeoutMS=20000)[BASE]
    print(f"{'ENSAYO (no escribe)' if not ESCRIBIR else 'ESCRIBIENDO EN PRODUCCION'}\n")

    correos_app = set()
    async for u in db.users.find({}, {"_id": 0, "email": 1}):
        if u.get("email"):
            correos_app.add(u["email"].lower())

    faltan = []
    for d in fs.collection("usuarios").stream():
        correo = d.id.lower()
        if correo in correos_app:
            continue
        doc = d.to_dict() or {}
        m = membresia_vigente(doc)
        if not m:
            continue
        faltan.append((correo, doc, m))

    print(f"activos en Calma que no tienen cuenta aqui: {len(faltan)}")
    if not faltan:
        return

    # Los hashes de Auth, en una pasada.
    quiero = {c for c, _, _ in faltan}
    hashes = {}
    pagina = auth.list_users()
    while pagina:
        for u in pagina.users:
            if u.email and u.email.lower() in quiero:
                hashes[u.email.lower()] = {"hash": getattr(u, "password_hash", None),
                                           "salt": getattr(u, "password_salt", None)}
        pagina = pagina.get_next_page()

    for correo, doc, m in faltan:
        plan = codigo_de_calma(m.get("nombre"))
        h = hashes.get(correo) or {}
        print(f"\n   {doc.get('nombre') or '?'}  <{correo}>")
        print(f"      plan en Calma: {m.get('nombre')}  ->  {plan}")
        print(f"      ciclo hasta:   {m['fin'].date().isoformat()}")
        print(f"      contraseña:    {'la suya de Calma (hash de Auth)' if h.get('hash') else 'NO tiene hash: tendra que usar «he olvidado mi contraseña»'}")

    if not ESCRIBIR:
        print("\n(ensayo: no se ha creado nada. Con --escribir se hace)")
        return

    creados = 0
    for correo, doc, m in faltan:
        plan = codigo_de_calma(m.get("nombre"))
        if not plan:
            print(f"   {correo}: sin plan que se pueda deducir, no se crea")
            continue
        h = hashes.get(correo) or {}
        user_id, client_id = str(uuid.uuid4()), str(uuid.uuid4())
        ahora = HOY.isoformat()

        await db.users.update_one({"email": correo}, {"$set": {
            "id": user_id, "email": correo,
            # Inservible a proposito: se entra con el hash de Firebase (o recuperando).
            "password": bcrypt.hashpw(uuid.uuid4().hex.encode(), bcrypt.gensalt()).decode(),
            "name": doc.get("nombre") or correo.split("@")[0],
            "phone": doc.get("telefono"), "role": "client", "plan": plan,
            "trainer_id": None, "created_at": ahora,
            "calma_migrated": True, "calma_email": correo,
            "firebase_password_hash": h.get("hash"),
            "firebase_password_salt": h.get("salt"),
        }}, upsert=True)

        macros_map = doc.get("macros") or {}
        ult = _ultimo(macros_map)
        entreno, peri, descanso = _macros(macros_map.get(ult)) if ult else ({}, {}, {})
        pesos = doc.get("pesos") or {}
        grasos = doc.get("porcentajesGrasos") or {}
        prefs = doc.get("preferencias") or {}
        up, ug = _ultimo(pesos), _ultimo(grasos)

        await db.client_profiles.update_one({"user_id": user_id}, {"$set": {
            "id": client_id, "user_id": user_id,
            "plan": plan, "calma_plan_raw": m.get("nombre"), "price": 0.0, "week": 1,
            "status": "activo", "trainer_id": None,
            "current_period_end": m["fin"].date().isoformat(),
            "current_period_end_origen": "calma_membresia",
            "macros_training": entreno, "macros_rest": descanso, "macros_periworkout": peri,
            "macros_source": "manual",
            "sex": {"M": "hombre", "F": "mujer"}.get(doc.get("sexo"), "hombre"),
            "weight": float(pesos[up]) if up else None,
            "body_fat": float(grasos[ug]) if ug else None,
            "food_preferences": [x for x in str(prefs.get("preferencias", "")).split("|") if x],
            "avoided_categories": [],
            "avoided_keywords": [x.strip() for x in str(prefs.get("alergias", "")).split(",") if x.strip()],
            "diet_momento_entreno": int(prefs.get("momentoEntrenamientoPreferente", 1) or 1),
            "diet_num_comidas": 4,
            "diet_opcion_peri": "intra_post" if prefs.get("intraentrenamiento") else "solo_post",
            "questionnaire_completed": True, "created_at": ahora, "calma_migrated": True,
        }}, upsert=True)
        creados += 1
        print(f"   creado {correo}  ({plan})")

    print(f"\naltas: {creados}")
    print("Ahora toca pasarles los `_sync_*` (dietas, macros y peso, reportes, fotos): "
          "cruzan por email y ya les encuentran.")


asyncio.run(main())
