"""El peso es la misma serie en Mis macros y en Seguimiento. Punto 4 del 17-08.

«Mis macros: Ahora 77,1 kg · +2,1 kg · 106 pesajes. Seguimiento → Evolución: Ahora 50 kg ·
−25 kg · 100 pesajes. Misma gráfica, mismos puntos, resultado opuesto.»

Eran tres fuentes distintas para una curva:

  1. la serie `pesos` del perfil, que es la buena,
  2. los pesajes que viajaron con cada ajuste de macros (`macro_history`), que son los
     únicos que llegan hasta 2022 en los clientes que vinieron de Calma,
  3. el `weight` de los reportes, en crudo y cortado a cien.

Mis macros juntaba 1 y 2 saneando; Evolución usaba solo 3 y sin sanear. Se arreglaron por
partes y hasta que Francisco preguntó «¿ninguna miente, verdad?» quedó a medias: el «ahora»
ya coincidía, pero Evolución enseñaba 2 pesajes donde Mis macros enseñaba 5, porque le
faltaba la fuente 2.

Este test comprueba las reglas de las tres, sin Mongo.
"""
import os
import sys

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _RAIZ)

from core.series_cliente import sanea_peso  # noqa: E402


def _junta(serie_perfil, historial, reportes):
    """Las tres fuentes, con la regla que aplican ya las dos pantallas.

    Manda la serie del perfil; el historial rellena lo que falte; y el reporte, lo que
    siga faltando. Un día solo puede tener un peso.
    """
    pesos = {}
    for f, v in serie_perfil:
        v = sanea_peso(v)
        if v is not None:
            pesos[f] = v
    for f, v in historial:
        v = sanea_peso(v)
        if f not in pesos and v is not None:
            pesos[f] = v
    for f, v in reportes:
        v = sanea_peso(v)
        if f not in pesos and v is not None:
            pesos[f] = v
    return [(f, pesos[f]) for f in sorted(pesos)]


def test_el_historial_de_macros_aporta_los_pesajes_viejos():
    """Sin esta fuente la curva empieza el día que estrenamos la serie."""
    curva = _junta(serie_perfil=[("2026-08-16", 74.0)],
                   historial=[("2022-03-01", 88.0), ("2024-06-01", 80.0)],
                   reportes=[])
    assert [f for f, _ in curva] == ["2022-03-01", "2024-06-01", "2026-08-16"]


def test_la_serie_del_perfil_manda_sobre_las_otras_dos():
    """El mismo día no puede tener dos pesos según quién lo cuente."""
    curva = _junta(serie_perfil=[("2026-08-16", 74.0)],
                   historial=[("2026-08-16", 99.0)],
                   reportes=[("2026-08-16", 50.0)])
    assert curva == [("2026-08-16", 74.0)]


def test_los_pesos_imposibles_no_entran_por_ninguna_de_las_tres():
    """El 0,0 de los ajustes viejos y el 0,433 (un % de grasa en el sitio del peso)."""
    curva = _junta(serie_perfil=[("2026-01-01", 0)],
                   historial=[("2026-02-01", 0.433)],
                   reportes=[("2026-03-01", 819), ("2026-04-01", 77.1)])
    assert curva == [("2026-03-01", 81.9), ("2026-04-01", 77.1)]


def test_el_ahora_es_el_ultimo_por_fecha():
    """«Ahora 50 kg» salía de coger el último guardado en vez del último por fecha."""
    curva = _junta(serie_perfil=[("2026-08-16", 77.3), ("2026-06-21", 80.0)],
                   historial=[], reportes=[("2026-07-01", 50.0)])
    assert curva[-1] == ("2026-08-16", 77.3)
    assert round(curva[-1][1] - curva[0][1], 1) == -2.7
