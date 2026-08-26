# -*- coding: utf-8 -*-
"""Pone el día de la cuenta de pruebas en un estado concreto, para VER en el navegador
los estados de la regla de color del artifact del 25-08 (cuadrado, dentro del margen,
pasado). Sin esto no hay forma de llegar a ellos: harían falta cuatro comidas montadas
al gramo.

Mete un solo «alimento» en la Comida 1 con los macros que se pidan y marca solo esa,
así `Llevas` es exactamente ese número y `Falta` es el objetivo menos eso.

Uso:  python _guia/_escenario_inicio.py <escenario>
      cuadrado | margen | pasado | limpio
"""
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from dotenv import load_dotenv                                    # noqa: E402
from pymongo import MongoClient                                   # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(RAIZ, "backend", ".env"))

USUARIO = "7b6fbddf-55c4-4e9b-9b07-d621953321e2"      # francisco@test.com
FECHA = "2026-08-26"
CLAVES = ("C1", "C2", "C3", "C4", "Intra", "Post")

# El objetivo del día de esa cuenta es 400 P · 280 H · 50 G.
ESCENARIOS = {
    # Clavado en los tres: los tres verdes, y en Falta tres ceros.
    "cuadrado": {"P": 400, "H": 280, "G": 50},
    # Dentro del margen: -2, -3 y -2. Verde igual, sin cuadrar al gramo.
    "margen": {"P": 398, "H": 277, "G": 48},
    # Pasado en hidratos por 13,7: el único decimal que sobrevive, en la línea de aviso.
    "pasado": {"P": 400, "H": 293.7, "G": 50},
    # EL BORDE, en una sola pantalla: a la proteína le faltan 4 (válido, verde) y a los
    # hidratos 5 (fuera, sin color). Un gramo cambia el color, y eso pasa siempre que hay
    # un umbral: no tiene arreglo salvo quitar la regla.
    "borde": {"P": 396, "H": 275, "G": 50},
}


def main():
    que = sys.argv[1] if len(sys.argv) > 1 else "limpio"
    db = MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "jg12_restored")]

    if que == "limpio":
        db.diets.update_one(
            {"user_id": USUARIO, "fecha": FECHA},
            {"$set": {**{f"comidas.{k}.marcada": False for k in CLAVES},
                      "comidas.C1.alimentos": []}})
        print("día limpio: nada marcado y la comida 1 vacía")
        return

    if que not in ESCENARIOS:
        sys.exit(f"No conozco «{que}». Son: {', '.join(ESCENARIOS)} o limpio.")

    m = ESCENARIOS[que]
    db.diets.update_one(
        {"user_id": USUARIO, "fecha": FECHA},
        {"$set": {
            "comidas.C1.alimentos": [{
                "nombre": f"(escenario {que})",
                "macros_efectivos": {"P": m["P"], "H": m["H"], "G": m["G"]},
            }],
            **{f"comidas.{k}.marcada": (k == "C1") for k in CLAVES},
        }})
    print(f"escenario «{que}»: Llevas = {m['P']} · {m['H']} · {m['G']} (objetivo 400 · 280 · 50)")


if __name__ == "__main__":
    main()
