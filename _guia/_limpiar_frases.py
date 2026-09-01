# -*- coding: utf-8 -*-
"""Deja en cada punto solo LO QUE LA APP TIENE QUE DECIR.

De la maqueta salen dos cosas mezcladas: el texto de la pantalla («Si comes algo que no
está en tu dieta del día...») y los datos del ejemplo (el domingo 30 de agosto, 175 de
proteína, la frase del día de ese cliente). Lo segundo no se puede comprobar en otra
cuenta y buscarlo solo produce falsos rojos.

Se quitan: los numeros sueltos, las fechas de ejemplo, los datos del cliente de la maqueta
y el propio titulo del apartado.

Uso:  ./backend/venv/Scripts/python.exe _guia/_limpiar_frases.py
"""
import io
import json
import os
import re
import unicodedata

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FICHERO = os.path.join(RAIZ, "_guia", "_puntos_todos.json")

MESES = ("enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|"
         "noviembre|diciembre")
DIAS = "lunes|martes|miércoles|jueves|viernes|sábado|domingo"

FUERA = [
    # Numeros y cifras sueltas: «175», «−2,8 kg», «47,5P · 72H · 12G», «4 hechas · ocultas»
    re.compile(r"^[\d\s.,%+−\-·/pghPGHkKgGmMlL]+$"),
    # Fechas del ejemplo
    re.compile(rf"(?i)\b\d{{1,2}} de ({MESES})\b"),
    re.compile(rf"(?i)^({DIAS}),"),
    # Datos de ESE cliente
    re.compile(r"(?i)hola,?\s*jes[uú]s"),
    re.compile(r"(?i)una buena planificaci[oó]n la noche de antes"),
    re.compile(r"(?i)^semana \d+ de tu ciclo$"),
    re.compile(r"(?i)^(objetivo|macros reales)\b.*·"),
    # Restos de la maqueta
    re.compile(r"(?i)^(ver|hecha|sin hacer|entreno|descanso|intra|post|c[1-5])$"),
    re.compile(r"(?i)^(macros|dieta|llevas|falta)( · (macros|dieta|llevas|falta))*$"),
]

# Frases del documento que SI son texto de pantalla aunque parezcan datos.
SALVAR = re.compile(r"(?i)(tu objetivo|perientreno incluido|marca lo que te vayas comiendo|"
                    r"tu dieta hoy|pendiente|semana \d+ de \d+)")


def normal(x: str) -> str:
    x = unicodedata.normalize("NFKD", x.lower())
    return "".join(c for c in x if not unicodedata.combining(c))


def main() -> None:
    puntos = json.load(io.open(FICHERO, encoding="utf-8"))
    quitadas, quedan = 0, 0
    for p in puntos:
        titulo = normal(p["titulo"])
        limpias = []
        for f in p["debe_verse"]:
            n = normal(f)
            # El titulo del apartado no es texto de pantalla: es como lo llama el documento.
            # Solo en «Todo lo validado»: alli el titulo es como el documento llama al
            # apartado. En los otros dos el titulo lo escribi yo y a veces ES el texto.
            if p["doc"] == "validado" and (
                    n == titulo or (n.startswith(titulo[:26]) and len(titulo) > 12)):
                quitadas += 1
                continue
            if SALVAR.search(f):
                limpias.append(f)
                continue
            if any(r.search(f) for r in FUERA):
                quitadas += 1
                continue
            limpias.append(f)
        p["debe_verse"] = limpias
        quedan += len(limpias)

    with io.open(FICHERO, "w", encoding="utf-8") as f:
        json.dump(puntos, f, ensure_ascii=False, indent=1)

    vacios = [p["titulo"] for p in puntos if not p["debe_verse"]]
    print(f"{quitadas} frases de ejemplo fuera · {quedan} frases que comprobar")
    if vacios:
        print(f"\n{len(vacios)} puntos se han quedado sin frase que buscar "
              f"(son los que el documento ilustra solo con datos):")
        for v in vacios:
            print(f"   {v}")


main()
