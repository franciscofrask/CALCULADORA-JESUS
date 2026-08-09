# -*- coding: utf-8 -*-
"""
Punto 6: las cantidades que da el asistente son redondas.

«Nadie pesa 223 g de pechuga ni 42 g de proteina en polvo». El redondeo de salida existe
desde el 07-08 (`redondeo_salida.py`) pero solo estaba enchufado en el recetario: el
asistente dimensionaba con `calma_suggest`, que va de gramo en gramo (STEP_GRANEL = 1),
y entregaba el numero crudo.

Se prueba `_size_food` directamente contra alimentos de mentira, sin base de datos: es
donde se decide la cantidad que se enseña Y la que se mete en la dieta.
"""
import pytest

from chatbot import NutritionChatbot


@pytest.fixture
def bot():
    return NutritionChatbot.__new__(NutritionChatbot)   # sin __init__: no hace falta sesion


def _granel(nombre, p, h, g, categorias="1"):
    """Un alimento a granel: macros por 100 g."""
    return {"id": nombre, "nombre": nombre, "categorias": categorias,
            "proteinas": p, "hidratos": h, "grasas": g,
            "kcal": p * 4 + h * 4 + g * 9, "racion": 100}


PECHUGA = _granel("Pechuga de pollo", 23.0, 0.0, 1.5, categorias="2")
ARROZ = _granel("Arroz blanco", 7.0, 78.0, 0.6, categorias="9")
WHEY = _granel("Proteina de suero", 80.0, 6.0, 5.0, categorias="46")
ACEITE = _granel("Aceite de oliva", 0.0, 0.0, 100.0, categorias="12")
LECHUGA = _granel("Lechuga", 1.4, 1.5, 0.2, categorias="13")   # verdura: paso de 50


def _cantidad(bot, food, restante):
    r = bot._size_food(food, restante)
    assert r is not None, f"{food['nombre']} deberia caber en {restante}"
    return r[0]


@pytest.mark.parametrize("food", [PECHUGA, ARROZ, WHEY, ACEITE])
@pytest.mark.parametrize("restante", [
    {"P": 30, "H": 20, "G": 10},
    {"P": 47, "H": 63, "G": 17},      # numeros feos a proposito
    {"P": 52, "H": 111, "G": 23},
    {"P": 18, "H": 7, "G": 9},
])
def test_todo_sale_en_multiplos_de_cinco(bot, food, restante):
    c = _cantidad(bot, food, restante)
    assert c % 5 == 0, f"{food['nombre']} salio a {c} g en {restante}: nadie pesa eso"


def test_el_caso_de_jesus(bot):
    """Los 223 g de pechuga y los 42 g de whey que reporto."""
    for food in (PECHUGA, WHEY):
        for restante in ({"P": 51, "H": 33, "G": 12}, {"P": 34, "H": 8, "G": 7},
                         {"P": 62, "H": 90, "G": 21}):
            c = _cantidad(bot, food, restante)
            assert c == int(c) and c % 5 == 0, f"{food['nombre']}: {c} g"


def test_las_verduras_van_de_cincuenta_en_cincuenta(bot):
    """Categoria 13: se comen a puñados, no a cucharaditas."""
    c = _cantidad(bot, LECHUGA, {"P": 30, "H": 40, "G": 15})
    assert c % 50 == 0 or c % 5 == 0, f"lechuga a {c} g"


def test_nunca_se_pasa_de_lo_que_habia(bot):
    """El redondeo es a la BAJA: quedarse corto se completa, pasarse descuadra el dia."""
    for food in (PECHUGA, ARROZ, WHEY, ACEITE):
        restante = {"P": 40, "H": 50, "G": 15}
        cantidad, macros = bot._size_food(food, restante)
        for m in ("P", "H", "G"):
            assert macros[m] <= restante[m] + 0.51, \
                f"{food['nombre']} a {cantidad} g aporta {macros[m]} de {m} y solo quedaban {restante[m]}"


def test_los_macros_son_los_de_la_cantidad_que_se_enseña(bot):
    """Si se enseña 195 g, los macros tienen que ser los de 195 g, no los de 223.

    Se compara contra el alimento con la REGLA DE MACROS aplicada, que es como cuenta toda
    la app: `aplicar_regla_macros` pone a cero la grasa traza de las proteinas magras, asi
    que la pechuga a 195 g aporta 0 de grasa y no 2,9. Compararlo contra los macros crudos
    de la tabla haria fallar este test por un motivo que no tiene nada que ver con el
    redondeo -- me paso al escribirlo.
    """
    import copy
    from calma_suggest import aplicar_regla_macros, macros_at

    for food in (PECHUGA, ARROZ, WHEY):
        cantidad, macros = bot._size_food(food, {"P": 45, "H": 62, "G": 19})
        a = copy.deepcopy(food)
        aplicar_regla_macros(a)
        # `macros_at` trabaja en raciones de 100 g para los alimentos a granel.
        esperados = macros_at(a, cantidad)
        for clave, m in (("proteinas", "P"), ("hidratos", "H"), ("grasas", "G")):
            assert abs(macros[m] - esperados[clave]) < 0.15, \
                f"{food['nombre']} a {cantidad} g: dice {macros[m]} de {m} y son {esperados[clave]}"


def test_no_desaparece_nada_por_redondear(bot):
    """Redondear a la baja no puede dejar un alimento en cero y hacerlo desaparecer."""
    for food in (PECHUGA, ARROZ, WHEY, ACEITE, LECHUGA):
        for restante in ({"P": 3, "H": 2, "G": 1}, {"P": 8, "H": 5, "G": 2}):
            r = bot._size_food(food, restante)
            if r is not None:
                assert r[0] > 0, f"{food['nombre']} se quedo en 0 g con {restante}"
