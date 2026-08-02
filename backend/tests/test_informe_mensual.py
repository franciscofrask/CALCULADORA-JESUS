"""
El informe mensual del cliente (especificacion 31-07-2026, parte 6).

Lo que se fija aqui son las dos condiciones duras del documento y las reglas que no
pueden salir mal, porque este informe es lo unico que el cliente lee del mes:

  - sin fotos no se genera informe,
  - el ritmo objetivo sale de SU perfil y no es el mismo para todos,
  - el peso se cuenta en porcentaje, no en kilos,
  - el cumplimiento sale de lo registrado, no de preguntarle,
  - y al que va mal no se le maquilla el mes: se le dice por que no se le tocan.
"""
import pytest

from core.informe_mensual import (
    comparar_macros,
    evaluar_cumplimiento,
    evaluar_peso,
    explicacion_del_sistema,
    montar_informe,
    ritmo_objetivo,
)

PERFIL = {"goal": "definicion", "body_fat": 22.0, "week": 5, "plan": "reto12en12_gold",
          "training_days": 4, "macros_training": {"protein": 180, "carbs": 200, "fat": 60}}
HACE_UN_MES = "2026-07-02T10:00:00+00:00"
HOY = "2026-08-02T10:00:00+00:00"


class TestSinFotosNoHayInforme:
    """La condicion mas dura del documento."""

    def _montar(self, photos):
        return montar_informe(
            perfil=PERFIL, reporte={"weight": 80, "photos": photos, "created_at": HOY},
            reporte_anterior={"weight": 82, "created_at": HACE_UN_MES},
            fotos_dia_cero=["a.jpg"], semanas_ciclo=12,
            dias_dieta=20, dias_entreno=15, dias_periodo=28,
            macros_comidos={}, macros_nuevos=None,
            explicacion_equipo=None, la_escribe_el_equipo=False)

    def test_sin_fotos_no_se_genera(self):
        r = self._montar([])
        assert r["generado"] is False
        assert r["motivo"] == "sin_fotos"

    def test_fotos_a_none_tampoco(self):
        assert self._montar(None)["generado"] is False

    def test_con_fotos_si(self):
        assert self._montar(["frente.jpg"])["generado"] is True


class TestElRitmoNoEsElMismoParaTodos:
    """"el objetivo de ritmo sale de su perfil y no es el mismo para todos"."""

    def test_el_que_tiene_mucha_grasa_puede_bajar_mas_deprisa(self):
        gordo = ritmo_objetivo("definicion", 32.0)
        seco = ritmo_objetivo("definicion", 12.0)
        assert gordo["min"] < seco["min"], "con 32% se puede bajar mas rapido que con 12%"

    def test_en_definicion_el_objetivo_es_bajar(self):
        r = ritmo_objetivo("definicion", 25.0)
        assert r["sentido"] == "bajar" and r["max"] < 0

    def test_en_volumen_el_objetivo_es_subir(self):
        r = ritmo_objetivo("volumen", 15.0)
        assert r["sentido"] == "subir" and r["min"] > 0

    def test_en_volumen_con_grasa_de_sobra_se_sube_mas_despacio(self):
        graso = ritmo_objetivo("volumen", 25.0)
        seco = ritmo_objetivo("volumen", 12.0)
        assert graso["max"] < seco["max"]

    def test_recomposicion_es_mantenerse(self):
        assert ritmo_objetivo("recomposicion", 20.0)["sentido"] == "mantener"

    def test_sin_objetivo_no_revienta(self):
        assert ritmo_objetivo(None, None)["sentido"] == "bajar"


