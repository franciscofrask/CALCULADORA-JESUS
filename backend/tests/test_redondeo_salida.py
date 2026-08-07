"""Redondeo de las cantidades que se le enseñan al cliente (punto 4 del doc del 07-08).

Regla de Jesús: unidades enteras o medias; verduras y bebidas vegetales de 50 en 50; salsas
y todo lo demás de 5 en 5; y los macros del día con la proteína y la grasa enteras y los
hidratos de 5 en 5. Siempre a la baja, porque pasarse descuadra la comida y quedarse corto lo
absorbe el resto del menú.
"""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from redondeo_salida import (paso_en_gramos, redondear_a_la_baja, redondear_cantidad,
                             redondear_macros_dia)


def _f(nombre, cat, unidades=False, racion=100):
    return {"nombre": nombre, "categorias": cat, "unidades": unidades, "racion": racion}


PECHUGA = _f("Pechuga de pollo", "2.2.1")
WHEY = _f("Proteína de suero", "4.1.1")
TOMATE = _f("Tomate", "13.1")
BEBIDA = _f("Bebida de avena", "24")
SALSA = _f("Salsa zero", "16.1")
KONJAC = _f("Konjac", "16.4")
ACEITE = _f("Aceite de oliva", "17.1.1")
HUEVO = _f("Huevo M", "1.2", unidades=True, racion=55)
LATA = _f("Atún en lata", "3.8", unidades=True, racion=52)


class TestElPasoDeCadaAlimento:
    def test_verduras_y_bebidas_vegetales_de_50_en_50(self):
        assert paso_en_gramos(TOMATE) == 50.0
        assert paso_en_gramos(BEBIDA) == 50.0

    def test_salsas_y_el_resto_de_5_en_5(self):
        assert paso_en_gramos(SALSA) == 5.0
        assert paso_en_gramos(PECHUGA) == 5.0
        assert paso_en_gramos(WHEY) == 5.0
        assert paso_en_gramos(ACEITE) == 5.0

    def test_el_konjac_va_con_las_verduras(self):
        # No es una salsa aunque comparta el 16: se come en paquetes grandes.
        assert paso_en_gramos(KONJAC) == 50.0

    def test_por_unidades_media_unidad(self):
        assert paso_en_gramos(HUEVO) == 27.5     # medio huevo de 55 g
        assert paso_en_gramos(LATA) == 26.0      # media lata de 52 g


class TestLosCasosDelDocumento:
    """Los cuatro ejemplos que trae el punto 4."""

    def test_223_de_pechuga(self):
        assert redondear_cantidad(PECHUGA, 223) == 220.0

    def test_42_de_whey(self):
        assert redondear_cantidad(WHEY, 42) == 40.0

    def test_102_de_tomate(self):
        assert redondear_cantidad(TOMATE, 102) == 100.0

    @pytest.mark.parametrize("alimento,cantidad,esperado", [
        (BEBIDA, 182.5, 150.0),
        (PECHUGA, 120.1, 120.0),
        (ACEITE, 62.8, 60.0),
    ])
    def test_los_menus_dejan_de_salir_con_decimales(self, alimento, cantidad, esperado):
        assert redondear_cantidad(alimento, cantidad) == esperado


class TestSiempreALaBaja:
    @pytest.mark.parametrize("cantidad", [221, 222, 223, 224, 224.9])
    def test_nunca_sube(self, cantidad):
        r = redondear_cantidad(PECHUGA, cantidad)
        assert r == 220.0 and r <= cantidad

    def test_lo_que_ya_es_redondo_no_se_toca(self):
        assert redondear_cantidad(PECHUGA, 220) == 220.0
        assert redondear_cantidad(TOMATE, 150) == 150.0
        assert redondear_cantidad(HUEVO, 110) == 110.0   # 2 huevos justos

    def test_un_float_feo_no_baja_un_multiplo_entero(self):
        # 149,99999 es un 150 mal contado, no un 100.
        assert redondear_cantidad(TOMATE, 149.99999999) == 150.0


