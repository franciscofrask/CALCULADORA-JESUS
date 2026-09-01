# -*- coding: utf-8 -*-
"""Monta el informe del mes de un cliente de verdad y ensena los diez bloques.

Sirve para ver que la parte de datos sale bien ANTES de pintar nada: si «tu dia tipo» o
«preferencias» salen vacios contra la base de dev, el problema es la consulta y no la
pantalla.

Uso:  ./venv/Scripts/python.exe _probar_informe_del_mes.py [correo]
"""
import asyncio
import json
import os
import sys

from core.database import db


async def main() -> None:
    correo = sys.argv[1] if len(sys.argv) > 1 else None
    if correo:
        user = await db.users.find_one({"email": correo}, {"_id": 0, "id": 1, "name": 1})
        if not user:
            print(f"no encuentro a {correo}")
            return
        perfil = await db.client_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
        reporte = await db.reports.find_one({"client_id": perfil["id"]}, {"_id": 0},
                                            sort=[("created_at", -1)])
    else:
        # NO SE INSERTA NADA. En dev los 3.414 reportes son de Calma y ninguno es de un
        # cliente con dietas guardadas, asi que el reporte se arma en memoria: solo hace
        # falta de quien es y de que dia, que es lo que leen los bloques.
        perfil, reporte = None, None
        con_dietas = await db.diets.distinct("user_id")
        mejor = (0, None, None)
        for uid in con_dietas:
            # El que mas dias tenga con comida de verdad: los documentos vacios se crean
            # solos al abrir Nutricion y no sirven para probar nada.
            llenas = 0
            ultima = None
            async for d in db.diets.find({"user_id": uid}, {"_id": 0, "fecha": 1, "comidas": 1}):
                if any((c or {}).get("alimentos") for c in (d.get("comidas") or {}).values()):
                    llenas += 1
                    ultima = max(ultima or "", d.get("fecha") or "")
            if llenas > mejor[0]:
                mejor = (llenas, uid, ultima)
        if mejor[1]:
            perfil = await db.client_profiles.find_one({"user_id": mejor[1]}, {"_id": 0})
            print(f"(el que mas dietas llenas tiene: {mejor[0]} dias, hasta {mejor[2]})")
        if perfil:
            reporte = {
                "id": "de-mentira", "client_id": perfil["id"], "tipo": "mensual",
                "created_at": f"{mejor[2]}T12:00:00+00:00",
                "weight": None, "measurements": {}, "trainer_feedback": None,
            }

    if not reporte or not perfil:
        print("no he encontrado ningun cliente con dietas suficientes")
        return

    from routes.reports import _bloques_del_informe

    anterior = await db.reports.find_one(
        {"client_id": reporte["client_id"], "created_at": {"$lt": reporte["created_at"]}},
        {"_id": 0}, sort=[("created_at", -1)])
    bloques = await _bloques_del_informe(reporte, perfil, anterior)

    # Y se deja el informe entero en un fichero, para poder pintarlo en el navegador sin
    # crearle un reporte a nadie: la pantalla se prueba con datos de verdad y la base se
    # queda como estaba.
    salida = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "_guia", "_informe_del_mes_ejemplo.json")
    with open(salida, "w", encoding="utf-8") as f:
        json.dump({"generado": True, "bloques": bloques}, f, ensure_ascii=False,
                  indent=1, default=str)
    print(f"(informe entero en {salida})")

    print(f"cliente: {perfil.get('name') or perfil.get('id')}  ·  reporte {reporte['id'][:8]}")
    print(f"periodo: {bloques['periodo']['label']}\n")
    for clave in ("donde_estas", "feedback", "peso", "medidas", "grasa", "hecho",
                  "dia_tipo", "preferencias", "extras"):
        b = bloques.get(clave) or {}
        print(f"── {clave.upper()} " + "─" * (60 - len(clave)))
        print(json.dumps(b, ensure_ascii=False, indent=1, default=str)[:1400])
        print()


asyncio.run(main())
