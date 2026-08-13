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


async def _tools(num_comidas=4, ir_a=None, tipo_dia="entrenamiento"):
    from motor.motor_asyncio import AsyncIOMotorClient
    from chatbot import NutritionChatbot
    from agent_tools import AgentTools
    db = AsyncIOMotorClient(MONGO_URL)[os.environ.get("DB_NAME", "test_database")]
    bot = NutritionChatbot("test_agent_tools", db)
    bot.configure_day(tipo_dia=tipo_dia, num_comidas=num_comidas,
                      momento_entreno=1, opcion_peri="intra_post")
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
        async def t():
            tools = await _tools()
            r = await tools.componer_menu(generico=True, n=1)
            assert r["borradores"]
            assert all(not i["es_marca"] for i in r["borradores"][0]["items"])
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
