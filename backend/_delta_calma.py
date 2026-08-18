# -*- coding: utf-8 -*-
"""Que falta por traer de Calma, cliente a cliente. SOLO LECTURA.

Francisco, 13-08-2026: «necesitamos actualizar la base de datos de produccion con los
datos actualizados a dia de hoy, de los clientes, no puede quedar nada fuera».

Antes de escribir una sola linea en produccion hay que saber QUE falta, y eso no se
adivina: se cuenta contra las dos puntas. Este script no escribe nada en ningun sitio.

    Fuente viva:  Firestore del proyecto jesusgallegopt (lo que Calma sigue guardando hoy)
    Destino:      Mongo de produccion, por el tunel del 27018

Se mide SOLO de los clientes que tienen cuenta en la app, que es el criterio de Francisco:
«solo tenemos que tener en cuenta los clientes activos de Calma».

    python _delta_calma.py            solo los que tienen la membresia viva
    python _delta_calma.py --todos    los 177 que estan en la app
"""
import asyncio
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

PROD = "mongodb://127.0.0.1:27018"
BASE_PROD = "jg12_prod"
CLAVE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "serviceAccountKey.json")

SOLO_VIVOS = "--todos" not in sys.argv


def _firestore():
    import firebase_admin
    from firebase_admin import credentials, firestore
    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(CLAVE))
    return firestore.client()


def _contar(coleccion):
    """Cuenta sin traerse los documentos (aggregation query).

    El `value` de una agregacion de Firestore llega como float, y luego revienta cualquier
    formato de entero. Se convierte aqui, en el unico sitio donde entra.
    """
    try:
        return int(coleccion.count().get()[0][0].value)
    except Exception:
        return sum(1 for _ in coleccion.stream())


async def main():
    from motor.motor_asyncio import AsyncIOMotorClient
    from datetime import datetime, timezone

    db = AsyncIOMotorClient(PROD)[BASE_PROD]
    hoy = datetime.now(timezone.utc).isoformat()[:10]

    # --- quienes nos importan
    users = {}
    async for u in db.users.find({"deleted_at": None}, {"_id": 0, "id": 1, "email": 1}):
        if u.get("email"):
            users[u["email"].lower()] = u["id"]

    gente = []
    async for c in db.calma_raw.find({}, {"_id": 0, "email": 1, "client_id": 1,
                                          "fin_membresia": 1, "fotos_descargadas": 1}):
        email = (c.get("email") or "").lower()
        uid = users.get(email)
        if not uid:
            continue
        vivo = (c.get("fin_membresia") or "") >= hoy
        if SOLO_VIVOS and not vivo:
            continue
        gente.append({"email": email, "uid": uid, "cid": c.get("client_id"), "vivo": vivo,
                      "fotos_bajadas": len(c.get("fotos_descargadas") or [])})

    print(f"Comparando {len(gente)} clientes "
          f"({'solo membresia viva' if SOLO_VIVOS else 'todos los que estan en la app'})")
    print(f"Firestore: proyecto jesusgallegopt   ->   Mongo: {BASE_PROD} por el tunel\n")

    fs = _firestore()
    total = defaultdict(lambda: {"calma": 0, "prod": 0, "clientes_con_hueco": 0})
    detalle = []

    for i, p in enumerate(gente, 1):
        if i % 20 == 0:
            print(f"   ... {i}/{len(gente)}")
        fila = {"email": p["email"], "vivo": p["vivo"]}

        # dietas y favoritas
        base = fs.collection("dietasUsuarios").document(p["email"])
        n_dietas = _contar(base.collection("dietas"))
        n_fav = _contar(base.collection("dietasFavoritas"))
        d_prod = await db.diets.count_documents({"user_id": p["uid"]})
        f_prod = await db.diet_favorites.count_documents({"user_id": p["uid"]})

        # macros, formularios y peso: viven en el documento del usuario
        doc = fs.collection("usuarios").document(p["email"]).get()
        u = doc.to_dict() or {} if doc.exists else {}
        n_macros = len(u.get("macros") or {})
        n_pesos = len(u.get("pesos") or {})
        n_grasa = len(u.get("porcentajesGrasos") or {})
        n_supl = len([k for k in (u.get("suplementacion") or {}) if k not in ("observaciones", "nota")])
        m_prod = await db.macro_history.count_documents({"client_id": p["cid"]}) if p["cid"] else 0

        fdoc = fs.collection("formularios").document(p["email"]).get()
        formularios = (fdoc.to_dict() or {}) if fdoc.exists else {}
        n_form = len([k for k in formularios if isinstance(formularios.get(k), dict)])
        r_prod = await db.reports.count_documents({"client_id": p["cid"]}) if p["cid"] else 0

        fila.update({"dietas": (n_dietas, d_prod), "favoritas": (n_fav, f_prod),
                     "macros": (n_macros, m_prod), "reportes": (n_form, r_prod),
                     "pesos": (n_pesos, 0), "grasa": (n_grasa, 0),
                     "suplementos": (n_supl, 0), "fotos_bajadas": p["fotos_bajadas"]})
        detalle.append(fila)

        for k in ("dietas", "favoritas", "macros", "reportes"):
            a, b = fila[k]
            total[k]["calma"] += a
            total[k]["prod"] += b
            if a > b:
                total[k]["clientes_con_hueco"] += 1
        for k in ("pesos", "grasa", "suplementos"):
            total[k]["calma"] += fila[k][0]

    print("\n" + "=" * 74)
    print(f"{'':22s}{'en Calma':>12s}{'en produccion':>15s}{'falta':>10s}{'clientes':>12s}")
    print("=" * 74)
    for k in ("dietas", "favoritas", "macros", "reportes"):
        t = total[k]
        print(f"{k:22s}{t['calma']:>12d}{t['prod']:>15d}"
              f"{max(t['calma'] - t['prod'], 0):>10d}{t['clientes_con_hueco']:>12d}")
    print("-" * 74)
    for k in ("pesos", "grasa", "suplementos"):
        print(f"{k:22s}{total[k]['calma']:>12d}{'(sin comparar)':>15s}")
    print("=" * 74)

    peores = sorted([f for f in detalle if f["dietas"][0] > f["dietas"][1]],
                    key=lambda f: f["dietas"][1] - f["dietas"][0])[:12]
    if peores:
        print("\nLos clientes con mas dietas por traer:")
        for f in peores:
            print(f"   {f['email'][:38]:40s} Calma {f['dietas'][0]:5d}   prod {f['dietas'][1]:5d}"
                  f"   faltan {f['dietas'][0] - f['dietas'][1]:5d}")

    import json
    salida = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_delta_calma.json")
    with open(salida, "w", encoding="utf-8") as fh:
        json.dump(detalle, fh, ensure_ascii=False, indent=1)
    print(f"\nDetalle por cliente en {salida}")

asyncio.run(main())
