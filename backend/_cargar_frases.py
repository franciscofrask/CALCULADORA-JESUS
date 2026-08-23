# -*- coding: utf-8 -*-
"""Carga DE GOLPE la cola de frases del día (punto 4 del doc del 23-08).

El panel solo programa a 7 días vista (a propósito), así que las 84 -- una por día
de ciclo -- entran por aquí, directo a `app_settings.frases_programadas`, que es la
cola que `ajustes_app()` resuelve al leer.

El fichero de entrada es texto plano, una frase por línea. Dos formatos:
  - «2026-08-25 | La frase de ese día»  -> con su fecha
  - «La frase de ese día»               -> sin fecha: se numeran seguidas desde --desde

Uso (contra PROD, por el túnel del 27018, con backup previo):
  python _cargar_frases.py frases.txt --desde 2026-08-25 [--mongo mongodb://127.0.0.1:27018] [--db jg12_prod]
Sin --mongo usa el MONGO_URL del .env (dev). NO borra la cola: funde por fecha
(una fecha repetida se reemplaza) y deja el resultado ordenado.
"""
import argparse
import datetime as dt
import json
import os
import sys

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

DOC_ID = "app_settings"          # el mismo DOC_ID de routes/settings.py


def leer_frases(ruta: str, desde: str):
    frases, fecha = [], dt.date.fromisoformat(desde) if desde else None
    for linea in open(ruta, encoding="utf-8"):
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        if "|" in linea and linea.split("|", 1)[0].strip().count("-") == 2:
            f, texto = (x.strip() for x in linea.split("|", 1))
        else:
            if fecha is None:
                sys.exit("Una línea viene sin fecha y no se ha dado --desde. No adivino fechas.")
            f, texto = fecha.isoformat(), linea
            fecha += dt.timedelta(days=1)
        if texto:
            frases.append({"fecha": f, "texto": texto, "puesta_por": "carga-de-golpe-2308"})
    return frases


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fichero")
    ap.add_argument("--desde", default=None, help="fecha de la primera línea sin fecha (YYYY-MM-DD)")
    ap.add_argument("--mongo", default=os.environ.get("MONGO_URL"))
    ap.add_argument("--db", default=os.environ.get("DB_NAME", "jg12_restored"))
    args = ap.parse_args()

    nuevas = leer_frases(args.fichero, args.desde)
    if not nuevas:
        sys.exit("El fichero no trae ninguna frase.")

    db = MongoClient(args.mongo)[args.db]
    doc = db.app_settings.find_one({"id": DOC_ID}, {"_id": 0}) or {}

    # Backup de lo que hay antes de tocar nada.
    sello = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta_backup = os.path.join(os.path.dirname(__file__), f"_backup_frases_{sello}.json")
    json.dump(doc, open(ruta_backup, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    # Fundir por fecha: lo nuevo pisa a lo viejo de esa fecha; el resto se queda.
    cola = {f["fecha"]: f for f in (doc.get("frases_programadas") or []) if f.get("fecha")}
    for f in nuevas:
        cola[f["fecha"]] = f
    ordenada = sorted(cola.values(), key=lambda f: f["fecha"])

    db.app_settings.update_one({"id": DOC_ID}, {"$set": {"frases_programadas": ordenada}}, upsert=True)
    print(f"Cargadas {len(nuevas)} frases (cola total: {len(ordenada)}).")
    print(f"De {ordenada[0]['fecha']} a {ordenada[-1]['fecha']}. Backup: {ruta_backup}")


if __name__ == "__main__":
    main()
