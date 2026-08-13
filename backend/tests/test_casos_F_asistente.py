# -*- coding: utf-8 -*-
"""Seccion F ("MARCO, EL ASISTENTE", casos 38-46) de la lista de 85 casos de Jesus, 12-08-2026.

Cinco de los nueve ya los cubre el banco de casos del asistente
(`backend/_banco_casos_chatbot.py`, familia `jesus`), que corre contra el agente real y se
pasa entero cada vez que se toca el prompt:

    38 -> J4   (que NO pise lo que ya estaba montado)
    41 -> J6   (el pescado en «evitar» de la ficha)
    42 -> J8   (tres «esto no me gusta» seguidos)
    44 -> J7   (post-entreno sin batido)
    45 -> J9   (que no suelte sus instrucciones)
    39 -> J12  (lo que se enseña en la tarjeta cierra el hueco)
    43 -> J13  (en el intra, MAP + hidrato rapido)

Aqui va lo que el banco no puede probar porque no pasa por el agente:

    38 (parte)  el anuncio de «ya tienes 2 de 4» y arrancar por la tercera, que lo hace la
                ruta POST /api/chatbot/configure, no el modelo.
    39          el nucleo del caso: la herramienta entrega cada alimento YA DIMENSIONADO a
                lo que falta, con sus macros a esa cantidad (agent_tools._item_de).
    40          la presentacion al abrirlo.
    43 (parte)  el universo del intra: solo aminoacidos (41) e hidrato rapido (18).
    46          que lo volcado a Nutricion sea exactamente lo que tiene el asistente.

Lo determinista se prueba contra el motor; lo demas, por HTTP contra el backend vivo con
el cliente demo. Las dietas que se crean se borran al terminar.
"""
import asyncio
import copy
import os
import sys
from datetime import date, timedelta

import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

MONGO_URL = os.environ.get("MONGO_URL")

# Los mismos macros que usa el banco: con ellos la Comida 1 pide 40 g de proteina justos,
# que es el «faltan 40,5 g» del caso 39.
MACROS_TEST = {
    "p_entreno": 160, "h_entreno": 50, "g_entreno": 40,
    "p_peri": 35, "h_peri": 15,
    "p_descanso": 140, "h_descanso": 40, "g_descanso": 40,
}

HUECO_39 = {"P": 40.5, "H": 0.0, "G": 0.0}


def correr(coro):
    """No hay pytest-asyncio en el proyecto: cada test abre su propio bucle."""
    return asyncio.run(coro)


async def _tools(ir_a=None, tipo_dia="entrenamiento", num_comidas=4, opcion_peri="intra_post"):
    from motor.motor_asyncio import AsyncIOMotorClient
    from chatbot import NutritionChatbot
    from agent_tools import AgentTools
    db = AsyncIOMotorClient(MONGO_URL)[os.environ.get("DB_NAME", "test_database")]
    bot = NutritionChatbot("test_casos_F", db)
    bot.set_user_macros(MACROS_TEST)
    bot.configure_day(tipo_dia=tipo_dia, num_comidas=num_comidas,
                      momento_entreno=1, opcion_peri=opcion_peri)
    tools = await AgentTools.crear(bot)
    if ir_a:
        tools.navegar(ir_a)
    return tools


def _macros_recalculados(food: dict, cantidad_g: float) -> dict:
    """Lo que aporta ese alimento a esa cantidad, con el motor de la calculadora."""
    from calma_suggest import aplicar_regla_macros, macros_at
    a = copy.deepcopy(food)
    aplicar_regla_macros(a)
    racion = float(a.get("racion") or 100) or 100.0
    cant = (cantidad_g / racion) if a.get("unidades") else cantidad_g
    m = macros_at(a, cant)
    return {"P": round(m["proteinas"], 1), "H": round(m["hidratos"], 1),
            "G": round(m["grasas"], 1)}


def _categorias(food: dict) -> list:
    return [c.strip() for c in str(food.get("categorias") or "").split("|") if c.strip()]


