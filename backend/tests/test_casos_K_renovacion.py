# -*- coding: utf-8 -*-
"""
Seccion K, "RENOVACION", de la lista de 85 casos de prueba que entrego Jesus el 12-08-2026.

    72. [CRITICO] Abrir la renovacion en la semana 12. Ningun dato aparece como NULL,
        vacio o cero cuando no lo es.
    73. [CRITICO] Un cliente que ha subido 400 g: lo dice en kilos y con signo, no
        como "0 %".
    74. Un cliente cuyo plan ya no se vende: se lo dice y le ofrece los actuales.
    75. [CRITICO] El plan de arriba va con "pedir llamada", sin precio ni boton de pagar.
    76. [CRITICO] El contador de ajustes coincide con el numero de ajustes del historico
        de Mis macros.

Los casos de Jesus son de PANTALLA, asi que casi todo esto va contra la API viva
(`GET /api/billing/renovacion`) y comparando con la otra pantalla que enseña lo mismo
(`GET /api/macros/historial`, que es lo que pinta "Mis macros"). Las piezas sueltas del
motor ya estan cubiertas en `test_renovacion.py`; aqui no se repiten: lo que se mira es si
los dos caminos dan el mismo numero, que es justo lo que no se ve desde un test unitario.
"""
import os
import time

import pytest
import requests

from core.renovacion import es_por_llamada, montar_renovacion, resumen_del_ciclo
from models.user import PLAN_CATALOG, opciones_de_renovacion

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api"

# El backend de desarrollo corre con `--reload`: cada vez que alguien guarda un fichero se
# reinicia y rechaza la conexion un par de segundos. Sin reintento saldrian rojos que no son
# del producto sino del servidor levantandose.
REINTENTOS = 20


def pedir(metodo, ruta, **kw):
    fallo = None
    for _ in range(REINTENTOS):
        try:
            return requests.request(metodo, f"{API}{ruta}", timeout=90, **kw)
        except requests.RequestException as e:  # el reload cierra el socket
            fallo = e
            time.sleep(2)
    raise AssertionError(f"El backend no responde en {ruta}: {fallo}")


def json_ok(respuesta, ruta):
    assert respuesta.status_code == 200, f"{ruta} devolvio {respuesta.status_code}: {respuesta.text[:200]}"
    return respuesta.json()


# Las cabeceras se sacan aqui y no de las fixtures del conftest a proposito: aquellas
# comprueban el servidor UNA vez y, si justo pillan un reinicio, se saltan la seccion
# entera. Un caso critico saltado se lee como un caso que no ha fallado, que es peor que
# un rojo.
@pytest.fixture(scope="module")
def cab_cliente():
    email = os.environ.get("TEST_CLIENT_EMAIL", "clientedemo@test.com")
    clave = os.environ.get("TEST_CLIENT_PASSWORD", "demo123")
    r = pedir("post", "/auth/login", json={"email": email, "password": clave})
    if r.status_code != 200:
        pytest.skip(f"No se puede entrar como cliente ({email}): {r.status_code}")
    d = r.json()
    return {"Authorization": "Bearer " + (d.get("access_token") or d.get("token"))}


@pytest.fixture(scope="module")
def renovacion(cab_cliente):
    return json_ok(pedir("get", "/billing/renovacion", headers=cab_cliente), "/billing/renovacion")


@pytest.fixture(scope="module")
def historial(cab_cliente):
    """Lo que ve el cliente en «Mis macros»."""
    return json_ok(pedir("get", "/macros/historial", headers=cab_cliente), "/macros/historial")


@pytest.fixture(scope="module")
def perfil(cab_cliente):
    return json_ok(pedir("get", "/clients/profile", headers=cab_cliente), "/clients/profile")


def inicio_de_ciclo(perfil):
    """El dia desde el que cuenta este ciclo: LA MISMA funcion que usa billing.

    Estaba copiado a mano (`arranque_lunes` o `created_at`) y el 24-08 dejo de ser cierto:
    el resumen de la renovacion pasa a contar EL CICLO QUE VIVE, con `current_period_start`
    y topado a la duracion del plan, para que al de dos años no le diga «45 de 730 dias».
    Con la copia vieja, este test comparaba dos ventanas distintas y cantaba una diferencia
    que no existia. Se llama a la de verdad: es lo que el test quiere fijar, que las dos
    pantallas cuenten lo mismo desde el mismo dia.
    """
    from core.renovacion import inicio_del_ciclo
    d0 = inicio_del_ciclo(perfil)
    return d0.isoformat() if d0 else ""


# ---------------------------------------------------------------------------
# CASO 72 [CRITICO] - abrir la renovacion y que ningun dato salga vacio sin serlo
# ---------------------------------------------------------------------------

