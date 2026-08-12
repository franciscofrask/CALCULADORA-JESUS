"""El peso que ve el cliente en «Mis macros» está saneado, como el del entrenador.

Jesús, 12-08-2026: «En el histórico de Mis macros los pesos van 77,1 → 94 → 75 → 50 → 118 kg.
Igual son mis propias pruebas, pero míralo».

Lo suyo sí eran pruebas (cuenta hola@jesusgallegopt.com, rol admin). Pero al mirarlo salió
que la pantalla del cliente era el ÚNICO camino que pintaba el peso crudo: el panel del
entrenador lo pasaba por `_sanea_peso` y este no. Medido en producción, en la serie que
ve el cliente hay 0,0 kg, un 0,433 (un porcentaje de grasa metido donde va el peso) y un
salto de 904 kg por un error de coma. Once cuentas de cliente con saltos de 15 kg o más.

La regla estaba escrita dos veces (routes/admin.py y macro_casos.py) y en la pantalla del
cliente ninguna de las dos. Ahora vive en `core.series_cliente`, con el rango del peso.
"""
import os
import sys

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _RAIZ)

import pytest  # noqa: E402

from core.series_cliente import PESO, sanea_peso  # noqa: E402


@pytest.mark.parametrize("crudo", [0, 0.0, 0.433, None, "", "vete a saber", -70, 24.9])
def test_lo_que_no_es_un_peso_no_se_enseña(crudo):
    assert sanea_peso(crudo) is None


@pytest.mark.parametrize("crudo,esperado", [
    (819, 81.9),        # el error de coma de tres cifras
    (51400, 51.4),      # y el de cinco
    (905, 90.5),        # el salto de 904 kg que hay en produccion
])
def test_el_error_de_coma_se_arregla(crudo, esperado):
    assert sanea_peso(crudo) == esperado


@pytest.mark.parametrize("crudo,esperado", [(77.1, 77.1), (94, 94.0), (118, 118.0), ("80.5", 80.5)])
def test_un_peso_normal_pasa_tal_cual(crudo, esperado):
    assert sanea_peso(crudo) == esperado


def test_usa_el_rango_de_la_serie_y_no_uno_suyo():
    """Si algún día se toca el rango del peso, esto va detrás solo.

    Por arriba no se comprueba el borde a propósito: un número de más de 300 no se descarta,
    se lee como un error de coma (301 son 30,1 kg), que es la razón de ser de esta función."""
    _serie, _campo, minimo, maximo = PESO
    assert sanea_peso(minimo - 0.1) is None
    assert sanea_peso((minimo + maximo) / 2) is not None


def test_las_dos_copias_viejas_dan_lo_mismo():
    """Estaban copiadas a mano en dos sitios; ahora delegan. Que no vuelvan a divergir."""
    from macro_casos import _sanea_peso as casos
    from routes.admin import _sanea_peso as admin
    for v in (0, 0.433, 819, 51400, 77.1, 300, 25, None, "x"):
        assert casos(v) == admin(v) == sanea_peso(v), f"discrepan en {v!r}"
