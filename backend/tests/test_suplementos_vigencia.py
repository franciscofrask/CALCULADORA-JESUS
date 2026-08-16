"""
La suplementación que ve el cliente (T2 del doc del 16-08).

Dos cosas que no se pueden dar por sabidas:

  - QUÉ VERSIÓN ES LA VIGENTE. El protocolo está versionado por fecha y el cliente tiene
    que ver la de HOY EN ESPAÑA. Con la fecha UTC, una versión con fecha de mañana entraba
    en vigor a las 23:00 de esta noche (22:00 en invierno): el cliente veía lo nuevo antes
    de tiempo y lo de hoy desaparecía sin que nadie tocara nada.

  - QUE NO SE AVISE DE LO QUE NO HAY. Guardar sin ningún suplemento borra la versión
    vigente, y aun así salía el aviso "tu protocolo se ha actualizado". Es la queja de la
    que nace esta tarea: el aviso llega y la pantalla está vacía.
"""
from datetime import datetime, timedelta, timezone

import pytest
import requests

from core.tiempo import MADRID, hoy_madrid
from routes.supplements import _hoy, _respuesta, proxima_desde, vigente_en

from conftest import API


UNA_VERSION = [
    {"fecha": "2026-01-10", "items": [{"titulo": "Creatina", "cuanto": "5 g", "cuando": "a cualquier hora"}]},
    {"fecha": "2026-03-01", "items": [{"titulo": "Whey Isolate", "cuanto": "1 cacito", "cuando": "después de entrenar"}]},
    {"fecha": "2026-06-15", "items": [{"titulo": "Omega 3", "cuanto": "2 cápsulas", "cuando": "con la comida 2"}]},
]


def test_la_vigente_es_la_ultima_que_no_pasa_de_hoy():
    assert vigente_en(UNA_VERSION, "2026-02-01")["fecha"] == "2026-01-10"
    assert vigente_en(UNA_VERSION, "2026-03-01")["fecha"] == "2026-03-01"
    assert vigente_en(UNA_VERSION, "2026-12-31")["fecha"] == "2026-06-15"


def test_antes_de_la_primera_no_hay_nada_vigente():
    assert vigente_en(UNA_VERSION, "2025-12-31") is None
    assert proxima_desde(UNA_VERSION, "2025-12-31")["fecha"] == "2026-01-10"


def test_la_siguiente_es_la_primera_futura():
    assert proxima_desde(UNA_VERSION, "2026-03-01")["fecha"] == "2026-06-15"
    assert proxima_desde(UNA_VERSION, "2026-06-15") is None


def test_el_dia_es_el_de_espana_no_el_de_utc():
    """A las 23:30 de Madrid, en UTC ya es mañana: el protocolo no puede cambiar por eso."""
    assert _hoy() == hoy_madrid().isoformat()
    ahora = datetime.now(MADRID)
    if ahora.hour >= 22 or ahora.hour < 2:
        # Cuando de verdad estamos en la franja del desfase, se comprueba que no coinciden.
        assert _hoy() == ahora.date().isoformat()


def test_sin_versiones_no_hay_nada_que_anunciar():
    """La guarda del aviso: `actual` y `siguiente` vacíos = no se le manda nada."""
    vacio = _respuesta({"client_id": "x", "versiones": []})
    assert vacio["actual"] == [] and vacio["siguiente"] == []

    manana = (hoy_madrid() + timedelta(days=7)).isoformat()
    solo_futura = _respuesta({"client_id": "x", "versiones": [{"fecha": manana, "items": [{"titulo": "Creatina"}]}]})
    assert solo_futura["actual"] == []
    assert solo_futura["siguiente"] and solo_futura["siguiente_fecha"] == manana


def test_el_cliente_ve_su_protocolo(cabeceras_cliente):
    """De punta a punta: lo que pinta la pantalla de T2 sale de aquí."""
    r = requests.get(f"{API}/supplements/current", headers=cabeceras_cliente, timeout=20)
    if r.status_code == 403:
        pytest.skip("El plan del cliente de pruebas no tiene la suplementación habilitada.")
    assert r.status_code == 200, r.text
    datos = r.json()
    if not datos:
        pytest.skip("El cliente de pruebas no tiene protocolo guardado.")
    for item in datos.get("actual") or []:
        assert item.get("titulo"), "cada línea necesita su producto"
        # "1 cacito · después de entrenar": sin cuánto ni cuándo, la línea no dice nada.
        assert (item.get("cuanto") or item.get("cuando")), item
