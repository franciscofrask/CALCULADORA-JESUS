"""
Macros reales (los de la etiqueta) frente a los del metodo.

El switch de la pestaña de Nutricion enseña las dos cifras. Estos tests fijan que:
  - `macros_reales` NO aplica ninguna regla del metodo (ni ye() ni el 25%),
  - escala igual que `macros_efectivos`, para que las dos cifras sean comparables,
  - y que es SOLO informativo: no toca lo que cuenta.
"""
import pytest

from calma_suggest import macros_efectivos, macros_reales


PAN = {"nombre": "Pan de molde", "proteinas": 9, "hidratos": 50, "grasas": 3,
       "racion": 100, "categorias": "8.1"}
ALMENDRAS = {"nombre": "Almendras", "proteinas": 21, "hidratos": 5, "grasas": 53,
             "racion": 100, "categorias": "17.2"}
POLLO = {"nombre": "Pechuga de pollo", "proteinas": 20, "hidratos": 0, "grasas": 0,
         "racion": 100, "categorias": "2.2.1"}


class TestLaEtiquetaNoSeToca:
    def test_da_lo_que_pone_el_paquete(self):
        # 100 g de pan son 9 P por etiqueta, cuente o no el metodo.
        assert macros_reales(PAN, 100) == {"P": 9.0, "H": 50.0, "G": 3.0}

    def test_proteina_del_pan_no_cuenta_pero_si_se_ve(self):
        # La regla del metodo: la proteina de un cereal solo cuenta si P > H/3.
        # 9 no supera 50/3, asi que el metodo la ignora y la etiqueta no.
        assert macros_efectivos(PAN, 100)["P"] == 0
        assert macros_reales(PAN, 100)["P"] == 9.0

    def test_proteina_de_los_frutos_secos_no_cuenta_pero_si_se_ve(self):
        assert macros_efectivos(ALMENDRAS, 100)["P"] == 0
        assert macros_reales(ALMENDRAS, 100)["P"] == 21.0

    def test_cuando_el_metodo_lo_cuenta_todo_las_dos_cifras_coinciden(self):
        assert macros_efectivos(POLLO, 150) == macros_reales(POLLO, 150)


class TestEscalado:
    def test_granel_escala_por_100_no_por_racion(self):
        """Un plato preparado con racion 250 sigue siendo "por 100 g" en granel.

        `calma_engine.calcular_macros_brutos` divide siempre por racion y aqui daria
        otra cifra; esa es justo la razon de no reutilizarla.
        """
        plato = {"nombre": "Lasaña", "proteinas": 8, "hidratos": 12, "grasas": 6,
                 "racion": 250, "categorias": "2.2.1"}
        assert macros_reales(plato, 250) == {"P": 20.0, "H": 30.0, "G": 15.0}

    def test_unidades_escalan_por_racion(self):
        huevo = {"nombre": "Huevo L", "proteinas": 8, "hidratos": 0, "grasas": 6,
                 "racion": 60, "unidades": True, "categorias": "3.1"}
        assert macros_reales(huevo, 120) == {"P": 16.0, "H": 0.0, "G": 12.0}

    def test_misma_escala_que_el_metodo(self):
        """Las dos cifras del switch tienen que ser comparables entre si."""
        for cantidad in (50, 100, 173.5, 250):
            assert macros_efectivos(POLLO, cantidad)["P"] == pytest.approx(
                macros_reales(POLLO, cantidad)["P"], abs=0.01)

    def test_cantidad_cero(self):
        assert macros_reales(PAN, 0) == {"P": 0.0, "H": 0.0, "G": 0.0}


class TestAlimentosIncompletos:
    def test_macros_a_none_no_revientan(self):
        raro = {"nombre": "Sin datos", "proteinas": None, "hidratos": None,
                "grasas": None, "racion": 100}
        assert macros_reales(raro, 100) == {"P": 0.0, "H": 0.0, "G": 0.0}

    def test_sin_racion_asume_100(self):
        sin_racion = {"nombre": "X", "proteinas": 10, "hidratos": 0, "grasas": 0}
        assert macros_reales(sin_racion, 200)["P"] == 20.0

    def test_racion_cero_no_divide_por_cero(self):
        cero = {"nombre": "X", "proteinas": 10, "hidratos": 0, "grasas": 0, "racion": 0}
        assert macros_reales(cero, 100)["P"] == 10.0


class TestNoContamina:
    def test_no_modifica_el_alimento(self):
        """Se llama con fichas del catalogo: no puede dejarlas tocadas."""
        antes = dict(PAN)
        macros_reales(PAN, 100)
        assert PAN == antes

    def test_no_cambia_lo_que_cuenta(self):
        """Llamar a macros_reales no altera el resultado de macros_efectivos."""
        antes = macros_efectivos(PAN, 100)
        macros_reales(PAN, 100)
        assert macros_efectivos(PAN, 100) == antes
