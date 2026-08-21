"""
GET /diets/semana: la semana de Mi semana (tarea 5.1 del rediseño, 21-08).

Se monta una semana lejana (enero de 2030) en la cuenta de prueba del cliente para no
pisar datos reales, y se comprueba:

  - los siete días llegan de lunes a domingo, pidiendo la semana por CUALQUIER día,
  - los estados: montada / empezada / sin_montar, con el conteo «X de N comidas»,
  - el peri (Post) NO cuenta como comida: un día con C1..C4 llenas y Post llena
    sigue siendo «montada» con 4 de 4,
  - un día guardado como descanso sale como descanso,
  - los macros de un día montado suman de verdad (alimento real del catálogo),
  - el resumen cuadra con los días.
"""
from datetime import date, timedelta

import pytest
import requests

from conftest import API

# Lunes de una semana que no existe en los datos reales.
LUNES = date(2030, 1, 7)
assert LUNES.weekday() == 0, "el ancla del test tiene que ser un lunes"
FECHAS = [(LUNES + timedelta(days=i)).isoformat() for i in range(7)]


def _alimento_real(cabeceras):
    """Un alimento del catálogo con proteína, para que el día montado sume macros."""
    r = requests.get(f"{API}/calculator/foods", params={"search": "pollo", "limit": 5},
                     headers=cabeceras, timeout=15)
    if r.status_code == 200 and isinstance(r.json(), list) and r.json():
        f = r.json()[0]
        return {"alimento_id": f.get("id"), "nombre": f.get("nombre", "Pollo"),
                "cantidad_g": 150}
    # Sin catálogo (base vacía) el test de estados sigue valiendo; el de macros se salta.
    return {"alimento_id": "no-existe", "nombre": "Alimento de prueba", "cantidad_g": 150}


def _guardar_dia(cabeceras, fecha, tipo_dia, comidas):
    r = requests.post(f"{API}/diets", headers=cabeceras, timeout=20, json={
        "fecha": fecha,
        "tipo_dia": tipo_dia,
        "num_comidas": 4,
        "comidas": comidas,
        "comidas_completas": True,
    })
    assert r.status_code == 200, f"no se pudo guardar {fecha}: {r.text}"


@pytest.fixture(scope="module")
def semana_montada(api_disponible, cabeceras_cliente):
    """Deja la semana de prueba montada y la limpia al terminar."""
    # Por si un run anterior no llegó a limpiar.
    for f in FECHAS:
        requests.delete(f"{API}/diets/{f}", headers=cabeceras_cliente, timeout=15)

    alimento = _alimento_real(cabeceras_cliente)
    con = {"alimentos": [dict(alimento)]}
    vacia = {"alimentos": []}

    # Lunes: montada (C1..C4 llenas) y ADEMÁS el Post lleno, que no debe contar.
    _guardar_dia(cabeceras_cliente, FECHAS[0], "entrenamiento",
                 {"C1": con, "C2": con, "C3": con, "C4": con, "Post": con})
    # Martes: empezada (2 de 4).
    _guardar_dia(cabeceras_cliente, FECHAS[1], "entrenamiento",
                 {"C1": con, "C2": con, "C3": vacia, "C4": vacia})
    # Miércoles: día de DESCANSO, empezado (1 de 4).
    _guardar_dia(cabeceras_cliente, FECHAS[2], "descanso",
                 {"C1": con, "C2": vacia, "C3": vacia, "C4": vacia})
    # Jueves: guardado pero sin nada -> sin montar. Viernes a domingo: sin documento.
    _guardar_dia(cabeceras_cliente, FECHAS[3], "entrenamiento",
                 {"C1": vacia, "C2": vacia, "C3": vacia, "C4": vacia})

    yield alimento

    for f in FECHAS:
        requests.delete(f"{API}/diets/{f}", headers=cabeceras_cliente, timeout=15)