def perfil_de_semana_12(**extra):
    base = {
        "plan": "nivel2", "week": 12, "body_fat": 18.0, "precio_alta": 897.0,
        "arranque_lunes": "2026-05-18T00:00:00+00:00",
        "fin_de_ciclo": "2026-08-16T00:00:00+00:00",
    }
    base.update(extra)
    return base


def test_en_la_semana_12_con_datos_completos_no_queda_ni_un_hueco():
    """Con un cliente que lo tiene TODO, la pantalla no puede devolver un solo None.

    Es el caso 72 leido al reves: si con todos los datos delante algo sale a None, el
    hueco lo pone la pantalla, no el cliente.
    """
    p = perfil_de_semana_12()
    pantalla = montar_renovacion(
        perfil=p, catalogo=PLAN_CATALOG,
        opciones_catalogo=opciones_de_renovacion(p["plan"], PLAN_CATALOG),
        resumen=resumen_del_ciclo(
            reporte_primero={"weight": 88.0, "body_fat": 26.0, "photos": ["a", "b"]},
            reporte_ultimo={"weight": 82.4, "photos": ["x", "y"]},
            perfil=p, dias_dieta=70, dias_totales=84, ajustes_de_macros=5),
    )
    peso = pantalla["resumen"]["peso"]
    assert peso["antes"] and peso["ahora"]
    assert peso["cambio_kg"] is not None and peso["cambio_pct"] is not None
    assert pantalla["resumen"]["grasa"]["antes"] is not None
    assert pantalla["resumen"]["grasa"]["ahora"] is not None
    assert pantalla["resumen"]["fotos"]["comparables"] is True
    assert pantalla["resumen"]["constancia"]["dias_totales"] > 0
    assert pantalla["resumen"]["ajustes_de_macros"] == 5
    assert pantalla["ciclo"]["dias_restantes"] is not None
    for salida in pantalla["salidas"]:
        assert salida["nombre"], f"la salida {salida['plan']} va sin nombre"
        assert salida["detalle"], f"la salida {salida['plan']} va sin explicacion"


def test_la_pantalla_abre_y_trae_sus_tres_partes(renovacion):
    """Lo conseguido, y despues lo que puede hacer. En ese orden y las dos cosas."""
    assert set(renovacion) >= {"ciclo", "resumen", "salidas"}
    assert renovacion["salidas"], "la renovacion no ofrece ni una salida"
    resumen = renovacion["resumen"]
    assert set(resumen) >= {"peso", "grasa", "fotos", "constancia", "ajustes_de_macros"}


def test_la_constancia_no_se_cuenta_sobre_cero_dias(renovacion):
    c = renovacion["resumen"]["constancia"]
    assert c["dias_totales"] > 0
    assert 0 <= c["pct"] <= 100
    assert c["dias_registrados"] <= c["dias_totales"], (
        f"registrados {c['dias_registrados']} de {c['dias_totales']} totales: "
        "el porcentaje de constancia sale de una division imposible")


def test_el_peso_de_la_renovacion_es_el_peso_que_tiene_el_cliente(renovacion, historial, perfil):
    """El "ahora" de la renovacion tiene que ser el peso de verdad del cliente.

    La renovacion lo saca del ULTIMO REPORTE (`reports.weight`) y «Mis macros» de la SERIE
    DE PESO (punto 30), que es donde caen todos los pesajes vengan de donde vengan: reporte,
    calculadora o ajuste del coach. Si el cliente se peso despues de su ultimo reporte, la
    renovacion le resume el ciclo con un peso viejo, y de ahi salen el "0 kg" y el "0 %".
    """
    serie = [p for p in (historial.get("evolucion_peso") or []) if p.get("peso")]
    if not serie:
        pytest.skip("el cliente de prueba no tiene ni un peso apuntado")
    ultimo = serie[-1]
    ahora = renovacion["resumen"]["peso"]["ahora"]
    assert ahora is not None, "la renovacion no enseña peso y el cliente si tiene pesajes"
    assert abs(float(ahora) - float(ultimo["peso"])) < 0.5, (
        f"la renovacion dice que pesa {ahora} kg y su ultimo pesaje ({ultimo['fecha']}) "
        f"es de {ultimo['peso']} kg")


def test_las_salidas_llevan_nombre_y_precio(renovacion):
    """Un plan sin nombre o a 0 EUR es un dato vacio en una pantalla de venta."""
    for salida in renovacion["salidas"]:
        assert salida.get("nombre"), f"{salida['plan']} sale sin nombre"
        if salida.get("por_llamada"):
            continue  # ese no lleva precio a proposito (caso 75)
        assert salida.get("precio"), f"{salida['plan']} sale a {salida.get('precio')} EUR"


