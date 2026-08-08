"""
Que macro se movio en cada ajuste (punto 31 del doc del 07-08).

Un booleano por macro, calculado al guardar comparando con lo que el cliente tenia. No
cambia ningun calculo. Sirve para dos cosas distintas:

  1. Pintar en rojo lo que cambio, que es como Jesus lee un historico de veinte filas: no
     lee numeros sueltos, lee la escalera. Esto ya se pintaba, pero comparandolo en
     pantalla fila con fila; ahora ademas queda guardado, que es lo que hace que un
     historico exportado, un informe o cualquier otra vista digan lo mismo.

  2. Decirle al modelo QUE PALANCA se movio en cada ajuste. Eso hoy no se guardaba en
     ninguna parte: en el historial estaban los ocho numeros de antes y los ocho de
     despues, pero no la decision. "Le baje los hidratos del dia de descanso" es el dato
     que el agente necesita para aprender el patron del coach, y se estaba tirando.

Formato, el mismo que usa el resto de la app para los macros:

    {"entreno":      {"proteina": bool, "hidratos": bool, "grasa": bool},
     "perientreno":  {"proteina": bool, "hidratos": bool},
     "descanso":     {"proteina": bool, "hidratos": bool, "grasa": bool}}

Devuelve None cuando no hay con que comparar (el primer ajuste de un cliente): ahi no es
que no haya cambiado nada, es que no habia nada antes, y decir False seria mentir.
"""
from typing import Any, Dict, Optional

# Cada bloque, con los campos que tiene y los dos nombres con los que viven en la base
# (la app guarda `protein`/`carbs`/`fat` y tambien `proteinas`/`hidratos`/`grasas`).
BLOQUES = {
    "entreno": [("proteina", "protein"), ("hidratos", "carbs"), ("grasa", "fat")],
    "perientreno": [("proteina", "protein"), ("hidratos", "carbs")],
    "descanso": [("proteina", "protein"), ("hidratos", "carbs"), ("grasa", "fat")],
}


def _valor(macros: Optional[Dict[str, Any]], es: str, en: str) -> Optional[float]:
    if not isinstance(macros, dict):
        return None
    v = macros.get(en)
    if v is None:
        v = macros.get(es)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def marcar_cambios(antes: Dict[str, Any], ahora: Dict[str, Any]) -> Optional[Dict[str, Dict[str, bool]]]:
    """Que macros cambian de `antes` a `ahora`.

    Las dos son {'entreno': {...}, 'perientreno': {...}, 'descanso': {...}}. Un macro
    cuenta como cambiado solo si hay numero en los dos lados y son distintos: si antes no
    habia perientreno, ponerlo no es "cambiar el intra", es estrenarlo, y marcarlo en rojo
    en veinte filas seguidas es ruido.
    """
    if not antes or not any(isinstance(antes.get(b), dict) for b in BLOQUES):
        return None

    fuera: Dict[str, Dict[str, bool]] = {}
    for bloque, campos in BLOQUES.items():
        a, b = antes.get(bloque), ahora.get(bloque)
        fuera[bloque] = {}
        for es, en in campos:
            va, vb = _valor(a, es, en), _valor(b, es, en)
            fuera[bloque][es] = va is not None and vb is not None and va != vb
    return fuera


def palancas(cambios: Optional[Dict[str, Dict[str, bool]]]) -> list:
    """Los macros que se movieron, en texto: ['descanso.hidratos', ...]. Para el modelo."""
    if not cambios:
        return []
    return [f"{bloque}.{campo}"
            for bloque, campos in cambios.items()
            for campo, movido in (campos or {}).items() if movido]
