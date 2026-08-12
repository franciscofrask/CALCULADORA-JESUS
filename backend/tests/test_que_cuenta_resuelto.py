"""El filtro del tercio le llega al asistente RESUELTO, no como regla que razonar.

Jesús, 12-08-2026: «Si le mandas "almendras: te cuenta la grasa, la proteína no", no tiene
que razonar la regla y no la puede fallar. Si le mandas la regla y los macros crudos, la
fallará algunas veces. Y basta una para que el cliente deje de fiarse. Lo mismo con las
excepciones por categoría: que lleguen resueltas».

La regla ya era determinista, pero solo se alcanzaba llamando a la herramienta `explicar`,
o sea cuando al modelo se le ocurría. Ahora va puesta en cada alimento que el asistente ve,
porque `_item_de` es la única puerta por la que entran todos.

Las fichas son copias literales del catálogo de producción, para que esto no compruebe lo
que yo supongo de una categoría sino lo que dice el alimento de verdad. Corre sin Mongo.
"""
import os
import sys

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _RAIZ)

import pytest  # noqa: E402

from agent_tools import AgentTools, _y  # noqa: E402
from chatbot import NutritionChatbot  # noqa: E402

MACROS = {"p_entreno": 160, "h_entreno": 120, "g_entreno": 40,
          "p_peri": 35, "h_peri": 15,
          "p_descanso": 140, "h_descanso": 40, "g_descanso": 40}

# Copiadas de db.foods en producción el 12-08-2026.
PAN = {"id": 432, "nombre": "Pan de barra", "categorias": "8.1 | YA | 25 | SNA",
       "proteinas": 9, "hidratos": 50, "grasas": 0, "racion": 100, "unidades": False}
LECHE = {"id": 358, "nombre": "Leche entera", "categorias": "5.1 | YA | 25",
         "proteinas": 3, "hidratos": 5, "grasas": 3, "racion": 100, "unidades": False}
ACEITE = {"id": 3, "nombre": "Aceite de oliva virgen extra una cucharada sopera",
          "categorias": "17.1.1 | YA | 42",
          "proteinas": 0, "hidratos": 0, "grasas": 10, "racion": 10, "unidades": True}
LECHUGA = {"id": 363, "nombre": "Lechuga", "categorias": "13.1 | YA",
           "proteinas": 0, "hidratos": 0, "grasas": 0, "racion": 100, "unidades": False}
POLLO = {"id": 119, "nombre": "Carne picada de pechuga de pollo", "categorias": "2.2.2 | HAM",
         "proteinas": 20, "hidratos": 0, "grasas": 4, "racion": 100, "unidades": False}


class _Solo:
    """Lo único que necesitan estos dos métodos es el bot: no hace falta montar el agente
    entero (que pide Mongo, embeddings y clave de OpenAI) para probar una regla del motor.
    Se toman prestados de `AgentTools` para probar el código de verdad, no una copia."""
    _frase_que_cuenta = AgentTools._frase_que_cuenta
    _item_de = AgentTools._item_de

    def __init__(self):
        self.bot = NutritionChatbot("test_que_cuenta", MACROS)


def frase(food):
    return AgentTools._frase_que_cuenta(_Solo(), food)


def test_el_pan_no_cuenta_la_proteina():
    """El caso del filtro del tercio: el pan lleva 9 g de proteína y no le cuenta."""
    assert frase(PAN) == "te cuenta los hidratos; la proteína y la grasa no"


def test_la_leche_entera_cuenta_los_tres():
    """Caso 9 de los diez de Jesús."""
    assert frase(LECHE) == "cuenta los tres macros"


def test_el_aceite_solo_cuenta_grasa():
    assert frase(ACEITE) == "te cuenta la grasa; la proteína y los hidratos no"


def test_la_verdura_es_libre():
    assert frase(LECHUGA) == "no cuenta ningún macro (es libre)"


def test_la_carne_no_cuenta_hidratos():
    assert frase(POLLO) == "te cuenta la proteína y la grasa; los hidratos no"


def test_va_en_cada_alimento_que_ve_el_asistente():
    """No es una herramienta aparte que el modelo tenga que acordarse de llamar: viaja en
    el propio alimento, y por `_item_de` pasan las búsquedas, los borradores y la comida."""
    s = _Solo()
    item = AgentTools._item_de(s, PAN, 80.0, {"P": 0, "H": 40, "G": 0})
    assert item["que_cuenta"] == "te cuenta los hidratos; la proteína y la grasa no"
    assert item["nombre"] == "Pan de barra"


def test_un_alimento_roto_no_tumba_la_busqueda():
    """Si una ficha del catálogo viene mal, se queda sin frase y la búsqueda sigue."""
    assert frase({"id": 0, "nombre": "roto"}) in ("", "no cuenta ningún macro (es libre)")


@pytest.mark.parametrize("palabras,esperado", [
    ([], ""),
    (["la grasa"], "la grasa"),
    (["la proteína", "la grasa"], "la proteína y la grasa"),
    (["la proteína", "los hidratos", "la grasa"], "la proteína, los hidratos y la grasa"),
])
def test_la_enumeracion_se_lee(palabras, esperado):
    assert _y(palabras) == esperado
