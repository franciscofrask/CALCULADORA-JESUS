# -*- coding: utf-8 -*-
"""«QUE PREGUNTE DE DONDE RECALCULA» (Jesus, nota de voz del 31-08-2026).

«Pregunte de que quiere bajar la proteina, del polvo o del queso [...] es imposible que la
aplicacion aprenda eso, porque te puede quedar mas denso, menos denso [...] lo mas sencillo
es preguntar.»

LO QUE PASABA ANTES, MEDIDO. Una comida con 60 g de aislado y 300 g de queso batido para un
objetivo de 38 P salia con el aislado en 5 g y el queso intacto. Y con los mismos dos
alimentos, cambiando SOLO el orden de la lista, salia el queso en 285 y el aislado en 10. La
app ya decidia; lo que no tenia era criterio: mandaba el orden.

Aqui se comprueban las dos mitades:
  - las reglas puras (core/de_donde_bajo.py), que no necesitan servidor,
  - y el endpoint, que es donde se ve que elegir sirve de algo y que el orden ya no manda.
"""
import os
import sys

import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import de_donde_bajo  # noqa: E402

API = os.environ.get("REACT_APP_BACKEND_URL", "http://127.0.0.1:8000").rstrip("/") + "/api"

# El batido de la nota de voz, con alimentos reales del catalogo.
POLVO = 2822    # Aislado de proteina - Whey Prime Isolate (Prozis): 88 P / 1,1 H / 2 G
QUESO = 1678    # Queso fresco batido 0 %: 10 P / 4 H / 0,1 G
POLLO = 498     # Pechuga de pollo: 20 P
ARROZ = 1657    # Arroz blanco: 7 P / 80 H

DIA = {"fecha": "2026-12-19", "tipo_dia": "entrenamiento", "num_comidas": 4,
       "momento_entreno": 1, "opcion_peri": "intra_post"}


def _al(fid, nombre, gramos):
    return {"id": fid, "alimento_id": fid, "nombre": nombre, "cantidad_g": gramos}


def _refit(cabeceras, alimentos, ajuste=None):
    cuerpo = dict(DIA, comidas={"C3": {"alimentos": alimentos}})
    if ajuste:
        cuerpo["ajuste"] = {"C3": ajuste}
    r = requests.post(f"{API}/calculator/refit-diet", headers=cabeceras, json=cuerpo, timeout=90)
    assert r.status_code == 200, f"refit-diet responde {r.status_code}: {r.text[:200]}"
    return r.json()


def _cantidades(res):
    return {a["alimento_id"]: a["cantidad_g"] for a in res["comidas"]["C3"]["alimentos"]}


# ── Las reglas, sin servidor ──────────────────────────────────────────────────

def test_solo_se_pregunta_por_lo_que_SOBRA():
    """Faltar se arregla anadiendo: eso no es una decision de donde quitar."""
    corto = {"P": 20, "H": 10, "G": 5}
    assert de_donde_bajo.macro_que_sobra(corto, {"P": 38, "H": 48, "G": 18}) is None


def test_se_pregunta_por_el_macro_que_MAS_se_pasa():
    servido = {"P": 45, "H": 90, "G": 19}
    assert de_donde_bajo.macro_que_sobra(servido, {"P": 38, "H": 48, "G": 18}) == "H"


def test_la_grasa_del_peri_no_cuenta():
    """En el peri la grasa va libre (objetivo infinito): ahi no se puede pasar nadie."""
    servido = {"P": 30, "H": 20, "G": 40}
    objetivo = {"P": 38, "H": 48, "G": float("inf")}
    assert de_donde_bajo.macro_que_sobra(servido, objetivo) is None


def test_con_una_sola_fuente_del_macro_no_se_pregunta():
    """Pollo con arroz: la proteina la pone el pollo. No hay nada que elegir."""
    aportes = [
        {"alimento_id": POLLO, "nombre": "Pollo", "cantidad_g": 300,
         "macros": {"P": 60, "H": 0, "G": 0}},
        {"alimento_id": ARROZ, "nombre": "Arroz", "cantidad_g": 50,
         "macros": {"P": 3.5, "H": 40, "G": 0.5}},
    ]
    assert de_donde_bajo.hay_que_preguntar(
        {"P": 63.5, "H": 40, "G": 0.5}, {"P": 38, "H": 48, "G": 18}, aportes) is None


def test_con_dos_fuentes_se_pregunta():
    aportes = [
        {"alimento_id": POLVO, "nombre": "Aislado", "cantidad_g": 60,
         "macros": {"P": 52.8, "H": 0.7, "G": 1.2}},
        {"alimento_id": QUESO, "nombre": "Queso", "cantidad_g": 300,
         "macros": {"P": 30, "H": 12, "G": 0.3}},
    ]
    assert de_donde_bajo.hay_que_preguntar(
        {"P": 82.8, "H": 12.7, "G": 1.5}, {"P": 38, "H": 48, "G": 18}, aportes) == "P"


def test_un_alimento_que_pone_una_miseria_no_entra_en_la_pregunta():
    """El arroz pone 7 P de 90: bajarlo no arregla la proteina y de paso carga los hidratos."""
    aportes = [
        {"alimento_id": POLLO, "nombre": "Pollo", "cantidad_g": 250, "macros": {"P": 50, "H": 0, "G": 0}},
        {"alimento_id": 1667, "nombre": "Atun", "cantidad_g": 150, "macros": {"P": 33, "H": 0, "G": 6}},
        {"alimento_id": ARROZ, "nombre": "Arroz", "cantidad_g": 100, "macros": {"P": 7, "H": 80, "G": 1}},
    ]
    nombres = [a["nombre"] for a in de_donde_bajo.de_donde_se_puede_bajar(aportes, "P")]
    assert nombres == ["Pollo", "Atun"], f"la lista de opciones sale {nombres}"