def _semana(cabeceras, inicio):
    r = requests.get(f"{API}/diets/semana", params={"inicio": inicio},
                     headers=cabeceras, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


class TestMiSemana:

    def test_siete_dias_de_lunes_a_domingo_desde_cualquier_dia(self, semana_montada, cabeceras_cliente):
        # Se pide por el MIÉRCOLES y tiene que volver la semana entera desde el lunes.
        data = _semana(cabeceras_cliente, FECHAS[2])
        assert data["inicio"] == FECHAS[0]
        assert data["fin"] == FECHAS[6]
        assert [d["fecha"] for d in data["dias"]] == FECHAS
        assert len(data["dias"]) == 7

    def test_estados_montada_empezada_y_sin_montar(self, semana_montada, cabeceras_cliente):
        dias = _semana(cabeceras_cliente, FECHAS[0])["dias"]
        estados = {d["fecha"]: d["estado"] for d in dias}
        assert estados[FECHAS[0]] == "montada"
        assert estados[FECHAS[1]] == "empezada"
        assert estados[FECHAS[2]] == "empezada"     # descanso con una comida puesta
        assert estados[FECHAS[3]] == "sin_montar"   # guardado vacío
        assert estados[FECHAS[4]] == "sin_montar"   # sin documento
        assert estados[FECHAS[5]] == "sin_montar"
        assert estados[FECHAS[6]] == "sin_montar"

        martes = next(d for d in dias if d["fecha"] == FECHAS[1])
        assert martes["n_comidas_con_alimentos"] == 2
        assert martes["n_comidas_total"] == 4

    def test_el_peri_no_cuenta_como_comida(self, semana_montada, cabeceras_cliente):
        lunes = next(d for d in _semana(cabeceras_cliente, FECHAS[0])["dias"]
                     if d["fecha"] == FECHAS[0])
        # El Post está lleno y aún así el día son 4 de 4, no 5 de nada.
        assert lunes["n_comidas_total"] == 4
        assert lunes["n_comidas_con_alimentos"] == 4
        assert lunes["estado"] == "montada"

    def test_un_dia_de_descanso_sale_como_descanso(self, semana_montada, cabeceras_cliente):
        dias = _semana(cabeceras_cliente, FECHAS[0])["dias"]
        miercoles = next(d for d in dias if d["fecha"] == FECHAS[2])
        assert miercoles["tipo_dia"] == "descanso"
        # Un día de descanso no lleva nombre de entreno ni entreno hecho.
        assert miercoles["entreno"]["nombre"] is None
        lunes = next(d for d in dias if d["fecha"] == FECHAS[0])
        assert lunes["tipo_dia"] == "entrenamiento"

    def test_los_macros_del_dia_montado_suman(self, semana_montada, cabeceras_cliente):
        lunes = next(d for d in _semana(cabeceras_cliente, FECHAS[0])["dias"]
                     if d["fecha"] == FECHAS[0])
        m = lunes["macros"]
        assert set(m) == {"P", "H", "G"}
        if semana_montada["alimento_id"] != "no-existe":
            # Cuatro comidas de pollo tienen que sumar proteína; el peri va aparte y
            # los macros son los del motor de conteo (calibrar_dia), no una clave leída
            # a mano, así que basta con que el total sea de verdad mayor que cero.
            assert m["P"] > 0

    def test_el_resumen_cuadra_con_los_dias(self, semana_montada, cabeceras_cliente):
        data = _semana(cabeceras_cliente, FECHAS[0])
        r = data["resumen"]
        assert r["montadas"] == 1
        assert r["empezadas"] == 2
        assert r["sin_montar"] == 4
        # Los entrenos: N son los días de entreno resueltos de ESTA semana, y los
        # hechos o son un número o son null (cuando el registro de sesiones está
        # apagado no se inventa un «0 de N»).
        de_entreno = sum(1 for d in data["dias"] if d["tipo_dia"] == "entrenamiento")
        assert r["entrenos_total"] == de_entreno
        assert r["entrenos_hechos"] is None or isinstance(r["entrenos_hechos"], int)
        assert "hoy" in data

    def test_fecha_invalida_da_400(self, api_disponible, cabeceras_cliente):
        r = requests.get(f"{API}/diets/semana", params={"inicio": "esto-no-es-fecha"},
                         headers=cabeceras_cliente, timeout=15)
        assert r.status_code == 400

    def test_sin_token_no_hay_semana(self, api_disponible):
        r = requests.get(f"{API}/diets/semana", timeout=15)
        assert r.status_code in (401, 403)