class TestElPesoEnPorcentaje:
    """"peso con el ritmo en porcentaje, no en kilos"."""

    def test_da_el_cambio_en_porcentaje(self):
        r = evaluar_peso(80.0, 82.0, HACE_UN_MES, HOY, "definicion", 22.0)
        assert r["cambio_pct"] == pytest.approx(-2.44, abs=0.05)
        assert r["cambio_kg"] == -2.0

    def test_los_mismos_kilos_pesan_distinto_segun_la_persona(self):
        """2 kg en alguien de 60 kg es mucho mas que en alguien de 120."""
        pequeno = evaluar_peso(58.0, 60.0, HACE_UN_MES, HOY, "definicion", 22.0)
        grande = evaluar_peso(118.0, 120.0, HACE_UN_MES, HOY, "definicion", 22.0)
        assert abs(pequeno["cambio_pct"]) > abs(grande["cambio_pct"])

    def test_bajando_a_buen_ritmo(self):
        # 82 -> 80 en un mes = -2.44 % total, -0.57 %/semana. Con 22 % de grasa toca
        # entre -0.5 y -1.0: esta dentro.
        r = evaluar_peso(80.0, 82.0, HACE_UN_MES, HOY, "definicion", 22.0)
        assert r["veredicto"] == "en_rango"

    def test_estancado_es_lento(self):
        r = evaluar_peso(81.8, 82.0, HACE_UN_MES, HOY, "definicion", 22.0)
        assert r["veredicto"] == "lento"

    def test_bajar_demasiado_deprisa_se_avisa(self):
        r = evaluar_peso(75.0, 82.0, HACE_UN_MES, HOY, "definicion", 22.0)
        assert r["veredicto"] == "rapido"

    def test_sin_peso_anterior_no_inventa(self):
        r = evaluar_peso(80.0, None, HACE_UN_MES, HOY, "definicion", 22.0)
        assert r["disponible"] is False and "objetivo" in r

    def test_peso_anterior_cero_no_divide_por_cero(self):
        assert evaluar_peso(80.0, 0, HACE_UN_MES, HOY, "definicion", 22.0)["disponible"] is False


class TestCumplimientoDeLoRegistrado:
    def test_sale_de_los_dias_registrados(self):
        c = evaluar_cumplimiento(dias_periodo=28, dias_dieta=25, dias_entreno=15,
                                 entrenos_previstos=16)
        assert c["dieta"]["pct"] == 89 and c["dieta"]["color"] == "verde"

    def test_pocos_dias_registrados_es_rojo(self):
        c = evaluar_cumplimiento(dias_periodo=28, dias_dieta=8, dias_entreno=4,
                                 entrenos_previstos=16)
        assert c["dieta"]["color"] == "rojo"

    def test_cuenta_los_huecos_para_poder_preguntarlos(self):
        """Los dias sin registrar no son dias incumplidos: hay que preguntarlos."""
        c = evaluar_cumplimiento(dias_periodo=14, dias_dieta=10, dias_entreno=6)
        assert c["huecos_dieta"] == 4

    def test_sin_entrenos_previstos_no_inventa_porcentaje(self):
        c = evaluar_cumplimiento(dias_periodo=28, dias_dieta=20, dias_entreno=10)
        assert c["entreno"]["pct"] is None and c["entreno"]["color"] == "sin_dato"

    def test_periodo_cero_no_revienta(self):
        assert evaluar_cumplimiento(0, 0, 0)["dias_periodo"] == 1


class TestMacrosQueTocabanVsComidos:
    def test_marca_en_verde_lo_que_cuadra(self):
        r = comparar_macros({"protein": 180, "carbs": 200, "fat": 60},
                            {"protein": 178, "carbs": 195, "fat": 62})
        assert all(f["color"] == "verde" for f in r["filas"])

    def test_marca_en_rojo_lo_que_se_va(self):
        r = comparar_macros({"protein": 180, "carbs": 200, "fat": 60},
                            {"protein": 100, "carbs": 300, "fat": 60})
        colores = {f["macro"]: f["color"] for f in r["filas"]}
        assert colores["Proteína"] == "rojo" and colores["Hidratos"] == "rojo"
        assert colores["Grasa"] == "verde"

    def test_sin_datos_de_lo_comido_no_pinta_desvios(self):
        r = comparar_macros({"protein": 180, "carbs": 200, "fat": 60}, {})
        assert all(f["comido"] == 0 for f in r["filas"])

    def test_objetivo_a_cero_no_divide_por_cero(self):
        r = comparar_macros({"protein": 0}, {"protein": 50})
        assert r["filas"][0]["desvio_pct"] is None


