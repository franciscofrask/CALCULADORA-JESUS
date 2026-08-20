# -*- coding: utf-8 -*-
"""Asigna a cada cliente su entrenador leyendo el plan de Calma (Firestore).

Bloque 12 del doc 19-08: «Asignar los 84 a su entrenador. El panel de entrenador
saldría vacío. El dato está en CALMA, escrito dentro del nombre del plan». Y Francisco
(20-08): revisar Calma porque «esos datos se actualizan todos los días; es para tener
las apps empatadas». Por eso este script es IDEMPOTENTE y sirve tanto para la primera
pasada como para un cron diario.

DE DONDE SALE EL ENTRENADOR
---------------------------
Del nombre de la membresia vigente en Firestore: «Bronze Trimestral (Jose Luis)»,
«Bronze (Montse)». OJO: el parentesis NO siempre es un entrenador. Medido el 20-08 en
Firestore: entre parentesis hay «Agosto» (15), «Jose Luis» (9), «Julio» (5), «Anual»
(4), «pero de 28 semanas, le regalo 1 mes» (1) y «Montse» (1). Por eso se cruza contra
una LISTA BLANCA de entrenadores, no se toma cualquier parentesis.

LAS REGLAS
----------
1. Parentesis con un entrenador de la lista -> ese entrenador.
2. Sin entrenador en el nombre y plan DE COACH (gold, silver, bronze, premium, 6m,
   personalizado, reto12en12, calma12) -> Jesus, que es quien lleva a los que no
   tienen otro nombre puesto (el doc: «lo tienen Jose Luis, Montse y Jesus»).
3. Plan de AUTOGESTION (elm, calculadora, mantenimiento, reto60, basica) -> no se
   asigna nadie: a esos no les toca entrenador y el panel no los espera.
4. LO PUESTO A MANO NO SE TOCA. Este script solo escribe si el perfil no tiene
   trainer_id, o si el que tiene lo puso este mismo sync (trainer_asignado_por ==
   "calma") y Calma ahora dice otro. Asi el cron diario mantiene las apps empatadas
   sin deshacer lo que el equipo asigne desde la ficha.

Uso:  python _sync_entrenadores.py            (ensayo: enseña, no escribe)
      python _sync_entrenadores.py --escribir (aplica, con backup previo en JSON)
"""
import asyncio
import json
import os
import re
import sys
import unicodedata
from collections import Counter
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import firebase_admin
from firebase_admin import credentials, firestore
from motor.motor_asyncio import AsyncIOMotorClient

PROD = "mongodb://127.0.0.1:27018"
BASE = "jg12_prod"
ESCRIBIR = "--escribir" in sys.argv
HOY = datetime.now(timezone.utc)

if not firebase_admin._apps:
    firebase_admin.initialize_app(credentials.Certificate(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "serviceAccountKey.json")))
fs = firestore.client()

# La lista blanca: lo que puede aparecer entre parentesis -> el email del entrenador en
# la app. Por EMAIL y no por nombre, que los nombres cambian de acento y de apellido.
ENTRENADORES = {
    "jose luis": "jlgb83@hotmail.com",
    "montse": "mtejero81@gmail.com",
    "jesus": "hola@jesusgallegopt.com",
}

# Planes que llevan entrenador detras aunque el nombre no diga cual: esos van a Jesus.
PLANES_DE_COACH = {"gold", "silver", "bronze", "premium", "plan_6m", "personalizado",
                   "reto12en12", "calma12"}


def _limpio(t: str) -> str:
    t = unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower()
    return " ".join(t.split())


def membresia_vigente(doc: dict):
    """El mismo criterio que _sync_planes_calma.py: la que cubre hoy, y si no, una que
    aun no ha vencido (el que renueva por adelantado sigue siendo miembro)."""
    tramos = [m for m in (doc.get("membresia") or [])
              if isinstance(m, dict) and m.get("inicio") and m.get("fin")]
    cubren_hoy = [m for m in tramos if m["inicio"] <= HOY <= m["fin"]]
    if cubren_hoy:
        return max(cubren_hoy, key=lambda x: x["fin"])
    sin_vencer = [m for m in tramos if m["fin"] >= HOY]
    return max(sin_vencer, key=lambda x: x["fin"]) if sin_vencer else None


def codigo_de_calma(nombre: str):
    """El codigo de plan, copiado de _sync_planes_calma.py (solo lo que hace falta para
    distinguir coach de autogestion)."""
    t = _limpio(nombre)
    if not t or "entrenador" in t:
        return None
    if "reto" in t and ("12en12" in t or "12 en 12" in t):
        return "reto12en12"
    if "reto 60" in t or "reto60" in t:
        return "reto60"
    for clave in ("gold", "silver", "premium", "mantenimiento", "basica", "personalizado"):
        if clave in t:
            return clave
    if "bronze" in t or "bronce" in t:
        return "bronze"
    if "lunes empiezo" in t or t == "elm":
        return "elm"
    if "calculadora" in t:
        return "calculadora_jp"
    if "calma" in t:
        return "calma12"
    if "6m" in t or "6 m" in t:
        return "plan_6m"
    return None


