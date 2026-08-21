"""
¿Los macros de este cliente se calcularon con datos de fiar? (tarea 1.4 del 21-08)

En produccion hay 98 perfiles con datos imposibles o incompletos: el de Juan (importado de
Calma) tiene edad 5, y hay estaturas de 1 cm y pesos de 1 kg. Los rangos de validacion
existen, pero solo en la puerta de la API (Pydantic, `RANGOS_PERFIL` en models/user.py): los
scripts de importacion escribieron directo en Mongo sin pasar por ahi. Y al calcular macros
no se re-valida nada, asi que el dato imposible no revienta: corrompe en silencio los
indices y el contexto del agente.

Esto se CALCULA AL VUELO al leer el perfil -- mismo patron que `sanea_peso` en
core/series_cliente -- y no se guarda ninguna bandera en base ni se migra nada: el dia que
el cliente complete sus datos, deja de salir solo.

OJO: «macros provisionales» ya significa otra cosa en la app (que nadie paso por el
cuestionario de ajuste: ver core/macros_de_quien). Este es un concepto DISTINTO: no dice
quien puso los numeros, dice si los datos del perfil con los que se trabaja son de fiar.
"""
from typing import Any, Dict, List, Optional

# Los rangos son los MISMOS que valida la puerta de la API al escribir el perfil
# (ClientProfileUpdate): declarados una sola vez alli y usados aqui para leer.
from models.user import RANGOS_PERFIL

# Como se le nombra cada campo al cliente (y al equipo en el panel).
NOMBRES = {
    "weight": "peso",
    "height": "altura",
    "age": "edad",
    "body_fat": "% graso",
    "sex": "sexo",
    "goal": "objetivo",
}

# Ademas de los cuatro con rango, el motor de macros necesita sexo y objetivo: sin ellos
# tambien se calcula "algo", pero con los valores por defecto de otro.
_SIN_RANGO = ("sex", "goal")


def datos_dudosos(perfil: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """La lista de campos del perfil que hacen dudosos sus macros. Vacia = perfil sano.

    Cada entrada: {campo, nombre, motivo} y, si el motivo es "imposible", el valor que
    hay guardado (para que el equipo lo vea sin abrir Mongo).

      motivo "falta"      el campo no esta (None o cadena vacia).
      motivo "imposible"  hay un valor, pero fuera del rango que la API no dejaria escribir
                          (o ni siquiera es un numero donde toca un numero).
    """
    perfil = perfil or {}
    dudosos: List[Dict[str, Any]] = []

    for campo, (minimo, maximo) in RANGOS_PERFIL.items():
        v = perfil.get(campo)
        if v is None or (isinstance(v, str) and not v.strip()):
            dudosos.append({"campo": campo, "nombre": NOMBRES[campo], "motivo": "falta"})
            continue
        try:
            n = float(v)
        except (TypeError, ValueError):
            # Hay algo guardado que ni siquiera es un numero: tan imposible como un 1 cm.
            dudosos.append({"campo": campo, "nombre": NOMBRES[campo],
                            "motivo": "imposible", "valor": v})
            continue
        if not (minimo <= n <= maximo):
            dudosos.append({"campo": campo, "nombre": NOMBRES[campo],
                            "motivo": "imposible", "valor": v})

    for campo in _SIN_RANGO:
        if not str(perfil.get(campo) or "").strip():
            dudosos.append({"campo": campo, "nombre": NOMBRES[campo], "motivo": "falta"})

    return dudosos


def datos_imposibles(perfil: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Solo los que tienen un valor fuera de rango (no los que faltan): lo que el panel de
    Operaciones enseña como «datos imposibles» sin cambiar la definicion de «sin datos»."""
    return [d for d in datos_dudosos(perfil) if d["motivo"] == "imposible"]