def _es_de_categoria(food: dict, prefijo: str) -> bool:
    return any(c == prefijo or c.startswith(prefijo + ".") for c in _categorias(food))


sin_mongo = pytest.mark.skipif(not MONGO_URL, reason="sin MONGO_URL: test de integracion")


# ======================================================================= caso 39
@sin_mongo
class TestCaso39LasOpcionesCierranLoQueFalta:
    """39 [CRITICO]. Faltan 40,5 g de proteina: todas las opciones los cierran, y ninguna
    enseña el numero por 100 g en vez de lo que aporta la cantidad propuesta."""

    def test_cada_opcion_aporta_los_405_g_de_proteina_que_faltan(self):
        async def t():
            tools = await _tools()
            # `hueco` es el agujero contra el que se dimensiona. Se fija a mano para probar
            # el enunciado tal cual (40,5 g de proteina y nada mas).
            r = await tools.buscar_alimentos(para_macro="P", hueco=dict(HUECO_39), limite=8)
            assert r["items"], r.get("sin_resultados_porque")
            # Margen del 20 %: el motor topa las cantidades a lo que una persona se pone en
            # el plato (una lata de atun no se parte por la mitad), asi que clavar los 40,5
            # no siempre se puede. Lo que no vale es ofrecer algo que aporte 5 g.
            flojas = [f"{i['nombre']} ({i['cantidad_display']}): {i['macros']['P']} g de P"
                      for i in r["items"]
                      if not 0.8 * HUECO_39["P"] <= i["macros"]["P"] <= 1.2 * HUECO_39["P"]]
            assert not flojas, f"opciones que no cierran los 40,5 g: {flojas}"
        correr(t())

    def test_los_macros_son_los_de_la_cantidad_propuesta_no_los_de_100_g(self):
        async def t():
            tools = await _tools()
            r = await tools.buscar_alimentos(para_macro="P", hueco=dict(HUECO_39), limite=8)
            assert r["items"], r.get("sin_resultados_porque")
            for it in r["items"]:
                food = tools.foods[it["id"]]
                esperados = _macros_recalculados(food, it["cantidad_g"])
                assert it["macros"] == esperados, (
                    f"{it['nombre']} a {it['cantidad_display']}: enseña {it['macros']} "
                    f"y a esa cantidad aporta {esperados}")
                # Y el contraste explicito del enunciado: si la cantidad no son 100 g, el
                # numero enseñado no puede ser el de la tabla por 100 g.
                por_100 = round(float(food.get("proteinas") or 0), 1)
                if abs(it["cantidad_g"] - 100) > 5 and por_100 > 0 and esperados["P"] != por_100:
                    assert it["macros"]["P"] != por_100, (
                        f"{it['nombre']}: enseña {por_100} g de P, que es el valor por 100 g, "
                        f"y la cantidad propuesta son {it['cantidad_display']}")
        correr(t())


# ======================================================================= caso 43
@sin_mongo
class TestCaso43ElIntra:
    """43. Dia con perientreno, al llegar al intra: MAP con hidrato de asimilacion rapida.

    La parte de «ofrece alternativa si no cuadra» la decide el modelo y va en el banco (J13).
    Aqui se prueba lo que el modelo no puede saltarse: lo que hay dentro del intra.
    """

    def test_en_el_intra_solo_entran_aminoacidos_e_hidrato_rapido(self):
        async def t():
            tools = await _tools(ir_a="intra")
            universo = tools._universo()
            assert universo, "el intra se quedo sin universo de alimentos"
            fuera = [f["nombre"] for f in universo
                     if not (_es_de_categoria(f, "41") or _es_de_categoria(f, "18"))]
            assert not fuera, f"en el intra no pinta nada: {fuera[:5]}"
        correr(t())

    def test_lo_que_ofrece_en_el_intra_lleva_map_y_lleva_hidrato_rapido(self):
        async def t():
            tools = await _tools(ir_a="intra")
            r = await tools.buscar_alimentos(limite=10)
            assert r["items"], r.get("sin_resultados_porque")
            fichas = [tools.foods[i["id"]] for i in r["items"]]
            assert any(_es_de_categoria(f, "41") for f in fichas), \
                f"ni un aminoacido (MAP) entre lo ofrecido: {[f['nombre'] for f in fichas]}"
            assert any(_es_de_categoria(f, "18") for f in fichas), \
                f"ni un hidrato rapido entre lo ofrecido: {[f['nombre'] for f in fichas]}"
        correr(t())


