# -*- coding: utf-8 -*-
"""Seccion E de la lista de 85 casos de Jesus: EL MOTOR DE MACROS (casos 31-37).

De donde sale la lista: Jesus, el dueno del metodo, entrego el 12-08-2026 una bateria de 85
casos de prueba repartida en doce secciones. Esta es la E, y de las doce es la que el marca
como innegociable: «Aqui esta el metodo. Si algo de esto falla, falla el producto entero».

Por que este bloque es el critico: todo lo demas de la app (el buscador, el asistente, el
generador de menus, el PDF, el panel del entrenador) se limita a ensenar lo que este motor
decide. Si el motor cuenta mal la proteina de un arroz, no falla una pantalla: falla el
numero que el cliente usa para comer, y falla en las doce pantallas a la vez, en silencio y
durante meses. Por eso aqui se prueba EL MOTOR y no la pantalla siempre que se pueda.

Como esta escrito:

  - Las fichas son copias LITERALES de db.foods (produccion, 12-08-2026). Inventarse los
    macros de unas almendras seria probar mi suposicion, no el metodo.
  - Los casos 31-34 van contra `calma_suggest.macros_efectivos`, la funcion canonica: lo que
    CUENTA un alimento a una cantidad. Sin Mongo y sin HTTP.
  - Donde el caso habla de lo que ve el cliente (la linea del alimento, el interruptor) se
    prueba tambien el camino real: el asistente (`agent_tools._frase_que_cuenta`), el
    catalogo del buscador (`/api/calculator/foods-listado`) o el codigo de la pantalla.
  - Lo que solo se puede ver con los ojos va marcado con skip y su motivo. No se finge.

Lo que sale en ROJO esta explicado en el docstring de cada test. Un rojo aqui no es un test
mal escrito: es que el metodo no se esta aplicando por ese camino.
"""
import base64
import os
import sys
import time

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _RAIZ)

import pytest  # noqa: E402
import requests  # noqa: E402

from conftest import (API, ADMIN_EMAIL, ADMIN_PASSWORD,  # noqa: E402
                      CLIENT_EMAIL, CLIENT_PASSWORD)
from agent_tools import AgentTools  # noqa: E402
from calibracion_dia import macros_item_por_acumulado  # noqa: E402
from calma_suggest import cantidad_minima, macros_efectivos, macros_reales  # noqa: E402
from chatbot import NutritionChatbot  # noqa: E402
from redondeo_salida import paso_en_gramos, redondear_cantidad  # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────
# FICHAS REALES. Copiadas de db.foods (jg12_restored) el 12-08-2026, campo a campo.
# Se pegan aqui para que estos tests corran sin base de datos: el motor es puro y no
# tiene por que depender de que Mongo este vivo. Si alguien cambia una ficha en el
# catalogo y estos numeros dejan de cuadrar, es que el catalogo cambio, y eso tambien
# hay que enterarse.
# ─────────────────────────────────────────────────────────────────────────────
ARROZ = {"id": 1657, "nombre": "Arroz blanco", "categorias": "21.1",
         "proteinas": 7, "hidratos": 80, "grasas": 1, "racion": 100, "unidades": False}
ALMENDRAS = {"id": 2018, "nombre": "Almendras", "categorias": "17.2.1 | YA | 42 | 38.2",
             "proteinas": 23, "hidratos": 4.8, "grasas": 53.1, "racion": 100, "unidades": False}
CALABACIN = {"id": 110, "nombre": "Calabacín", "categorias": "13.1",
             "proteinas": 1.2, "hidratos": 3.1, "grasas": 0.3, "racion": 100, "unidades": False}
LECHE = {"id": 358, "nombre": "Leche entera", "categorias": "5.1 | YA | 25",
         "proteinas": 3, "hidratos": 5, "grasas": 3, "racion": 100, "unidades": False}
PAN = {"id": 432, "nombre": "Pan de barra", "categorias": "8.1 | YA | 25 | SNA",
       "proteinas": 9, "hidratos": 50, "grasas": 0, "racion": 100, "unidades": False}
LECHUGA = {"id": 363, "nombre": "Lechuga", "categorias": "13.1 | YA",
           "proteinas": 0, "hidratos": 0, "grasas": 0, "racion": 100, "unidades": False}

MACROS_BOT = {"p_entreno": 160, "h_entreno": 120, "g_entreno": 40,
              "p_peri": 35, "h_peri": 15,
              "p_descanso": 140, "h_descanso": 40, "g_descanso": 40}


class _SoloLaFrase:
    """Lo unico que necesita `_frase_que_cuenta` es el bot, no el agente entero (que pide
    Mongo, embeddings y clave de OpenAI). Se toma prestado de `AgentTools` a proposito: asi
    se prueba el codigo que corre en produccion, no una copia que se quede vieja."""

    def __init__(self):
        self.bot = NutritionChatbot("test_casos_E", MACROS_BOT)


def frase(food: dict) -> str:
    """La frase con la que el asistente le dice al cliente que le cuenta de un alimento."""
    return AgentTools._frase_que_cuenta(_SoloLaFrase(), food)


#: Un PNG de un pixel. Desde el punto 161 del 27-08 las dos fotos son obligatorias para pedir
#: un alimento, asi que los casos que mandan una solicitud tienen que adjuntar algo. El
#: servidor comprueba el tipo y el tamano, no lo que se ve.
_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")


