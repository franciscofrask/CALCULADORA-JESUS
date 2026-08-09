"""El asistente no puede negar lo que sí sabe hacer.

De la auditoría con agentes de navegador (08-08-2026). A «¿tienes recetas de Jesús?»
contestaba: *«no tengo un recetario de Jesús como tal dentro de la app; lo que ves son
menús que siguen su forma de trabajar»*. Falso: tiene **159 recetas suyas**, importadas de
noteconformesconmenos.com con su nombre, su foto y su enlace.

Eran tres cosas a la vez:

  1. Nadie se lo había dicho: la ficha de `componer_menu` no mencionaba el recetario.
  2. El enlace y la foto se perdían por el camino (`_ajustar_plantilla` no los devolvía),
     así que ni enseñándolas podía citar la fuente.
  3. Y aunque lo supiera, no tenía forma de PEDIRLAS: el recetario solo entraba cuando la
     llamada venía sin estilo ni filtros, y una pregunta directa nunca cumple eso.

Se comprobaron también otras capacidades que la auditoría daba por dudosas -- calcular
gramos para un objetivo de macros, cambiar la configuración del día, sumar lo que llevas --
y esas sí funcionaban.
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


def _hablar(mensaje):
    async def _correr():
        from motor.motor_asyncio import AsyncIOMotorClient
        from chatbot import NutritionChatbot
        from agent_loop import AgentLoop
        db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "jg12_restored")]
        bot = NutritionChatbot(f"cap_{mensaje[:14]}", db)
        bot.set_user_macros(MACROS)
        bot.configure_day("entrenamiento", 4, momento_entreno=1, opcion_peri="intra_post")
        loop = await AgentLoop.crear(bot)
        return await loop.procesar(mensaje)
    return asyncio.run(_correr())


NEGACIONES = ("no tengo", "no puedo", "no dispongo", "no soy capaz", "no manejo")


@pytest.mark.parametrize("pregunta", [
    "tienes recetas de Jesus? enseñame alguna",
    "ponme una receta del recetario para el desayuno",
])
def test_el_recetario_existe_y_lo_dice(pregunta):
    r = _hablar(pregunta)
    texto = str(r.get("message") or "").lower()
    del_recetario = [b for b in (r.get("borradores") or []) if b.get("origen") == "recetario"]
    assert del_recetario, f"no trae ninguna receta de Jesús: {texto[:160]}"
    assert all(b.get("receta_url") for b in del_recetario), (
        "las trae sin enlace: el cliente no puede ver la receta entera")
    assert all(b.get("nombre") for b in del_recetario), "las trae sin nombre"


def test_no_niega_tener_recetario():
    r = _hablar("tienes el recetario de no te conformes con menos?")
    texto = str(r.get("message") or "").lower()
    niega = [n for n in NEGACIONES if f"{n} un recetario" in texto or f"{n} recetario" in texto
             or f"{n} recetas" in texto]
    assert not niega, f"lo niega teniéndolo: {texto[:200]}"


@pytest.mark.parametrize("pregunta", [
    "puedes cambiarme el dia a 3 comidas?",
    "me puedes decir cuanta proteina llevo hoy en total?",
])
def test_lo_que_ya_sabia_hacer_lo_sigue_haciendo(pregunta):
    """Estas tres se comprobaron en la misma tanda y funcionaban; quedan fijadas para que
    el arreglo del recetario no se lleve nada por delante."""
    r = _hablar(pregunta)
    texto = str(r.get("message") or "").lower()
    assert texto, "no contesta"
    assert not any(texto.startswith(n) for n in NEGACIONES), texto[:160]
