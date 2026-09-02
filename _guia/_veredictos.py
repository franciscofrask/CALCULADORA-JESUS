# -*- coding: utf-8 -*-
"""EL VEREDICTO DE CADA PUNTO, en cristiano y con su porque.

El repaso anterior tenia cuatro etiquetas -- visto / no esta / sin comprobar / sin pantalla --
y eso no se entendia: un punto podia salir «visto» con la mitad de sus frases tachadas, y
«sin pantalla» tapaba por igual lo que no es una pantalla y lo que no estaba hecho.

Aqui hay cinco estados, y ninguno es una excusa:

    HECHO             esta en la app y la captura lo enseña.
    HECHO_CON_MATIZ   esta, pero con una diferencia que hay que decir.
    FALTA             no esta. Punto.
    DECIDIDO_DESPUES  se cambio a proposito por una decision posterior a este documento.
    NO_ES_PANTALLA    no hay nada que mirar: es su calendario o una tarea suya.

Y ADEMAS, CADA FRASE QUE NO SE VE LLEVA SU MOTIVO. Es lo que faltaba: una frase tachada
puede ser un fallo, o el dato del cliente del ejemplo, o texto que en la app vive en otra
pestaña. Sin decirlo, las tres se leen igual de mal.
"""

HECHO = "hecho"
MATIZ = "hecho_con_matiz"
FALTA = "falta"
DESPUES = "decidido_despues"
NO_PANTALLA = "no_es_pantalla"

ETIQUETA = {
    HECHO: "Está en la app",
    MATIZ: "Está, con un matiz",
    FALTA: "No está",
    DESPUES: "Cambiado después",
    NO_PANTALLA: "No es una pantalla",
}

#: Por que una frase concreta no aparece, cuando el punto SI esta hecho. La clave es la
#: frase tal cual la escribio el, y el valor lo que hay que saber.
MOTIVOS_DE_FRASE = {
    "Proteína": "En la app los macros están en la pestaña «Macros» y la pantalla abre en "
                "«Llevas», que es lo que pide el punto de al lado. Se ve al cambiar de "
                "pestaña.",
    "tu objetivo": "Igual: es el rótulo de la pestaña «Macros».",
    "Hidratos": "Igual: es el rótulo de la pestaña «Macros».",
    "Grasa": "Igual: es el rótulo de la pestaña «Macros».",
    "Sensaciones generales del día":
        "Esta pregunta se quitó del cierre del día con su documento «El día» del 31-08, "
        "que es POSTERIOR a este. El campo se sigue guardando y el historial de quien la "
        "tenga contestada la sigue pintando.",
    "Semana 2 · hasta mañana jueves a las ocho":
        "Es la cabecera con el plazo. Sale con la fecha de verdad del cliente, así que "
        "dice su jueves y no el del ejemplo.",
}

#: Los numeros de sus maquetas son del cliente del ejemplo. Cuando una frase es solo un
#: numero o una fecha, no se busca: se dice que es del ejemplo.
import re                                                              # noqa: E402

_SOLO_DATOS = re.compile(
    r"^(\d+([.,]\d+)?\s*(kg|%|g|ml|min|días?|de \d+)?|"
    r"\d+ de \d+|[-−+]?\d+([.,]\d+)?|Semana \d+|"
    r"\d+([.,]\d+)? kg|—|·)$", re.I)


def es_dato_del_ejemplo(frase: str) -> bool:
    """Si esa «frase» es en realidad un numero del cliente de su maqueta."""
    return bool(_SOLO_DATOS.match((frase or "").strip()))


def motivo_de(frase: str) -> str:
    """Por que no se ve esa frase, cuando el punto esta hecho."""
    f = (frase or "").strip()
    if f in MOTIVOS_DE_FRASE:
        return MOTIVOS_DE_FRASE[f]
    if es_dato_del_ejemplo(f):
        return ("Es un dato del cliente de su maqueta. La app enseña el del cliente de "
                "verdad, que es otro número.")
    return ""
