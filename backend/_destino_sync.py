# -*- coding: utf-8 -*-
"""A donde escriben los sincronizadores de Calma: produccion o desarrollo.

Los `_sync_*.py` nacieron apuntando SOLO a produccion (el tunel del 27018 contra
`jg12_prod`), porque se escribieron para el corte del 13-08. Francisco, 24-08:
«actualizalos en dev, revisa que todo este ok, y si si entonces actualizas en prod».
Para poder ensayar hace falta poder cambiarles el destino sin tocar nada mas.

    python _sync_lo_que_sea.py                 mide contra PRODUCCION, sin escribir
    python _sync_lo_que_sea.py --escribir      escribe en PRODUCCION
    python _sync_lo_que_sea.py --dev           mide contra DESARROLLO, sin escribir
    python _sync_lo_que_sea.py --dev --escribir   escribe en DESARROLLO

La FUENTE no cambia nunca: Firestore y las bases de Calma viven donde viven, y de ahi
se lee siempre. Lo unico que mueve esto es a que base se escribe.
"""
import os
import sys

from dotenv import load_dotenv

_AQUI = os.path.dirname(os.path.abspath(__file__))

PROD_URI = "mongodb://127.0.0.1:27018"
PROD_BASE = "jg12_prod"


def es_dev(argv=None) -> bool:
    return "--dev" in (sys.argv if argv is None else argv)


def destino(argv=None):
    """(uri, base) a donde escribir. Por defecto produccion, con --dev desarrollo."""
    if not es_dev(argv):
        return PROD_URI, PROD_BASE
    load_dotenv(os.path.join(_AQUI, ".env"))
    uri = os.environ.get("MONGO_URL")
    if not uri:
        raise SystemExit("--dev necesita MONGO_URL en backend/.env")
    return uri, os.environ.get("DB_NAME", "jg12_restored")


def solo_correos(argv=None):
    """El conjunto de correos al que limitar la pasada, o None para todos.

        python _sync_lo_que_sea.py --solo _guia/_correos_activos.txt

    Nace del encargo del 24-08: el Excel «Clientes Activos» dice QUIENES entran, y solo
    hay que tocar a esos. Importa de verdad en `_sync_planes_calma`, que CAMBIA el plan:
    suelto, le devolveria a los nueve Premium el plan que tenian antes de la decision del
    23-08 de pasarlos a nivel3.
    """
    argv = sys.argv if argv is None else argv
    if "--solo" not in argv:
        return None
    i = argv.index("--solo")
    if i + 1 >= len(argv):
        raise SystemExit("--solo necesita el fichero con los correos, uno por linea")
    ruta = argv[i + 1]
    with open(ruta, encoding="utf-8") as f:
        correos = {l.strip().lower() for l in f if l.strip() and not l.startswith("#")}
    if not correos:
        raise SystemExit(f"{ruta} no tiene ni un correo")
    return correos


def no_entra(correo, conjunto) -> bool:
    """True si este cliente NO entra en la pasada (para cortar el bucle de una linea)."""
    return bool(conjunto) and (correo or "").strip().lower() not in conjunto


def rotulo(argv=None) -> str:
    """Para que ningun script escriba sin decir en voz alta donde."""
    uri, base = destino(argv)
    donde = "DESARROLLO" if es_dev(argv) else "PRODUCCION"
    tapado = uri if uri.startswith("mongodb://127.") else uri.split("@")[-1][:40]
    return f"{donde} · {base} · {tapado}"
