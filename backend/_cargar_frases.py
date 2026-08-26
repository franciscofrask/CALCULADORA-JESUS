# -*- coding: utf-8 -*-
"""Carga DE GOLPE las frases del día (punto 4 del doc del 23-08).

Escribe en `db.app_settings`, documento «app», y sirve para las dos listas:

  - LA ROTACIÓN (`--rotacion`, lo normal desde el 26-08): el repertorio que rota día a
    día y no se agota nunca. Va a `frases_rotacion` y NO lleva fechas: la fecha decide
    sola cuál toca (routes/settings.py, `_frase_por_rotacion`).
  - LA COLA (por defecto): frases atadas a un día concreto. Va a `frases_programadas`,
    que `ajustes_app()` resuelve al leer. El panel solo programa a 7 días vista, así que
    las tandas largas entran por aquí.

El fichero de entrada es texto plano, una frase por línea (`#` para comentar). Formatos:
  - «2026-08-25 | La frase de ese día»  -> con su fecha (cola)
  - «La frase de ese día»               -> sin fecha: en la cola se numeran seguidas
                                           desde --desde; en la rotación van tal cual

Uso:
  python _cargar_frases.py frases.txt --rotacion
  python _cargar_frases.py frases.txt --desde 2026-08-25
Contra PROD, por el túnel del 27018 y con backup previo:
  ... --mongo mongodb://127.0.0.1:27018 --db jg12_prod
Sin --mongo usa el MONGO_URL del .env (dev). La cola NO se borra: funde por fecha (una
fecha repetida se reemplaza) y deja el resultado ordenado. La rotación SÍ se reemplaza
entera: es un repertorio, no un histórico, y fundirlo dejaría frases viejas dentro.
"""
import argparse
import datetime as dt
import json
import os
import sys

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# OJO CON ESTE VALOR. Es el id del ÚNICO documento de app_settings, y tiene que ser el
# mismo que routes/settings.py:28. Estaba puesto a "app_settings" (el nombre de la
# colección, no el del documento), así que este cargador escribía en un documento aparte
# que la app no lee jamás: se habrían cargado las 84 frases, habría dicho «Cargadas 84» y
# no habría pasado nada, sin un solo error. Si lo cambias aquí, cámbialo allí.
DOC_ID = "app"                   # el mismo DOC_ID de routes/settings.py


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


def leer_textos(ruta: str):
    """Para la rotación: solo el texto, sin fechas. Si una línea trae fecha delante se
    le quita, para poder reutilizar el mismo fichero que la cola."""
    textos = []
    for linea in open(ruta, encoding="utf-8"):
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        if "|" in linea and linea.split("|", 1)[0].strip().count("-") == 2:
            linea = linea.split("|", 1)[1].strip()
        if linea:
            textos.append(linea)
    return textos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fichero")
    ap.add_argument("--rotacion", action="store_true",
                    help="carga el repertorio que rota día a día (frases_rotacion) en vez de la cola")
    ap.add_argument("--desde", default=None, help="fecha de la primera línea sin fecha (YYYY-MM-DD)")
    ap.add_argument("--mongo", default=os.environ.get("MONGO_URL"))
    ap.add_argument("--db", default=os.environ.get("DB_NAME", "jg12_restored"))
    args = ap.parse_args()

    db = MongoClient(args.mongo)[args.db]
    doc = db.app_settings.find_one({"id": DOC_ID}, {"_id": 0}) or {}

    # Backup de lo que hay antes de tocar nada.
    sello = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta_backup = os.path.join(os.path.dirname(__file__), f"_backup_frases_{sello}.json")
    json.dump(doc, open(ruta_backup, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    if args.rotacion:
        textos = leer_textos(args.fichero)
        if not textos:
            sys.exit("El fichero no trae ninguna frase.")
        # La rotación se reemplaza entera a propósito (ver cabecera).
        db.app_settings.update_one(
            {"id": DOC_ID},
            {"$set": {"frases_rotacion": [{"texto": t} for t in textos]}}, upsert=True)
        antes = len(doc.get("frases_rotacion") or [])
        print(f"Rotación cargada: {len(textos)} frases (antes había {antes}).")
        print(f"Rota una por día, sin agotarse. Backup: {ruta_backup}")
        return

    nuevas = leer_frases(args.fichero, args.desde)
    if not nuevas:
        sys.exit("El fichero no trae ninguna frase.")

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
