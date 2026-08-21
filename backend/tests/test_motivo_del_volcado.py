# -*- coding: utf-8 -*-
"""El asistente no dice «Guardado» cuando no ha guardado (tarea 1.3 del 21-08).

El «✅ Guardado en tu pestaña de nutrición» lo escribía el front tras CUALQUIER volcado:
editar una comida ya volcada, reconfigurar el día o vaciar re-sincronizan el plan con la
misma bandera que el guardar de verdad, y el cliente leía «Guardado» sin haber pedido
guardar nada. Ahora la bandera viaja con su `motivo`: 'guardado' SOLO cuando el cliente
ha guardado (guardar_comida o el botón); el resto es 'resincronizacion' y el front lo
anuncia como una actualización.

Todo esto corre sin OpenAI y sin Mongo: la regla vive en `_motivo_del_volcado` y en los
atajos deterministas de `procesar` (deshacer), que contestan antes de llamar al modelo.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_loop import _motivo_del_volcado  # noqa: E402


class _Bot:
    """Lo justo que lee `_motivo_del_volcado`: la comida actual y las marcas."""

    def __init__(self, key="C1", saved=None, traidas=None):
        self.state = {"saved_meals": saved or [], "comidas_traidas": traidas or []}
        self._key = key

    def current_meal_key(self):
        return self._key


def test_guardar_comida_es_el_unico_guardado():
    assert _motivo_del_volcado("guardar_comida", {"ok": True}, {}, _Bot()) == "guardado"


def test_sin_ok_no_se_vuelca_nada():
    for nombre in ("guardar_comida", "configurar_dia", "editar_comida"):
        assert _motivo_del_volcado(nombre, {"ok": False}, {}, _Bot()) is None, nombre


def test_configurar_dia_es_resincronizacion():
    assert _motivo_del_volcado("configurar_dia", {"ok": True}, {}, _Bot()) \
        == "resincronizacion"


def test_editar_una_comida_ya_volcada_es_resincronizacion():
    """El caso que motivó la tarea: «sustitúyeme X» sobre una comida guardada volcaba
    (bien) y anunciaba «Guardado» (mal)."""
    args = {"operaciones": [{"op": "sustituir", "nombre": "a", "texto": "b"}]}
    assert _motivo_del_volcado("editar_comida", {"ok": True}, args,
                               _Bot(saved=["C1"])) == "resincronizacion"
    assert _motivo_del_volcado("editar_comida", {"ok": True}, args,
                               _Bot(traidas=["C1"])) == "resincronizacion"


def test_editar_una_comida_sin_volcar_no_vuelca():
    """Mientras se MONTA una comida el volcado espera al guardar, como siempre."""
    args = {"operaciones": [{"op": "añadir", "texto": "x"}]}
    assert _motivo_del_volcado("editar_comida", {"ok": True}, args, _Bot()) is None


def test_vaciar_vuelca_como_resincronizacion_aunque_no_este_guardada():
    for op in ("vaciar", "vaciar_dia"):
        args = {"operaciones": [{"op": op}]}
        assert _motivo_del_volcado("editar_comida", {"ok": True}, args, _Bot()) \
            == "resincronizacion", op


def test_otras_herramientas_no_vuelcan():
    for nombre in ("navegar", "ver_estado", "aplicar_borrador", "buscar_alimentos"):
        assert _motivo_del_volcado(nombre, {"ok": True}, {}, _Bot()) is None, nombre


def test_deshacer_por_chat_anuncia_actualizacion_no_guardado():
    """El atajo determinista de «deshaz» contesta sin modelo: vuelca (el plan también
    vuelve atrás) pero con motivo 'resincronizacion', que deshacer no es guardar."""
    from agent_loop import AgentLoop
    from agent_tools import AgentTools
    from chatbot import NutritionChatbot

    bot = NutritionChatbot("test_motivo_deshacer", None)
    bot.configure_day(tipo_dia="entrenamiento", num_comidas=4, momento_entreno=1,
                      opcion_peri="sin_peri")
    bot.apuntar_para_deshacer("quitar el tomate")
    tools = AgentTools.__new__(AgentTools)   # el atajo no toca el catálogo
    tools.bot = bot
    loop = AgentLoop(bot, tools)
    r = asyncio.run(loop.procesar("deshaz"))
    assert r.get("comida_guardada") is True, r
    assert r.get("motivo") == "resincronizacion", r
