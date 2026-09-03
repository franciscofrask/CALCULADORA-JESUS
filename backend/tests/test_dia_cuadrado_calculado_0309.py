"""EL DIA CUADRA O NO SE CALCULA, NO SE LEE DE UNA MARCA (3-09-2026).

El color de Mi semana y del calendario salia de `diets.is_cuadrado`, una marca guardada que
solo escribia la pantalla de Nutricion al guardar. Medido en dev: 42.747 dias de dieta y 3
en verde, y uno de esos 3 se pasaba 71 g de hidratos. O sea que fallaba en las dos
direcciones, que es lo que reporto Gonzalo: «no hay ninguna diferencia cuando esta cuadrado
y cuando no».

La regla es la del informe del mes y ahora vive en un solo sitio, `core/dia_cuadrado`, para
que el «cuadraste los macros N dias» del reporte y los dias verdes del calendario salgan del
mismo calculo sobre los mismos datos.

Funcion pura: se prueba sin base ni servidor. Lo de la pantalla se comprobo en el navegador
(`_guia/_probar_naranja_semana.js`).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.dia_cuadrado import MARGEN_VALIDO, cuadra      # noqa: E402

OBJETIVO = {"P": 300.0, "H": 200.0, "G": 80.0}


def test_clavado_cuadra():
    assert cuadra({"P": 300, "H": 200, "G": 80}, OBJETIVO) is True


def test_dentro_de_los_cuatro_gramos_tambien():
    assert cuadra({"P": 296, "H": 204, "G": 76}, OBJETIVO) is True


def test_pasarse_de_proteina_no_es_un_fallo():
    # Jesus, 13-08: la proteina cuenta como hecha en cuanto esta CUBIERTA. Un dia con 60 g
    # de proteina de mas sigue siendo un dia cuadrado.
    assert cuadra({"P": 360, "H": 200, "G": 80}, OBJETIVO) is True


def test_quedarse_corto_de_proteina_si():
    assert cuadra({"P": 295, "H": 200, "G": 80}, OBJETIVO) is False


def test_el_dia_del_22_de_diciembre():
    # El caso real que tenia la marca en verde: 351 de hidratos sobre 280, o sea 71 de mas.
    assert cuadra({"P": 300, "H": 271, "G": 80}, {"P": 300, "H": 200, "G": 80}) is False


def test_pasarse_de_hidratos_o_de_grasa_descuadra_el_dia():
    assert cuadra({"P": 300, "H": 205, "G": 80}, OBJETIVO) is False
    assert cuadra({"P": 300, "H": 200, "G": 85}, OBJETIVO) is False


def test_sin_objetivo_no_se_juzga():
    # Decir «no cuadra» de un dia del que no sabemos que se le pedia es acusarle de algo
    # que no se ha medido.
    assert cuadra({"P": 300, "H": 200, "G": 80}, {}) is None
    assert cuadra({"P": 300, "H": 200, "G": 80}, {"P": 0, "H": 0, "G": 0}) is None


def test_el_margen_es_el_de_la_casa():
    assert MARGEN_VALIDO == 4
