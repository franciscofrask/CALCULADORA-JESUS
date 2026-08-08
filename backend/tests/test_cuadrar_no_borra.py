"""Cuadrar reparte, no sirve en cola, y no quita ingredientes.

Francisco, 08-08-2026: montó una Comida 2 con seis ingredientes, pulsó «Cuadrar» y le
quedaron tres. «Vaciar no debería eliminar comidas, dime cuál es el criterio actual».

El criterio era una cola: se recorrían los alimentos EN EL ORDEN DE LA LISTA y cada uno
se llevaba todo lo que podía del presupuesto que quedaba. Los últimos se lo encontraban
a cero, recibían cantidad 0 y se borraban con el motivo «no_cabe». Se comprobó poniendo
el mismo alimento el primero y el cuarto: **el primero sobrevivía y el cuarto no, fuera
cual fuera el alimento**. No se iban por descuadrar: se iban por llegar tarde. Y el aviso
que veía el cliente («no cabían ni al mínimo») no era cierto: sí cabían.

Ahora se le reserva a cada uno su mínimo antes de repartir, así que los seis siguen ahí,
y lo que no se llega a cuadrar se dice en vez de resolverlo borrando.
"""
import os

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8000")

# El caso tal cual lo montó Francisco
HUEVOS, CLARAS, AVENA = 321, 144, 1662
CACAO, LECHE_ALMENDRAS, PLATANO = 2940, 1708, 528
SEIS = [HUEVOS, CLARAS, AVENA, CACAO, LECHE_ALMENDRAS, PLATANO]

DIA = {"fecha": "2026-08-08", "tipo_dia": "entrenamiento", "num_comidas": 4,
       "momento_entreno": 1, "opcion_peri": "intra_post"}


@pytest.fixture(scope="module")
def headers():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": "clientedemo@test.com", "password": "demo123"},
                      timeout=60)
    assert r.status_code == 200, f"no se pudo entrar: {r.status_code}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _cuadrar(headers, ids, meal="C2"):
    alimentos = [{"alimento_id": i, "cantidad_g": 100} for i in ids]
    r = requests.post(f"{BASE_URL}/api/calculator/refit-diet",
                      json={**DIA, "comidas": {meal: {"alimentos": alimentos}}},
                      headers=headers, timeout=180)
    assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"
    d = r.json()
    return d["comidas"][meal]["alimentos"], d.get("excluidos", []), d.get("desfases", {}).get(meal)


def test_cuadrar_no_quita_ingredientes(headers):
    """Los seis que entran son los seis que salen."""
    alimentos, excluidos, _ = _cuadrar(headers, SEIS)
    assert len(alimentos) == len(SEIS), (
        f"entraron {len(SEIS)} ingredientes y salieron {len(alimentos)}: "
        f"{[a['nombre'] for a in alimentos]}")
    assert not excluidos, f"se han quitado: {[e.get('nombre') for e in excluidos]}"


def test_el_orden_no_decide_quien_sobrevive(headers):
    """Antes sobrevivían los tres primeros y morían los tres últimos, fuera cual fuera
    el alimento. Dar la vuelta a la lista tiene que dar los mismos seis."""
    normal, _, _ = _cuadrar(headers, SEIS)
    alreves, _, _ = _cuadrar(headers, list(reversed(SEIS)))
    assert {a["alimento_id"] for a in normal} == {a["alimento_id"] for a in alreves}, (
        "cambiar el orden cambia quién sobrevive")


def test_cada_ingrediente_se_lleva_algo(headers):
    """Que estén no basta: ninguno puede quedarse a cero."""
    alimentos, _, _ = _cuadrar(headers, SEIS)
    a_cero = [a["nombre"] for a in alimentos if float(a.get("cantidad_g") or 0) <= 0]
    assert not a_cero, f"se han quedado a cero: {a_cero}"


def test_el_peri_se_cuadra_aunque_ya_no_tenga_boton(headers):
    """El intra y el post SÍ se cuadran, aunque en la pantalla ya no haya botón.

    El botón estaba y no hacía nada -- el objetivo del peri vive en `periworkout` y no
    en `comidas`, y el endpoint solo miraba el primero, así que entraban 500 g de avena
    y salían 500 g. Se arregló, y después Francisco pidió quitar el botón del peri
    (08-08-2026), porque ahí se monta con «Construir» y con el sugeridor.

    Pero el arreglo del motor se queda, y por eso este test sigue aquí: `refit-diet` es
    lo que ajusta una dieta favorita al aplicarla y al pasarla de entreno a descanso.
    Sin él, el peri de esas favoritas se copiaba tal cual, sin ajustar a los macros del
    día. Quitar el botón fue una decisión de pantalla; esto es otra cosa.
    """
    for meal in ("Post", "Intra"):
        alimentos = [{"alimento_id": AVENA, "cantidad_g": 500},
                     {"alimento_id": CLARAS, "cantidad_g": 600}]
        r = requests.post(f"{BASE_URL}/api/calculator/refit-diet",
                          json={**DIA, "comidas": {meal: {"alimentos": alimentos}}},
                          headers=headers, timeout=180)
        assert r.status_code == 200
        d = r.json()
        obj = (d.get("distribution") or {}).get("periworkout", {}).get(meal)
        assert obj, f"{meal} no tiene objetivo en periworkout"
        servidos = d["comidas"][meal]["alimentos"]
        assert len(servidos) == 2, f"{meal}: ha quitado alimentos"
        cantidades = {a["alimento_id"]: a["cantidad_g"] for a in servidos}
        assert cantidades[AVENA] < 500 and cantidades[CLARAS] < 600, (
            f"{meal}: las cantidades salen igual que entraron, no ha cuadrado nada")
        tot = {m: sum(float((a.get("macros_efectivos") or {}).get(m, 0) or 0) for a in servidos)
               for m in ("P", "H")}
        for m in ("P", "H"):
            assert abs(tot[m] - float(obj[m])) <= 6, (
                f"{meal}: {m} se queda en {tot[m]:.1f} con objetivo {obj[m]}")


