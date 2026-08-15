# -*- coding: utf-8 -*-
"""Un cliente SIN macros asignados no recibe una dieta inventada.

Nutrición a ese cliente le corta con «aún no tienes macros asignados». El asistente era la
única pantalla que no lo comprobaba: tiraba del relleno de `macros_por_fecha` (160 P de
entreno), le montaba un día de 195 P y se lo guardaba en su dieta (QA del 15-08 en
producción, fallo 27 de Jesús). Y el relleno saltaba también con clientes que SÍ tenían
macros, porque estaban guardados con las claves en inglés.
"""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from macros_por_fecha import en_castellano, para_el_chat, POR_DEFECTO   # noqa: E402
from chatbot import NutritionChatbot                                    # noqa: E402


def correr(coro):
    return asyncio.run(coro)


class TestClavesDeMacros:
    def test_ingles_y_castellano_valen_lo_mismo(self):
        en = en_castellano({"protein": 190, "carbs": 110, "fat": 50, "calories": 1650})
        es = en_castellano({"proteinas": 190, "hidratos": 110, "grasas": 50})
        assert en == es == {"proteinas": 190, "hidratos": 110, "grasas": 50}

    def test_sin_macros_los_tres_quedan_vacios(self):
        assert en_castellano({}) == {"proteinas": None, "hidratos": None, "grasas": None}
        assert en_castellano(None)["proteinas"] is None


class TestPropios:
    def test_sin_perfil_no_son_suyos(self):
        m = correr(para_el_chat(None, None, "2026-08-15"))
        assert m["propios"] is False
        assert m["p_entreno"] == POR_DEFECTO["p_entreno"]


class TestElBotSeNiega:
    def test_sin_macros_propios_el_bot_lo_dice(self):
        bot = NutritionChatbot("test_sin_macros", None)
        bot.set_user_macros({**POR_DEFECTO, "propios": False})
        assert bot.sin_macros_asignados() is True
        # Y `propios` no se cuela entre los macros: reventaría cualquier cuenta.
        assert "propios" not in bot.state["macros_usuario"]

    def test_con_macros_suyos_monta_como_siempre(self):
        bot = NutritionChatbot("test_con_macros", None)
        bot.set_user_macros({"p_entreno": 190, "h_entreno": 110, "g_entreno": 50,
                             "propios": True})
        assert bot.sin_macros_asignados() is False

    def test_quien_llama_con_macros_a_mano_los_trae_de_verdad(self):
        """Tests y scripts pasan los macros sin la marca: se dan por buenos."""
        bot = NutritionChatbot("test_a_mano", None)
        bot.set_user_macros({"p_entreno": 200})
        assert bot.sin_macros_asignados() is False