# ---------------------------------------------------------------------------
# CASO 73 [CRITICO] - 400 g se dicen en kilos y con signo
# ---------------------------------------------------------------------------

def test_una_subida_de_400_g_se_cuenta_en_kilos_y_con_signo():
    r = resumen_del_ciclo(reporte_primero={"weight": 75.0, "photos": ["a"]},
                          reporte_ultimo={"weight": 75.4, "photos": ["b"]},
                          perfil={}, dias_dieta=80, dias_totales=84, ajustes_de_macros=2)
    assert r["peso"]["cambio_kg"] == 0.4, "400 g son 0,4 kg, no cero"
    assert r["peso"]["cambio_kg"] > 0, "y hacia arriba, con su signo"


def test_una_bajada_pequena_tambien_conserva_el_signo():
    r = resumen_del_ciclo(reporte_primero={"weight": 75.0, "photos": ["a"]},
                          reporte_ultimo={"weight": 74.6, "photos": ["b"]},
                          perfil={}, dias_dieta=80, dias_totales=84, ajustes_de_macros=2)
    assert r["peso"]["cambio_kg"] == -0.4


def test_en_alguien_de_120_kilos_400_g_siguen_sin_ser_cero():
    """El porcentaje se come los cambios pequeños en la gente grande: 0,4 sobre 120 es un
    0,3 %. Por eso el kilaje tiene que viajar SIEMPRE, que es lo que pide el caso 73."""
    r = resumen_del_ciclo(reporte_primero={"weight": 120.0, "photos": ["a"]},
                          reporte_ultimo={"weight": 120.4, "photos": ["b"]},
                          perfil={}, dias_dieta=80, dias_totales=84, ajustes_de_macros=2)
    assert r["peso"]["cambio_kg"] == 0.4
    assert r["peso"]["cambio_pct"] != 0


def test_si_el_cliente_ha_cambiado_de_peso_la_renovacion_no_dice_cero(renovacion, historial, perfil):
    """Lo mismo que arriba, pero con el cliente de verdad y sus dos pantallas."""
    desde = inicio_de_ciclo(perfil)
    serie = [p for p in (historial.get("evolucion_peso") or [])
             if p.get("peso") and (p.get("fecha") or "") >= desde]
    if len(serie) < 2:
        pytest.skip("el cliente de prueba no tiene dos pesajes en este ciclo")
    movido = round(float(serie[-1]["peso"]) - float(serie[0]["peso"]), 1)
    if abs(movido) < 0.3:
        pytest.skip("el cliente de prueba no se ha movido de peso en este ciclo")
    cambio = renovacion["resumen"]["peso"]["cambio_kg"]
    assert cambio, (
        f"su peso se movio {movido:+} kg entre {serie[0]['fecha']} y {serie[-1]['fecha']} "
        f"y la renovacion resume el ciclo con cambio_kg={cambio}")


# ---------------------------------------------------------------------------
# CASO 74 - al del plan que ya no se vende se le dice, y se le ofrece lo de ahora
# ---------------------------------------------------------------------------

def test_al_del_plan_retirado_se_le_explica_por_que_cambia(renovacion, perfil):
    plan = (perfil.get("plan") or "").lower()
    se_sigue_vendiendo = opciones_de_renovacion(plan, PLAN_CATALOG).get("puede_seguir_igual")
    if se_sigue_vendiendo:
        pytest.skip(f"el cliente de prueba esta en «{plan}», que se sigue vendiendo")
    assert renovacion.get("motivo_cambio"), (
        f"«{plan}» ya no se vende y la pantalla no le dice por que no puede seguir igual")
    tipos = [s["tipo"] for s in renovacion["salidas"]]
    assert "renovar" not in tipos, "se le ofrece seguir en un plan que ya no se vende"


def test_y_se_le_ofrecen_los_planes_de_ahora(renovacion, perfil):
    plan = (perfil.get("plan") or "").lower()
    if opciones_de_renovacion(plan, PLAN_CATALOG).get("puede_seguir_igual"):
        pytest.skip(f"el cliente de prueba esta en «{plan}», que se sigue vendiendo")
    ofrecidos = {s["plan"] for s in renovacion["salidas"] if s["tipo"] == "cambiar"}
    esperados = set(opciones_de_renovacion(plan, PLAN_CATALOG).get("opciones") or [])
    assert ofrecidos == esperados - {plan}, (
        f"se le ofrecen {sorted(ofrecidos)} y el catalogo de hoy vende {sorted(esperados)}")


# ---------------------------------------------------------------------------
# CASO 75 [CRITICO] - el de arriba va por llamada, sin precio ni boton de pagar
# ---------------------------------------------------------------------------