# ============================================================ HTTP: casos 38, 40 y 46
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api"


def _alimento(cabeceras, texto):
    """Una ficha del catalogo por su nombre, para montar dietas de prueba."""
    r = requests.get(f"{API}/calculator/foods", params={"search": texto, "limit": 1},
                     headers=cabeceras, timeout=30)
    assert r.status_code == 200, r.text
    fichas = r.json()
    assert fichas, f"no hay ningun alimento que se llame '{texto}'"
    return fichas[0]


def _item_de_dieta(ficha, cantidad_g):
    return {"alimento_id": ficha["id"], "nombre": ficha["nombre"], "cantidad_g": cantidad_g,
            "categorias": ficha.get("categorias"), "racion": ficha.get("racion"),
            "unidades": ficha.get("unidades", False)}


def _arrancar(cabeceras, fecha, **config):
    """/start + /configure, que es como abre el asistente el front. Devuelve las dos."""
    r = requests.post(f"{API}/chatbot/start", headers=cabeceras, timeout=60)
    assert r.status_code == 200, r.text
    arranque = r.json()
    cfg = {"tipo_dia": "entrenamiento", "num_comidas": 4, "momento_entreno": 1,
           "opcion_peri": "sin_peri", "fecha": fecha}
    cfg.update(config)
    r2 = requests.post(f"{API}/chatbot/configure",
                       params={"session_id": arranque["session_id"]},
                       headers=cabeceras, json=cfg, timeout=120)
    assert r2.status_code == 200, r2.text
    return arranque, r2.json()


@pytest.fixture
def fecha_libre(cabeceras_cliente):
    """Un dia futuro del cliente demo, vacio al empezar y borrado al terminar."""
    fecha = (date.today() + timedelta(days=40)).isoformat()
    requests.delete(f"{API}/diets/{fecha}", headers=cabeceras_cliente, timeout=30)
    yield fecha
    requests.delete(f"{API}/diets/{fecha}", headers=cabeceras_cliente, timeout=30)


@pytest.fixture
def dia_con_dos_comidas(cabeceras_cliente, fecha_libre):
    """El dia del caso 38: las comidas 1 y 2 ya montadas en Nutricion."""
    pollo = _alimento(cabeceras_cliente, "Pechuga de pollo")
    arroz = _alimento(cabeceras_cliente, "Arroz blanco")
    cuerpo = {
        "fecha": fecha_libre,
        "tipo_dia": "entrenamiento",
        "num_comidas": 4,
        "momento_entreno": 1,
        "opcion_peri": "sin_peri",
        "comidas": {
            "C1": {"alimentos": [_item_de_dieta(pollo, 150), _item_de_dieta(arroz, 100)]},
            "C2": {"alimentos": [_item_de_dieta(pollo, 120), _item_de_dieta(arroz, 80)]},
        },
    }
    r = requests.post(f"{API}/diets", headers=cabeceras_cliente, json=cuerpo, timeout=30)
    assert r.status_code == 200, r.text
    return fecha_libre


