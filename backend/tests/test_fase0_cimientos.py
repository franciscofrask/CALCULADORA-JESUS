"""
Los cimientos del doc 16-08 (fase 0): la hora de España, la rotación de variantes
y la mezcla de interruptores de pantalla. Todo puro: sin base y sin servidor.
"""
from datetime import datetime, timezone

import pytest

from core.avisos_cliente import rotar_variante
from core.tiempo import MADRID, a_madrid, a_utc, ahora_madrid, hoy_madrid
from routes.settings import PANTALLAS, _mezclar_pantallas


# ── core/tiempo ───────────────────────────────────────────────────────────────

def test_a_madrid_convierte_utc_de_verano():
    # En agosto Madrid va dos horas por delante de UTC.
    d = a_madrid("2026-08-16T16:00:00+00:00")
    assert (d.hour, d.minute) == (18, 0)
    assert d.tzinfo is not None


def test_a_madrid_convierte_utc_de_invierno():
    # Y en enero, una.
    d = a_madrid("2026-01-16T16:00:00+00:00")
    assert d.hour == 17


def test_a_madrid_sin_zona_asume_utc():
    # Mongo guarda ISOs sin zona: son UTC, como escribe todo el backend.
    d = a_madrid("2026-08-16T22:30:00")
    assert d.day == 17 and d.hour == 0 and d.minute == 30


def test_a_madrid_aguanta_basura():
    assert a_madrid(None) is None
    assert a_madrid("esto no es una fecha") is None


def test_ida_y_vuelta():
    original = datetime(2026, 8, 17, 18, 0, tzinfo=MADRID)   # el lunes 17 a las 18:00
    assert a_utc(original).hour == 16
    assert a_madrid(a_utc(original)) == original


def test_el_dia_del_cliente_no_es_el_de_utc():
    # A las 23:30 de Madrid, en UTC ya es mañana. El día del cliente manda.
    tarde = datetime(2026, 8, 16, 23, 30, tzinfo=MADRID)
    assert a_utc(tarde).day == 16 and a_utc(tarde).hour == 21
    assert ahora_madrid().tzinfo is not None
    assert hoy_madrid() == ahora_madrid().date()


# ── rotación de variantes (regla 6 del doc) ──────────────────────────────────

VARIANTES = [
    {"titulo": "Cierra tu día", "cuerpo": "Dos toques y listo."},
    {"titulo": "¿Cómo fuiste hoy?", "cuerpo": "Un minuto y lo tengo."},
    {"titulo": "Te falta cerrar el día", "cuerpo": "Lo que no apuntas, no lo veo."},
]


def test_la_primera_vez_sale_la_primera():
    v = rotar_variante(VARIANTES, None)
    assert v["titulo"] == "Cierra tu día" and v["variante"] == 0


def test_nunca_la_misma_dos_veces_seguidas():
    ultima = None
    vistos = []
    for _ in range(7):
        v = rotar_variante(VARIANTES, ultima)
        if vistos:
            assert v["variante"] != vistos[-1]
        vistos.append(v["variante"])
        ultima = v["variante"]
    # Y rota por todas, no alterna entre dos.
    assert set(vistos) == {0, 1, 2}


def test_con_una_sola_variante_no_se_rompe():
    # "nunca la misma dos veces" no puede impedir avisar cuando solo hay un texto.
    v = rotar_variante([{"titulo": "Te lo he aplazado 7 días"}], 0)
    assert v["variante"] == 0


def test_sin_variantes_es_un_error():
    with pytest.raises(ValueError):
        rotar_variante([], None)


# ── interruptores de pantalla ────────────────────────────────────────────────

def test_defaults_sin_nada_guardado():
    pantallas = _mezclar_pantallas(None)
    assert pantallas == {k: bool(v) for k, v in PANTALLAS.items()}
    # Las pantallas nuevas nacen apagadas; la de suplementos ya existía.
    assert pantallas["t2_suplementos"] is True
    assert pantallas["t3_entreno"] is False


def test_lo_tocado_en_el_panel_manda():
    pantallas = _mezclar_pantallas({"t3_entreno": True, "t2_suplementos": False})
    assert pantallas["t3_entreno"] is True
    assert pantallas["t2_suplementos"] is False


def test_una_clave_vieja_no_resucita():
    # Un interruptor que ya no existe en el código no se sirve aunque siga en la base.
    pantallas = _mezclar_pantallas({"pantalla_que_ya_no_existe": True})
    assert "pantalla_que_ya_no_existe" not in pantallas
