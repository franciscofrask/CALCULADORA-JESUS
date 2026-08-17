"""Los fallos de la batería del 17-08, cada uno con su candado.

La ronda entera está en el informe; aquí quedan fijados los que se pueden comprobar sin
modelo y sin base de datos, que son los que de verdad no pueden volver.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_loop import _OFRECE_COMPLETAR, _numeros_humanos  # noqa: E402
from calculator import get_food_config  # noqa: E402
from meal_builder import get_food_limits  # noqa: E402


# ---------------------------------------------------------------- «¿te la completo?» / «sí»
def test_reconoce_la_oferta_de_completar():
    """Ofreció completar la comida, dijo «si», y le devolvió ocho tarjetas sueltas."""
    ofrece = [
        "¿Quieres que te proponga algo pequeño de hidratos + grasa para cuadrarla, "
        "o la prefieres así más ligera?",
        "¿Te la completo yo y la vemos?",
        "¿Quieres que te la complete para cuadrar esos macros?",
        "Te propongo añadir una grasa para cuadrar, ¿lo hago?",
        "¿La remato yo con un poco de pan?",
    ]
    no_ofrece = [
        "¿Qué quieres tomar?",
        "¿Te la aplico o cambiamos algo?",
        "¿Prefieres pollo o pavo?",
        "¿Quieres que la guarde así?",
        "Completa el cuestionario en tu perfil, ¿vale?",
    ]
    for t in ofrece:
        assert _OFRECE_COMPLETAR.search(t), t
    for t in no_ofrece:
        assert not _OFRECE_COMPLETAR.search(t), t


# ---------------------------------------------------------------- los números, con sus comas
def test_los_macros_en_cadena_llevan_comas():
    """«47,5 g de proteína 35 g de hidratos 13,8 g de grasa», sin una coma, en su pantalla."""
    assert _numeros_humanos("tiene de objetivo P=47.5 H=35 G=13.8, y la comida está vacía") == (
        "tiene de objetivo 47,5 g de proteína, 35 g de hidratos y 13,8 g de grasa, "
        "y la comida está vacía")
    # Uno solo sigue saliendo como antes
    assert _numeros_humanos("la comida pide P=63.3 g") == "la comida pide 63,3 g de proteína"
    # Y lo que no son macros no se toca
    assert _numeros_humanos("200 g de arroz") == "200 g de arroz"


# ---------------------------------------------------------------- el mínimo de la ficha manda
def test_el_minimo_declarado_en_el_catalogo_se_respeta():
    """El aguacate declara 25 g y el asistente lo montaba a 15 (y a 5 el 16-08)."""
    aguacate = {"nombre": "Aguacate", "categorias": "17.6 | 42 | YA",
                "racion": 100, "unidades": False, "minimo": 25}
    minimo, maximo = get_food_limits(aguacate, get_food_config(aguacate))
    assert minimo >= 25, f"el aguacate puede entrar a {minimo} g"
    assert minimo <= maximo


def test_sin_minimo_declarado_manda_la_categoria():
    """Los frutos secos y los aceites siguen con sus límites de familia."""
    nueces = {"nombre": "Nueces", "categorias": "17.2.1 | YA",
              "racion": 100, "unidades": False, "minimo": None}
    assert get_food_limits(nueces, get_food_config(nueces)) == (5, 25)
    aceite = {"nombre": "Aceite de oliva virgen extra", "categorias": "17.1",
              "racion": 10, "unidades": True, "minimo": None}
    assert get_food_limits(aceite, get_food_config(aceite)) == (5, 10)


def test_un_minimo_absurdo_no_supera_al_maximo():
    """Si la ficha declara un mínimo mayor que el máximo, eso no es un límite."""
    raro = {"nombre": "Nueces", "categorias": "17.2.1", "racion": 100,
            "unidades": False, "minimo": 400}
    minimo, maximo = get_food_limits(raro, get_food_config(raro))
    assert minimo == maximo == 25
