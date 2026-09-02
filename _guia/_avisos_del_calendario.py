# -*- coding: utf-8 -*-
"""LOS AVISOS DEL CALENDARIO, sacados del modulo de verdad, para poder VERLOS.

Un aviso nace solo el dia que le toca y con el estado del cliente que le toca: para mirar
el del viernes hay que ser viernes, tener el reporte mandado y una sola pesada. Reunir eso
seis veces en una base de dev no prueba mas y cuesta un dia.

Asi que aqui se le PIDE AL PROPIO MODULO que los componga -- `avisos_de_calendario_doc`, el
mismo que corre en produccion -- para cada momento del calendario del 1-09, y se guardan en
un JSON. Luego `_capturar_los_doce.js` se lo da a `GET /notifications` y la campanita de
verdad los pinta.

    EL TEXTO NO LO ESCRIBE ESTE GUION. Lo escribe `core/avisos_cliente.py`. Aqui solo se
    dice QUE DIA ES y COMO ESTA el cliente, que es el estado de partida.

Uso:  ./backend/venv/Scripts/python.exe _guia/_avisos_del_calendario.py
"""
import io
import json
import os
import sys
from datetime import datetime

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "backend"))

from core.avisos_cliente import avisos_de_calendario_doc     # noqa: E402
from core.tiempo import MADRID                                # noqa: E402


def es(y, m, d, h, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=MADRID)


#: La semana 2 del ciclo: el quincenal abre el miercoles 2 a las 10:00 y cierra el jueves 3
#: a las 20:00. Son las horas de su calendario (bloque 6).
VENTANA = {"tipo": "quincenal", "semana": 2,
           "abre": es(2026, 9, 2, 10), "cierra": es(2026, 9, 3, 20), "mandado": False}

#: Cada momento del calendario, con el estado del cliente en ese momento.
MOMENTOS = [
    ("peso-martes", "Semana 2 · martes por la mañana",
     es(2026, 9, 1, 9), {"toca_quincenal_esta_semana": True}),
    ("quincenal-abierto", "Semana 2 · miércoles a las 10:00",
     es(2026, 9, 2, 10), {}),
    ("quincenal-ultimo", "Semana 2 · jueves por la mañana",
     es(2026, 9, 3, 9), {}),
    ("quincenal-fuera-de-plazo", "Semana 2 · jueves, de 20:00 a medianoche",
     es(2026, 9, 3, 21), {}),
    ("peso-viernes", "Semana 2 · viernes, de 10:00 a 13:00",
     es(2026, 9, 4, 10), {"le_falta_una_pesada": True,
                          "ventanas": [{**VENTANA, "mandado": True}]}),
    ("peso-semana1", "Semana 1 · miércoles (solo el primer ciclo)",
     es(2026, 9, 2, 9), {"semana": 1, "primer_ciclo": True, "ventanas": []}),
]


def main() -> None:
    fuera = {}
    for clave, cuando, ahora, extra in MOMENTOS:
        ventanas = extra.pop("ventanas", [VENTANA])
        avisos = avisos_de_calendario_doc(
            ahora_es=ahora, cliente_id="captura", ventanas=ventanas,
            es_premium=True, plan_con_cierre_dia=True, cerro_hoy=True, **extra)
        # Solo los que nacen EN ESE MOMENTO por el calendario del peso o del reporte: los
        # de contrato y los del cierre del dia tienen su propio punto en el documento.
        suyos = [a for a in avisos
                 if a.get("familia", "").startswith(("peso_", "quincenal_", "reporte_no"))]
        fuera[clave] = {
            "cuando": cuando,
            # Con LAS MISMAS CLAVES que manda `GET /notifications` (`title`, `body`,
            # `clave`), que es lo que la campanita sabe pintar. Si se inventaran otras, la
            # captura saldría vacía y parecería que el aviso no existe.
            "avisos": [{
                "id": f"{clave}-{i}",
                "title": a.get("titulo") or (a.get("variantes") or [{}])[0].get("titulo"),
                "body": a.get("cuerpo") or (a.get("variantes") or [{}])[0].get("cuerpo"),
                "clave": a.get("clave"),
                "type": a.get("tipo"),
                "link": a.get("link"),
                "created_at": ahora.isoformat(),
                "read": False,
            } for i, a in enumerate(suyos)],
        }
        print(f"{clave:26} {cuando}")
        for a in fuera[clave]["avisos"]:
            print(f"     · {a['title']}")

    ruta = os.path.join(RAIZ, "_guia", "_avisos_del_calendario.json")
    json.dump(fuera, io.open(ruta, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\nGuardado en {ruta}")


if __name__ == "__main__":
    main()
