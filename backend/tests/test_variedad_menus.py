"""Variedad en los menús sugeridos, y el turrón que no podía cuadrar.

Jesús, 12-08-2026: varias recetas del recetario no salían nunca. Al medirlo salieron dos
cosas distintas:

1. **El reparto por familia de proteína.** El sugeridor da 3 opciones con proteínas
   diferentes -- un hueco por familia -- y en comida hay 22 menús de pollo peleando por ese
   hueco. El orden no cambiaba, así que ganaba siempre el mismo.

   El techo real es más bajo de lo que parecía: con unos macros dados, solo 20 de los 56
   menús de comida pueden cuadrar. Antes se veían 17 de esos 20; con la memoria de lo ya
   propuesto, los 20, a cambio de 0,04 g de error medio.

2. **El «Turrón Crunch de Cacao»** -- frutos secos y chocolate -- no lleva NI UN ingrediente
   de proteína, y una merienda pide 25-35 g. Como se descarta lo que acabe a más de 12 g del
   objetivo, no cuadraba con ningún cliente: 0 de 48 objetivos probados. Es la única de las
   159 en esa situación.

Corre sin Mongo: se le da la lista de plantillas ya ajustadas.
"""
import os
import sys

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _RAIZ)

import meal_templates as MT  # noqa: E402


def _op(pid, cuadrada, err):
    """Lo que devuelve `_ajustar_plantilla`, en lo que le importa al orden."""
    return ({"plantilla_id": pid, "cuadrada": cuadrada}, "2.2", err)


def _ordenar(ajustadas, vistos, politica):
    """El mismo criterio que usa `generar_opciones_menu` (sin semilla: determinista)."""
    antes = MT.POLITICA_VARIEDAD
    MT.POLITICA_VARIEDAD = politica
    try:
        vistos = vistos or set()

        def clave(x):
            opcion, err = x[0], x[2]
            visto = 1 if opcion.get("plantilla_id") in vistos else 0
            cuadra = not opcion.get("cuadrada", False)
            escalon = int(err // MT.ESCALON_ERROR)
            if MT.POLITICA_VARIEDAD == "escalon":
                return (cuadra, escalon, visto)
            if MT.POLITICA_VARIEDAD == "cuadradas":
                return (cuadra, visto, escalon)
            return (cuadra, escalon)

        return [x[0]["plantilla_id"] for x in sorted(ajustadas, key=lambda x: clave(x) + (x[2],))]
    finally:
        MT.POLITICA_VARIEDAD = antes


# Dos que cuadran (escalón 0 y escalón 1) y una que no cuadra.
LISTA = [_op("mejor", True, 1.0), _op("otro", True, 6.0), _op("floja", False, 20.0)]


def test_sin_memoria_gana_siempre_el_que_mejor_cuadra():
    assert _ordenar(LISTA, set(), "cuadradas")[0] == "mejor"


def test_con_la_memoria_le_toca_al_que_no_ha_visto():
    """El fallo de fondo: el mejor ganaba siempre y los demás no salían nunca."""
    assert _ordenar(LISTA, {"mejor"}, "cuadradas")[0] == "otro"


def test_pero_nunca_por_delante_de_una_que_no_cuadre():
    """La variedad no se paga enseñando menús descuadrados."""
    orden = _ordenar(LISTA, {"mejor", "otro"}, "cuadradas")
    assert orden[-1] == "floja", orden


def test_la_politica_del_escalon_no_cruza_escalones():
    """Documenta por qué «escalon» no servía: «otro» está en el escalón de al lado."""
    assert _ordenar(LISTA, {"mejor"}, "escalon")[0] == "mejor"


def test_dentro_del_mismo_escalon_si_desempata():
    dos = [_op("a", True, 1.0), _op("b", True, 2.0)]
    assert _ordenar(dos, {"a"}, "escalon")[0] == "b"


def test_la_politica_puesta_es_la_medida():
    """Si alguien la cambia, que sea a propósito y leyendo los números del módulo."""
    assert MT.POLITICA_VARIEDAD == "cuadradas"


def test_sin_memoria_el_orden_es_el_de_siempre():
    """Quien no pase `vistos` -- el buscador del coach, los tests viejos -- no ve ningún
    cambio: sin nada visto, el criterio nuevo vale 0 para todos."""
    assert _ordenar(LISTA, set(), "cuadradas") == _ordenar(LISTA, set(), "ninguna")
