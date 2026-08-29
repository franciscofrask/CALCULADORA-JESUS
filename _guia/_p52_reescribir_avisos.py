# -*- coding: utf-8 -*-
"""Punto 52: los avisos YA GENERADOS que siguen con los textos viejos.

«En la bandeja del cliente: "Llevas 133 semanas con los mismos macros" y "Con tus datos
puedo mirarlo" en primera persona. Se topó el número y se pasó todo a plural, pero lo que
ya estaba escrito no se tocó.»

LO QUE QUEDABA DE VERDAD (medido en produccion el 28-08):

  - Los de «Llevas N semanas» pasados de 12 YA ESTABAN RETIRADOS (`caducada`) desde la
    fase 0 del 24-08: el cliente no los ve. Ahi no habia nada que hacer.
  - «Con tus datos puedo mirarlo» tampoco queda ninguno vivo.
  - Lo que SI sigue en las bandejas son tres titulos que el codigo ya no escribe.

SE REESCRIBE EL TITULO, NO SE RETIRA EL AVISO. Los tres siguen siendo verdad y llevan al
mismo sitio: retirarlos le quitaria al cliente un aviso que sirve. Y no se toca:

  - el CUERPO, porque en varios es la nota que escribio el entrenador con sus palabras;
  - `read`, porque marcarlos sin leer seria avisar hoy de algo de julio;
  - `familia` ni ningun otro campo: no se inventan datos que aquel aviso no tuvo.

MIRA Y NO TOCA SIN `--escribir`. Deja copia antes.

  MONGO_URL=mongodb://localhost:27018 DB_NAME=jg12_prod python _guia/_p52_reescribir_avisos.py
  ... --escribir
"""
import asyncio, json, os, sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend", ".env"))
ESCRIBIR = "--escribir" in sys.argv

# viejo -> el que escribe el codigo hoy.
# Del de suplementos se coge la variante PLURAL a proposito: la otra que hay hoy («Te he
# cambiado la suplementacion») es de primera persona, y reescribir un aviso viejo METIENDOLE
# la primera persona seria hacer justo lo que el punto 52 viene a quitar.
CAMBIOS = {
    "Tu coach ha actualizado tus macros": "Ya tienes tus macros nuevos",
    "Tu protocolo de suplementos se ha actualizado": "Tienes suplementación nueva",
    "Sin fotos no puedo comparar": "Sin fotos no podemos comparar",
}


async def main():
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = cli[os.environ["DB_NAME"]]
    print(f"base: {os.environ['DB_NAME']}   modo: {'ESCRIBIR' if ESCRIBIR else 'solo mirar'}\n")

    # Quien es cada dueño, para no confundir un cliente de verdad con una cuenta de pruebas.
    de_prueba, equipo = set(), set()
    async for u in db.users.find({}, {"id": 1, "email": 1, "role": 1, "es_prueba": 1}):
        if u.get("es_prueba"):
            de_prueba.add(u["id"])
        if (u.get("role") or "") in ("admin", "trainer"):
            equipo.add(u["id"])

    copia, total, reales = [], 0, 0
    for viejo, nuevo in CAMBIOS.items():
        docs = await db.notifications.find(
            {"title": viejo, "caducada": {"$ne": True}}, {"_id": 0}).to_list(500)
        if not docs:
            continue
        print(f"«{viejo}»\n   -> «{nuevo}»   ({len(docs)} avisos)")
        for d in docs:
            uid = d.get("user_id")
            quien = "de prueba" if uid in de_prueba else ("del equipo" if uid in equipo else "CLIENTE")
            if quien == "CLIENTE" and not d.get("read"):
                reales += 1
            print(f"      {d['id'][:8]}  {'SIN LEER' if not d.get('read') else 'leido  '}  "
                  f"{str(d.get('created_at'))[:10]}  {quien}")
            copia.append({k: d.get(k) for k in ("id", "user_id", "title", "body", "read", "created_at")})
            total += 1
        print()

    print(f"a reescribir: {total} avisos")
    print(f"de ellos, SIN LEER y de un cliente de verdad: {reales}")

    if not ESCRIBIR:
        print("\n(solo se ha mirado; para escribir de verdad, --escribir)")
        cli.close(); return

    sello = datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend",
                        f"_backup_avisos_texto_{sello}.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump({"base": os.environ["DB_NAME"], "cuando": sello, "cambios": CAMBIOS,
                   "antes": copia}, f, ensure_ascii=False, indent=2, default=str)
    print(f"\ncopia guardada en {os.path.abspath(ruta)}")

    for viejo, nuevo in CAMBIOS.items():
        r = await db.notifications.update_many(
            {"title": viejo, "caducada": {"$ne": True}}, {"$set": {"title": nuevo}})
        print(f"   {r.modified_count:>3} reescritos: «{viejo}»")

    print("\n== comprobacion ==")
    for viejo, nuevo in CAMBIOS.items():
        quedan = await db.notifications.count_documents({"title": viejo, "caducada": {"$ne": True}})
        ahora = await db.notifications.count_documents({"title": nuevo, "caducada": {"$ne": True}})
        print(f"   «{viejo}»: quedan {quedan}   ·   «{nuevo}»: {ahora}")
    cli.close()

asyncio.run(main())
