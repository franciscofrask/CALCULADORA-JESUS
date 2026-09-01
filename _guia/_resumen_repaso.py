# -*- coding: utf-8 -*-
"""El recuento del repaso, por documento, y la lista de lo que no esta cerrado."""
import io
import json
import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
datos = json.load(io.open(os.path.join(RAIZ, "_guia", "_repaso_tres_documentos.json"),
                          encoding="utf-8"))

src = io.open(os.path.join(RAIZ, "_guia", "_armar_artifact_repaso.py"), encoding="utf-8").read()
trozo = src[src.index("MATICES = {"):src.index("ORDEN = {")]
ns = {}
exec(trozo, ns)                                          # noqa: S102 · es nuestro fichero
MATICES = ns["MATICES"]

NOMBRE = {"validado": "Todo lo validado antes del 1 de septiembre",
          "mensual": "El reporte mensual", "informe": "El informe del mes"}

for doc in ("validado", "mensual", "informe"):
    cuenta = {"cerrado": 0, "parcial": 0, "abierto": 0}
    pendientes = []
    for x in datos:
        if x["doc"] != doc:
            continue
        estado = MATICES[x["punto"]][0] if x["punto"] in MATICES else x["estado"]
        cuenta[estado] += 1
        if estado != "cerrado":
            pendientes.append((estado, x["bloque"], x["punto"]))
    print(f'\n{NOMBRE[doc]}: {cuenta["cerrado"]} cerrados · '
          f'{cuenta["parcial"]} a medias · {cuenta["abierto"]} abiertos')
    for estado, bloque, punto in pendientes:
        print(f'   [{estado:8}] {bloque} · {punto}')
