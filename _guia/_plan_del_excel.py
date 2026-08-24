# -*- coding: utf-8 -*-
"""Le pone a cada cliente del Excel el plan que dice el Excel.

Francisco, 24-08: el Excel «Prueba Nueva Calculadora - Clientes Activos» es la lista de
quien entra y con que plan. Donde el Excel y Calma discrepan, MANDA EL EXCEL (decidido
el 24-08); `_sync_planes_calma.py` hace lo contrario -- pone lo que diga Calma --, asi que
este se pasa DESPUES y es el que deja la ultima palabra.

Solo toca el codigo de plan (`users.plan` y `client_profiles.plan`). NO toca la
membresia, ni las fechas del ciclo, ni la semana: cambiar de plan conserva la semana del
ciclo (punto 70 del doc del 23-08) y aqui se respeta escribiendo solo el plan.

    python _guia/_plan_del_excel.py                  ensayo contra DEV
    python _guia/_plan_del_excel.py --escribir       escribe en DEV
    python _guia/_plan_del_excel.py --prod           ensayo contra PRODUCCION
    python _guia/_plan_del_excel.py --prod --escribir
"""
import io
import json
import os
import sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from dotenv import load_dotenv
from pymongo import MongoClient

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
load_dotenv(os.path.join(RAIZ, "backend", ".env"))
sys.path.insert(0, os.path.join(RAIZ, "backend"))

PROD = "--prod" in sys.argv
ESCRIBIR = "--escribir" in sys.argv

# La etiqueta del Excel -> nuestro codigo de plan.
#   PREMIUM      los nueve pasaron a nivel3 el 23-08 y ahi se quedan (Francisco, 24-08).
#   Premium 500  es el «Plan Personalizado 500/550» de Calma: nuestro `personalizado`.
#   6M           el «Plan 6M»; CALMA 12 el `calma12`.
MAPA = {
    "GOLD": "gold", "PREMIUM": "nivel3", "ELM": "elm", "RETO12EN12": "reto12en12",
    "BRONZE": "bronze", "MANTENIMIENTO": "mantenimiento", "SILVER": "silver",
    "CALCULADORA JP": "calculadora_jp", "6M": "plan_6m", "CALMA 12": "calma12",
    "PREMIUM 500": "personalizado",
}


def main():
    from models.user import PLAN_CATALOG

    filas = json.load(open(os.path.join(AQUI, "_excel_activos_2408.json"), encoding="utf-8"))
    if PROD:
        db = MongoClient("mongodb://127.0.0.1:27018", serverSelectionTimeoutMS=8000)["jg12_prod"]
    else:
        db = MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "jg12_restored")]
    print("%s en %s\n" % ("ESCRIBIENDO" if ESCRIBIR else "ENSAYO (no escribe)",
                          "PRODUCCION" if PROD else "DESARROLLO"))

    desconocidas = {f["plan"] for f in filas if f["plan"].upper() not in MAPA}
    if desconocidas:
        raise SystemExit("etiquetas del Excel que no se como traducir: %s" % sorted(desconocidas))
    malos = {v for v in MAPA.values() if v not in PLAN_CATALOG}
    if malos:
        raise SystemExit("planes que no estan en el catalogo: %s" % sorted(malos))

    n = Counter()
    cambios = []
    for f in filas:
        destino = MAPA[f["plan"].upper()]
        u = db.users.find_one({"email": f["email"]}, {"id": 1, "email": 1, "name": 1, "plan": 1})
        if not u:
            n["sin cuenta"] += 1
            continue
        p = db.client_profiles.find_one({"user_id": u["id"]}, {"plan": 1, "user_id": 1}) or {}
        if (u.get("plan") == destino) and (p.get("plan") == destino):
            n["ya estaba"] += 1
            continue
        cambios.append((f["email"], u.get("name") or "", u.get("plan"), p.get("plan"), destino, u["id"]))

    print("clientes del Excel: %d · ya con su plan: %d · sin cuenta: %d · a cambiar: %d\n"
          % (len(filas), n["ya estaba"], n["sin cuenta"], len(cambios)))
    if cambios:
        print("   %-34s %-22s %-14s %-14s %s" % ("correo", "nombre", "users.plan", "ficha.plan", "queda en"))
        for correo, nombre, pu, pf, destino, _ in cambios:
            print("   %-34s %-22s %-14s %-14s %s" % (correo[:34], nombre[:22], pu, pf, destino))

    if not ESCRIBIR:
        print("\n(ensayo: no se ha escrito nada. Con --escribir se aplica)")
        return

    for correo, _, _, _, destino, uid in cambios:
        db.users.update_one({"id": uid}, {"$set": {"plan": destino}})
        db.client_profiles.update_one({"user_id": uid}, {"$set": {"plan": destino}})
    print("\nescritos %d clientes" % len(cambios))


if __name__ == "__main__":
    main()
