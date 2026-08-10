"""En qué MOMENTO del día cae cada comida (desayuno, comida, merienda, cena, peri).

El chat sabía en qué comida estaba ("Comida 1"), pero no qué es esa comida, y por eso
proponía callos a la madrileña para desayunar. Esto lo resuelve.

Decisión del 06-08-2026 (Francisco): el momento va por POSICIÓN y no tiene excepciones.
Comida 1 desayuno, Comida 2 almuerzo, y así hasta la cena. El momento del entreno NO
renombra ninguna comida: quien entrena en ayunas sigue teniendo un desayuno en su Comida 1.
Que haya entrenado antes es contexto que se le pasa aparte al asistente (`entreno_antes`),
no un cambio de nombre. Es predecible, se explica en una frase y el cliente siempre sabe
en qué está.

Los valores canónicos son los del recetario (`db.menu_templates.momento`: desayuno /
comida / merienda / cena), para poder filtrarlo directamente. `peri` no existe en el
recetario a propósito: el intra y el post son bebidas y batidos, y sus categorías
permitidas ya las decide `calculator.filtrar_por_tipo_comida`.
"""
from typing import Optional

DESAYUNO = "desayuno"
COMIDA = "comida"
MERIENDA = "merienda"
CENA = "cena"
PERI = "peri"

MOMENTOS = (DESAYUNO, COMIDA, MERIENDA, CENA, PERI)

# Cómo se le nombra al cliente. "comida" es el valor del recetario, pero decirle
# "Comida 2 (comida)" no aclara nada: para él eso es el almuerzo.
ETIQUETA = {
    DESAYUNO: "desayuno",
    COMIDA: "almuerzo",
    MERIENDA: "merienda",
    CENA: "cena",
    PERI: "peri-entreno",
}

# Reparto por número de comidas principales del día. La primera es el desayuno y la
# última la cena; lo de en medio depende de cuántas haya.
_REPARTO = {
    1: [COMIDA],
    2: [DESAYUNO, CENA],
    3: [DESAYUNO, COMIDA, CENA],
    4: [DESAYUNO, COMIDA, MERIENDA, CENA],
}


def _reparto(num_comidas: int) -> list:
    """Lista de momentos, uno por comida principal, en orden."""
    n = max(1, int(num_comidas or 1))
    if n in _REPARTO:
        return list(_REPARTO[n])
    # 5 o más: desayuno, almuerzo, cena en sus sitios y meriendas en medio. No es un
    # caso que la app ofrezca hoy (3 o 4, o bloque único), pero no puede reventar.
    return [DESAYUNO, COMIDA] + [MERIENDA] * (n - 3) + [CENA]


def momento_de_comida(meal_key: str, num_comidas: int, single_meal: bool = False) -> str:
    """Momento de una comida por su clave ('C1', 'C3', 'Intra', 'Post').

    Args:
        meal_key: clave de la comida, tal cual la usa el chatbot.
        num_comidas: comidas PRINCIPALES del día (sin contar intra ni post).
        single_meal: día en bloque único.

    Returns:
        Uno de MOMENTOS. Si la clave no se reconoce, COMIDA (lo más neutro).
    """
    if meal_key in ("Intra", "Post"):
        return PERI
    if single_meal:
        return COMIDA
    if not meal_key or not meal_key.startswith("C"):
        return COMIDA
    try:
        pos = int(meal_key[1:])
    except ValueError:
        return COMIDA
    reparto = _reparto(num_comidas)
    if 1 <= pos <= len(reparto):
        return reparto[pos - 1]
    # Comida fuera del reparto (reconfiguraciones a mitad): la última que haya.
    return reparto[-1] if reparto else COMIDA


def etiqueta_momento(momento: str) -> str:
    """Cómo se le nombra al cliente ('comida' -> 'almuerzo')."""
    return ETIQUETA.get(momento, momento or "")


def describe_comida(meal_key: str, num_comidas: int, single_meal: bool = False,
                    meal_label: Optional[str] = None) -> str:
    """Cómo se nombra esta comida DE CARA AL CLIENTE: 'Comida 2', 'Post-entreno'.

    AQUÍ ESTABA EL ORIGEN DEL «(desayuno)» DEL PUNTO 10.5. Esto devolvía
    'Comida 2 (almuerzo)' y es lo que alimenta el estado que lee el asistente, así que el
    paréntesis se lo estábamos dando hecho: cuando escribía «Comida 1 (desayuno)» no se
    inventaba nada, copiaba nuestro propio formato. Se intentó corregir por prompt dos veces
    y falló las dos, como tenía que pasar.

    Decisión de Francisco, 09-08-2026: «que no diga desayuno, que diga la comida que
    corresponde». La app nombra las comidas por su POSICIÓN, que es lo que el cliente ve en
    su pantalla, y una sola forma de llamarlas.

    Ojo, esto NO deshace la decisión del 06-08: el momento (desayuno / comida / merienda /
    cena) sigue existiendo igual y sigue decidiendo qué alimento es típico de cada comida.
    Lo único que cambia es que esa palabra ya no se le enseña al cliente. `etiqueta_momento`
    se queda para el panel del entrenador y para explicaciones internas.
    """
    return meal_label or meal_key


def entreno_antes_de(meal_key: str, momento_entreno: int, meal_order: list) -> bool:
    """¿El entreno cae ANTES de esta comida? No cambia el momento (ver cabecera),
    pero sí es contexto: a quien acaba de entrenar no se le propone lo mismo.

    `momento_entreno` es la posición donde se intercalan las peri en `meal_order`
    (0 = en ayunas, antes de la Comida 1). Misma convención que `_build_meal_order`.
    """
    if meal_key in ("Intra", "Post"):
        return meal_key == "Post"
    if not meal_key.startswith("C"):
        return False
    try:
        pos = int(meal_key[1:])
    except ValueError:
        return False
    # Sin peri en el recorrido no hay entreno que situar.
    if not any(k in ("Intra", "Post") for k in (meal_order or [])):
        return False
    return pos > int(momento_entreno or 0)