@pytest.mark.usefixtures("api_disponible")
class TestCaso38AbrirConTrabajoHecho:
    """38 [CRITICO]. Con dos comidas montadas: lo dice y sigue por la tercera.

    Que no las PISE lo prueba el banco (J4), que habla con el agente. Lo de aqui es lo que
    pasa al abrirlo, que no depende del modelo: lo escribe POST /api/chatbot/configure.
    """

    def test_anuncia_cuantas_comidas_lleva_hechas(self, cabeceras_cliente, dia_con_dos_comidas):
        _, cfg = _arrancar(cabeceras_cliente, dia_con_dos_comidas)
        mensaje = cfg["mensaje"].lower()
        assert "2 de 4 comidas" in mensaje, f"no dice por donde va: {cfg['mensaje']!r}"
        assert cfg["day_overview"]["completas"] == 2, cfg["day_overview"]

    def test_sigue_por_la_tercera_y_no_por_la_primera(self, cabeceras_cliente, dia_con_dos_comidas):
        _, cfg = _arrancar(cabeceras_cliente, dia_con_dos_comidas)
        assert cfg["comida_actual"] == 3, \
            f"arranca en la comida {cfg['comida_actual']} teniendo hechas la 1 y la 2"
        assert not cfg["alimentos"], f"la comida 3 no estaba vacia: {cfg['alimentos']}"

    def test_lo_que_ya_estaba_montado_sigue_estando(self, cabeceras_cliente, dia_con_dos_comidas):
        arranque, _ = _arrancar(cabeceras_cliente, dia_con_dos_comidas)
        r = requests.get(f"{API}/chatbot/summary",
                         params={"session_id": arranque["session_id"]},
                         headers=cabeceras_cliente, timeout=60)
        assert r.status_code == 200, r.text
        por_clave = {c["key"]: c for c in r.json()["comidas"]}
        assert len(por_clave["C1"]["alimentos"]) == 2, por_clave["C1"]
        assert len(por_clave["C2"]["alimentos"]) == 2, por_clave["C2"]
        # Y con macros de verdad: leidos a cero es como si no estuvieran (el fallo del 12-08).
        assert por_clave["C1"]["macros"]["P"] > 0, por_clave["C1"]["macros"]


@pytest.mark.usefixtures("api_disponible")
class TestCaso40LaPresentacion:
    """40. La primera vez se presenta; la segunda no repite la presentacion."""

    def test_al_abrirlo_se_presenta(self, cabeceras_cliente):
        # Saluda y dice QUIEN es. Se pedia la palabra «asistente» porque era lo que decia
        # entonces; desde que existe el saludo de Marco se presenta por su nombre, que es
        # justo lo que pedia el caso siguiente. Francisco, 13-08: «la buena es la de Marco».
        r = requests.post(f"{API}/chatbot/start", headers=cabeceras_cliente, timeout=60)
        assert r.status_code == 200, r.text
        mensaje = (r.json().get("message") or "").lower()
        assert "hola" in mensaje and "marco" in mensaje, \
            f"la primera pantalla no presenta a nadie: {mensaje!r}"

    def test_se_presenta_con_su_nombre(self, cabeceras_cliente):
        # Jesus llama a la seccion «MARCO, EL ASISTENTE» y pide «el saludo de Marco»: el
        # asistente tiene nombre en su metodo. Ya lo tiene tambien en la app.
        r = requests.post(f"{API}/chatbot/start", headers=cabeceras_cliente, timeout=60)
        mensaje = (r.json().get("message") or "").lower()
        assert "marco" in mensaje, f"el asistente no se presenta por su nombre: {mensaje!r}"

    def test_no_vuelve_a_presentarse_al_configurar_el_dia(self, cabeceras_cliente, fecha_libre):
        _, cfg = _arrancar(cabeceras_cliente, fecha_libre)
        assert "soy tu asistente" not in cfg["mensaje"].lower(), \
            f"repite la presentacion en el segundo mensaje: {cfg['mensaje']!r}"