def entrenador_del_nombre(nombre_plan: str):
    """(alias o None). Solo si el parentesis casa con la lista blanca."""
    for trozo in re.findall(r"\(([^)]+)\)", nombre_plan or ""):
        alias = _limpio(trozo)
        for conocido in ENTRENADORES:
            if conocido in alias:
                return conocido
    return None


async def main():
    db = AsyncIOMotorClient(PROD, serverSelectionTimeoutMS=20000)[BASE]
    print(f"{'ENSAYO (no escribe)' if not ESCRIBIR else 'ESCRIBIENDO EN PRODUCCION'}\n")

    # Los entrenadores de la app, por email.
    ids = {}
    for alias, email in ENTRENADORES.items():
        u = await db.users.find_one({"email": email, "deleted_at": None},
                                    {"_id": 0, "id": 1, "name": 1})
        if not u:
            print(f"OJO: no existe el usuario {email} ({alias}); ese alias no se asigna.")
            continue
        ids[alias] = u
    if not ids:
        print("Sin entrenadores que asignar. No se hace nada.")
        return

    # Sin el equipo: los admin y trainers con perfil de cliente (existen para probar la
    # app) no son clientes de nadie y solo meterian ruido en el panel.
    usuarios = {}
    async for u in db.users.find({}, {"_id": 0, "id": 1, "email": 1, "name": 1, "role": 1}):
        if u.get("email") and u.get("role") not in ("admin", "trainer"):
            usuarios[u["email"].lower()] = u

    cambios, respetados, ya_bien = [], [], 0
    sin_perfil, autogestion = 0, 0
    por_entrenador = Counter()

    for d in fs.collection("usuarios").stream():
        correo = d.id.lower()
        u = usuarios.get(correo)
        if not u:
            continue
        m = membresia_vigente(d.to_dict() or {})
        if not m:
            continue
        nombre_plan = (m.get("nombre") or "").strip()
        codigo = codigo_de_calma(nombre_plan)

        alias = entrenador_del_nombre(nombre_plan)
        if not alias:
            if codigo in PLANES_DE_COACH:
                alias = "jesus"
            else:
                autogestion += 1
                continue
        destino = ids.get(alias)
        if not destino:
            continue

        perfil = await db.client_profiles.find_one(
            {"user_id": u["id"]},
            {"_id": 0, "id": 1, "trainer_id": 1, "trainer_asignado_por": 1, "status": 1})
        if not perfil:
            sin_perfil += 1
            continue

        actual = perfil.get("trainer_id")
        if actual == destino["id"]:
            ya_bien += 1
            por_entrenador[destino["name"]] += 1
            continue
        # Lo puesto a mano por el equipo manda sobre Calma.
        if actual and perfil.get("trainer_asignado_por") != "calma":
            respetados.append((u.get("name") or correo, nombre_plan))
            continue
        cambios.append({"perfil": perfil["id"], "cliente": u.get("name") or correo,
                        "correo": correo, "plan_calma": nombre_plan,
                        "antes": actual, "entrenador": destino["name"],
                        "trainer_id": destino["id"]})
        por_entrenador[destino["name"]] += 1

    print(f"ya estaban bien: {ya_bien}")
    print(f"se asignan ahora: {len(cambios)}")
    print(f"a mano (se respetan): {len(respetados)}")
    print(f"autogestion (sin entrenador a proposito): {autogestion}")
    print(f"en Calma pero sin perfil en la app: {sin_perfil}\n")
    print("reparto resultante:", dict(por_entrenador), "\n")
    for c in sorted(cambios, key=lambda x: (x["entrenador"], x["cliente"])):
        print(f"   {c['cliente'][:28]:30}{c['plan_calma'][:34]:36}-> {c['entrenador']}")

    if not ESCRIBIR or not cambios:
        if not ESCRIBIR:
            print("\nEnsayo. Ejecuta con --escribir para aplicar.")
        return

    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        f"_backup_trainers_{HOY.strftime('%Y%m%d_%H%M%S')}.json")
    backup = []
    for c in cambios:
        backup.append({"perfil": c["perfil"], "trainer_id_antes": c["antes"]})
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(backup, f, ensure_ascii=False, indent=1)
    print(f"\nbackup: {ruta}")

    for c in cambios:
        await db.client_profiles.update_one(
            {"id": c["perfil"]},
            {"$set": {"trainer_id": c["trainer_id"], "trainer_asignado_por": "calma",
                      "trainer_asignado_at": HOY.isoformat()}})
    print(f"escritos: {len(cambios)}")


if __name__ == "__main__":
    asyncio.run(main())
