"""Los tres modificadores del quiz (punto 11 del doc del 07-08).

Son actividad diaria, deporte extra y cómo engorda, y el documento fija ocho reglas:

  1. Solo tocan los hidratos: nunca la proteína ni el perientreno.
  2. Solo suben, nunca bajan. Al sedentario no se le quita nada.
  3. Se suman entre sí y se aplican UNA sola vez sobre el valor de la tabla, no en cadena.
  4. Actividad diaria: muy activo, +10 % en entreno y en descanso. Sedentario y normal, nada.
  5. Deporte extra: en definición +10 % y en volumen +20 %, los dos solo el día de descanso.
  6. Cómo engorda: "casi no lo noto" con grasa bajo el umbral, +20 % en los dos; por encima
     del umbral, nada; "engordo enseguida", veto: no sube nada aunque toque todo lo demás.
  7. Techo con todo activado: +30 % entreno y +40 % descanso.
  8. Si el descanso queda por encima del entreno, se sube el entreno hasta igualarlo. El
     perientreno no entra en esa comparación.
"""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from macro_engine import (calcular_macros_v2, MOD_MUY_ACTIVO_ENTRENO, MOD_NO_ENGORDA,
                          TOPE_SUBIDA_ENTRENO, TOPE_SUBIDA_DESCANSO, BF_MAX_NO_ENGORDA)

BASE = dict(peso=80, sexo="hombre", porcentaje_graso=18, dieta_reportada=None,
            farmacologia="no", historial_dietas="no", como_va=None)


def macros(actividad=None, deporte=None, engorda=None, objetivo="definicion", **extra):
    args = {**BASE, **extra}
    r = calcular_macros_v2(objetivo=objetivo, actividad_diaria=actividad,
                           deporte_extra=deporte, facilidad_engordar=engorda, **args)
    return r["macros"]


def hc(m):
    return (m["entreno"]["hidratos"], m["descanso"]["hidratos"])


SIN_NADA = macros()


class TestSoloTocanLosHidratos:
    """Regla 1: la proteína y el perientreno no se mueven pase lo que pase."""

    @pytest.mark.parametrize("kwargs", [
        {"actividad": "muy_activo"},
        {"deporte": True},
        {"engorda": "casi_no"},
        {"actividad": "muy_activo", "deporte": True, "engorda": "casi_no"},
    ])
    def test_la_proteina_y_el_peri_no_se_mueven(self, kwargs):
        m = macros(**kwargs)
        assert m["entreno"]["proteina"] == SIN_NADA["entreno"]["proteina"]
        assert m["descanso"]["proteina"] == SIN_NADA["descanso"]["proteina"]
        assert m["perientreno"] == SIN_NADA["perientreno"]

    def test_la_grasa_tampoco(self):
        m = macros(actividad="muy_activo", deporte=True, engorda="casi_no")
        assert m["entreno"]["grasa"] == SIN_NADA["entreno"]["grasa"]
        assert m["descanso"]["grasa"] == SIN_NADA["descanso"]["grasa"]


class TestSoloSubenNuncaBajan:
    """Regla 2."""

    @pytest.mark.parametrize("actividad", ["sedentario", "normal", None])
    def test_al_sedentario_no_se_le_quita(self, actividad):
        assert hc(macros(actividad=actividad)) == hc(SIN_NADA)

    def test_no_hay_combinacion_que_baje(self):
        for actividad in (None, "sedentario", "normal", "muy_activo"):
            for deporte in (None, False, True):
                for engorda in (None, "enseguida", "normal", "casi_no"):
                    e, d = hc(macros(actividad, deporte, engorda))
                    base_e, base_d = hc(SIN_NADA)
                    assert e >= base_e and d >= base_d, (actividad, deporte, engorda)


class TestActividadDiaria:
    """Regla 4."""

    def test_muy_activo_sube_los_dos_dias(self):
        e, d = hc(macros(actividad="muy_activo"))
        base_e, base_d = hc(SIN_NADA)
        assert e == pytest.approx(base_e * (1 + MOD_MUY_ACTIVO_ENTRENO), abs=5)
        assert d == pytest.approx(base_d * (1 + MOD_MUY_ACTIVO_ENTRENO), abs=5)


class TestDeporteExtra:
    """Regla 5: solo el día de descanso, y más en volumen que en definición."""

    def test_el_deporte_por_si_solo_no_sube_el_dia_de_entreno(self):
        """Sube el descanso; si al hacerlo lo deja por encima del entreno, el entreno sube
        detrás, pero por la regla 8, no por el deporte. Con la grasa baja el margen entre
        los dos días es suficiente para verlo aislado."""
        e, d = hc(macros(deporte=True, objetivo="definicion", porcentaje_graso=30))
        base_e, base_d = hc(macros(objetivo="definicion", porcentaje_graso=30))
        assert d > base_d, "el descanso sube"
        assert e == base_e or e == d, "el entreno solo se mueve para igualar al descanso"

    def test_en_volumen_sube_mas_que_en_definicion(self):
        _, d_def = hc(macros(deporte=True, objetivo="definicion"))
        _, d_vol = hc(macros(deporte=True, objetivo="volumen"))
        base_def = hc(macros(objetivo="definicion"))[1]
        base_vol = hc(macros(objetivo="volumen"))[1]
        assert (d_vol - base_vol) / base_vol > (d_def - base_def) / base_def


