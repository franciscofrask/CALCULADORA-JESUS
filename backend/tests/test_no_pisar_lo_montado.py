"""Lo que el cliente ya traía montado no se toca sin pedírselo.

Jesús, 12-08-2026: «Si alguien lo abre a media tarde, le monta el día otra vez y le pisa lo
que ya tenía».

Que el asistente LEA el día (test_precarga_dia_montado.py) era la mitad. La otra mitad es
que no lo reescriba. Medido contra la app con dos comidas puestas y «móntame el día»: el
agente rehacía una de ellas 1 de cada 4 veces -- `navegar` a la Comida 1 y `editar_comida`
encima. Que estuviera montada y guardada no lo paraba, porque nada se lo impedía.

La regla es de código y no de prompt a propósito: un prompt acierta casi siempre, y aquí
«casi siempre» significa perder el trabajo de un cliente una de cada cuatro veces.

Corre sin Mongo ni OpenAI: se llama a las herramientas directamente.
"""
import asyncio
import os
import sys

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _RAIZ)

import pytest  # noqa: E402

from agent_tools import AgentTools  # noqa: E402
from chatbot import NutritionChatbot  # noqa: E402

MACROS = {"p_entreno": 160, "h_entreno": 120, "g_entreno": 40,
          "p_peri": 35, "h_peri": 15,
          "p_descanso": 140, "h_descanso": 40, "g_descanso": 40}

POLLO = {"id": 119, "nombre": "Carne picada de pechuga de pollo", "categorias": "2.2.2 | HAM",
         "proteinas": 20, "hidratos": 0, "grasas": 4, "racion": 100, "unidades": False}
ARROZ = {"id": 1657, "nombre": "Arroz blanco", "categorias": "7.2",
         "proteinas": 7, "hidratos": 80, "grasas": 0.6, "racion": 100, "unidades": False}
CATALOGO = {f["id"]: f for f in (POLLO, ARROZ)}

DIA_GUARDADO = {"C1": {"alimentos": [
    {"alimento_id": 119, "nombre": "Carne picada de pechuga de pollo", "cantidad_g": 150},
    {"alimento_id": 1657, "nombre": "Arroz blanco", "cantidad_g": 100},
]}}


class _Solo:
    """Las piezas de `AgentTools` que se prueban aquí solo necesitan el bot."""
    _protegida = AgentTools._protegida
    _nombre_comida_actual = AgentTools._nombre_comida_actual
    ver_estado = AgentTools.ver_estado
    editar_comida = AgentTools.editar_comida

    def __init__(self, bot):
        self.bot = bot


@pytest.fixture
def herramientas():
    bot = NutritionChatbot("test_no_pisar", MACROS)
    bot.configure_day(tipo_dia="entrenamiento", num_comidas=4, momento_entreno=1,
                      opcion_peri="sin_peri")
    bot.precargar_desde_dieta(DIA_GUARDADO, CATALOGO)
    return _Solo(bot)


def test_la_comida_traida_queda_marcada(herramientas):
    assert herramientas.bot.state["comidas_traidas"] == ["C1"]


def test_no_se_puede_editar_una_comida_traida(herramientas):
    """El caso medido: navegar a la Comida 1 y escribir encima."""
    herramientas.bot.state["comida_actual"] = 1
    r = asyncio.run(herramientas.editar_comida([{"op": "quitar", "nombre": "Arroz blanco"}]))
    assert r["ok"] is False
    assert "ya la tenía montada" in r["error"]
    # Y lo importante: sigue ahí.
    assert len(herramientas.bot.state["comidas_completadas"]["C1"]["alimentos"]) == 2


def test_el_aviso_le_dice_al_agente_que_hacer(herramientas):
    """Un error que enseña, no una lista vacía (principio 4 del plan del agente)."""
    herramientas.bot.state["comida_actual"] = 1
    r = asyncio.run(herramientas.editar_comida([{"op": "quitar", "nombre": "Arroz blanco"}]))
    assert "forzar=true" in r["error"]
    assert "comida vacía" in r["error"]
    assert r["comida_ya_montada"]["alimentos"]


def test_si_el_cliente_lo_pide_si_se_puede(herramientas):
    """No es una prohibición: es que tenga que pedirlo él."""
    herramientas.bot.state["comida_actual"] = 1
    r = asyncio.run(herramientas.editar_comida(
        [{"op": "quitar", "nombre": "Arroz blanco"}], forzar=True))
    assert r.get("ok") is not False
    assert len(herramientas.bot.state["comidas_completadas"]["C1"]["alimentos"]) == 1


def test_las_comidas_vacias_no_estan_protegidas(herramientas):
    """Es lo normal: montar lo que le falta tiene que seguir funcionando sin fricción."""
    herramientas.bot.state["comida_actual"] = 3
    assert herramientas._protegida() is None


def test_lo_montado_en_esta_conversacion_no_esta_protegido():
    """Solo lo que venía de antes. Lo que se monta hablando lo está viendo el cliente."""
    bot = NutritionChatbot("test_no_pisar_2", MACROS)
    bot.configure_day(tipo_dia="entrenamiento", num_comidas=4, momento_entreno=1,
                      opcion_peri="sin_peri")
    bot.state["saved_meals"] = ["C1"]          # guardada con «guardar y siguiente»
    t = _Solo(bot)
    bot.state["comida_actual"] = 1
    assert t._protegida() is None


def test_al_reconfigurar_el_dia_la_marca_se_limpia(herramientas):
    """Si la comida deja de existir, su marca tampoco puede quedarse."""
    herramientas.bot.configure_day(tipo_dia="descanso", num_comidas=3, momento_entreno=1,
                                   opcion_peri="sin_peri", single_meal=True)
    vivas = set(herramientas.bot.state["meal_order"])
    assert all(k in vivas for k in herramientas.bot.state["comidas_traidas"])
