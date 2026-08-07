# -*- coding: utf-8 -*-
"""La tabla se acaba, y hay que decirlo.

La tabla llega a 120 kg y 45 % en hombres (50 % en mujeres). Quien pasa de ahí no recibe
su fila: recibe la del extremo. Hasta el 06-08-2026 eso pasaba en silencio, y el avatar
más numeroso de Jesús es justo el que llega gordo -- hay clientes que entraron al 44 %.

Lo que se fija aquí: el cálculo NO cambia (no hay otra fila que usar), pero deja de ser
mudo.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from macro_engine import calcular_macros_v2                       # noqa: E402
from target_calculator import calcular_targets                    # noqa: E402


class TestDentroDeLaTablaNoAvisa:
    def test_un_caso_normal_no_dispara_nada(self):
        t = calcular_targets(85, "hombre", 25, "definicion")
        assert t["lookup"]["fuera_de_tabla"] == []

    def test_justo_en_el_borde_tampoco(self):
        """120 kg y 45 % son filas de verdad: el aviso es para lo que se sale, no para el borde."""
        t = calcular_targets(120, "hombre", 45, "definicion")
        assert t["lookup"]["fuera_de_tabla"] == []

    def test_el_borde_de_mujer(self):
        """Ojo, los topes NO son los mismos: ellas llegan a 115 kg (ellos a 120) y al
        50 % de grasa (ellos al 45)."""
        t = calcular_targets(115, "mujer", 50, "definicion")
        assert t["lookup"]["fuera_de_tabla"] == []

    def test_una_mujer_de_120_ya_se_sale(self):
        t = calcular_targets(120, "mujer", 40, "definicion")
        assert [a["campo"] for a in t["lookup"]["fuera_de_tabla"]] == ["peso"]


class TestCuandoSeSaleAvisa:
    def test_el_caso_del_documento(self):
        """130 kg al 40 %: no tiene fila y se le pega al tope."""
        t = calcular_targets(130, "hombre", 40, "definicion")
        avisos = t["lookup"]["fuera_de_tabla"]
        assert len(avisos) == 1
        assert avisos[0]["campo"] == "peso"
        assert avisos[0]["valor"] == 130 and avisos[0]["tope"] == 120

    def test_grasa_por_encima_del_tope(self):
        t = calcular_targets(100, "hombre", 48, "definicion")
        campos = [a["campo"] for a in t["lookup"]["fuera_de_tabla"]]
        assert campos == ["porcentaje_graso"]

    def test_los_dos_a_la_vez(self):
        t = calcular_targets(140, "hombre", 50, "definicion")
        campos = {a["campo"] for a in t["lookup"]["fuera_de_tabla"]}
        assert campos == {"peso", "porcentaje_graso"}

    def test_tambien_por_abajo(self):
        """Alguien muy delgado o muy ligero tiene el mismo problema al revés."""
        t = calcular_targets(50, "hombre", 8, "volumen")
        campos = {a["campo"] for a in t["lookup"]["fuera_de_tabla"]}
        assert campos == {"peso", "porcentaje_graso"}

    def test_la_mujer_tiene_sus_propios_topes(self):
        """El 48 % es fila de verdad en mujeres (llegan al 50) y tope en hombres (45)."""
        assert calcular_targets(100, "mujer", 48, "definicion")["lookup"]["fuera_de_tabla"] == []
        assert calcular_targets(100, "hombre", 48, "definicion")["lookup"]["fuera_de_tabla"] != []

    def test_el_aviso_se_puede_leer(self):
        aviso = calcular_targets(130, "hombre", 40, "definicion")["lookup"]["fuera_de_tabla"][0]
        assert "130" in aviso["detalle"] and "120" in aviso["detalle"]


class TestElMotorLoArrastra:
    """De nada sirve avisar en la tabla si el motor se lo come."""

    def test_el_motor_devuelve_el_aviso(self):
        r = calcular_macros_v2(130, "hombre", 40, "definicion")
        assert r["fuera_de_tabla"], "el motor se comió el aviso de la tabla"
        assert r["fuera_de_tabla"][0]["campo"] == "peso"

    def test_y_aparece_en_el_desglose(self):
        r = calcular_macros_v2(130, "hombre", 40, "definicion")
        pasos = [p["paso"] for p in r["desglose"]]
        assert "fuera_de_tabla" in pasos

    def test_un_caso_normal_no_lo_lleva(self):
        r = calcular_macros_v2(85, "hombre", 25, "definicion")
        assert r["fuera_de_tabla"] == []
        assert "fuera_de_tabla" not in [p["paso"] for p in r["desglose"]]

    def test_el_calculo_NO_cambia(self):
        """Esto solo avisa. Los números tienen que ser exactamente los de antes."""
        con_aviso = calcular_macros_v2(130, "hombre", 40, "definicion")
        en_el_tope = calcular_macros_v2(120, "hombre", 40, "definicion")
        assert con_aviso["macros"] == en_el_tope["macros"]