class TestComoEngorda:
    """Regla 6, con el veto incluido."""

    def test_casi_no_engordo_y_grasa_baja_sube_los_dos(self):
        e, d = hc(macros(engorda="casi_no", porcentaje_graso=15))
        base = macros(porcentaje_graso=15)
        assert e > base["entreno"]["hidratos"] and d > base["descanso"]["hidratos"]

    def test_con_grasa_por_encima_del_umbral_no_sube(self):
        limite = BF_MAX_NO_ENGORDA["hombre"]
        con = macros(engorda="casi_no", porcentaje_graso=limite + 5)
        sin = macros(porcentaje_graso=limite + 5)
        assert hc(con) == hc(sin)

    def test_engordo_enseguida_veta_todo_lo_demas(self):
        """Aunque sea muy activo y juegue al pádel, no sube nada."""
        vetado = macros(actividad="muy_activo", deporte=True, engorda="enseguida")
        assert hc(vetado) == hc(SIN_NADA)

    def test_sin_el_veto_esa_misma_combinacion_si_subiria(self):
        # Comprueba que el test de arriba no pasa por casualidad.
        sin_veto = macros(actividad="muy_activo", deporte=True, engorda="casi_no")
        assert hc(sin_veto) != hc(SIN_NADA)


class TestElTecho:
    """Regla 7: +30 % entreno y +40 % descanso con todo activado."""

    @pytest.mark.parametrize("objetivo", ["definicion", "volumen"])
    def test_el_descanso_no_pasa_del_cuarenta_por_ciento(self, objetivo):
        base_d = hc(macros(objetivo=objetivo, porcentaje_graso=15))[1]
        d = hc(macros("muy_activo", True, "casi_no", objetivo=objetivo, porcentaje_graso=15))[1]
        assert d <= base_d * (1 + TOPE_SUBIDA_DESCANSO) + 5

    @pytest.mark.parametrize("objetivo", ["definicion", "volumen"])
    def test_el_entreno_no_pasa_del_treinta_salvo_por_igualar_al_descanso(self, objetivo):
        """El techo se aplica ANTES de la comprobación final. Si el descanso, con su techo
        del 40 %, acaba por encima del entreno con el suyo del 30 %, el entreno sube hasta
        igualarlo y se queda por encima de su propio techo. Es lo que sale de juntar las dos
        reglas del documento, y en volumen pasa: 234 de entreno contra 238 de descanso."""
        base_e = hc(macros(objetivo=objetivo, porcentaje_graso=15))[0]
        e, d = hc(macros("muy_activo", True, "casi_no", objetivo=objetivo, porcentaje_graso=15))
        techo = base_e * (1 + TOPE_SUBIDA_ENTRENO) + 5
        assert e <= techo or e == d, f"{e} pasa del techo sin ser por igualar al descanso"


class TestElDescansoNuncaPorEncima:
    """Regla 8."""

    @pytest.mark.parametrize("objetivo", ["definicion", "volumen"])
    @pytest.mark.parametrize("actividad", [None, "muy_activo"])
    @pytest.mark.parametrize("deporte", [None, True])
    @pytest.mark.parametrize("engorda", [None, "casi_no"])
    def test_el_descanso_nunca_supera_al_entreno(self, objetivo, actividad, deporte, engorda):
        e, d = hc(macros(actividad, deporte, engorda, objetivo=objetivo, porcentaje_graso=15))
        assert d <= e, f"descanso {d} > entreno {e}"

    @pytest.mark.parametrize("objetivo", ["definicion", "volumen"])
    def test_el_peri_no_entra_en_la_comparacion(self, objetivo):
        """El peri va aparte: ni lo tocan los modificadores ni cuenta para igualar los días."""
        base = macros(objetivo=objetivo, porcentaje_graso=15)
        con_todo = macros("muy_activo", True, "casi_no", objetivo=objetivo, porcentaje_graso=15)
        assert con_todo["perientreno"] == base["perientreno"]


class TestSeSumanYSeAplicanUnaVez:
    """Regla 3: sumados sobre el valor de tabla, no encadenados uno tras otro."""

    def test_la_subida_conjunta_es_la_suma_no_el_producto(self):
        base_e = hc(macros(porcentaje_graso=15))[0]
        e = hc(macros("muy_activo", None, "casi_no", porcentaje_graso=15))[0]
        sumado = base_e * (1 + MOD_MUY_ACTIVO_ENTRENO + MOD_NO_ENGORDA)
        encadenado = base_e * (1 + MOD_MUY_ACTIVO_ENTRENO) * (1 + MOD_NO_ENGORDA)
        assert abs(e - sumado) < abs(e - encadenado) or e == pytest.approx(sumado, abs=5)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