def test_en_el_peri_la_grasa_va_libre(headers):
    """En Calma el objetivo del peri no tiene clave de grasas: no es que sea 0, es que
    no se cuadra. Meter nueces en el post no puede saltar como «te sobra grasa»."""
    NUECES = 425
    alimentos = [{"alimento_id": NUECES, "cantidad_g": 60},
                 {"alimento_id": CLARAS, "cantidad_g": 300},
                 {"alimento_id": AVENA, "cantidad_g": 100}]
    r = requests.post(f"{BASE_URL}/api/calculator/refit-diet",
                      json={**DIA, "comidas": {"Post": {"alimentos": alimentos}}},
                      headers=headers, timeout=180)
    d = r.json()
    servidos = d["comidas"]["Post"]["alimentos"]
    grasa = sum(float((a.get("macros_efectivos") or {}).get("G", 0) or 0) for a in servidos)
    assert grasa > 0, "el caso ya no lleva grasa; hay que rehacerlo"
    assert d["desfases"]["Post"]["G"] == 0, "cuenta desfase de grasa en el peri"


def test_adaptar_una_favorita_a_descanso_sigue_vaciando_el_peri(headers):
    """El arreglo del peri toca la misma condición que usa «adaptar al tipo de día».
    En un día de descanso no hay entreno, así que Intra y Post sí se vacían."""
    r = requests.post(f"{BASE_URL}/api/calculator/refit-diet",
                      json={**DIA, "tipo_dia": "descanso", "descartar_sin_objetivo": True,
                            "comidas": {"Post": {"alimentos": [{"alimento_id": CLARAS, "cantidad_g": 300}]},
                                        "C1": {"alimentos": [{"alimento_id": CLARAS, "cantidad_g": 200}]}}},
                      headers=headers, timeout=180)
    d = r.json()
    assert d["comidas"]["Post"]["alimentos"] == [], "el Post no se ha vaciado en descanso"
    assert len(d["comidas"]["C1"]["alimentos"]) == 1, "ha vaciado una comida que sí existe"
    motivos = {e.get("motivo") for e in d.get("excluidos", [])}
    assert "sin_objetivo_en_dia" in motivos


def test_si_sobra_un_macro_dice_que_quitar(headers):
    """No basta con «sobran 22 g de grasa»: hay que decir por cuál empezar.

    Cuatro aceites: cada uno pone 10 g de grasa ya en su cantidad mínima, así que no
    hay forma de cuadrar sin quitar alguno. El aviso tiene que señalar el que más
    aporta -- y quitarlo lo decide el cliente, no la app.
    """
    ACEITE_COCO, AOVE, ACEITE_AGUACATE, MACADAMIAS = 801, 3, 1, 2393
    alimentos, excluidos, desfase = _cuadrar(
        headers, [ACEITE_COCO, AOVE, ACEITE_AGUACATE, MACADAMIAS])
    assert len(alimentos) == 4 and not excluidos, "ha quitado alimentos por su cuenta"
    assert desfase["G"] > 4, "el caso ya no se pasa de grasa; hay que rehacerlo"
    s = desfase.get("sugerencia")
    assert s, "no dice qué habría que tocar"
    # Manda lo que se pasa, aunque falten más gramos de otro macro (aquí faltan 47 de
    # proteína y 51 de hidratos, y aun así el problema es la grasa que sobra).
    assert s["que_hacer"] == "quitar_o_bajar", f"sugiere {s['que_hacer']} en vez de quitar"
    assert s["macro"] == "G", f"señala {s['macro']} en vez de la grasa que sobra"
    assert s["alimento"], "no dice cuál quitar"
    assert s["aporta"] >= 9, "no señala al que más grasa aporta"


def test_si_falta_un_macro_dice_que_anadir(headers):
    """Cuando no sobra nada, no hay nada que quitar: hay que añadir."""
    _, _, desfase = _cuadrar(headers, [HUEVOS, CACAO, CLARAS])
    s = desfase.get("sugerencia")
    assert s and s["que_hacer"] == "anadir"
    assert s["macro"] == "H", "no son los hidratos lo que falta"


def test_cuando_no_cuadra_se_dice_y_no_se_borra(headers):
    """Tres alimentos grasos y ningún hidrato: no puede cuadrar. Lo que NO puede hacer
    es resolverlo quitando cosas, ni pasarse de largo para tapar el hueco."""
    alimentos, excluidos, desfase = _cuadrar(headers, [HUEVOS, CACAO, CLARAS])
    assert len(alimentos) == 3, "ha quitado alimentos para poder cuadrar"
    assert not excluidos
    assert desfase is not None, "no dice cuánto se ha quedado sin cuadrar"
    # Faltar hidratos es inevitable (no hay ninguno); pasarse de grasa, no.
    assert desfase["G"] <= 4, f"se pasa {desfase['G']}g de grasa para tapar el hueco"
    assert desfase["P"] <= 4, f"se pasa {desfase['P']}g de proteína para tapar el hueco"
