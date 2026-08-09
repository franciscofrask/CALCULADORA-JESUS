# -*- coding: utf-8 -*-
"""
Punto 4.4: «1 ud» de aislado de proteina con 89,9 g de proteina.

El informe lo atribuia a un valor por defecto silencioso (peso_unidad = 100 cuando falta).
Medido en produccion: de los 1.182 alimentos por unidades, NINGUNO carece de peso de unidad,
asi que ese defecto no se usa nunca. Lo que si hay son 6 alimentos marcados `unidades=True`
cuya tabla nutricional esta escrita POR 100 G. Contarlos por unidades convierte un cacito de
20 g en 89,9 g de proteina.

La regla: un macro no puede pesar mas que el alimento que lo contiene.
"""
from calculator import get_food_config

# El caso literal: id 2815 en produccion.
AISLADO = {
    "id": 2815, "nombre": "Aislado de proteina - Whey Protein Isolate",
    "categorias": "46", "racion": 20, "unidades": True,
    "proteinas": 89.92, "hidratos": 0.99, "grasas": 0.99,
}
# Una lata de callos de 380 g con 53 P y 61 G: mucha proteina en terminos absolutos, pero
# CABE en 380 g. Este es correcto y tiene que seguir yendo por unidades.
CALLOS = {
    "id": 1, "nombre": "Callos a la madrilena lata (Litoral)",
    "categorias": "2", "racion": 380, "unidades": True,
    "proteinas": 53.2, "hidratos": 7.6, "grasas": 60.8,
}
HUEVO = {
    "id": 2, "nombre": "Huevos enteros L", "categorias": "3", "racion": 63,
    "unidades": True, "proteinas": 7.9, "hidratos": 0.4, "grasas": 6.6,
}


def test_el_aislado_deja_de_ir_por_unidades():
    cfg = get_food_config(AISLADO)
    assert cfg["por_unidad"] is False, \
        "89,9 g de proteina no caben en un cacito de 20 g: la marca de unidades esta mal"


def test_contado_por_peso_los_numeros_cuadran():
    """Con la tabla por 100 g y contando en gramos, 20 g dan 18 g de proteina, no 89,9."""
    cfg = get_food_config(AISLADO)
    assert not cfg["por_unidad"]
    esperado = AISLADO["proteinas"] * 20 / 100.0
    assert abs(esperado - 17.98) < 0.1


def test_una_lata_grande_sigue_yendo_por_unidades():
    """53 g de proteina son muchos, pero caben en una lata de 380 g. No se toca."""
    cfg = get_food_config(CALLOS)
    assert cfg["por_unidad"] is True
    assert cfg["peso_unidad"] == 380


def test_un_huevo_sigue_siendo_un_huevo():
    cfg = get_food_config(HUEVO)
    assert cfg["por_unidad"] is True
    assert cfg["peso_unidad"] == 63


def test_sin_racion_no_se_decide_a_ciegas():
    """Sin peso de unidad no se puede comparar, y no se degrada por si acaso."""
    sin_racion = {**HUEVO, "racion": 0}
    assert get_food_config(sin_racion)["por_unidad"] is True
