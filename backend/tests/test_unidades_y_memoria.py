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


def test_un_numero_sin_unidad_que_dispara_el_macro_se_pregunta():
    """El caso exacto de producción: «aceite a 5» sin decir si son gramos o cucharadas."""
    async def _probar():
        bot = await _bot("test_unidades_barbaridad")
        aceite = (await bot.search_foods("Aceite de oliva virgen extra una cucharada sopera",
                                         limit=1))
        assert aceite, "no está el aceite en el catálogo"
        sin_unidad = await bot._es_desmedido({"nombre": aceite[0]["nombre"], "cantidad": 5})
        # Y con la unidad dicha, lo que pide el cliente es lo que va: no se le frena.
        con_gramos = await bot._es_desmedido({"nombre": aceite[0]["nombre"], "cantidad": 5,
                                              "unidad": "g"})
        return sin_unidad, con_gramos
    sin_unidad, con_gramos = correr(_probar())
    assert sin_unidad and "grasa" in sin_unidad["texto"], sin_unidad
    assert con_gramos is None, con_gramos


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


def test_una_pantalla_vieja_no_pisa_lo_que_toco_la_otra():
    """El mismo día abierto en dos sitios: el segundo en guardar no borra lo del primero."""
    async def _probar():
        from motor.motor_asyncio import AsyncIOMotorClient
        import routes.diets as rd
        db = AsyncIOMotorClient(MONGO_URL)[os.environ.get("DB_NAME", "test_database")]
        rd.db = db
        uid, fecha = "test_qa_dos_pestanas", "2026-08-20"
        await db.diets.delete_many({"user_id": uid, "fecha": fecha})
        # Las dos pantallas cargan el día tal y como está.
        primero = await rd.upsert_diet_doc(uid, {"fecha": fecha, "comidas": {
            "C1": {"alimentos": [{"nombre": "Pollo", "cantidad_g": 100}]}}})
        version_de_ambas = primero["updated_at"]
        # La pestaña A cambia la Comida 1.
        await rd.upsert_diet_doc(uid, {"fecha": fecha, "base_updated_at": version_de_ambas,
                                       "comidas": {"C1": {"alimentos": [
                                           {"nombre": "Merluza", "cantidad_g": 150}]}}})
        # La pestaña B, que sigue con la versión de antes, guarda su copia vieja.
        r = await rd.upsert_diet_doc(uid, {"fecha": fecha, "base_updated_at": version_de_ambas,
                                           "comidas": {"C1": {"alimentos": [
                                               {"nombre": "Pollo", "cantidad_g": 100}]}}})
        doc = await db.diets.find_one({"user_id": uid, "fecha": fecha}, {"_id": 0})
        await db.diets.delete_many({"user_id": uid, "fecha": fecha})
        return r, doc
    r, doc = correr(_probar())
    assert r.get("conflictos") == ["C1"], r.get("conflictos")
    assert doc["comidas"]["C1"]["alimentos"][0]["nombre"] == "Merluza", \
        "la pestaña vieja ha pisado el cambio de la otra"


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
# ------------------------------------- las banderas de un solo turno no se quedan pegadas
def test_las_banderas_de_un_turno_no_se_persisten():
    """`config_tocada` encendida para siempre = la config del día viejo pisando al nuevo."""
    async def _probar():
        from motor.motor_asyncio import AsyncIOMotorClient
        from chatbot import get_or_create_chatbot, save_chatbot_session, clear_session
        from routes.chatbot import _estado_para_front
        db = AsyncIOMotorClient(MONGO_URL)[os.environ.get("DB_NAME", "test_database")]
        sesion = "chat_test_banderas_qa"
        await clear_session(sesion, db)
        bot = await get_or_create_chatbot(sesion, db, dict(MACROS))
        bot.state["config_tocada"] = True
        bot.state["fecha_pedida"] = "2026-08-17"
        # El orden de la ruta: primero se consume el estado del turno, después se guarda.
        estado = _estado_para_front(bot)
        await save_chatbot_session(bot)
        doc = await db.chatbot_sessions.find_one({"session_id": sesion}, {"_id": 0, "state": 1})
        await clear_session(sesion, db)
        return estado, (doc or {}).get("state") or {}
    estado, guardado = correr(_probar())
    assert estado["config_tocada"] is True and estado["fecha_pedida"] == "2026-08-17", estado
    assert not guardado.get("config_tocada"), "la bandera se ha quedado guardada"
    assert not guardado.get("fecha_pedida"), "la fecha pedida se ha quedado guardada"


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


# ------------------------------------------------------------------ bajar no es quitar
def test_bajar_no_se_ejecuta_como_quitar():
    """El asistente propuso «bajar algo el arroz», el cliente dijo que sí, y lo quitó entero."""
    async def _probar():
        from agent_tools import AgentTools
        bot = await _bot("test_bajar_no_quitar")
        t = await AgentTools.crear(bot)
        arroz = next((f for f in t.foods.values()
                      if (f.get("nombre") or "").lower().startswith("arroz blanco")), None)
        assert arroz, "no hay arroz blanco en el catálogo de pruebas"
        await t.editar_comida([{"op": "añadir", "alimento_id": int(arroz["id"]),
                                "cantidad": 60, "unidad": "g"}])
        # Lo que dijo el cliente en ESTE mensaje es lo que manda.
        bot.mensaje_en_curso = "vale, baja algo el arroz"
        r = await t.editar_comida([{"op": "quitar", "nombre": arroz["nombre"]}])
        sigue = any("arroz" in (a.get("nombre") or "").lower()
                    for a in bot.state["comidas_completadas"][bot.current_meal_key()]["alimentos"])
        # Y si de verdad pide quitarlo, se quita.
        bot.mensaje_en_curso = "quita el arroz"
        await t.editar_comida([{"op": "quitar", "nombre": arroz["nombre"]}])
        fuera = not any("arroz" in (a.get("nombre") or "").lower()
                        for a in bot.state["comidas_completadas"][bot.current_meal_key()]["alimentos"])
        return r, sigue, fuera
    r, sigue, fuera = correr(_probar())
    assert sigue, "ha quitado el arroz cuando le pidieron bajarlo"
    assert r.get("fallos"), r
    assert "BAJAR" in str(r["fallos"][0].get("detalle", "")), r["fallos"]
    assert fuera, "no ha quitado el arroz cuando sí se lo han pedido"