class TestUnidadesEnterasOMedias:
    def test_dos_huevos_y_tres_cuartos_bajan_a_dos_y_medio(self):
        assert redondear_cantidad(HUEVO, 151.0) == 137.5   # 2,75 ud -> 2,5 ud

    def test_una_lata_justa_se_respeta(self):
        assert redondear_cantidad(LATA, 52.0, minimo_g=26) == 52.0

    @pytest.mark.parametrize("unidades", [0.5, 1.0, 1.5, 2.0, 2.5, 3.0])
    def test_las_medias_unidades_sobreviven(self, unidades):
        gramos = unidades * 55
        assert redondear_cantidad(HUEVO, gramos) == pytest.approx(gramos)


class TestElSueloDelMinimo:
    """Un paso grande no puede hacer desaparecer el alimento del plato."""

    def test_treinta_gramos_de_verdura_no_se_quedan_en_cero(self):
        assert redondear_cantidad(TOMATE, 30, minimo_g=5) == 30.0

    def test_cae_al_multiplo_de_5_cuando_el_de_50_no_llega(self):
        assert redondear_cantidad(TOMATE, 49, minimo_g=5) == 45.0

    def test_por_debajo_del_minimo_se_deja_como_venia(self):
        # Falsear 4 g de aceite a 0 sería peor que enseñar un número poco redondo.
        assert redondear_cantidad(ACEITE, 4, minimo_g=5) == 4.0

    def test_cantidad_cero_o_negativa_no_revienta(self):
        assert redondear_cantidad(PECHUGA, 0) == 0
        assert redondear_a_la_baja(10, 0) == 10     # paso 0: se devuelve tal cual


class TestMacrosDelDia:
    def test_proteina_y_grasa_enteras_hidratos_de_cinco_en_cinco(self):
        assert redondear_macros_dia({"P": 190.4, "H": 182.3, "G": 60.7}) == {
            "P": 190.0, "H": 180.0, "G": 61.0}

    def test_entiende_los_nombres_en_ingles(self):
        assert redondear_macros_dia({"protein": 147.6, "carbs": 203.1, "fat": 58.2}) == {
            "protein": 148.0, "carbs": 205.0, "fat": 58.0}

    def test_conserva_las_demas_claves(self):
        r = redondear_macros_dia({"P": 190.4, "H": 182.3, "G": 60.7, "calories": 2120.0})
        assert r["calories"] == 2120.0

    def test_vacio_o_none_no_revienta(self):
        assert redondear_macros_dia({}) == {}
        assert redondear_macros_dia(None) is None


class TestElMotorYaDaMacrosRedondos:
    """Los macros del día que calcula la app ya cumplen la regla sin tener que retocarlos.

    Se comprobó sobre los 232 clientes que hay en la base y ninguno la incumple, así que
    `redondear_macros_dia` no se aplica en ninguna ruta: sería tapar con un parche algo que
    ya sale bien. Estos tests son la alarma de que dejara de salir bien.
    """

    @pytest.mark.parametrize("peso,sexo,graso,objetivo", [
        (80, "hombre", 20, "definicion"),
        (63.4, "mujer", 27.5, "volumen"),
        (91.2, "hombre", 32.3, "definicion"),
        (55.7, "mujer", 19.1, "definicion"),
        (104.3, "hombre", 41.8, "volumen"),
    ])
    def test_proteina_y_grasa_enteras_hidratos_de_cinco_en_cinco(self, peso, sexo, graso, objetivo):
        from macro_engine import calcular_macros_v2
        r = calcular_macros_v2(peso=peso, sexo=sexo, porcentaje_graso=graso, objetivo=objetivo,
                               actividad_diaria="media", deporte_extra="no",
                               facilidad_engordar="normal", dieta_reportada=None,
                               farmacologia="no", historial_dietas="no", como_va=None)
        for bloque, macros in r["macros"].items():
            for clave in ("proteina", "grasa"):
                if macros.get(clave) is not None:
                    assert float(macros[clave]) == round(float(macros[clave])), f"{bloque}.{clave}"
            if macros.get("hidratos") is not None:
                assert float(macros["hidratos"]) % 5 == 0, f"{bloque}.hidratos = {macros['hidratos']}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
