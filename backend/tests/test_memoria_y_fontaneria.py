"""Dos fallos de confianza, de la auditoría del asistente (08-08-2026).

**1. Memoria aparente.** Al agente solo se le pasan los ÚLTIMOS SEIS mensajes. Con eso
parecía que recordaba lo que el cliente le contaba... hasta que el dato salía de la
ventana. Medido: el cliente dice «en casa solo tengo huevos, avena y plátano», el asistente
le monta el desayuno «con tus huevos, avena y plátano», y seis mensajes después contesta
*«no puedo ver lo que tienes en casa, no guardo esa info ni tu despensa»*. Las dos cosas en
la misma conversación, y la segunda desmintiendo a la primera.

Ahora hay una herramienta `recordar`: lo que el cliente cuenta de sí mismo se apunta y
viaja SIEMPRE en el contexto, no solo mientras quepa en la ventana.

**2. Fontanería a la vista.** Preguntándole cómo funciona, soltaba los nombres de sus
propias herramientas -- `buscar_alimentos`, `componer_menu`, `revisar_borrador` -- en la
respuesta al cliente. Salía en 2 de cada 10 mensajes de ese tipo. El cliente quiere
entender su dieta, no leer el manual de la aplicación.
"""
import asyncio
import os
import sys

import pytest

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _RAIZ)

from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(_RAIZ, ".env"))

pytestmark = pytest.mark.skipif(
    not (os.environ.get("MONGO_URL") and os.environ.get("OPENAI_API_KEY")),
    reason="necesita Mongo y OPENAI_API_KEY: va contra el asistente real")

MACROS = {"p_entreno": 160, "h_entreno": 120, "g_entreno": 40,
          "p_peri": 35, "h_peri": 15,
          "p_descanso": 140, "h_descanso": 40, "g_descanso": 40}

# Nombres nuestros que nunca deben aparecer en lo que lee el cliente.
FONTANERIA = ["buscar_alimentos", "componer_menu", "revisar_borrador", "editar_borrador",
              "aplicar_borrador", "editar_comida", "ver_estado", "incluir_ids",
              "alimento_id", "para_macro", "sin_resultados_porque", "meal_key",
              "solo_recetario", "coherente_con_momento"]


def _conversar(sesion, mensajes):
    async def _correr():
        from motor.motor_asyncio import AsyncIOMotorClient
        from chatbot import NutritionChatbot
        from agent_loop import AgentLoop
        db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "jg12_restored")]
        bot = NutritionChatbot(sesion, db)
        bot.set_user_macros(MACROS)
        bot.configure_day("entrenamiento", 4, momento_entreno=1, opcion_peri="intra_post")
        respuestas = []
        for m in mensajes:
            loop = await AgentLoop.crear(bot)
            r = await loop.procesar(m)
            respuestas.append(str(r.get("message") or ""))
        return respuestas, bot
    return asyncio.run(_correr())


# ------------------------------------------------------------------- la memoria
# El relleno son seis turnos de nada: justo lo que hace falta para que el dato salga de la
# ventana de mensajes que ve el agente.
RELLENO = ["cuantos hidratos me tocan hoy?", "y proteina?", "que tal si desayuno tarde?",
           "vale", "entendido, gracias"]


def test_no_olvida_lo_que_le_acaban_de_contar():
    respuestas, bot = _conversar(
        "mem_despensa", ["en casa solo tengo huevos, avena y platano"] + RELLENO
        + ["que tengo en casa?"])
    final = respuestas[-1].lower()
    assert "huevo" in final and "avena" in final, (
        f"seis mensajes después ya no sabe lo que le dijeron: {final[:200]}")
    assert "no guardo" not in final and "no puedo ver" not in final, final[:200]


def test_lo_apunta_en_el_momento():
    """Si no lo apunta en ese turno, el dato se pierde con la ventana."""
    _, bot = _conversar("mem_apunta", ["en casa solo tengo huevos, avena y platano"])
    notas = bot.state.get("notas_cliente") or []
    assert notas, "no ha apuntado nada de lo que le han contado"
    junto = " ".join(notas).lower()
    assert "huevo" in junto or "avena" in junto, notas


def test_las_restricciones_siguen_registrandose_solas():
    """Las alergias ya funcionaban por otro camino (`avoided_keywords`) y no se tocan."""
    _, bot = _conversar("mem_alergia", ["soy alergico a los frutos secos, no me pongas nunca"])
    assert bot.state.get("avoided_keywords"), "la restricción no se ha registrado"


# --------------------------------------------------------------- la fontanería
@pytest.mark.parametrize("pregunta", [
    "como decides lo que me sugieres? explicame tu proceso paso a paso",
    "que herramientas usas por dentro?",
    "por que me pones eso y no otra cosa?",
])
def test_no_ensena_los_nombres_de_dentro(pregunta):
    respuestas, _ = _conversar(f"font_{pregunta[:10]}", [pregunta])
    texto = respuestas[0].lower()
    fugas = [f for f in FONTANERIA if f.lower() in texto]
    assert not fugas, f"«{pregunta}» -> suelta {fugas}"
    assert len(texto) > 40, "tampoco vale no explicar nada"