def test_el_factor_deja_a_los_candidatos_justo_en_el_objetivo():
    # 82,8 P puestos, hay que bajar 44,8 -> se quedan en 38
    k = de_donde_bajo.factor_proporcional(44.8, 82.8)
    assert abs(82.8 * k - 38.0) < 0.01


def test_el_titulo_no_dice_nada_que_la_app_no_sepa():
    """Sin adjetivos: ni «mas espeso» ni «mas liquido». En un plato de pollo con arroz esa
    frase no significaria nada, y la app no sabe la textura de nada."""
    t = de_donde_bajo.titulo("P", 44.8)
    assert t == "Sobra proteína: hay que bajar 44,8 g. ¿De dónde?"
    for palabra in ("espeso", "líquido", "denso", "textura"):
        assert palabra not in t.lower()


# ── El endpoint ───────────────────────────────────────────────────────────────

def test_el_batido_de_la_nota_devuelve_la_pregunta(cabeceras_cliente):
    res = _refit(cabeceras_cliente, [_al(POLVO, "Aislado", 60), _al(QUESO, "Queso", 300)])
    d = res.get("decisiones", {}).get("C3")
    assert d, "no viene la pregunta: la app vuelve a decidir sola de donde baja"
    assert d["macro"] == "P"
    modos = [o["modo"] for o in d["opciones"]]
    assert modos.count("solo") == 2 and modos.count("proporcional") == 1, modos
    # Cada opcion dice en cuanto se quedaria: es lo unico que la app sabe de verdad.
    for o in d["opciones"]:
        if o["modo"] == "solo":
            assert o["queda_en"] <= o["cantidad_ahora"], o


def test_elegir_un_alimento_baja_ESE_y_deja_el_otro_como_estaba(cabeceras_cliente):
    """«Lo que elijas es lo unico que baja»: si no, la respuesta del cliente no sirve."""
    alimentos = [_al(POLVO, "Aislado", 60), _al(QUESO, "Queso", 300)]
    del_polvo = _cantidades(_refit(cabeceras_cliente, alimentos,
                                   {"modo": "solo", "alimento_id": POLVO}))
    assert del_polvo[QUESO] == 300, f"el queso se ha movido a {del_polvo[QUESO]} g"
    assert del_polvo[POLVO] < 60, "el polvo no ha bajado"

    del_queso = _cantidades(_refit(cabeceras_cliente, alimentos,
                                  {"modo": "solo", "alimento_id": QUESO}))
    assert del_queso[POLVO] == 60, f"el polvo se ha movido a {del_queso[POLVO]} g"
    assert del_queso[QUESO] < 300, "el queso no ha bajado"


def test_de_todos_baja_a_los_dos_y_mantiene_la_proporcion(cabeceras_cliente):
    """La tercera opcion: la misma comida, con menos cantidad."""
    alimentos = [_al(POLVO, "Aislado", 60), _al(QUESO, "Queso", 300)]
    q = _cantidades(_refit(cabeceras_cliente, alimentos, {"modo": "proporcional"}))
    assert q[POLVO] < 60 and q[QUESO] < 300, f"no ha bajado a los dos: {q}"
    # 60/300 = 0,2. El redondeo a cantidades pesables mueve algo, pero no la desfigura.
    assert abs(q[POLVO] / q[QUESO] - 0.2) < 0.08, f"la proporcion se ha ido: {q}"


def test_el_orden_de_la_lista_YA_NO_DECIDE(cabeceras_cliente):
    """LO QUE MOTIVO TODO ESTO. El mismo batido salia de dos maneras segun quien estuviera
    antes en la lista: aislado 5 g / queso 300, o queso 285 / aislado 10."""
    uno = _cantidades(_refit(cabeceras_cliente, [_al(POLVO, "Aislado", 60), _al(QUESO, "Queso", 300)]))
    otro = _cantidades(_refit(cabeceras_cliente, [_al(QUESO, "Queso", 300), _al(POLVO, "Aislado", 60)]))
    assert uno == otro, f"segun el orden sale {uno} o {otro}"


def test_una_comida_que_no_se_pasa_no_pregunta_nada(cabeceras_cliente):
    res = _refit(cabeceras_cliente, [_al(POLLO, "Pollo", 100), _al(ARROZ, "Arroz", 50)])
    assert not res.get("decisiones"), f"pregunta sin que sobre nada: {res.get('decisiones')}"


def test_lo_que_promete_la_pregunta_es_lo_que_sale(cabeceras_cliente):
    """El «se quedaria en N g» de la opcion tiene que ser el N g que sale al elegirla, o el
    cliente estaria eligiendo a ciegas."""
    alimentos = [_al(POLVO, "Aislado", 60), _al(QUESO, "Queso", 300)]
    d = _refit(cabeceras_cliente, alimentos)["decisiones"]["C3"]
    for o in d["opciones"]:
        if o["modo"] != "solo":
            continue
        q = _cantidades(_refit(cabeceras_cliente, alimentos,
                               {"modo": "solo", "alimento_id": o["alimento_id"]}))
        assert abs(q[o["alimento_id"]] - o["queda_en"]) < 0.5, (
            f"{o['nombre']}: la pregunta decia {o['queda_en']} g y salen {q[o['alimento_id']]}")


@pytest.fixture(autouse=True)
def _sin_servidor(api_disponible):
    """Las pruebas del endpoint necesitan backend; las de las reglas no, pero el fixture es
    de sesion y saltarlas todas juntas es mas claro que media bateria en gris."""
    return api_disponible