def test_el_plan_de_arriba_de_la_renovacion_va_por_llamada(renovacion):
    """El primero de la lista es el mas caro, y el mas caro se contrata hablando.

    Lo que hacia esta pantalla el 11-08 era invitar a pagar 1.500 EUR por dentro un plan
    que el propio catalogo dice que se cierra por telefono.
    """
    cambios = [s for s in renovacion["salidas"] if s["tipo"] == "cambiar"]
    if not cambios:
        pytest.skip("a este cliente no se le ofrece cambiar de nivel")
    arriba = cambios[0]
    if not es_por_llamada(arriba["plan"]):
        pytest.skip(f"el plan de arriba es «{arriba['plan']}», que si se vende desde la app")
    assert arriba.get("por_llamada") is True, (
        f"«{arriba['plan']}» se contrata por llamada y la salida no lo marca: la pantalla "
        "le pintaria su precio y su boton de pagar")


def test_solo_los_planes_por_llamada_llevan_esa_marca(renovacion):
    for salida in renovacion["salidas"]:
        if salida["tipo"] != "cambiar":
            continue
        assert bool(salida.get("por_llamada")) == es_por_llamada(salida["plan"]), (
            f"«{salida['plan']}» esta marcado como por_llamada={salida.get('por_llamada')} "
            "y el catalogo dice lo contrario")


def test_el_que_va_por_llamada_no_se_vende_con_una_frase_de_precio(renovacion):
    """Su texto no puede empujar a pagar: lo que toca es hablar antes."""
    for salida in renovacion["salidas"]:
        if salida.get("por_llamada"):
            assert "€" not in (salida.get("detalle") or ""), (
                f"«{salida['plan']}» va por llamada y su frase lleva un precio: {salida['detalle']}")


@pytest.mark.skip(reason="visual: que el boton diga «Pedir llamada» y no se pinte el precio "
                         "se ve en RenovacionPage.jsx, no en la API. La API si manda el flag "
                         "`por_llamada`, que es lo que aqui se comprueba.")
def test_el_boton_dice_pedir_llamada():
    pass


# ---------------------------------------------------------------------------
# CASO 76 [CRITICO] - el contador de ajustes contra el historico de Mis macros
# ---------------------------------------------------------------------------

def test_el_contador_de_ajustes_coincide_con_el_historico_de_mis_macros(
        renovacion, historial, perfil):
    """Los dos numeros que el cliente puede leer el mismo dia, uno en cada pantalla.

    La renovacion cuenta DIAS distintos con ajuste dentro del ciclo y hasta hoy
    (`routes/billing._dias_con_ajuste`). «Mis macros» lista las entradas de `macro_history`
    con vigencia hasta hoy (`routes/users.get_mi_historial_de_macros`). Son dos caminos
    distintos, asi que este test compara de verdad: cuenta los dias distintos que salen en
    el historico dentro del ciclo y los pone al lado del contador.
    """
    desde = inicio_de_ciclo(perfil)
    assert desde, "el perfil no dice cuando arranco el ciclo"
    if not historial.get("con_historico"):
        pytest.skip("el plan del cliente de prueba no enseña historico de macros")

    dias = sorted({e["fecha"] for e in historial["entradas"]
                   if e.get("fecha") and e["fecha"] >= desde})
    contador = renovacion["resumen"]["ajustes_de_macros"]
    assert contador == len(dias), (
        f"la renovacion dice {contador} ajustes en el ciclo y «Mis macros» enseña "
        f"{len(dias)} dias con ajuste desde {desde} ({dias}). El historico devuelve como "
        f"mucho 60 filas (`to_list(60)` en routes/users.py) y este cliente tiene "
        f"{len(historial['entradas'])}, asi que a partir de ahi las dos pantallas cuentan "
        "cosas distintas")


def test_ningun_ajuste_del_historico_esta_fechado_por_delante(historial):
    """Un ajuste que aun no ha empezado no es un ajuste que le hayan hecho."""
    from datetime import datetime, timezone
    hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    futuras = [e["fecha"] for e in historial.get("entradas", []) if (e.get("fecha") or "") > hoy]
    assert not futuras, f"«Mis macros» enseña ajustes con fecha de mañana o mas: {futuras[:5]}"


def test_el_contador_no_puede_ser_mayor_que_los_dias_del_ciclo(renovacion):
    """La tarjeta resume DOCE SEMANAS: mas de 84 ajustes no cabe, sea cual sea la cuenta.

    Es el sintoma que reporto Jesus el 12-08 («AJUSTES 176»): contaba filas de toda la vida
    del cliente en una tarjeta que habla del ciclo.
    """
    ajustes = renovacion["resumen"]["ajustes_de_macros"]
    dias_del_ciclo = renovacion["resumen"]["constancia"]["dias_totales"]
    assert ajustes <= dias_del_ciclo, (
        f"{ajustes} ajustes en {dias_del_ciclo} dias de ciclo")
