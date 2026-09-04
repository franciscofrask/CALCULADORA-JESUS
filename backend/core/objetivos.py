"""
LOS OBJETIVOS DEL CLIENTE, EN UN SOLO SITIO (doc de Jesús del 2-09, fase 2; decisiones de
Francisco del 4-09).

Hasta hoy el objetivo salía del cuestionario de alta, con dos valores («volumen» o
«definicion»), y el cliente lo reescribía cada mes desde el reporte. Jesús: «los objetivos
los pones tú, no él»; la lista, «cerrada pero ampliable»: ganar volumen, perder grasa,
máxima definición, recomposición, mantenimiento y tonificación. «Cerrada porque si cada uno
se escribe a mano no se puede comparar nada después». Y «tonificación con foco glúteo» se
parte en dos campos: el objetivo y el foco.

Dos niveles: el objetivo DEL CICLO (se pone al abrirlo y vive en el cuaderno,
`ciclos.objetivo`) y el objetivo ACTUAL (`client_profiles.objetivo_actual`, se pone en cada
feedback y matiza al del ciclo). El `foco` va en la ficha (`client_profiles.foco`).

`goal` NO desaparece: es la clave que entiende el motor de macros y el informe («volumen»,
«definicion», «mantenimiento», «recomposicion»), y se deriva del objetivo cada vez que el
entrenador lo cambia (`motor_de`). Así el motor no se toca y el objetivo del negocio manda.

Las dos definiciones que Jesús dejó escritas: máxima definición = bajar del 14 % (Francisco,
4-09: el mismo número para todos, sin preguntarle si en mujeres es otro; se le explica al
cerrar) y recomposición = cuando termina una definición.

Ampliable EN CÓDIGO (Francisco, 4-09): se añade aquí y en `frontend/src/lib/objetivos.js`,
que es su espejo. Si la lista se mueve más de dos veces, entonces una pantalla.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

OBJETIVOS: List[Dict[str, Any]] = [
    {"clave": "ganar_volumen", "nombre": "Ganar volumen", "motor": "volumen", "ritmo": "volumen",
     "definicion": None},
    {"clave": "perder_grasa", "nombre": "Perder grasa", "motor": "definicion", "ritmo": "definicion",
     "definicion": None},
    {"clave": "maxima_definicion", "nombre": "Máxima definición", "motor": "definicion", "ritmo": "definicion",
     "definicion": "Bajar del 14 % de grasa."},
    {"clave": "recomposicion", "nombre": "Recomposición", "motor": "mantenimiento", "ritmo": "recomposicion",
     "definicion": "Empieza cuando termina una definición."},
    {"clave": "mantenimiento", "nombre": "Mantenimiento", "motor": "mantenimiento", "ritmo": "recomposicion",
     "definicion": None},
    {"clave": "tonificacion", "nombre": "Tonificación", "motor": "definicion", "ritmo": "definicion",
     "definicion": None},
]

_POR_CLAVE = {o["clave"]: o for o in OBJETIVOS}
CLAVES = tuple(_POR_CLAVE)

# El umbral de «máxima definición», el mismo para todos (Francisco, 4-09).
GRASA_MAXIMA_DEFINICION = 14.0

# De lo que había (`goal` del cuestionario y del reporte, y las etiquetas sueltas que quedaron
# por ahí) al objetivo nuevo, LITERAL: definición pasa a perder grasa, nunca a máxima
# definición, porque eso no lo dijo nadie; el entrenador afina después (Francisco, 4-09).
_DESDE_GOAL = {
    "volumen": "ganar_volumen",
    "definicion": "perder_grasa",
    "perdida_grasa": "perder_grasa",
    "perdida-grasa": "perder_grasa",
    "mantenimiento": "mantenimiento",
    "recomposicion": "recomposicion",
    "tonificacion": "tonificacion",
    # Lo que quedó escrito a mano en fichas viejas (medido en dev el 4-09: «mantener»,
    # «perder grasa» con espacio) y las variantes que ya entendía el informe.
    "mantener": "mantenimiento",
    "perder grasa": "perder_grasa",
    "ganar_musculo": "ganar_volumen",
    "ganar musculo": "ganar_volumen",
    "recomposición": "recomposicion",
    "definición": "perder_grasa",
    "tonificación": "tonificacion",
}


def es_valido(clave: Optional[str]) -> bool:
    return (clave or "").strip().lower() in _POR_CLAVE


def normalizar(clave: Optional[str]) -> Optional[str]:
    """Una clave de la lista, o el equivalente literal de un `goal` viejo, o None."""
    c = (clave or "").strip().lower()
    if c in _POR_CLAVE:
        return c
    return _DESDE_GOAL.get(c)


def desde_goal(goal: Optional[str]) -> Optional[str]:
    """El objetivo literal que corresponde a un `goal` viejo (la migración)."""
    return normalizar(goal)


def nombre_de(clave: Optional[str]) -> Optional[str]:
    o = _POR_CLAVE.get(normalizar(clave) or "")
    return o["nombre"] if o else None


def definicion_de(clave: Optional[str]) -> Optional[str]:
    o = _POR_CLAVE.get(normalizar(clave) or "")
    return o["definicion"] if o else None


def motor_de(clave: Optional[str]) -> Optional[str]:
    """La clave que entiende el motor de macros («volumen», «definicion», «mantenimiento»)."""
    o = _POR_CLAVE.get(normalizar(clave) or "")
    return o["motor"] if o else None


def ritmo_de(clave: Optional[str]) -> Optional[str]:
    """La familia de ritmo del informe (`core/informe_mensual.ritmo_objetivo`): «volumen»,
    «definicion» o «recomposicion» (mantener)."""
    o = _POR_CLAVE.get(normalizar(clave) or "")
    return o["ritmo"] if o else None


def para_el_front() -> List[Dict[str, Any]]:
    """La lista tal cual, por si algún día se sirve en vez de espejarse."""
    return [dict(o) for o in OBJETIVOS]