def pedir(metodo: str, ruta: str, **kw):
    """Una llamada a la API que aguanta que el servidor de desarrollo se reinicie.

    En dev el backend corre con `watchfiles` (RELOAD=1 en el .env): cualquiera que toque un
    .py del backend reinicia el proceso entero, y una peticion que caiga justo en ese hueco
    se va con «connection refused». Eso no es un fallo del metodo, y hacer que estos tests
    -- que son los que Jesus mira -- salgan en rojo por eso seria enterrar lo que importa.
    Se reintenta hasta que vuelva, y si no vuelve se dice claramente que fue el servidor.
    """
    kw.setdefault("timeout", 60)
    ultimo = None
    for _ in range(8):     # ~24 s de margen: de sobra para un reinicio de watchfiles
        try:
            return requests.request(metodo, f"{API}{ruta}", **kw)
        except requests.exceptions.ConnectionError as e:
            ultimo = e
            time.sleep(3)
    raise AssertionError(f"El backend no respondio a {metodo} {ruta}: {ultimo}")


def _entrar(email: str, password: str) -> dict:
    r = pedir("POST", "/auth/login", json={"email": email, "password": password})
    if r.status_code != 200:
        pytest.skip(f"No se pudo entrar como {email} (respondio {r.status_code})")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# Estos dos tapan a los del conftest a proposito. Los de alli comprueban el /health una sola
# vez por sesion y, si el servidor estaba justo reiniciandose, se saltan TODAS las pruebas
# que hablan con la API. Un bloque critico que se salta entero sin que se note es peor que
# uno en rojo: aqui se reintenta la entrada y solo se rinde si el backend no esta de verdad.
@pytest.fixture(scope="module")
def cabeceras_cliente():
    return _entrar(CLIENT_EMAIL, CLIENT_PASSWORD)


