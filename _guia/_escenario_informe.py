# -*- coding: utf-8 -*-
"""EL ESCENARIO DEL INFORME, para que sus diez bloques tengan algo que enseñar.

Dos bloques del informe del mes salian vacios contra la base de dev, y no porque estuvieran
mal: es que el cliente del ejemplo no daba pie a ellos.

  - «El porcentaje que ha bajado cada semana» necesita que el peso CAMBIE. Sin cambio no hay
    nada que repartir por semanas, y el bloque se calla, que es lo correcto.
  - «Extras registrados» necesita que haya apuntado algun extra.

Asi que se le montan los dos al cliente del ejemplo -- SOLO EN DEV, y son datos suyos de
prueba --, y luego `_probar_informe_del_mes.py` vuelve a armar el informe y la pantalla lo
pinta con lo que salga.

    backend/venv/Scripts/python.exe _guia/_escenario_informe.py
"""
import asyncio
import os
import sys
from datetime import date, timedelta

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "backend"))


async def main() -> None:
    from core.database import db

    if "12en12app" in (os.environ.get("MONGO_URL") or ""):
        print("Esto es dev. No se ejecuta contra produccion.")
        return

    # El mismo cliente que elige `_probar_informe_del_mes.py`: el que mas dias tiene con
    # comida de verdad. Se busca igual para que los dos guiones hablen del mismo.
    mejor = (0, None, None)
    for uid in await db.diets.distinct("user_id"):
        llenas, ultima = 0, None
        async for d in db.diets.find({"user_id": uid}, {"_id": 0, "fecha": 1, "comidas": 1}):
            if any((c or {}).get("alimentos") for c in (d.get("comidas") or {}).values()):
                llenas += 1
                ultima = max(ultima or "", d.get("fecha") or "")
        if llenas > mejor[0]:
            mejor = (llenas, uid, ultima)
    if not mejor[1]:
        print("no he encontrado ningun cliente con dietas")
        return

    perfil = await db.client_profiles.find_one({"user_id": mejor[1]}, {"_id": 0})
    fin = date.fromisoformat(mejor[2])
    print(f"cliente {perfil.get('name') or perfil['id']} · informe hasta {fin}")

    # ── UN MES DE PESO QUE BAJA, una pesada por semana ──
    # Cuatro pesadas, de 84,0 a 82,1: -1,9 kg repartidos de forma desigual, que es lo que
    # hace que el reparto por semanas diga algo.
    pesadas = {(fin - timedelta(days=21)): 84.0, (fin - timedelta(days=14)): 83.4,
               (fin - timedelta(days=7)): 83.1, fin: 82.1}
    pesos = [p for p in (perfil.get("pesos") or [])
             if str(p.get("fecha") or "")[:10] not in {d.isoformat() for d in pesadas}]
    for dia, valor in pesadas.items():
        pesos.append({"fecha": dia.isoformat(), "valor": valor,
                      "origen": "escenario de pruebas del informe"})
    pesos.sort(key=lambda p: str(p.get("fecha")))
    await db.client_profiles.update_one({"user_id": mejor[1]}, {"$set": {"pesos": pesos}})
    print(f"  · {len(pesadas)} pesadas, de {list(pesadas.values())[0]} a {list(pesadas.values())[-1]} kg")

    # ── Y DOS EXTRAS APUNTADOS ──
    # Los extras viven en el dia de la dieta, que es de donde los lee el informe.
    puestos = 0
    for dias_atras, texto in ((5, "Dos cervezas con la comida"), (12, "Un trozo de tarta")):
        dia = (fin - timedelta(days=dias_atras)).isoformat()
        d = await db.diets.find_one({"user_id": mejor[1], "fecha": dia}, {"_id": 0, "extras": 1})
        extras = [e for e in ((d or {}).get("extras") or [])
                  if not str(e.get("id", "")).startswith("escenario-")]
        extras.append({"id": f"escenario-{dia}", "texto": texto, "origen": "inicio"})
        await db.diets.update_one({"user_id": mejor[1], "fecha": dia},
                                  {"$set": {"extras": extras}}, upsert=True)
        puestos += 1
        print(f"  · extra del {dia}: {texto}")

    print(f"\nListo. Ahora: backend/venv/Scripts/python.exe backend/_probar_informe_del_mes.py")


asyncio.run(main())
