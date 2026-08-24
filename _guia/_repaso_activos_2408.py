# -*- coding: utf-8 -*-
"""Repaso de los clientes del Excel «Prueba Nueva Calculadora - Clientes Activos».

Por cada uno: si tiene cuenta, si puede entrar con su clave de Calma, si el plan cuadra
con el Excel, y si tiene lo que la calculadora necesita para funcionarle el primer dia
(macros, peso, ficha). Solo lectura.

    python _guia/_repaso_activos_2408.py            mira DEV
    python _guia/_repaso_activos_2408.py --prod     mira PRODUCCION (tunel 27018)
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

EXCEL = os.path.join(AQUI, "_excel_activos_2408.json")
PROD = "--prod" in sys.argv

# La etiqueta del Excel -> el codigo de plan nuestro. «Premium 500» es el «Plan
# Personalizado 500» de Calma, y PREMIUM son los que el 23-08 pasaron a nivel3.
MAPA = {"GOLD": "gold", "PREMIUM": "nivel3", "ELM": "elm", "RETO12EN12": "reto12en12",
        "BRONZE": "bronze", "MANTENIMIENTO": "mantenimiento", "SILVER": "silver",
        "CALCULADORA JP": "calculadora_jp", "6M": "plan_6m", "CALMA 12": "calma12",
        "PREMIUM 500": "personalizado"}


def base():
    if PROD:
        return MongoClient("mongodb://127.0.0.1:27018", serverSelectionTimeoutMS=8000)["jg12_prod"]
    return MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "jg12_restored")]


def main():
    filas = json.load(open(EXCEL, encoding="utf-8"))
    db = base()
    print("mirando %s · %d clientes del Excel\n" % ("PRODUCCION" if PROD else "DESARROLLO", len(filas)))

    correos = [f["email"] for f in filas]
    usuarios = {u["email"].strip().lower(): u for u in db.users.find({"email": {"$in": correos}})}
    ids = [u["id"] for u in usuarios.values()]
    fichas = {p["user_id"]: p for p in db.client_profiles.find({"user_id": {"$in": ids}})}

    # OJO: no vale mirar solo `macros_training` de la ficha. Es un espejo y puede estar
    # vacio teniendo el cliente sus macros: la app los resuelve con `macros_por_fecha`
    # contra `macro_history` (Daniel Ricobaldi salia «sin macros» y los tiene desde 2025).
    cids = [p["id"] for p in fichas.values()]
    con_historial = {h["client_id"] for h in
                     db.macro_history.find({"client_id": {"$in": cids}}, {"client_id": 1})}
    con_macros = {p["user_id"] for p in fichas.values()
                  if (p.get("macros_training") or {}).get("protein") or p["id"] in con_historial}
    con_dieta = {d["user_id"] for d in db.diets.find({"user_id": {"$in": ids}}, {"user_id": 1}).limit(100000)}
    con_serie = {s["client_id"] for s in db.series_cliente.find({"client_id": {"$in": cids}}, {"client_id": 1})} \
        if "series_cliente" in db.list_collection_names() else set()
    con_reporte = {r["client_id"] for r in db.reports.find({"client_id": {"$in": cids}}, {"client_id": 1})}

    n = Counter()
    problemas = []
    for f in filas:
        u = usuarios.get(f["email"])
        if not u:
            n["sin cuenta"] += 1
            problemas.append(("SIN CUENTA", f["email"], f["plan"], ""))
            continue
        n["con cuenta"] += 1
        p = fichas.get(u["id"]) or {}
        if not p:
            problemas.append(("SIN FICHA", f["email"], f["plan"], ""))
            n["sin ficha"] += 1
            continue
        if u.get("firebase_password_hash") or u.get("password"):
            n["puede entrar"] += 1
        else:
            problemas.append(("SIN CLAVE", f["email"], f["plan"], ""))
        esperado = MAPA.get(f["plan"].upper())
        actual = p.get("plan") or ""
        if esperado and actual != esperado:
            n["plan distinto del Excel"] += 1
            problemas.append(("PLAN", f["email"], f["plan"], "%s (excel: %s)" % (actual, esperado)))
        else:
            n["plan cuadra"] += 1
        if u["id"] in con_macros:
            n["con macros"] += 1
        else:
            problemas.append(("SIN MACROS", f["email"], f["plan"], ""))
        if p.get("weight"):
            n["con peso"] += 1
        if u["id"] in con_dieta:
            n["con alguna dieta"] += 1
        if p["id"] in con_reporte:
            n["con algun reporte"] += 1
        if p.get("current_period_end"):
            n["con fin de ciclo"] += 1

    print("%-28s %s" % ("", "de %d" % len(filas)))
    for k in ("con cuenta", "sin cuenta", "puede entrar", "plan cuadra", "plan distinto del Excel",
              "con macros", "con peso", "con alguna dieta", "con algun reporte", "con fin de ciclo"):
        print("  %-28s %4d" % (k, n[k]))

    if problemas:
        print("\nlo que hay que mirar (%d):" % len(problemas))
        for tipo, correo, plan_excel, extra in sorted(problemas):
            print("  %-11s %-34s excel=%-14s %s" % (tipo, correo[:34], plan_excel, extra))


if __name__ == "__main__":
    main()
