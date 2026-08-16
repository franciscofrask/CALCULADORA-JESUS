"""
EL MISMO DÍA, EL MISMO OBJETIVO EN LAS DOS PANTALLAS.

Inicio (T1) enseñaba `macros_snapshot.P_total` a pelo y Nutrición enseña ese total menos el
perientreno, que lleva su cuenta aparte. Resultado: 235 arriba y 225 en Nutrición para el
mismo día y el mismo cliente, y también dos "te faltan" distintos.

Ahora el objetivo lo resuelve el servidor (`GET /diets/{fecha}` -> `objetivo_comidas`) con
la misma función que suma el reparto, así que estos tests fijan las dos mitades:

  - la cuenta: objetivo = total del día - perientreno = lo que suman las comidas,
  - y que lo que sirve la API para Inicio es exactamente lo que sirve para Nutrición.
"""
import pytest
import requests

from macro_distribution import distribuir_macros, objetivo_de_las_comidas

from conftest import API


def _reparto(**kwargs):
    base = dict(
        p_entreno=190, h_entreno=170, g_entreno=60,
        p_peri=45, h_peri=50,
        p_descanso=225, h_descanso=170, g_descanso=60,
        tipo_dia="entrenamiento", num_comidas=4, momento_entreno=1,
        opcion_peri="intra_post",
    )
    base.update(kwargs)
    return distribuir_macros(**base)


def _suma(comidas, clave):
    return round(sum(c[clave] for c in comidas.values()), 1)


@pytest.mark.parametrize("opcion_peri", ["intra_post", "solo_post", "solo_intra", "sin_peri"])
def test_el_objetivo_es_lo_que_suman_las_comidas(opcion_peri):
    """Con peri y sin peri: el objetivo del día es el de las COMIDAS, no el total.

    La holgura es el redondeo de Calma: cada comida se cuadra a medio gramo, así que la suma
    de las cuatro puede quedarse a un par de décimas del total del día. Lo que no puede
    pasar -- y es lo que pasaba -- es que se lleven los gramos enteros del perientreno.
    """
    r = _reparto(opcion_peri=opcion_peri)
    objetivo = objetivo_de_las_comidas(r)
    assert objetivo["P"] == pytest.approx(_suma(r["comidas"], "P"), abs=0.5)
    assert objetivo["H"] == pytest.approx(_suma(r["comidas"], "H"), abs=0.5)
    assert objetivo["G"] == pytest.approx(_suma(r["comidas"], "G"), abs=0.5)


def test_con_peri_el_objetivo_es_menor_que_el_total_del_dia():
    """El caso que destapó el fallo: los gramos del peri no se le piden a las comidas."""
    r = _reparto(opcion_peri="intra_post")
    peri_p = sum(v["P"] for v in r["periworkout"].values())
    assert peri_p > 0
    assert objetivo_de_las_comidas(r)["P"] == round(r["resumen"]["P_total"] - peri_p, 1)


def test_sin_peri_el_presupuesto_del_peri_se_come_en_las_comidas():
    """En `sin_peri` no hay intra ni post, así que el objetivo SÍ es el total del día, y es
    mayor que los macros de entreno: ese peri se reparte entre las comidas."""
    r = _reparto(opcion_peri="sin_peri")
    assert r["periworkout"] == {}
    objetivo = objetivo_de_las_comidas(r)
    assert objetivo["P"] == r["resumen"]["P_total"]
    assert objetivo["P"] > r["resumen"]["P_entreno"]


def test_en_descanso_no_hay_peri_que_descontar():
    r = _reparto(tipo_dia="descanso")
    assert objetivo_de_las_comidas(r) == {"P": 225.0, "H": 170.0, "G": 60.0}


def test_sin_reparto_no_se_inventa_un_objetivo():
    assert objetivo_de_las_comidas(None) == {"P": 0, "H": 0, "G": 0}
    assert objetivo_de_las_comidas({}) == {"P": 0, "H": 0, "G": 0}


# ── De punta a punta: la API le dice lo mismo a las dos pantallas ────────────

def test_inicio_y_nutricion_ven_el_mismo_objetivo(cabeceras_cliente):
    """Lo que pinta Inicio (`/diets/{fecha}.objetivo_comidas`) contra lo que pinta la
    cabecera de Nutrición (el reparto de `/calculator/distribute` menos el peri)."""
    from core.tiempo import hoy_madrid
    fecha = hoy_madrid().isoformat()

    dia = requests.get(f"{API}/diets/{fecha}", headers=cabeceras_cliente, timeout=20)
    assert dia.status_code == 200, dia.text
    datos = dia.json()
    objetivo = datos.get("objetivo_comidas")
    if not objetivo:
        pytest.skip("El cliente de pruebas no tiene macros asignados todavía.")

    # La misma configuración del día que usa Nutrición al abrir esa fecha.
    config = {
        "fecha": fecha,
        "tipo_dia": datos.get("tipo_dia") or "entrenamiento",
        "num_comidas": datos.get("num_comidas") or 4,
        "momento_entreno": datos.get("momento_entreno") if datos.get("momento_entreno") is not None else 1,
        "opcion_peri": datos.get("opcion_peri") or "intra_post",
    }
    config["single_meal"] = config["num_comidas"] == 1
    reparto = requests.post(f"{API}/calculator/distribute", json=config,
                            headers=cabeceras_cliente, timeout=20)
    assert reparto.status_code == 200, reparto.text
    r = reparto.json()

    peri_p = sum((v or {}).get("P", 0) for v in (r.get("periworkout") or {}).values())
    peri_h = sum((v or {}).get("H", 0) for v in (r.get("periworkout") or {}).values())
    assert objetivo["P"] == round(r["resumen"]["P_total"] - peri_p, 1)
    assert objetivo["H"] == round(r["resumen"]["H_total"] - peri_h, 1)
    assert objetivo["G"] == round(r["resumen"]["G_total"], 1)
    # Y es lo que suman los objetivos por comida (con el medio gramo del redondeo de cada
    # una), que es lo que el cliente va cuadrando comida a comida.
    assert objetivo["P"] == pytest.approx(sum(c["P"] for c in r["comidas"].values()), abs=0.5)


def test_el_objetivo_no_baila_entre_lecturas(cabeceras_cliente):
    """TRES LECTURAS DEL MISMO DÍA, EL MISMO NÚMERO.

    El fallo que se vio en pantalla no era solo que Inicio y Nutrición discreparan: es que
    Inicio enseñaba 190, luego 235 y luego 225 del mismo día, según qué petición contestara
    antes, porque el objetivo se componía de dos fuentes. Ahora sale de una sola y del
    servidor, así que leerlo varias veces no puede cambiarlo.
    """
    from core.tiempo import hoy_madrid
    fecha = hoy_madrid().isoformat()
    lecturas = []
    for _ in range(3):
        r = requests.get(f"{API}/diets/{fecha}", headers=cabeceras_cliente, timeout=20)
        assert r.status_code == 200, r.text
        lecturas.append(r.json().get("objetivo_comidas"))
    assert all(l == lecturas[0] for l in lecturas), lecturas


def test_el_objetivo_viaja_aunque_el_dia_no_exista(cabeceras_cliente):
    """Un día futuro sin montar: Inicio tiene que poder decir de cuánto es el día."""
    r = requests.get(f"{API}/diets/2027-12-31", headers=cabeceras_cliente, timeout=20)
    assert r.status_code == 200, r.text
    datos = r.json()
    assert datos["exists"] is False
    assert "objetivo_comidas" in datos
