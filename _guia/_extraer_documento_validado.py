# -*- coding: utf-8 -*-
"""Saca la estructura ENTERA del documento «Todo lo validado antes del 1 de septiembre».

El PDF se dejo la mitad y la primera lectura conto ocho secciones de dieciseis. Esto lee el
HTML guardado -- que si las trae -- y devuelve, en orden, cada seccion, cada apartado y
cada estado nuevo, con su pie y su explicacion. De ahi sale la lista de puntos: uno por
cada cosa que el documento dice que tiene que quedar de una forma.

Uso:  ./backend/venv/Scripts/python.exe _guia/_extraer_documento_validado.py
"""
import html
import io
import json
import os
import re

FUENTE = ("C:/Users/Administrador/Desktop/Todo lo validado antes del 1 de septiembre_files/"
          "saved_resource.html")
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SALIDA = os.path.join(RAIZ, "_guia", "_documento_validado.json")

# Las clases con las que el documento marca sus propias piezas.
#   sub  el subtitulo de una seccion        pie  el pie de una comparacion
#   tit  «Como esta hoy» / «Como queda»     rot  el rotulo de un estado suelto
#   exp  la explicacion de un estado        q    el titulo de un paso del calendario
PIEZAS = re.compile(
    r'<(?P<h>h[123])>(?P<ht>.*?)</(?P=h)>'
    r'|<p class="(?P<c>sub|pie|tit|rot|exp|q|baj|pieg)"[^>]*>(?P<t>.*?)</p>',
    re.S)


def limpio(x: str) -> str:
    x = re.sub(r"<br\s*/?>", " ", x or "")
    x = re.sub(r"<[^>]+>", "", x)
    return " ".join(html.unescape(x).replace("\xa0", " ").split())


def main() -> None:
    s = io.open(FUENTE, encoding="utf-8", errors="replace").read()

    doc = {"titulo": None, "bajada": [], "secciones": []}
    seccion = None
    item = None

    for m in PIEZAS.finditer(s):
        if m.group("h"):
            nivel, texto = m.group("h"), limpio(m.group("ht"))
            if not texto:
                continue
            if nivel == "h1":
                doc["titulo"] = texto
            elif nivel == "h2":
                seccion = {"titulo": texto, "sub": None, "items": []}
                doc["secciones"].append(seccion)
                item = None
            elif nivel == "h3" and seccion is not None:
                item = {"titulo": texto, "tipo": "comparacion", "pie": None, "notas": []}
                seccion["items"].append(item)
        else:
            clase, texto = m.group("c"), limpio(m.group("t"))
            if not texto:
                continue
            if clase == "baj":
                doc["bajada"].append(texto)
            elif clase == "pieg":
                doc["cierre"] = texto
            elif clase == "sub" and seccion is not None:
                seccion["sub"] = texto
            elif clase == "pie" and item is not None:
                item["pie"] = texto
            elif clase in ("rot", "q") and seccion is not None:
                # Un estado suelto («A la mañana siguiente, nueva») o un paso del
                # calendario: cada uno es un punto por su cuenta.
                item = {"titulo": texto, "tipo": "estado" if clase == "rot" else "paso",
                        "pie": None, "notas": []}
                seccion["items"].append(item)
            elif clase == "exp" and item is not None:
                item["pie"] = texto

    # Los <p> sueltos del calendario van con su paso.
    for sec in doc["secciones"]:
        for it in sec["items"]:
            it["notas"] = [n for n in it["notas"] if n]

    with io.open(SALIDA, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)

    total = sum(len(s2["items"]) for s2 in doc["secciones"])
    print(f'{doc["titulo"]}')
    print(f'{len(doc["secciones"])} secciones · {total} apartados\n')
    for sec in doc["secciones"]:
        print(f'── {sec["titulo"]}' + (f'  ({sec["sub"]})' if sec["sub"] else ""))
        for it in sec["items"]:
            print(f'     [{it["tipo"]:11}] {it["titulo"]}')
    print(f"\n(en {SALIDA})")


main()
