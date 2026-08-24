# -*- coding: utf-8 -*-
"""Los 9 Premium legacy pasan a `nivel3`, con el precio que tiene cada uno.

EL PORQUÉ (fallo 03 del doc del 19-08, y punto 20 del repaso del 23-08)
El Premium estaba por duplicado: la ficha buena (`nivel3`, 1.500 € el ciclo) con cero
clientes, y una de «especiales» (`premium`, 0 €) con los nueve de verdad. El catálogo
ya quedó con una sola ficha vendible, pero los nueve siguen apuntando a la vieja: hoy
`users.plan` dice «premium» y `client_profiles.plan` dice «nivel3» en algunos, que es
justo el tipo de campo doble que muerde («Dos ids de cliente y campos muertos»).

QUÉ HACE
Deja a cada uno en `nivel3` en LOS DOS SITIOS (users y client_profiles) y NO le toca el
precio: el suyo manda (`price` del perfil). Lo que estaba en «premium» y no tiene precio
propio se queda con el del catálogo al leer, como cualquier otro.

CÓMO SE USA (prod, por el túnel del 27018, y SIEMPRE con el OK de Francisco)
    python _mover_premium_a_nivel3.py                      # simulación: dice qué haría
    python _mover_premium_a_nivel3.py --hazlo              # lo hace, con backup previo
    python _mover_premium_a_nivel3.py --hazlo --mongo mongodb://127.0.0.1:27018 --db jg12_prod

Escribe backup de todo lo que va a tocar antes de tocarlo.
"""
import argparse
import datetime as dt
import json
import os

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hazlo", action="store_true", help="sin esto, solo simula")
    ap.add_argument("--mongo", default=os.environ.get("MONGO_URL"))
    ap.add_argument("--db", default=os.environ.get("DB_NAME", "jg12_restored"))
    args = ap.parse_args()

    db = MongoClient(args.mongo)[args.db]

    usuarios = list(db.users.find({"plan": "premium"}, {"_id": 0, "id": 1, "name": 1,
                                                        "email": 1, "plan": 1}))
    perfiles = list(db.client_profiles.find({"plan": "premium"},
                                            {"_id": 0, "id": 1, "user_id": 1,
                                             "plan": 1, "price": 1}))
    ids_usuarios = [u["id"] for u in usuarios]
    # Los perfiles de esos usuarios, aunque su perfil ya diga nivel3 (para el backup).
    perfiles_de_ellos = list(db.client_profiles.find(
        {"user_id": {"$in": ids_usuarios}},
        {"_id": 0, "id": 1, "user_id": 1, "plan": 1, "price": 1}))

    print(f"users con plan=premium: {len(usuarios)}")
    for u in usuarios:
        perfil = next((p for p in perfiles_de_ellos if p["user_id"] == u["id"]), {})
        print(f"  - {u.get('name')} <{u.get('email')}> | perfil.plan={perfil.get('plan')} "
              f"| price={perfil.get('price')}")
    print(f"client_profiles con plan=premium: {len(perfiles)}")

    if not args.hazlo:
        print("\nSIMULACIÓN: nada tocado. Repite con --hazlo cuando Francisco dé el OK.")
        return

    sello = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta = os.path.join(os.path.dirname(__file__), f"_backup_premium_a_nivel3_{sello}.json")
    json.dump({"users": usuarios, "client_profiles": perfiles_de_ellos},
              open(ruta, "w", encoding="utf-8"), ensure_ascii=False, indent=2, default=str)

    r1 = db.users.update_many({"plan": "premium"}, {"$set": {"plan": "nivel3"}})
    r2 = db.client_profiles.update_many({"plan": "premium"}, {"$set": {"plan": "nivel3"}})
    print(f"\nusers movidos: {r1.modified_count} · perfiles movidos: {r2.modified_count}")
    print(f"backup: {ruta}")
    print("El precio de cada uno NO se ha tocado: el suyo manda.")


if __name__ == "__main__":
    main()
