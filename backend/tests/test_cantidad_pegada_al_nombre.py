"""La cantidad no puede viajar dentro del nombre del alimento.

Salió del caso 9 de los diez de Jesús (12-08-2026): «un alimento que cuenta los tres macros,
como la leche entera». Al probarlo, «ponme 500 ml de leche entera» metía en la comida
**leche de almendras**. El propio asistente lo decía en su respuesta: «el sistema ha metido
leche de almendras sin azúcares en vez de leche entera de vaca».

El motivo, medido contra el buscador:

    'leche entera'             -> Leche entera, Leche entera sin lactosa
    '500 ml de leche entera'   -> Leche de almendras sin azúcares, Leche entera, ...

Al modelo se le pide que mande la cantidad aparte, y a veces no lo hace; entonces el texto
entero se va a la búsqueda semántica y los números y las unidades arrastran el vector.

Se arregla en código y no pidiéndoselo mejor al prompt: separar un número de un nombre es
gramática, no vocabulario, así que no choca con la regla de no meter comida en el prompt.
"""
import os
import sys

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _RAIZ)

import pytest  # noqa: E402

from chatbot import NutritionChatbot  # noqa: E402

sacar = NutritionChatbot._sacar_cantidad


@pytest.mark.parametrize("texto,esperado", [
    ("500 ml de leche entera", ("leche entera", 500.0, "g")),
    ("300 g de arroz",         ("arroz", 300.0, "g")),
    ("80g de pan",             ("pan", 80.0, "g")),
    ("200 gramos de atun",     ("atun", 200.0, "g")),
    ("1 kg de pollo",          ("pollo", 1000.0, "g")),
    ("1,5 l de agua",          ("agua", 1500.0, "g")),
])
def test_el_peso_sale_del_nombre_y_queda_en_gramos(texto, esperado):
    assert sacar(texto, None, None) == esperado


@pytest.mark.parametrize("texto,esperado", [
    ("2 huevos",            ("huevos", 2.0, "ud")),
    ("3 uds de tortitas",   ("tortitas", 3.0, "ud")),
])
def test_un_numero_sin_unidad_son_piezas(texto, esperado):
    """«2 huevos» son dos huevos, no dos gramos."""
    assert sacar(texto, None, None) == esperado


@pytest.mark.parametrize("texto", [
    "leche entera",
    "Leche entera 3,8% MG",      # el numero va DENTRO del nombre del producto
    "medio litro de leche",      # sin digito no hay nada que separar
    "arroz 3 delicias",
])
def test_lo_que_no_empieza_por_un_numero_no_se_toca(texto):
    assert sacar(texto, None, None) == (texto, None, None)


def test_la_cantidad_que_ya_venia_aparte_manda():
    """Si el modelo la mandó bien, esa es la buena; del nombre solo se limpia el texto."""
    assert sacar("500 ml de leche entera", 250, "g") == ("leche entera", 250, "g")


def test_un_numero_solo_no_deja_al_alimento_sin_nombre():
    """«500» no es un alimento: si no queda nada detrás, no se toca nada."""
    assert sacar("500 g", None, None) == ("500 g", None, None)
    assert sacar("2", None, None) == ("2", None, None)


def test_entra_por_la_puerta_por_la_que_pasan_todos():
    """`_normalize_food_items` es el sitio por el que entran los alimentos del modelo."""
    items = NutritionChatbot._normalize_food_items([{"nombre": "500 ml de leche entera"}])
    assert items[0]["nombre"] == "leche entera"
    assert items[0]["cantidad"] == 500.0
    assert items[0]["unidad"] == "g"
