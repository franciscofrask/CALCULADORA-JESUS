# -*- coding: utf-8 -*-
"""Las 8 herramientas del agente (agent_tools.py), contra la base de dev.

Integración de verdad: catálogo, embeddings y perfil de momento reales. Lo único que
gastan es una llamada de embedding por texto de búsqueda nuevo (céntimos). Si no hay
Mongo o faltan los embeddings, se saltan con el motivo claro.
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


def correr(coro):
    return asyncio.run(coro)


async def _tools(num_comidas=4, ir_a=None, tipo_dia="entrenamiento", dijo=None):
    """`dijo`: lo que el cliente ha escrito en la conversación, para los filtros con cita."""
    from motor.motor_asyncio import AsyncIOMotorClient
    from chatbot import NutritionChatbot
    from agent_tools import AgentTools
    db = AsyncIOMotorClient(MONGO_URL)[os.environ.get("DB_NAME", "test_database")]
    bot = NutritionChatbot("test_agent_tools", db)
    bot.configure_day(tipo_dia=tipo_dia, num_comidas=num_comidas,
                      momento_entreno=1, opcion_peri="intra_post")
    bot.messages_history = [{"role": "user", "content": d} for d in (dijo or [])]
    tools = await AgentTools.crear(bot)
    if ir_a:
        tools.navegar(ir_a)
    return tools


# ------------------------------------------------------------ buscar_alimentos
class TestBuscarAlimentos:
    def test_generico_no_devuelve_marcas(self):
        async def t():
            tools = await _tools()
            r = await tools.buscar_alimentos("proteina", para_macro="P", generico=True)
            assert r["items"], r.get("sin_resultados_porque")
            assert all(not i["es_marca"] for i in r["items"])
        correr(t())

    def test_marca_filtra_por_nombre(self):
        async def t():
            tools = await _tools()
            r = await tools.buscar_alimentos("yogur", marca="Hacendado")
            assert r["items"]
            assert all("hacendado" in i["nombre"].lower() for i in r["items"])
        correr(t())

    def test_errata_fonetica(self):
        async def t():
            tools = await _tools()
            r = await tools.buscar_alimentos("wevos")
            assert any("huevo" in i["nombre"].lower() for i in r["items"])
        correr(t())

    def test_desayuno_sin_atipicos(self):
        async def t():
            tools = await _tools(ir_a="1")   # C1 = desayuno
            r = await tools.buscar_alimentos(para_macro="P")
            momento = tools._momento_actual()
            assert momento == "desayuno"
            if tools.perfil:
                for i in r["items"]:
                    food = tools.foods[i["id"]]
                    assert tools.perfil.coherencia(food, momento) >= 0.25, i["nombre"]
        correr(t())

    def test_sin_resultados_explica(self):
        async def t():
            tools = await _tools()
            r = await tools.buscar_alimentos("zzzznoexiste", marca="marcainventada9")
            assert not r["items"] and r["sin_resultados_porque"]
        correr(t())

    def test_dimensionado_del_motor(self):
        async def t():
            tools = await _tools()
            r = await tools.buscar_alimentos("pechuga de pollo", para_macro="P")
            assert r["items"]
            top = r["items"][0]
            assert top["cantidad_g"] > 0 and top["macros"]["P"] > 0
        correr(t())


# ------------------------------------------------------------ componer_menu
class TestComponerMenu:
    def test_menu_simple_cuadra(self):
        async def t():
            tools = await _tools()
            r = await tools.componer_menu(n=2)
            assert r["borradores"], r.get("sin_resultados_porque")
            b = r["borradores"][0]
            assert b["items"] and b["macros_totales"]["P"] > 0
            # el desvío del motor es razonable (no prosa: comida montada de verdad)
            assert sum(abs(v) for v in b["desvio"].values()) <= 40
        correr(t())

    def test_incluir_ids_obligatorios(self):
        async def t():
            tools = await _tools()
            batido = await tools.buscar_alimentos("batido de proteinas", para_macro="P", limite=1)
            fruta = await tools.buscar_alimentos("platano", limite=1)
            ids = [batido["items"][0]["id"], fruta["items"][0]["id"]]
            r = await tools.componer_menu(incluir_ids=ids, n=1)
            assert r["borradores"]
            en_menu = {i["id"] for i in r["borradores"][0]["items"]}
            assert set(ids) <= en_menu
        correr(t())

    def test_generico_respetado(self):
        """Pedido POR EL CLIENTE y citado, el filtro se aplica y no entra ni una marca."""
        async def t():
            tools = await _tools(dijo=["dame opciones pero sin marcas"])
            r = await tools.componer_menu(generico=True, filtro_porque="sin marcas", n=1)
            assert r["borradores"]
            assert all(not i["es_marca"] for i in r["borradores"][0]["items"])
            assert not r.get("nota")
        correr(t())

    def test_sin_cita_no_hay_filtro_de_marca(self):
        """El modelo no puede atribuirle al cliente una preferencia que no dijo.

        Francisco, 13-08-2026: «siempre me dice que pedí genéricos, y solo le pedí
        opciones, nunca mencioné ni genéricos ni marcas». En la sesión de producción los
        borradores llevaban `generico: True` después de un «para la comida dos dame
        opciones», y el revisor lo repetía en la tarjeta como un hecho del cliente. De
        paso estrechaba el catálogo a genéricos en TODAS las composiciones, que es lo
        contrario de la variedad que se le pide.
        """
        async def t():
            tools = await _tools(dijo=["para la comida dos dame opciones"])
            r = await tools.componer_menu(generico=True, n=1)
            assert r["borradores"]
            assert r["borradores"][0]["filtros"]["generico"] is None
            assert r.get("nota"), "tiene que decirle por qué no lo ha aplicado"
            rev = await tools.revisar_borrador(r["borradores"][0]["id"])
            assert all(p["tipo"] != "marca_no_pedida" for p in rev.get("problemas", []))
        correr(t())

    def test_una_cita_inventada_no_cuela(self):
        """La cita se comprueba contra lo que el cliente escribió, no se cree."""
        async def t():
            tools = await _tools(dijo=["dame opciones"])
            r = await tools.componer_menu(generico=True, n=1,
                                          filtro_porque="el cliente prefiere genéricos")
            assert r["borradores"][0]["filtros"]["generico"] is None
        correr(t())

    def test_lo_apuntado_en_otro_turno_vale(self):
        """Lo que el cliente dijo antes y quedó apuntado sigue siendo suyo."""
        async def t():
            tools = await _tools(dijo=["dame opciones"])
            tools.bot.state.setdefault("notas_cliente", []).append("no compra marcas")
            r = await tools.componer_menu(generico=True, filtro_porque="no compra marcas", n=1)
            assert r["borradores"][0]["filtros"]["generico"] is True
        correr(t())

    def test_el_nombre_de_la_comida_no_es_un_estilo(self):
        """Llegaba `estilo='Comida 1'` desde el modelo, y eso se va a la búsqueda
        semántica a buscar alimentos que se parezcan a la frase «Comida 1»."""
        async def t():
            tools = await _tools()
            assert tools._estilo_limpio("Comida 1") == ""
            assert tools._estilo_limpio("comida 2") == ""
            assert tools._estilo_limpio("Intra") == ""
            assert tools._estilo_limpio("algo rápido sin cocinar") == "algo rápido sin cocinar"
        correr(t())


# ------------------------------------------------------------ comidas reales
class TestComidasReales:
    """Las opciones salen de comidas que alguien comió, no de inventar (14-08-2026).

    Francisco: «tengo una base de datos de todas las dietas de los usuarios, ¿por qué no
    la entrenas con eso?» y «un usuario puede armar un día sin sentido porque hizo una
    prueba, y esos menús no pueden pasar». Estos tests fijan las dos mitades: que el
    historial y la biblioteca alimentan las opciones, y que lo no repetido no pasa sin
    juez.
    """

    def test_la_puerta_mecanica_del_juez(self):
        """Lo repetido pasa solo; lo de una sola vez, no. Sin llamar a ningún modelo."""
        from core.juez_menus import pasa_sin_juicio
        assert pasa_sin_juicio(clientes_distintos=2)
        assert pasa_sin_juicio(fechas_distintas=2)
        assert not pasa_sin_juicio(clientes_distintos=1, fechas_distintas=1)
        assert not pasa_sin_juicio()

    def test_la_firma_ignora_cantidades_y_orden(self):
        """La coherencia es de la combinación: 100 g o 300 g del mismo trío es el mismo
        juicio, y el orden de los ids no puede crear firmas distintas."""
        from core.juez_menus import firma_de
        assert firma_de("comida", [3, 1, 2]) == firma_de("comida", [2, 3, 1, 1])
        assert firma_de("desayuno", [1, 2]) != firma_de("comida", [1, 2])

    def test_el_historial_del_cliente_vuelve_como_opcion(self):
        """Dos días iguales en su historial → esa comida sale como opción, con SUS
        alimentos exactos y las cantidades recuadradas a lo que falta hoy. Dos fechas
        para que pase la puerta mecánica sin gastar juez (un día suelto es una prueba)."""
        async def t():
            from motor.motor_asyncio import AsyncIOMotorClient
            db = AsyncIOMotorClient(MONGO_URL)[os.environ.get("DB_NAME", "test_database")]
            tools = await _tools()
            tools.navegar("Comida 2")
            # Tres piezas reales del catálogo, buscadas como las buscaría la app.
            pollo = (await tools.buscar_alimentos("pechuga de pollo", limite=1))["items"][0]
            arroz = (await tools.buscar_alimentos("arroz", limite=1))["items"][0]
            aceite = (await tools.buscar_alimentos("aceite de oliva", limite=1))["items"][0]
            firma = sorted([pollo["id"], arroz["id"], aceite["id"]])
            key = tools.bot.current_meal_key()
            docs = [{"user_id": "test_agent_tools", "fecha": f"2099-01-0{i}",
                     "comidas": {key: {"alimentos": [
                         {"alimento_id": fid, "cantidad_g": 100} for fid in firma]}}}
                    for i in (1, 2)]
            await db.diets.insert_many(docs)
            try:
                restante = tools.bot.get_remaining_macros()
                ops = await tools._menus_del_historial(restante, tools._momento_actual(),
                                                       n=2, juicios={"n": 0})
                assert ops, "el historial del cliente no volvió como opción"
                assert ops[0]["origen"] == "historial"
                assert sorted(i["id"] for i in ops[0]["items"]) == firma, \
                    "la opción no lleva SUS alimentos exactos"
                tot = {m: sum(i["macros"][m] for i in ops[0]["items"]) for m in ("P", "H", "G")}
                assert all(abs(tot[m] - restante[m]) <= 24 for m in ("P", "H", "G")), \
                    f"no se recuadró a lo que falta hoy: {tot} vs {restante}"
            finally:
                await db.diets.delete_many({"user_id": "test_agent_tools",
                                            "fecha": {"$in": ["2099-01-01", "2099-01-02"]}})
        correr(t())

    def test_un_dia_de_prueba_no_pasa_sin_juez(self):
        """Una sola fecha en el historial: la puerta mecánica no la deja pasar, y con el
        cupo de juicios agotado la opción NO se ofrece. Es la mitad que protege de los
        días sin sentido: sin veredicto no hay tarjeta."""
        async def t():
            from motor.motor_asyncio import AsyncIOMotorClient
            db = AsyncIOMotorClient(MONGO_URL)[os.environ.get("DB_NAME", "test_database")]
            tools = await _tools()
            tools.navegar("Comida 2")
            pollo = (await tools.buscar_alimentos("pechuga de pollo", limite=1))["items"][0]
            arroz = (await tools.buscar_alimentos("arroz", limite=1))["items"][0]
            key = tools.bot.current_meal_key()
            await db.diets.insert_one({"user_id": "test_agent_tools", "fecha": "2099-02-01",
                                       "comidas": {key: {"alimentos": [
                                           {"alimento_id": pollo["id"], "cantidad_g": 100},
                                           {"alimento_id": arroz["id"], "cantidad_g": 100}]}}})
            try:
                restante = tools.bot.get_remaining_macros()
                # Cupo de juicios ya gastado: el candidato de una sola fecha no puede pasar.
                from core.juez_menus import JUICIOS_POR_PETICION, firma_de
                # La condición del test hay que CREARLA, no suponerla: desde que la caché
                # de veredictos se copió de producción, esta pareja puede venir ya
                # aprobada de un menú real y entonces no necesita juez. Se borra su
                # veredicto (si lo hay) para que el camino probado sea el del cupo.
                await db.menu_juicios.delete_one(
                    {"firma": firma_de(tools._momento_actual(), [pollo["id"], arroz["id"]])})
                ops = await tools._menus_del_historial(
                    restante, tools._momento_actual(), n=2,
                    juicios={"n": JUICIOS_POR_PETICION})
                assert not ops, "una comida de UNA sola fecha pasó sin juez"
            finally:
                await db.diets.delete_many({"user_id": "test_agent_tools",
                                            "fecha": "2099-02-01"})
        correr(t())

    def test_la_biblioteca_vuelve_como_opcion(self):
        """Un menú real de la biblioteca (montado por 2+ personas, con el filtro de
        calidad puesto y 5 piezas o menos) sale como opción cuando el objetivo es
        alcanzable. Se prueban varios objetivos tomados de menús reales: alguno tiene
        que volver; que uno concreto caiga por coherencia de momento o recuadre es
        legítimo, que caigan todos no."""
        async def t():
            from motor.motor_asyncio import AsyncIOMotorClient
            db = AsyncIOMotorClient(MONGO_URL)[os.environ.get("DB_NAME", "test_database")]
            docs = [d async for d in db.meal_library.find(
                {"tipo": "comida", "calidad.pasa": True, "clientes": {"$gte": 2},
                 "repetido_de": {"$exists": False}}, {"_id": 0}).limit(12)
                if len(d.get("alimentos") or []) <= 5]
            if not docs:
                pytest.skip("la biblioteca de este entorno no tiene menús de 2+ clientes y ≤5 piezas")
            tools = await _tools()
            tools.navegar("Comida 2")
            encontrado = []
            for doc in docs[:8]:
                objetivo = {m: float(doc["macros"][m]) for m in ("P", "H", "G")}
                ops = await tools._menus_de_la_biblioteca(objetivo, tools._momento_actual(),
                                                          n=2, juicios={"n": 0})
                if ops:
                    encontrado = ops
                    break
            assert encontrado, "la biblioteca no dio ninguna opción para ningún objetivo real"
            assert all(o["origen"] == "biblioteca" for o in encontrado)
            assert all(o.get("nombre") for o in encontrado), "la opción de biblioteca va con nombre"
        correr(t())

    def test_los_evitados_del_cliente_no_vuelven_por_el_historial(self):
        """Su historial trae lo que comía ANTES de sus restricciones de ahora: si hoy
        evita una palabra, esa comida suya ya no se le ofrece."""
        async def t():
            from motor.motor_asyncio import AsyncIOMotorClient
            db = AsyncIOMotorClient(MONGO_URL)[os.environ.get("DB_NAME", "test_database")]
            tools = await _tools()
            tools.navegar("Comida 2")
            pollo = (await tools.buscar_alimentos("pechuga de pollo", limite=1))["items"][0]
            arroz = (await tools.buscar_alimentos("arroz", limite=1))["items"][0]
            key = tools.bot.current_meal_key()
            docs = [{"user_id": "test_agent_tools", "fecha": f"2099-03-0{i}",
                     "comidas": {key: {"alimentos": [
                         {"alimento_id": pollo["id"], "cantidad_g": 100},
                         {"alimento_id": arroz["id"], "cantidad_g": 100}]}}}
                    for i in (1, 2)]
            await db.diets.insert_many(docs)
            tools.bot.state.setdefault("avoided_keywords", []).append("pollo")
            try:
                ops = await tools._menus_del_historial(
                    tools.bot.get_remaining_macros(), tools._momento_actual(),
                    n=2, juicios={"n": 0})
                assert all(all("pollo" not in i["nombre"].lower() for i in o["items"])
                           for o in ops), "volvió un alimento que el cliente evita hoy"
            finally:
                await db.diets.delete_many({"user_id": "test_agent_tools",
                                            "fecha": {"$in": ["2099-03-01", "2099-03-02"]}})
        correr(t())


# ------------------------------------------------------------ revisar / editar / aplicar
class TestBorradores:
    def test_revisar_detecta_marca_no_pedida(self):
        async def t():
            tools = await _tools()
            r = await tools.componer_menu(n=1)
            b = r["borradores"][0]
            b["filtros"]["generico"] = True     # forzamos la condición
            con_marca = next((i for i in b["items"] if i["es_marca"]), None)
            rev = await tools.revisar_borrador(b["id"])
            if con_marca:
                assert any(p["tipo"] == "marca_no_pedida" for p in rev["problemas"])
            else:
                assert all(p["tipo"] != "marca_no_pedida" for p in rev["problemas"])
        correr(t())

    def test_editar_sustituye_y_recuadra(self):
        async def t():
            tools = await _tools()
            r = await tools.componer_menu(n=1)
            b = r["borradores"][0]
            viejo = b["items"][0]
            alt = await tools.buscar_alimentos(para_macro="P", limite=3)
            nuevo = next(i for i in alt["items"] if i["id"] != viejo["id"])
            r2 = await tools.editar_borrador(b["id"], [
                {"op": "sustituir", "item_id": viejo["id"], "por_id": nuevo["id"]}])
            assert r2["ok"], r2.get("error")
            ids = {i["id"] for i in r2["borrador"]["items"]}
            assert nuevo["id"] in ids and viejo["id"] not in ids
        correr(t())

    def test_aplicar_bloquea_con_problemas(self):
        async def t():
            tools = await _tools()
            r = await tools.componer_menu(n=1)
            b = r["borradores"][0]
            # Provocar un problema comprobable: desvío enorme. Se toca `macros_totales`,
            # que es de donde `revisar_borrador` saca el desvío; escribir `desvio` a mano
            # no valía, porque el revisor lo recalcula y machaca lo escrito, así que el
            # test solo pasaba cuando el menú ya salía torcido de fábrica.
            b["macros_totales"] = dict(b["macros_totales"],
                                       P=float(b["macros_totales"]["P"]) + 50)
            res = await tools.aplicar_borrador(b["id"])
            assert not res["ok"] and res.get("bloqueado_por")
            assert not tools.ver_estado()["alimentos"]   # nada entró en la comida
        correr(t())

    def test_aplicar_vuelca_la_comida(self):
        async def t():
            tools = await _tools()
            r = await tools.componer_menu(n=1)
            b = r["borradores"][0]
            rev = await tools.revisar_borrador(b["id"])
            res = await tools.aplicar_borrador(b["id"], forzar=not rev["ok"])
            assert res["ok"], res
            comida = tools.ver_estado()
            assert len(comida["alimentos"]) == len(b["items"])
        correr(t())


# ------------------------------------------------------------ editar_comida
class TestEditarComida:
    def test_quitar_y_anadir_en_una_llamada(self):
        async def t():
            tools = await _tools()
            await tools.editar_comida([{"op": "añadir", "texto": "arroz", "cantidad": 80, "unidad": "g"}])
            r = await tools.editar_comida([
                {"op": "quitar", "nombre": "arroz"},
                {"op": "añadir", "texto": "patata", "cantidad": 150, "unidad": "g"},
            ])
            assert r["ok"], r["fallos"]
            nombres = " ".join(a["nombre"].lower() for a in r["comida"]["alimentos"])
            assert "patata" in nombres and "arroz" not in nombres
        correr(t())

    def test_ajustar_fija_cantidad(self):
        async def t():
            tools = await _tools()
            await tools.editar_comida([{"op": "añadir", "texto": "almendras", "cantidad": 40, "unidad": "g"}])
            r = await tools.editar_comida([{"op": "ajustar", "nombre": "almendras", "a": 20, "unidad": "g"}])
            assert r["ok"], r["fallos"]
            alm = next(a for a in r["comida"]["alimentos"] if "almendra" in a["nombre"].lower())
            assert "20" in str(alm["cantidad"])
        correr(t())


# ------------------------------------------------------------ estado / navegar / explicar / configurar
class TestEstadoYNavegacion:
    def test_estado_lleva_el_momento(self):
        """El momento sigue viajando en el estado, pero YA NO dentro del nombre de la comida.

        Este test exigía «desayuno» dentro de `est["comida"]` porque hasta el 09-08
        `describe_comida()` devolvía literalmente «Comida 1 (desayuno)». Ese paréntesis era
        el origen del «(desayuno)» del punto 10.5: cuando el asistente lo escribía no se
        inventaba nada, copiaba nuestro propio formato, y por eso los dos intentos de
        corregirlo por prompt fallaron (uno lo empeoró: prohibir la palabra la subió a 6 de
        cada 6). Decisión de Francisco del 09-08: las comidas se nombran por la que
        corresponde, así que de las herramientas sale «Comida 1» y punto.

        Lo que sí tiene que seguir llegando -- y es lo que se vigila aquí ahora -- es el
        momento como DATO, porque es quien decide qué alimento es típico de cada comida y va
        al contexto del agente en la línea del día («Comida 1 (desayuno, vacía) <- actual»).
        No se comprueba dentro de `ver_estado("comida")` a propósito: ese diccionario vuelve
        al modelo como resultado de herramienta, y volver a meter ahí la palabra es regalarle
        otra vez el paréntesis que tanto costó localizar.
        """
        async def t():
            tools = await _tools()
            est = tools.ver_estado("comida")
            assert est["comida"] == "Comida 1", est["comida"]
            assert not any(h in est["comida"].lower()
                           for h in ("desayuno", "almuerzo", "merienda", "cena")), est["comida"]
            dia = tools.ver_estado("dia")
            actual = next(c for c in dia["comidas"] if c["es_actual"])
            assert actual["momento"] == "desayuno", actual
        correr(t())

    def test_navegar_y_volver(self):
        async def t():
            tools = await _tools()
            r = tools.navegar("2")
            assert r["ok"] and "Comida 2" in r["comida"]["comida"]
            r2 = tools.navegar("post")
            assert r2["ok"] and "Post" in r2["comida"]["comida"]
        correr(t())

    def test_navegar_a_comida_inexistente(self):
        async def t():
            tools = await _tools()
            r = tools.navegar("9")
            assert not r["ok"] and "no encuentro" in r["error"]
        correr(t())

    def test_guardar_vacia_no_deja(self):
        async def t():
            tools = await _tools()
            r = tools.guardar_comida()
            assert not r["ok"]
        correr(t())

    def test_explicar_arroz(self):
        async def t():
            tools = await _tools()
            r = await tools.explicar("arroz blanco")
            assert r["ok"]
            assert r["cuenta_en_calma"]["hidratos"] is True
            assert r["cuenta_en_calma"]["proteína"] is False   # la regla CALMA de siempre
        correr(t())

    def test_configurar_cambia_a_descanso_3_comidas(self):
        async def t():
            tools = await _tools()
            r = tools.configurar_dia(tipo_dia="descanso", num_comidas=3)
            assert r["ok"]
            assert len([c for c in r["dia"]["comidas"] if c["momento"] != "peri"]) == 3
            assert r["dia"]["tipo_dia"] == "descanso"
        correr(t())
