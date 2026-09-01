# -*- coding: utf-8 -*-
"""De cada apartado del documento «Todo lo validado», LO QUE TIENE QUE VERSE.

No basta con el titulo del apartado: lo que hay que comprobar es el texto de la maqueta de
«Como queda» -- o de la unica maqueta, en los estados nuevos --, que es literalmente lo que
el cliente tiene que leer en la pantalla.

Salida: una lista de puntos, cada uno con sus frases. Esa lista es la que se busca despues
en la app de verdad.

Uso:  ./backend/venv/Scripts/python.exe _guia/_extraer_puntos_validado.py
"""
import html
import io
import json
import os
import re

FUENTE = ("C:/Users/Administrador/Desktop/Todo lo validado antes del 1 de septiembre_files/"
          "saved_resource.html")
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SALIDA = os.path.join(RAIZ, "_guia", "_puntos_validado.json")

# Lo que abre un apartado. El orden importa: se recorre el documento de arriba abajo.
ABRE = re.compile(
    r'<h2>(?P<h2>.*?)</h2>'
    r'|<h3>(?P<h3>.*?)</h3>'
    r'|<p class="(?P<c>rot|q|sub)"[^>]*>(?P<t>.*?)</p>', re.S)


def texto(x: str) -> str:
    x = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", x or "", flags=re.S)
    x = re.sub(r"<br\s*/?>", "\n", x)
    x = re.sub(r"</(p|div|h1|h2|h3|h4|li|button)>", "\n", x)
    x = re.sub(r"<[^>]+>", " ", x)
    return html.unescape(x).replace("\xa0", " ")


def renglones(x: str) -> list:
    fuera = []
    for linea in texto(x).split("\n"):
        linea = " ".join(linea.split())
        # Se cuelan numeros sueltos de las maquetas y las etiquetas de las columnas.
        if len(linea) < 3 or linea in ("Como está hoy", "Como queda"):
            continue
        fuera.append(linea)
    return fuera


def main() -> None:
    s = io.open(FUENTE, encoding="utf-8", errors="replace").read()

    cortes = [(m.start(), m) for m in ABRE.finditer(s)]
    puntos, seccion, sub = [], None, None

    for i, (pos, m) in enumerate(cortes):
        fin = cortes[i + 1][0] if i + 1 < len(cortes) else len(s)
        trozo = s[pos:fin]

        if m.group("h2") is not None:
            seccion, sub = " ".join(texto(m.group("h2")).split()), None
            continue
        if m.group("c") == "sub":
            sub = " ".join(texto(m.group("t")).split())
            continue

        titulo = " ".join(texto(m.group("h3") or m.group("t")).split())
        if not titulo:
            continue

        # LA COLUMNA DE LA DERECHA es «Como queda». Si no hay dos columnas, el apartado
        # tiene una sola maqueta y esa ya es la buena (los estados «nueva»).
        col_b = re.search(r'<div class="col b">(.*?)(?=<div class="fi">|$)', trozo, re.S)
        cuerpo = col_b.group(1) if col_b else trozo
        lineas = renglones(cuerpo)

        # El pie explica el porque; no es texto de pantalla.
        pie = re.search(r'<p class="(?:pie|exp)"[^>]*>(.*?)</p>', trozo, re.S)
        pie = " ".join(texto(pie.group(1)).split()) if pie else None
        if pie and pie in lineas:
            lineas.remove(pie)

        puntos.append({
            "doc": "validado", "seccion": seccion, "sub": sub, "titulo": titulo,
            "tipo": "comparacion" if m.group("h3") else ("paso" if m.group("c") == "q" else "estado"),
            "pie": pie,
            "debe_verse": lineas[:14],
        })

    with io.open(SALIDA, "w", encoding="utf-8") as f:
        json.dump(puntos, f, ensure_ascii=False, indent=1)

    print(f"{len(puntos)} puntos en «Todo lo validado»\n")
    sec = None
    for p in puntos:
        if p["seccion"] != sec:
            sec = p["seccion"]
            print(f"── {sec}")
        n = len(p["debe_verse"])
        print(f'   {p["titulo"][:62]:64} {n} frase(s)')
    print(f"\n(en {SALIDA})")


main()