class TestLaExplicacion:
    def test_al_que_no_registra_se_le_dice_por_que_no_se_le_toca(self):
        """Decision ya tomada: ni se le señala el incumplimiento ni se le ignora."""
        peso = evaluar_peso(80.0, 82.0, HACE_UN_MES, HOY, "definicion", 22.0)
        cumpl = evaluar_cumplimiento(28, 5, 2, 16)
        texto = explicacion_del_sistema(peso, cumpl, False)
        assert "no te tocamos los macros" in texto.lower()
        assert "tapa el problema" in texto.lower()

    def test_al_que_va_bien_no_se_le_marea(self):
        peso = evaluar_peso(80.0, 82.0, HACE_UN_MES, HOY, "definicion", 22.0)
        cumpl = evaluar_cumplimiento(28, 26, 15, 16)
        assert "ritmo que te toca" in explicacion_del_sistema(peso, cumpl, False)

    def test_no_regaña(self):
        """"todas escritas desde el alivio, no desde la exigencia"."""
        peso = evaluar_peso(81.9, 82.0, HACE_UN_MES, HOY, "definicion", 22.0)
        for cumpl in (evaluar_cumplimiento(28, 5, 2, 16), evaluar_cumplimiento(28, 26, 15, 16)):
            texto = explicacion_del_sistema(peso, cumpl, True).lower()
            for palabra in ("fuerza de voluntad", "excusa", "vago", "deberías haber"):
                assert palabra not in texto


class TestElInformeCompleto:
    def _montar(self, **extra):
        args = dict(
            perfil=PERFIL, reporte={"weight": 80, "photos": ["f.jpg", "e.jpg", "p.jpg"],
                                    "created_at": HOY},
            reporte_anterior={"weight": 82, "created_at": HACE_UN_MES},
            fotos_dia_cero=["dia0-frente.jpg", "dia0-espalda.jpg"], semanas_ciclo=12,
            dias_dieta=24, dias_entreno=15, dias_periodo=28,
            macros_comidos={"protein": 175, "carbs": 210, "fat": 58},
            macros_nuevos={"training": {"protein": 180}}, explicacion_equipo=None,
            la_escribe_el_equipo=False)
        args.update(extra)
        return montar_informe(**args)

    def test_trae_los_ocho_apartados(self):
        r = self._montar()
        for apartado in ("ciclo", "peso", "grasa", "fotos", "cumplimiento", "macros",
                         "macros_nuevos", "referencia"):
            assert apartado in r, f"falta el apartado {apartado}"

    def test_tres_o_cuatro_fotos_no_dos(self):
        r = self._montar()
        assert len(r["fotos"]["ahora"]) + len(r["fotos"]["dia_cero"]) >= 3

    def test_dice_en_que_semana_del_ciclo_va(self):
        r = self._montar()
        assert r["ciclo"]["semana"] == 5 and r["ciclo"]["semanas_totales"] == 12

    def test_en_nivel_1_la_explicacion_la_escribe_el_sistema(self):
        r = self._montar(la_escribe_el_equipo=False)
        assert r["explicacion"]["la_escribe"] == "sistema"
        assert r["explicacion"]["texto"]

    def test_en_niveles_2_y_3_la_escribe_el_equipo(self):
        r = self._montar(la_escribe_el_equipo=True, explicacion_equipo="Lo hemos visto, seguimos igual.")
        assert r["explicacion"]["la_escribe"] == "equipo"
        assert r["explicacion"]["texto"] == "Lo hemos visto, seguimos igual."

    def test_si_el_equipo_no_ha_escrito_se_marca_pendiente_y_no_se_inventa(self):
        r = self._montar(la_escribe_el_equipo=True, explicacion_equipo=None)
        assert r["explicacion"]["pendiente"] is True
        assert r["explicacion"]["texto"] == ""

    def test_la_comparacion_con_otros_se_declara_no_disponible(self):
        """Es otro pendiente del documento: se dice, no se inventa."""
        assert self._montar()["referencia"]["disponible"] is False
