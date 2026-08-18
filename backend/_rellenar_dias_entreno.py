# -*- coding: utf-8 -*-
"""Los dias de entreno que faltan, a cuatro.

Francisco, 18-08-2026: la pregunta «¿cuantos dias a la semana puedes entrenar?» se retira del
alta (bloque 5 del documento del cuestionario) porque la respuesta es siempre la misma. El
codigo ya trabaja con cuatro cuando el campo esta vacio, pero el dato en si seguia sin existir
en la ficha, y hay sitios que lo leen crudo.

QUE HACE
    Pone `training_days = 4` en los perfiles que NO tienen ninguno. Al que ya tiene un numero
    -- porque lo contesto en su dia -- no se le toca: su respuesta manda sobre la pauta.

Uso, desde backend/:
    venv/Scripts/python.exe _rellenar_dias_entreno.py              # dry-run, no escribe
    venv/Scripts/python.exe _rellenar_dias_entreno.py --escribir   # escribe, con copia antes

El tunel al Mongo de produccion tiene que estar abierto:
    ssh -i ~/.ssh/id_ed25519_jg12 -o StrictHostKeyChecking=no -N \
        -L 27018:127.0.0.1:27017 root@s1.jesusgallegopt.com
"""
import datetime
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
from pymongo import MongoClient

PROD = "mongodb://127.0.0.1:27018"
BASE = "jg12_prod"
DIAS = 4

escribir = "--escribir" in sys.argv

cli = MongoClient(PROD, serverSelectionTimeoutMS=15000)
db = cli[BASE]

sin_dato = {"$or": [{"training_days": None}, {"training_days": {"$exists": False}},
                    {"training_days": ""}]}

total = db.client_profiles.count_documents({})
faltan = list(db.client_profiles.find(sin_dato, {"_id": 0, "id": 1, "user_id": 1, "plan": 1}))

print("=" * 78)
print(f"  {'ESCRIBIENDO' if escribir else 'DRY-RUN (no escribe nada)'}   ->   {BASE} por el tunel del 27018")
print("=" * 78)
print(f"\nperfiles: {total}")
print(f"sin dias de entreno: {len(faltan)}")
print(f"con dias puestos, que NO se tocan: {total - len(faltan)}")

if not escribir:
    print("\n  DRY-RUN: no se ha escrito nada. Repite con --escribir.")
    raise SystemExit(0)

# La copia, antes de tocar nada. Solo lo que se va a cambiar: id del perfil y lo que tenia.
sello = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
copia = f"_backup_training_days_{sello}.json"
with open(copia, "w", encoding="utf-8") as f:
    json.dump(faltan, f, ensure_ascii=False, indent=1)
print(f"\ncopia de los que se van a tocar: {copia}")

r = db.client_profiles.update_many(sin_dato, {"$set": {"training_days": DIAS}})
print(f"escritos: {r.modified_count}")

quedan = db.client_profiles.count_documents(sin_dato)
print(f"siguen sin dato: {quedan}")