@pytest.fixture(scope="module")
def cabeceras_admin():
    return _entrar(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def catalogo(cabeceras_cliente):
    """El catalogo del Buscador, pedido UNA vez: son 3.200 alimentos con la regla ya
    aplicada, y no hace falta traerlo tres veces para mirar tres fichas."""
    r = pedir("GET", "/calculator/foods-listado", headers=cabeceras_cliente, timeout=180)
    assert r.status_code == 200, r.text[:200]
    return {f.get("id"): f for f in r.json()}


_FRONT = os.path.join(os.path.dirname(_RAIZ), "frontend", "src")


def fuente(ruta_relativa: str) -> str:
    """El codigo de una pantalla, para los casos que hablan de lo que se VE.

    No es un test de interfaz de verdad, pero contesta en blanco y negro a la unica pregunta
    que hace falta: ese dato, ¿llega a pintarse o se queda en el estado?
    """
    ruta = os.path.join(_FRONT, *ruta_relativa.split("/"))
    if not os.path.exists(ruta):
        pytest.skip(f"No esta el frontend en {ruta}")
    with open(ruta, encoding="utf-8") as fh:
        return fh.read()


# ═════════════════════════════════════════════════════════════════════════════
# CASO 31 [CRITICO] · Meter arroz en una comida.
# Espero: cuentan solo los hidratos. Su proteina no cuenta y la app lo dice en la propia
# linea del alimento.
# ═════════════════════════════════════════════════════════════════════════════
class TestCaso31ElArroz:

    def test_del_arroz_solo_cuentan_los_hidratos(self):
        """150 g de arroz blanco: 120 g de hidratos y nada mas.

        El arroz es categoria 21 (pasta, arroz y legumbres). La regla del metodo pone su
        proteina a cero por categoria -- la proteina de un cereal es incidental, no es la
        que el cliente cuenta como proteina -- y su grasa por el filtro del 25 %.
        """
        assert macros_efectivos(ARROZ, 150) == {"P": 0.0, "H": 120.0, "G": 0.0}

    def test_la_proteina_del_arroz_esta_en_la_etiqueta_pero_no_suma(self):
        """7 g por 100 g siguen estando en el paquete: lo que no hacen es contar."""
        assert macros_reales(ARROZ, 150)["P"] == 10.5
        assert macros_efectivos(ARROZ, 150)["P"] == 0.0

    def test_no_cuenta_a_ninguna_cantidad(self):
        """No es un efecto del redondeo ni de una cantidad concreta: no cuenta nunca."""
        for cantidad in (25, 50, 100, 173, 300):
            assert macros_efectivos(ARROZ, cantidad)["P"] == 0.0
            assert macros_efectivos(ARROZ, cantidad)["H"] > 0

    def test_el_asistente_lo_dice_con_palabras(self):
        """Segunda mitad del caso: la app tiene que DECIRLO, no dejar un 0 que interpretar."""
        assert frase(ARROZ) == "te cuenta los hidratos; la proteína y la grasa no"

    def test_el_buscador_lo_dice_en_la_linea_del_alimento(self, catalogo):
        """En el Buscador de alimentos si sale, debajo del nombre (`que_te_cuenta`).

        LA REDACCION CAMBIO EL 27-08 (punto 147). Decia «Te cuenta hidratos. Ni su proteína
        ni su grasa te cuentan.»; ahora el «solo» dice lo mismo en tres palabras y se ahorra
        la coletilla, que era una linea por alimento. El arroz lleva mas de un macro y solo
        le cuenta uno, asi que es el caso del «solo».
        """
        ficha = catalogo.get(ARROZ["id"])
        assert ficha, "El arroz blanco (id 1657) ya no esta en el catalogo"
        assert ficha["que_te_cuenta"] == "Te cuenta solo el hidrato"

    def test_la_linea_de_nutricion_tambien_lo_dice(self):
        """La linea del alimento de Nutricion dice que cuenta, por dos vias.

        Este test nacio FALLANDO A PROPOSITO (12-08): MealCard no pintaba `que_cuenta` y el
        cliente veia «0 g proteinas» sin saber si el arroz no lleva o no le cuenta. Desde
        entonces la pantalla lo resolvio por otro camino y el test seguia buscando el
        literal viejo (actualizado el 3-09): `macrosLine` pinta SOLO los macros efectivos
        -- el anulado desaparece de la linea, y sin ninguno dice «sin macros» --, y
        `ContadorFamilia` pone «Su proteina no te cuenta» a los calibrados que no pasan el
        tercio (punto 133). Comprobado en pantalla el 3-09: el arroz dice «30 g hidratos» a
        secas y las nueces llevan su frase debajo. Aqui se guarda que no se pierda.
        """
        mealcard = fuente("components/nutrition/MealCard.jsx")
        # El texto pasó de «sin macros» a «No aporta macros» el 3-09 (Jesús, minuto 11:59 de
        # la reunión con Gonzalo). Lo que este test cuida sigue siendo lo mismo: que la línea
        # distinga «no lleva» de «no cuenta», no la redacción exacta.
        assert "macrosLine" in mealcard and "No aporta macros" in mealcard, (
            "La linea del alimento ya no pinta solo los macros que cuentan (macrosLine): "
            "el cliente vuelve a ver ceros sin saber si son de no llevar o de no contar")
        assert "ContadorFamilia" in mealcard, (
            "La linea del alimento ya no lleva el contador de familia: los calibrados se "
            "quedan sin su «Su proteina no te cuenta»")
        contador = fuente("components/nutrition/ContadorFamilia.jsx")
        assert "no te cuenta" in contador, (
            "ContadorFamilia ya no dice «Su proteina no te cuenta» al que no pasa el tercio")


# ═════════════════════════════════════════════════════════════════════════════
# CASO 32 [CRITICO] · Meter almendras.
# Espero: cuenta solo la grasa. Su proteina no cuenta, por la excepcion de frutos secos.
# ═════════════════════════════════════════════════════════════════════════════
class TestCaso32LasAlmendras:

    def test_de_las_almendras_solo_cuenta_la_grasa(self):
        """30 g de almendras: 15,93 g de grasa y nada mas.

        Categoria 17.2.1 (frutos secos naturales). El metodo cuenta un fruto seco por lo que
        es -- una fuente de grasa --, asi que su proteina y sus hidratos no entran.
        """
        assert macros_efectivos(ALMENDRAS, 30) == {"P": 0.0, "H": 0.0, "G": 15.93}

    def test_los_veintitres_gramos_de_proteina_siguen_en_la_etiqueta(self):
        assert macros_reales(ALMENDRAS, 30)["P"] == 6.9
        assert macros_efectivos(ALMENDRAS, 30)["P"] == 0.0

    def test_el_asistente_lo_dice_con_palabras(self):
        assert frase(ALMENDRAS) == "te cuenta la grasa; la proteína y los hidratos no"

    def test_la_proteina_tampoco_cuenta_al_calibrar_el_dia(self):
        """FALLA. Dos especificaciones de Jesus dicen cosas distintas sobre este alimento.

        Este caso 32 (12-08) dice que la proteina de las almendras NO cuenta. La calibracion
        progresiva (spec del 17-07, `calibracion_dia.py`) dice que en los frutos secos la
        proteina SI cuenta cuando supera G/3, escalonada por los gramos acumulados del dia:
        0 % hasta 20 g, 50 % entre 20 y 40, 100 % por encima de 40.

        En las almendras 23 > 53,1/3 = 17,7, asi que pasa el filtro, y 30 g caen en el tramo
        del 50 %: la calibracion les da 3,45 g de proteina.

        No es un fallo de codigo, las dos reglas estan bien implementadas: es que el camino
        por el que entra el alimento decide cuanto cuenta. Al anadirlo, `/macros-efectivos`
        dice 0 g de proteina; al recalcular el dia, `/calibrar-dia` reescribe esa misma linea
        con 3,5 g y `que_cuenta.P = true`. El numero cambia solo delante del cliente.

        Lo tiene que resolver Jesus, no yo: o el caso 32 se lee «al margen de la calibracion»,
        o la calibracion no debe aplicarse a la proteina de los frutos secos.
        """
        assert macros_item_por_acumulado(ALMENDRAS, 30, acum_fs=0)["P"] == 0.0

    def test_la_grasa_cuenta_siempre_venga_por_donde_venga(self):
        """Lo que si esta de acuerdo en los dos caminos: la grasa entera."""
        assert macros_efectivos(ALMENDRAS, 30)["G"] == 15.93
        assert macros_item_por_acumulado(ALMENDRAS, 30, acum_fs=0)["G"] == 15.93


# ═════════════════════════════════════════════════════════════════════════════
# CASO 33 [CRITICO] · Meter leche entera, que aporta los tres macros.
# Espero: cuentan los tres y se ensenan los tres. No una sola etiqueta.
# ═════════════════════════════════════════════════════════════════════════════
class TestCaso33LaLecheEntera:

    def test_cuentan_los_tres(self):
        """200 ml de leche entera: 6 P / 10 H / 6 G. Ninguno se pone a cero.

        Es el caso que impide leer el metodo como «cada alimento es de un macro». La leche
        (5.1) no pasa ninguno de los filtros de la regla, asi que va entera.
        """
        assert macros_efectivos(LECHE, 200) == {"P": 6.0, "H": 10.0, "G": 6.0}

    def test_ninguno_se_queda_a_cero(self):
        efectivos = macros_efectivos(LECHE, 200)
        assert all(efectivos[m] > 0 for m in ("P", "H", "G"))

    def test_lo_que_cuenta_y_lo_que_pone_la_etiqueta_coinciden(self):
        """Si el metodo no quita nada, las dos cifras del interruptor tienen que ser la misma."""
        assert macros_efectivos(LECHE, 200) == macros_reales(LECHE, 200)

    def test_el_asistente_no_la_etiqueta_con_un_solo_macro(self):
        assert frase(LECHE) == "cuenta los tres macros"

    def test_el_buscador_dice_que_cuentan_los_tres(self, catalogo):
        """Y vuelve a decirlo, que es lo que este caso pedia desde el principio (1-09).

        La frase es de Jesus y la marca como suya en «Todo lo validado antes del 1 de
        septiembre», punto 2.10. El 27-08 (punto 147) se cambio entera por «Te cuenta todo»
        con un motivo bueno: del huevo, «los tres» es falso, porque tiene proteina y grasa y
        no tiene hidratos.

        Lo que fallaba no era la frase, era aplicarla a todos. Medido contra el catalogo, de
        3.219 fichas hay 1.218 que llevan los tres macros y le cuentan los tres, y ahi «Te
        cuentan los tres» es exacta. Asi que se dice donde es verdad --la leche entera es el
        caso-- y donde no llega a tres se queda «Te cuenta todo», que no miente en ninguna:
        el huevo lo sigue diciendo, y la pechuga de pollo (20 P / 0 H / 0 G) tambien.
        """
        ficha = catalogo.get(LECHE["id"])
        assert ficha, "La leche entera (id 358) ya no esta en el catalogo"
        assert ficha["que_te_cuenta"] == "Te cuentan los tres"


# ═════════════════════════════════════════════════════════════════════════════
# CASO 34 [CRITICO] · Meter una verdura libre, como el calabacin.
# Espero: no pide cantidad y no suma macros. Sale como "come lo que quieras".
# ═════════════════════════════════════════════════════════════════════════════
class TestCaso34LaVerduraLibre:

    def test_el_calabacin_no_suma_nada(self):
        """Categoria 13 (verduras y hortalizas): los tres macros a cero, cueste lo que cueste.

        Ojo con el detalle: el calabacin SI lleva macros en la tabla (1,2 P / 3,1 H / 0,3 G
        por 100 g). Que no sumen es una decision del metodo, no que la ficha venga vacia.
        """
        assert macros_efectivos(CALABACIN, 200) == {"P": 0.0, "H": 0.0, "G": 0.0}
        assert macros_reales(CALABACIN, 200) == {"P": 2.4, "H": 6.2, "G": 0.6}

    def test_da_igual_cuanto_se_coma(self):
        """«Libre» quiere decir libre: 500 g siguen sumando cero."""
        for cantidad in (50, 100, 250, 500):
            assert macros_efectivos(CALABACIN, cantidad) == {"P": 0.0, "H": 0.0, "G": 0.0}

    def test_una_verdura_sin_macros_en_tabla_se_comporta_igual(self):
        """La lechuga viene ya con ceros: el resultado tiene que ser el mismo."""
        assert macros_efectivos(LECHUGA, 300) == {"P": 0.0, "H": 0.0, "G": 0.0}

    def test_el_asistente_dice_que_es_libre(self):
        assert frase(CALABACIN) == "no cuenta ningún macro (es libre)"

    def test_sale_como_come_lo_que_quieras(self, catalogo):
        """La frase literal del caso, tal y como la pinta el Buscador de alimentos.

        Desde el 27-08 la frase se parte en dos (puntos 145 y 150): «No te cuenta nada» va en
        la linea de que te cuenta, y «Come lo que quieras» ocupa el sitio del numero. Lo pone
        la pantalla, porque de un liquido dice «Bebe lo que quieras» y eso es cosa de como se
        escribe, no del motor.

        Y DESDE EL 1-09 SE LEEN COMO UNA SOLA FRASE: «No te cuenta nada: come lo que quieras»
        («Todo lo validado antes del 1 de septiembre», punto 2.10). Partidas y separadas por
        un hueco se leian como dos avisos distintos. El cambio es de la PANTALLA -- los dos
        puntos y la minuscula --; el motor sigue devolviendo «No te cuenta nada» a secas, que
        es lo que comprueba este caso.

        Y son 100 g, no los 50 de la maqueta. El punto 148 saca los minimos de CALMA, y el de
        las verduras es uno de los dos que Jesus cambio despues: video 3 del 15-08, «los
        vegetales siempre que sugiera 100 gramos, no 50 por defecto». Manda lo que decidio
        mirando la app. Ver MINIMOS_JESUS en calma_suggest.py.
        """
        ficha = catalogo.get(CALABACIN["id"])
        assert ficha, "El calabacin (id 110) ya no esta en el catalogo"
        assert ficha["que_te_cuenta"] == "No te cuenta nada"
        assert ficha["tiene_macros"] is False
        # Y su minimo sigue existiendo aunque no cuente nada (punto 150): «Desde 50 g».
        assert ficha["desde"] == "100 g"
        assert ficha["necesitas"] is None

    @pytest.mark.skip(reason="visual: hay que ver la pantalla. Lo comprobable desde aqui es "
                             "que el motor le sigue dando una cantidad minima (50 g), y que "
                             "el contador de gramos de MealCard.jsx se pinta sin mirar si el "
                             "alimento cuenta algo. O sea que la app SI pide cantidad.")
    def test_no_pide_cantidad(self):
        """Caso 34, primera mitad: «no pide cantidad»."""

    def test_aun_asi_el_motor_le_asigna_un_minimo(self):
        """El dato que hace falta para decidir el caso de arriba, ya medido.

        Un alimento libre no queda fuera del motor: sigue teniendo cantidad minima porque hay
        que escribir algo en el plato. Que eso se le ENSENE o no al cliente era la decision de
        pantalla que pedia el caso, y desde el punto 150 del 27-08 SE LE ENSENA: «Desde 100 g
        · siempre cabe».

        ERAN 50 Y SON 100, y por eso este test estaba en rojo. El 50 es el de la categoria 13
        en el mapa portado de Calma; Jesus lo subio a 100 el 15-08 viendo las sugerencias del
        chat («los vegetales siempre que sugiera 100 gramos, no 50 por defecto»), y desde
        entonces el numero bueno es el de MINIMOS_JESUS. El test se habia quedado con el
        heredado.
        """
        assert cantidad_minima(CALABACIN) == 100


# ═════════════════════════════════════════════════════════════════════════════
# CASO 35 [CRITICO] · Poner el interruptor en "Reales" con un alimento cuyos macros del
# metodo no coinciden.
# Espero: los totales cambian a los reales y se ve que ha cambiado.
# ═════════════════════════════════════════════════════════════════════════════
class TestCaso35ElInterruptorReales:

    def test_los_dos_numeros_son_distintos(self):
        """El arroz es justo el alimento del caso: 10,5 g de proteina que el metodo no cuenta."""
        assert macros_efectivos(ARROZ, 150) != macros_reales(ARROZ, 150)

    def test_reales_no_aplica_ninguna_regla_del_metodo(self):
        """Lo de la etiqueta es lo de la etiqueta, sin filtro del tercio ni regla del 25 %."""
        assert macros_reales(ARROZ, 100) == {"P": 7.0, "H": 80.0, "G": 1.0}
        assert macros_reales(ALMENDRAS, 100) == {"P": 23.0, "H": 4.8, "G": 53.1}
        assert macros_reales(PAN, 100) == {"P": 9.0, "H": 50.0, "G": 0.0}

    def test_el_total_de_la_comida_cambia(self):
        """No es un cambio por alimento: el TOTAL de la comida tiene que moverse."""
        comida = [(ARROZ, 150), (ALMENDRAS, 30), (CALABACIN, 100)]
        metodo = {m: round(sum(macros_efectivos(f, c)[m] for f, c in comida), 1)
                  for m in ("P", "H", "G")}
        reales = {m: round(sum(macros_reales(f, c)[m] for f, c in comida), 1)
                  for m in ("P", "H", "G")}
        assert metodo == {"P": 0.0, "H": 120.0, "G": 15.9}
        assert reales == {"P": 18.6, "H": 124.5, "G": 17.7}

    def test_el_backend_devuelve_los_dos_totales(self, cabeceras_cliente):
        """El camino real: `/macros-comida` da `total_efectivos` y `total_brutos` de una vez,
        para que el interruptor no tenga que recalcular nada por su cuenta."""
        r = pedir("POST", "/calculator/macros-comida", headers=cabeceras_cliente, json={
            "alimentos": [{"alimento_id": ARROZ["id"], "cantidad_g": 150},
                          {"alimento_id": ALMENDRAS["id"], "cantidad_g": 30}]})
        assert r.status_code == 200, r.text[:200]
        d = r.json()
        assert d["total_efectivos"] != d["total_brutos"]
        assert d["total_efectivos"]["P"] == 0.0
        assert d["total_brutos"]["P"] == 17.4     # 10,5 del arroz + 6,9 de las almendras

    def test_la_pantalla_no_puede_enseñar_los_de_la_etiqueta_en_silencio(self):
        """«Y se ve que ha cambiado»: los numeros de la etiqueta no pueden colarse como si
        fueran los del metodo.

        Hasta el 26-08 esto se cumplia con un aviso: la pantalla tenia un conmutador
        «Metodo / Reales» y, en reales, un renglon encima de los totales explicando que lo
        que se veia no era lo que contaba. El punto 112 del artifact del 25-08 se lleva las
        dos cosas -- «fuera, con Metodo / Reales» --, asi que ahora la garantia es mas fuerte
        que un aviso: en la lista de ingredientes ya solo hay una cifra, la del metodo.

        Los dos totales SIGUEN existiendo en el backend (el test de aqui arriba), que es lo
        que pedia el caso 35; lo que se ha retirado es la forma de verlos mezclados.
        """
        page = fuente("pages/NutritionPage.jsx")
        assert "ModoMacrosSelector" not in page and "AvisoMacrosReales" not in page, (
            "vuelve el conmutador Metodo/Reales a Nutricion (punto 112): si vuelve, tiene "
            "que volver tambien el aviso de que lo que se ve no es lo que cuenta")
        card = fuente("components/nutrition/MealCard.jsx")
        assert "macrosDeVista" not in card, (
            "la lista de ingredientes vuelve a poder pintar los macros de la etiqueta")
        assert "macros_efectivos" in card, (
            "la lista de ingredientes ha dejado de pintar los macros del metodo")


# ═════════════════════════════════════════════════════════════════════════════
# CASO 36 · Pulsar "Cuadrar" con un solo gramo de margen.
# Espero: redondea sin pasarse y sin dejarlo a medias.
# ═════════════════════════════════════════════════════════════════════════════
class TestCaso36Cuadrar:

    @pytest.mark.parametrize("pedido,esperado", [
        (101, 100),   # un gramo de mas: se baja, no se sube a 105
        (51, 50),
        (26, 25),
        (96, 95),
        (150, 150),   # ya era redondo: se queda igual
    ])
    def test_un_gramo_de_mas_baja_al_multiplo(self, pedido, esperado):
        """El redondeo es SIEMPRE a la baja. Subir haria que el alimento aportase mas de lo
        que queda de comida, que es justo lo que el motor evita: quedarse corto se absorbe
        con el resto del menu, pasarse descuadra el dia."""
        assert redondear_cantidad(ARROZ, pedido, cantidad_minima(ARROZ)) == esperado

    @pytest.mark.parametrize("cantidad", [25, 26, 40, 51, 99, 101, 173.4, 249.9])
    def test_nunca_se_pasa_de_lo_que_cabia(self, cantidad):
        assert redondear_cantidad(ARROZ, cantidad, cantidad_minima(ARROZ)) <= cantidad

    @pytest.mark.parametrize("food", [ARROZ, ALMENDRAS, PAN, CALABACIN, LECHE])
    @pytest.mark.parametrize("cantidad", [51, 76, 101, 127.3, 199.9])
    def test_no_lo_deja_a_medias(self, food, cantidad):
        """«Sin dejarlo a medias»: sale un numero redondo y mayor que cero. Nadie pesa 127,3 g
        y un alimento no puede desaparecer del plato por haberlo redondeado.

        CON UNA SALIDA, Y ES LA QUE TENIA ESTE TEST EN ROJO. Si ni bajando al multiplo de 5 se
        llega al minimo del alimento, `redondear_a_la_baja` devuelve la cantidad tal cual:
        «falsearla seria peor que tener un numero feo». El caso es el calabacin a 51 y a 76 g,
        con minimo 100.

        No es un fallo nuevo: se destapo el 15-08, cuando Jesus subio las verduras de 50 a 100
        («los vegetales siempre que sugiera 100 gramos, no 50 por defecto»). Con el minimo en
        50, los 51 g bajaban a 50 y el test pasaba; con el minimo en 100 ya no hay ningun
        multiplo por debajo que valga. Nadie ato las dos cosas y el rojo se quedo ahi.

        Lo que se comprueba es la regla entera, no media: redondo Y por encima del minimo, o
        la cantidad intacta cuando eso es imposible.
        """
        minimo = cantidad_minima(food)
        salida = redondear_cantidad(food, cantidad, minimo)
        assert salida > 0, f"{food['nombre']}: {cantidad} g se quedaron en 0"
        if cantidad < minimo:
            assert salida == cantidad, (
                f"{food['nombre']}: {cantidad} g no llegan a su minimo ({minimo} g), asi que "
                f"tienen que salir tal cual y salieron {salida}")
            return
        assert salida % 5 == 0, f"{food['nombre']}: {cantidad} g salieron a {salida}"
        assert salida >= minimo, f"{food['nombre']}: {salida} g por debajo del minimo {minimo}"

    def test_las_verduras_van_de_cincuenta_en_cincuenta(self):
        """Cada alimento tiene su paso: una verdura se come a punados, no a cucharaditas."""
        assert paso_en_gramos(CALABACIN) == 50
        assert paso_en_gramos(ARROZ) == 5
        assert redondear_cantidad(CALABACIN, 99, 50) == 50

    def test_el_boton_cuadrar_devuelve_cantidades_redondas(self, cabeceras_cliente):
        """El camino real del boton «Cuadrar» de cada comida: `/refit-diet`. Se le mandan
        cantidades feas a proposito (101, 21, 99) y tienen que volver redondas."""
        r = pedir("POST", "/calculator/refit-diet", headers=cabeceras_cliente, json={
            "fecha": "2026-08-12", "tipo_dia": "entrenamiento", "num_comidas": 4,
            "momento_entreno": 1, "opcion_peri": "intra_post",
            "comidas": {"C1": {"alimentos": [
                {"alimento_id": ARROZ["id"], "cantidad_g": 101, "nombre": "Arroz blanco"},
                {"alimento_id": ALMENDRAS["id"], "cantidad_g": 21, "nombre": "Almendras"},
                {"alimento_id": CALABACIN["id"], "cantidad_g": 99, "nombre": "Calabacín"}]}}})
        assert r.status_code == 200, r.text[:300]
        alimentos = r.json()["comidas"]["C1"]["alimentos"]
        assert len(alimentos) == 3, "Cuadrar no puede hacer desaparecer alimentos"
        for a in alimentos:
            assert a["cantidad_g"] > 0, f"{a['nombre']} se quedo en 0 g al cuadrar"
            assert a["cantidad_g"] % 5 == 0, f"{a['nombre']} salio a {a['cantidad_g']} g"

    def test_cuadrar_no_se_pasa_del_objetivo(self, cabeceras_cliente):
        """La otra mitad del caso: «sin pasarse». Se acepta el margen del metodo (4 g)."""
        from calma_suggest import MARGEN_VALIDO
        r = pedir("POST", "/calculator/refit-diet", headers=cabeceras_cliente, json={
            "fecha": "2026-08-12", "tipo_dia": "entrenamiento", "num_comidas": 4,
            "momento_entreno": 1, "opcion_peri": "intra_post",
            "comidas": {"C1": {"alimentos": [
                {"alimento_id": ARROZ["id"], "cantidad_g": 301, "nombre": "Arroz blanco"},
                {"alimento_id": ALMENDRAS["id"], "cantidad_g": 101, "nombre": "Almendras"}]}}})
        assert r.status_code == 200, r.text[:300]
        objetivo = r.json()["distribution"]["comidas"]["C1"]
        servido = {m: 0.0 for m in ("P", "H", "G")}
        for a in r.json()["comidas"]["C1"]["alimentos"]:
            for m in servido:
                servido[m] += float((a.get("macros_efectivos") or {}).get(m, 0) or 0)
        for m in ("P", "H", "G"):
            tope = float(objetivo.get(m, 0) or 0) + MARGEN_VALIDO
            assert servido[m] <= tope, f"cuadrar se paso de {m}: {servido[m]} sobre {tope}"

    def test_repetir_de_otro_dia_tambien_cuadra(self, cabeceras_cliente):
        """FALLA. `/api/calculator/cuadrar-comida` devuelve 500 SIEMPRE.

        Es el otro boton de cuadrar: el de «Repetir de otro dia» (NutritionPage, linea 1292).
        El endpoint monta sus items con `alimento_id`, `cantidad_g` y `nombre`, y se los pasa
        a `meal_templates._ajustar_plantilla`, que en la linea 484 hace `item["rol"]` -- una
        clave que solo traen los items del recetario. KeyError, 500, y el front se lo come en
        su `catch` y cae al escalado por proteina de antes (el que Jesus ya habia rechazado
        porque «ni es fiel al dia que copias ni te deja la comida en verde»).

        O sea: el arreglo del punto 4.9 del 09-08 esta escrito pero no llega a ejecutarse
        nunca. No se ve porque hay plan B silencioso.
        """
        r = pedir("POST", "/calculator/cuadrar-comida", headers=cabeceras_cliente, json={
            "items": [{"alimento_id": ARROZ["id"], "cantidad_g": 101},
                      {"alimento_id": ALMENDRAS["id"], "cantidad_g": 21}],
            "macros_objetivo": {"P": 31, "H": 41, "G": 11}, "mealKey": "C1"})
        assert r.status_code == 200, f"cuadrar-comida respondio {r.status_code}: {r.text[:200]}"
        for it in r.json()["items"]:
            assert float(it["cantidad_g"]) % 5 == 0, f"{it['nombre']} a {it['cantidad_g']} g"


# ═════════════════════════════════════════════════════════════════════════════
# CASO 37 [CRITICO] · Anadir un alimento nuevo desde el panel sin categoria asignada.
# Espero: no deja aprobarlo: la categoria es obligatoria porque de ella depende que
# excepcion del filtro se aplica.
# ═════════════════════════════════════════════════════════════════════════════
class TestCaso37LaCategoriaEsObligatoria:

    def test_no_se_aprueba_una_sugerencia_sin_categoria(self, cabeceras_cliente, cabeceras_admin):
        """El camino que Jesus encontro el 11-08: aprobar una sugerencia de un cliente.

        Este si esta cerrado. Sin categoria el alimento entraria al catalogo sin que nadie
        sepa que excepcion del filtro se le aplica, o sea sin saber que macros le cuentan al
        cliente, y eso no se ve hasta meses despues en unas cuentas que no cuadran.
        """
        # Las dos fotos y el enlace son obligatorios desde el punto 161 del 27-08: una
        # solicitud sin ellos no se puede dar de alta y el servidor la rechaza con un 400.
        # Este caso va de la CATEGORIA, no del formulario, asi que se manda completa.
        r = pedir("POST", "/calculator/suggest-food", headers=cabeceras_cliente, data={
            "nombre": "Alimento de prueba caso 37", "por_unidad": "false", "racion": "100",
            "proteinas": "10", "hidratos": "20", "grasas": "5", "sin_web": "true"},
            files={"foto_frontal": ("frontal.png", _PNG, "image/png"),
                   "foto_reverso": ("reverso.png", _PNG, "image/png")})
        if r.status_code == 429:
            pytest.skip("El cliente de prueba ya gasto sus sugerencias de la semana")
        assert r.status_code == 200, r.text[:300]
        sugerencia_id = r.json()["id"]
        try:
            ra = pedir("POST", f"/admin/food-suggestions/{sugerencia_id}/approve",
                       headers=cabeceras_admin)
            assert ra.status_code == 400, (
                f"Se aprobo un alimento sin categoria (respondio {ra.status_code})")
            assert "categor" in ra.json().get("detail", "").lower(), (
                "El motivo del rechazo no le dice al admin que le falta la categoria")
        finally:
            # La sugerencia de prueba no se queda en la bandeja del admin, y asi el limite
            # semanal del cliente de prueba tampoco se agota al repetir el test.
            pedir("DELETE", f"/admin/food-suggestions/{sugerencia_id}", headers=cabeceras_admin)

    def test_no_se_crea_un_alimento_sin_categoria_desde_el_panel(self, cabeceras_admin):
        """FALLA. El mismo panel tiene un segundo boton -- «anadir alimento» a mano -- que no
        comprueba nada de esto.

        `POST /api/admin/foods` (routes/admin.py:1822) solo valida el nombre, y guarda
        `categorias: None` tan tranquilo. El formulario de AdminFoodSuggestionsPage.jsx hace
        lo mismo: `categorias: addForm.categorias || null`.

        Es literalmente el agujero del caso 37 por la otra puerta, y ademas la mas usada:
        aprobar una sugerencia pasa una vez al mes, dar de alta un alimento a mano es lo que
        se hace todas las semanas. Un alimento sin categoria no pasa por ninguna excepcion
        del filtro del tercio, asi que cuenta sus tres macros crudos para siempre.

        El alimento que crea este test se borra al terminar, aprobado o no.
        """
        r = pedir("POST", "/admin/foods", headers=cabeceras_admin, json={
            "nombre": "Alimento de prueba caso 37 (alta directa)", "por_unidad": False,
            "racion": 100, "proteinas": 10, "hidratos": 20, "grasas": 5})
        food_id = r.json().get("food_id") if r.status_code == 200 else None
        try:
            assert r.status_code == 400, (
                f"El panel creo un alimento SIN categoria (respondio {r.status_code}). "
                "Sin categoria no se sabe que macros le cuentan al cliente.")
        finally:
            if food_id:
                pedir("DELETE", f"/admin/foods/{food_id}", headers=cabeceras_admin)

    def test_sin_categoria_un_alimento_cuenta_sus_tres_macros_crudos(self):
        """POR QUE la categoria es obligatoria, medido en el motor.

        La regla del metodo (`aplicar_regla_macros`) empieza por preguntar en que categoria
        esta el alimento: si no esta en ninguna, se sale sin tocar nada y el alimento cuenta
        sus tres macros tal cual vienen de la etiqueta, para siempre. Con la 13.1 (verduras)
        el mismo alimento pierde la proteina, porque en las verduras la proteina no cuenta.

        Ese es el dano real de aprobar sin categoria: no es una ficha incompleta, es un
        alimento que cuenta MAL y nadie lo va a mirar otra vez.
        """
        etiqueta = {"nombre": "El mismo alimento", "proteinas": 10, "hidratos": 20,
                    "grasas": 5, "racion": 100, "unidades": False}
        sin_categoria = {**etiqueta, "categorias": None}
        con_categoria = {**etiqueta, "categorias": "13.1"}
        assert macros_efectivos(sin_categoria, 100) == {"P": 10.0, "H": 20.0, "G": 5.0}
        assert macros_efectivos(con_categoria, 100)["P"] == 0.0

    def test_con_categoria_si_se_aprueba(self, cabeceras_cliente, cabeceras_admin):
        """La otra mitad: puesta la categoria, la sugerencia se aprueba y el alimento entra
        al catalogo con esa categoria escrita, que es de lo que luego cuelga el conteo."""
        # Completa, como la de arriba: desde el punto 161 las dos fotos son obligatorias.
        r = pedir("POST", "/calculator/suggest-food", headers=cabeceras_cliente, data={
            "nombre": "Alimento de prueba caso 37 (con categoria)", "por_unidad": "false",
            "racion": "100", "proteinas": "10", "hidratos": "20", "grasas": "5",
            "sin_web": "true"},
            files={"foto_frontal": ("frontal.png", _PNG, "image/png"),
                   "foto_reverso": ("reverso.png", _PNG, "image/png")})
        if r.status_code == 429:
            pytest.skip("El cliente de prueba ya gasto sus sugerencias de la semana")
        assert r.status_code == 200, r.text[:300]
        sugerencia_id = r.json()["id"]
        food_id = None
        try:
            pedir("PUT", f"/admin/food-suggestions/{sugerencia_id}",
                  headers=cabeceras_admin, json={"categorias": "13.1"})
            ra = pedir("POST", f"/admin/food-suggestions/{sugerencia_id}/approve",
                       headers=cabeceras_admin)
            assert ra.status_code == 200, ra.text[:300]
            food_id = ra.json()["food_id"]
            rf = pedir("GET", f"/admin/food-suggestions/{sugerencia_id}", headers=cabeceras_admin)
            assert rf.status_code == 200, rf.text[:200]
            assert rf.json()["categorias"] == "13.1"
            assert rf.json()["status"] == "approved"
        finally:
            if food_id:
                pedir("DELETE", f"/admin/foods/{food_id}", headers=cabeceras_admin)
            pedir("DELETE", f"/admin/food-suggestions/{sugerencia_id}", headers=cabeceras_admin)
