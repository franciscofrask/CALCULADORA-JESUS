# -*- coding: utf-8 -*-
"""Los tres arreglos del 16-08, salidos de probar la app real en producción.

1. «Ajusta el aceite a 5» (pensando en gramos) dejaba 5 CUCHARADAS: 50 g de aceite, 45 g de
   grasa por encima del objetivo, y guardado sin preguntar. El guardarraíl medía gramos
   donde el motor contaba piezas.
2. Pedir 3 comidas por el chat borraba del plan la Comida 4 entera, y no había vuelta atrás.
3. El asistente no recordaba ni una frase: el historial no se guardaba en ninguna parte.
"""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

MONGO_URL = os.environ.get("MONGO_URL")
pytestmark = pytest.mark.skipif(not MONGO_URL, reason="sin MONGO_URL: test de integración")

MACROS = {"p_entreno": 135, "h_entreno": 65, "g_entreno": 50, "p_peri": 15, "h_peri": 15,
          "p_descanso": 135, "h_descanso": 65, "g_descanso": 50}


def correr(coro):
    return asyncio.run(coro)


async def _bot(sesion):
    from motor.motor_asyncio import AsyncIOMotorClient
    from chatbot import NutritionChatbot
    db = AsyncIOMotorClient(MONGO_URL)[os.environ.get("DB_NAME", "test_database")]
    bot = NutritionChatbot(sesion, db)
    bot.set_user_macros(dict(MACROS))
    bot.configure_day("entrenamiento", 4, momento_entreno=1, opcion_peri="sin_peri")
    return bot


# --------------------------------------------------- 1. cucharadas que se leían como gramos
async def _aceite_a_cinco():
    from agent_tools import AgentTools
    bot = await _bot("test_unidades_aceite")
    t = await AgentTools.crear(bot)
    aceite = next((f for f in t.foods.values()
                   if (f.get("nombre") or "").lower().startswith(
                       "aceite de oliva virgen extra una cucharada sopera")), None)
    assert aceite, "no está el aceite por cucharadas en el catálogo de pruebas"
    await t.editar_comida([{"op": "añadir", "alimento_id": int(aceite["id"]),
                            "cantidad": 10, "unidad": "g"}])
    # Lo que hizo el modelo en producción: «ajustar a 5» sin decir la unidad.
    r = await t.editar_comida([{"op": "ajustar", "nombre": aceite["nombre"], "a": 5}])
    comida = bot.state["comidas_completadas"].get(bot.current_meal_key(), {})
    return r, [(a.get("nombre"), a.get("cantidad_g")) for a in comida.get("alimentos", [])]


def test_ajustar_sin_unidad_no_multiplica_la_grasa_por_cinco():
    r, alimentos = correr(_aceite_a_cinco())
    aceite = next((c for n, c in alimentos if "aceite" in n.lower()), None)
    assert aceite is not None, alimentos
    # O lo frena preguntando, o lo deja en 5 g; lo que no puede es plantar 50 g.
    assert aceite <= 10, f"el aceite se fue a {aceite} g"
    if r.get("fallos"):
        assert any("grasa" in str(f.get("detalle", "")).lower()
                   or "son 50" in str(f.get("detalle", "")) for f in r["fallos"]), r["fallos"]


def test_una_pieza_que_dobla_el_objetivo_del_macro_se_pregunta():
    async def _probar():
        bot = await _bot("test_unidades_barbaridad")
        aceite = (await bot.search_foods("Aceite de oliva virgen extra una cucharada sopera",
                                         limit=1))
        assert aceite, "no está el aceite en el catálogo"
        return await bot._es_desmedido({"nombre": aceite[0]["nombre"], "cantidad": 50,
                                        "unidad": "g"})
    aviso = correr(_probar())
    assert aviso and "grasa" in aviso["texto"], aviso


# --------------------------------------------------- 2. guardar un día no borra otras comidas
def test_guardar_el_dia_no_borra_las_comidas_que_no_vienen():
    async def _probar():
        from motor.motor_asyncio import AsyncIOMotorClient
        import routes.diets as rd
        db = AsyncIOMotorClient(MONGO_URL)[os.environ.get("DB_NAME", "test_database")]
        rd.db = db
        uid, fecha = "test_qa_merge", "2026-08-18"
        await db.diets.delete_many({"user_id": uid, "fecha": fecha})
        await rd.upsert_diet_doc(uid, {"fecha": fecha, "num_comidas": 4, "comidas": {
            "C1": {"alimentos": [{"nombre": "Pollo", "cantidad_g": 100}]},
            "C4": {"alimentos": [{"nombre": "Caballa", "cantidad_g": 130}]}}})
        # Ahora se guarda el día con TRES comidas, como hacía el chat al reconfigurar.
        await rd.upsert_diet_doc(uid, {"fecha": fecha, "num_comidas": 3, "comidas": {
            "C1": {"alimentos": [{"nombre": "Pollo", "cantidad_g": 100}]}}})
        doc = await db.diets.find_one({"user_id": uid, "fecha": fecha}, {"_id": 0})
        await db.diets.delete_many({"user_id": uid, "fecha": fecha})
        return doc
    doc = correr(_probar())
    assert "C4" in (doc.get("comidas") or {}), "la Comida 4 se ha perdido al guardar"
    assert doc["comidas"]["C4"]["alimentos"][0]["nombre"] == "Caballa"


def test_vaciar_una_comida_sigue_vaciandola():
    async def _probar():
        from motor.motor_asyncio import AsyncIOMotorClient
        import routes.diets as rd
        db = AsyncIOMotorClient(MONGO_URL)[os.environ.get("DB_NAME", "test_database")]
        rd.db = db
        uid, fecha = "test_qa_merge2", "2026-08-19"
        await db.diets.delete_many({"user_id": uid, "fecha": fecha})
        await rd.upsert_diet_doc(uid, {"fecha": fecha, "comidas": {
            "C1": {"alimentos": [{"nombre": "Pollo", "cantidad_g": 100}]}}})
        await rd.upsert_diet_doc(uid, {"fecha": fecha, "comidas": {"C1": {"alimentos": []}}})
        doc = await db.diets.find_one({"user_id": uid, "fecha": fecha}, {"_id": 0})
        await db.diets.delete_many({"user_id": uid, "fecha": fecha})
        return doc
    doc = correr(_probar())
    assert doc["comidas"]["C1"]["alimentos"] == []


# --------------------------------------------------- 3. la conversación se recuerda
def test_la_conversacion_sobrevive_a_la_siguiente_peticion():
    async def _probar():
        from motor.motor_asyncio import AsyncIOMotorClient
        from chatbot import get_or_create_chatbot, save_chatbot_session, clear_session
        db = AsyncIOMotorClient(MONGO_URL)[os.environ.get("DB_NAME", "test_database")]
        sesion = "chat_test_memoria_qa"
        await clear_session(sesion, db)
        bot = await get_or_create_chatbot(sesion, db, dict(MACROS))
        bot.messages_history = [{"role": "user", "content": "quiero pollo"},
                                {"role": "assistant", "content": "te pongo pollo"}]
        bot.state["mensajes"] = bot.messages_history
        await save_chatbot_session(bot)
        # Otra petición = otra instancia, como en producción (y otro worker).
        otro = await get_or_create_chatbot(sesion, db, dict(MACROS))
        historial = list(otro.messages_history or [])
        await clear_session(sesion, db)
        return historial
    historial = correr(_probar())
    assert len(historial) == 2, historial
    assert historial[0]["content"] == "quiero pollo"