@pytest.mark.usefixtures("api_disponible")
class TestCaso46LoVolcadoEsLoQueSeVe:
    """46 [CRITICO]. Terminar el dia con el asistente: lo guardado coincide EXACTAMENTE
    con lo que se ve en Nutricion."""

    @staticmethod
    def _volcar(cabeceras, session_id, fecha):
        r = requests.post(f"{API}/chatbot/save-to-diet",
                          params={"session_id": session_id, "fecha": fecha, "overwrite": True},
                          headers=cabeceras, timeout=60)
        assert r.status_code == 200, r.text
        assert not r.json().get("needs_confirmation"), r.json()
        return r.json()

    @staticmethod
    def _dieta(cabeceras, fecha):
        r = requests.get(f"{API}/diets/{fecha}", headers=cabeceras, timeout=30)
        assert r.status_code == 200, r.text
        return r.json()

    @staticmethod
    def _resumen(cabeceras, session_id):
        r = requests.get(f"{API}/chatbot/summary", params={"session_id": session_id},
                         headers=cabeceras, timeout=60)
        assert r.status_code == 200, r.text
        return r.json()

    def test_lo_que_monta_el_asistente_llega_igual_a_nutricion(self, cabeceras_cliente, fecha_libre):
        arranque, _ = _arrancar(cabeceras_cliente, fecha_libre)
        sid = arranque["session_id"]
        r = requests.post(f"{API}/chatbot/message", headers=cabeceras_cliente,
                          json={"session_id": sid,
                                "message": "ponme 150 g de pechuga de pollo y 80 g de arroz"},
                          timeout=180)
        assert r.status_code == 200, r.text

        resumen = self._resumen(cabeceras_cliente, sid)
        montado = {c["key"]: c["alimentos"] for c in resumen["comidas"] if c["alimentos"]}
        assert montado, f"el asistente no monto nada: {r.json()['response'].get('message')}"

        self._volcar(cabeceras_cliente, sid, fecha_libre)
        comidas = self._dieta(cabeceras_cliente, fecha_libre).get("comidas") or {}

        assert set(comidas) == set(montado), \
            f"comidas volcadas {sorted(comidas)} frente a las montadas {sorted(montado)}"
        for clave, alimentos in montado.items():
            en_dieta = comidas[clave]["alimentos"]
            visto = [(a["nombre"], round(float(a.get("cantidad_g") or 0), 1),
                      {k: round(float((a.get("macros_efectivos") or {}).get(k) or 0), 1)
                       for k in ("P", "H", "G")})
                     for a in en_dieta]
            esperado = [(a["nombre"], round(float(a.get("cantidad_g") or 0), 1),
                         {k: round(float((a.get("macros") or {}).get(k) or 0), 1)
                          for k in ("P", "H", "G")})
                        for a in alimentos]
            assert visto == esperado, f"{clave}: en Nutricion {visto}, en el asistente {esperado}"

    def test_lo_que_venia_de_nutricion_vuelve_entero(self, cabeceras_cliente, dia_con_dos_comidas):
        # El caso de verdad de «terminar el dia con el»: se abre con las comidas 1 y 2 ya
        # hechas, se acaba con el asistente y se vuelca. Lo que se trajo de Nutricion tiene
        # que volver como estaba, con su alimento_id: sin el, el alimento pierde su ficha y
        # la pantalla se queda sin foto, sin unidades y sin los macros de la etiqueta.
        arranque, _ = _arrancar(cabeceras_cliente, dia_con_dos_comidas)
        sid = arranque["session_id"]
        antes = self._dieta(cabeceras_cliente, dia_con_dos_comidas)["comidas"]

        self._volcar(cabeceras_cliente, sid, dia_con_dos_comidas)
        despues = self._dieta(cabeceras_cliente, dia_con_dos_comidas)["comidas"]

        for clave in ("C1", "C2"):
            ids_antes = [a.get("alimento_id") for a in antes[clave]["alimentos"]]
            ids_despues = [a.get("alimento_id") for a in despues[clave]["alimentos"]]
            assert ids_despues == ids_antes, \
                f"{clave}: los alimentos han perdido su ficha ({ids_despues} en vez de {ids_antes})"
            g_antes = [a.get("cantidad_g") for a in antes[clave]["alimentos"]]
            g_despues = [a.get("cantidad_g") for a in despues[clave]["alimentos"]]
            assert g_despues == g_antes, f"{clave}: cantidades {g_despues} en vez de {g_antes}"
