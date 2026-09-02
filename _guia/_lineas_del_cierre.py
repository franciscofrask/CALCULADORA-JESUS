# -*- coding: utf-8 -*-
"""LAS LINEAS DE LA ESCALADA DEL CIERRE, sacadas del modulo de verdad.

La fila de «¿Como fuiste hoy?» cambia de texto segun lo que lleve sin cerrar: a los 2 dias,
a los 4 y a la semana. Para verlas en la app hace falta una cuenta que de verdad lleve esos
dias sin cerrar, y son tres cuentas y tres esperas.

Asi que se le pide al propio modulo -- `core/ventana_del_dia.texto_de_la_linea`, el mismo
que corre en produccion -- que componga las tres, y `_capturar_los_doce.js` se las da a
`GET /checkins/estado` para que Inicio las pinte.

    EL TEXTO NO LO ESCRIBE ESTE GUION. Lo escribe el servidor. Aqui solo se dice CUANTOS
    DIAS LLEVA, que es el estado de partida.

Uso:  ./backend/venv/Scripts/python.exe _guia/_lineas_del_cierre.py
"""
import io
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "backend"))

from core.ventana_del_dia import texto_de_la_linea      # noqa: E402

#: Cuantos dias sin cerrar hacen falta para cada escalon, con el nombre del punto del doc.
ESCALONES = [
    ("dos-dias", "Tras 2 días perdidos", 2),
    ("cuatro-dias", "Tras 4 días perdidos", 4),
    ("una-semana", "Tras una semana", 7),
]


def main() -> None:
    fuera = {}
    for clave, cuando, racha in ESCALONES:
        linea = texto_de_la_linea(racha, es_de_ayer=False)
        fuera[clave] = {"cuando": cuando, "racha": racha, "linea": linea}
        print(f"{clave:14} {racha} dias: {linea['titulo']} | {linea['detalle']}")

    ruta = os.path.join(RAIZ, "_guia", "_lineas_del_cierre.json")
    json.dump(fuera, io.open(ruta, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\nGuardado en {ruta}")


if __name__ == "__main__":
    main()
