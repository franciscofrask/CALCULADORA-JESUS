"""Tests del motor de macros v2 (spec "QUIZ INICIAL + MOTOR DE MACROS" 18-07-2026).

Unitarios y en local (sin HTTP): importan macro_engine directamente.
Casos de referencia contrastados con la tabla v3:
  - Hombre 80 kg / 20% volumen:   190/170/60 - 45/50 - 225/170/60
  - Hombre 80 kg / 20% definicion: 190/140/60 - 45/40 - 225/130/60
  - Mujer 60 kg / 25% definicion:  130/100/60 - 30/40 - 140/90/60 (ejemplo 4 de la spec)
"""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from macro_engine import (
    calcular_macros_v2, ajustes_to_kwargs, redondear5,
    UMBRAL_REVISION,
)


def m8(res):
    """Los 8 numeros como tupla plana para comparar de un vistazo."""
    m = res["macros"]
    return (m["entreno"]["proteina"], m["entreno"]["hidratos"], m["entreno"]["grasa"],
            m["perientreno"]["proteina"], m["perientreno"]["hidratos"],
            m["descanso"]["proteina"], m["descanso"]["hidratos"], m["descanso"]["grasa"])


def pasos(res):
    return [d["paso"] for d in res["desglose"]]


class TestTablaPura:
    def test_sin_ajustes_igual_tabla(self):
        res = calcular_macros_v2(80, "hombre", 20, "volumen")
        assert m8(res) == (190, 170, 60, 45, 50, 225, 170, 60)
        assert res["version_motor"] == 2
        assert res["revision"] is None
        assert pasos(res) == ["tabla"]

    def test_ejemplo_spec_mujer_sedentaria(self):
        # Ejemplo 4 de la spec: "No reporta dieta (Mujer 60/25 def sedentaria, tabla pura)"
        res = calcular_macros_v2(60, "mujer", 25, "definicion", actividad_diaria="sedentario")
        assert m8(res) == (130, 100, 60, 30, 40, 140, 90, 60)


class TestModificadores:
    def test_muy_activo(self):
        res = calcular_macros_v2(80, "hombre", 20, "volumen", actividad_diaria="muy_activo")
        # Solo HC: 170*1.1 = 187 -> 185
        assert m8(res) == (190, 185, 60, 45, 50, 225, 185, 60)

    def test_deporte_extra_solo_descanso(self):
        res = calcular_macros_v2(80, "hombre", 20, "volumen", deporte_extra=True)
        assert m8(res) == (190, 170, 60, 45, 50, 225, 185, 60)

    def test_casi_no_engorda_hombre_seco(self):
        res = calcular_macros_v2(80, "hombre", 20, "volumen", facilidad_engordar="casi_no")
        # 170*1.2 = 204 -> 205
        assert m8(res) == (190, 205, 60, 45, 50, 225, 205, 60)

    def test_casi_no_engorda_no_aplica_bf_alto(self):
        res = calcular_macros_v2(80, "hombre", 25, "volumen", facilidad_engordar="casi_no")
        base = calcular_macros_v2(80, "hombre", 25, "volumen")
        assert m8(res) == m8(base)
        assert any(d["paso"] == "casi_no_engorda" and d["estado"] == "no_aplica_bf"
                   for d in res["desglose"])

    def test_casi_no_engorda_mujer_no_aplica_pero_se_guarda(self):
        res = calcular_macros_v2(60, "mujer", 20, "volumen", facilidad_engordar="casi_no")
        base = calcular_macros_v2(60, "mujer", 20, "volumen")
        assert m8(res) == m8(base)
        assert res["no_aplicados"]["engorda_mujer"] == "casi_no"

    def test_ejemplo_spec_modificadores_al_max(self):
        # Ejemplo 5: def, muy activo + casi no engorda (bf 20) -> +30%/+30%
        res = calcular_macros_v2(80, "hombre", 20, "definicion",
                                 actividad_diaria="muy_activo", facilidad_engordar="casi_no")
        # 140*1.3 = 182 -> 180; 130*1.3 = 169 -> 170
        assert m8(res) == (190, 180, 60, 45, 40, 225, 170, 60)

    def test_topes_30_40(self):
        # muy activo (10/10) + deporte (0/10) + casi no (20/20) = 30/40: en el tope justo
        res = calcular_macros_v2(80, "hombre", 20, "volumen", actividad_diaria="muy_activo",
                                 deporte_extra=True, facilidad_engordar="casi_no")
        # entreno 170*1.3 = 221 -> 220; descanso 170*1.4 = 238 -> 240
        assert m8(res) == (190, 220, 60, 45, 50, 225, 240, 60)

    def test_veto_engorda_enseguida(self):
        res = calcular_macros_v2(80, "hombre", 20, "volumen", actividad_diaria="muy_activo",
                                 deporte_extra=True, facilidad_engordar="enseguida")
        base = calcular_macros_v2(80, "hombre", 20, "volumen")
        assert m8(res) == m8(base)
        assert any(d["paso"] == "veto_engorda_enseguida" for d in res["desglose"])

    def test_veto_tambien_en_mujer(self):
        res = calcular_macros_v2(60, "mujer", 25, "volumen", actividad_diaria="muy_activo",
                                 facilidad_engordar="enseguida")
        base = calcular_macros_v2(60, "mujer", 25, "volumen")
        assert m8(res) == m8(base)

    def test_historial_se_guarda_no_se_aplica(self):
        res = calcular_macros_v2(80, "hombre", 20, "volumen", historial_dietas="siempre a ojo")
        base = calcular_macros_v2(80, "hombre", 20, "volumen")
        assert m8(res) == m8(base)
        assert res["no_aplicados"]["historial_dietas"] == "siempre a ojo"

    def test_peri_jamas_modificado(self):
        base = calcular_macros_v2(80, "hombre", 15, "volumen")
        for kwargs in (
            {"actividad_diaria": "muy_activo"},
            {"deporte_extra": True},
            {"facilidad_engordar": "casi_no"},
            {"actividad_diaria": "muy_activo", "deporte_extra": True, "facilidad_engordar": "casi_no"},
            {"farmacologia": True},
        ):
            res = calcular_macros_v2(80, "hombre", 15, "volumen", **kwargs)
            assert res["macros"]["perientreno"] == base["macros"]["perientreno"], kwargs

    def test_proteina_y_grasa_intactas_por_modificadores(self):
        res = calcular_macros_v2(80, "hombre", 20, "volumen", actividad_diaria="muy_activo",
                                 deporte_extra=True, facilidad_engordar="casi_no")
        assert res["macros"]["entreno"]["proteina"] == 190
        assert res["macros"]["descanso"]["proteina"] == 225
        assert res["macros"]["entreno"]["grasa"] == 60
        assert res["macros"]["descanso"]["grasa"] == 60


class TestFarmacologia:
    def test_mas_10_solo_proteina_descanso(self):
        res = calcular_macros_v2(80, "hombre", 20, "volumen", farmacologia=True)
        # 225*1.1 = 247.5 -> 250 (half-even sobre /5: 49.5 -> 50)
        assert res["macros"]["descanso"]["proteina"] == 250
        assert res["macros"]["entreno"]["proteina"] == 190
        assert res["macros"]["entreno"]["hidratos"] == 170


class TestDietaReportada:
    def test_volumen_reparto_bandas(self):
        # 250 g -> banda 60 de peri, 190 a comidas, descanso 190-25% = 142.5 -> 140
        res = calcular_macros_v2(80, "hombre", 20, "volumen",
                                 dieta_reportada={"hc_entreno": 250})
        m = res["macros"]
        assert m["perientreno"]["hidratos"] == 60
        assert m["entreno"]["hidratos"] == 190
        assert m["descanso"]["hidratos"] == 140
        assert m["entreno"]["proteina"] == 190     # proteina siempre la de tabla
        assert m["entreno"]["grasa"] == 60
        assert m["descanso"]["grasa"] == 70        # volumen reportado: descanso 70

    def test_volumen_bestia_split(self):
        # 420 g totales: peri 90, comidas 330, descanso 247.5 -> 250; grasa >70 -> 70/80
        res = calcular_macros_v2(80, "hombre", 20, "volumen",
                                 dieta_reportada={"hc_entreno": 420, "grasa_entreno": 75})
        m = res["macros"]
        assert m["perientreno"]["hidratos"] == 90
        assert m["entreno"]["hidratos"] == 330
        assert m["descanso"]["hidratos"] == 250
        assert m["entreno"]["grasa"] == 70         # >70 pero HC <= 450
        assert m["descanso"]["grasa"] == 80

    def test_volumen_grasa_80_con_hc_muy_altos(self):
        res = calcular_macros_v2(80, "hombre", 20, "volumen",
                                 dieta_reportada={"hc_entreno": 470, "grasa_entreno": 80})
        assert res["macros"]["entreno"]["grasa"] == 80

    @pytest.mark.parametrize("hc,peri", [(150, 50), (200, 50), (250, 60), (300, 60), (350, 75), (400, 75), (500, 90)])
    def test_bandas_peri(self, hc, peri):
        res = calcular_macros_v2(80, "hombre", 20, "volumen",
                                 dieta_reportada={"hc_entreno": hc})
        assert res["macros"]["perientreno"]["hidratos"] == peri

    def test_ejemplo_spec_en_las_ultimas(self):
        # Ejemplo 3: "Llega en las ultimas" (H80/20 def, reporta 60 g)
        res = calcular_macros_v2(80, "hombre", 20, "definicion",
                                 dieta_reportada={"hc_entreno": 60})
        assert m8(res) == (190, 60, 50, 45, 15, 225, 50, 60)

    @pytest.mark.parametrize("hc,recorte", [(150, 20), (200, 25), (250, 30), (300, 40), (350, 45), (400, 55), (480, 55)])
    def test_recortes_definicion(self, hc, recorte):
        res = calcular_macros_v2(80, "hombre", 20, "definicion",
                                 dieta_reportada={"hc_entreno": hc})
        total = hc - recorte
        m = res["macros"]
        # peri por banda del total YA recortado; el resto a comidas
        assert m["entreno"]["hidratos"] == redondear5(total - m["perientreno"]["hidratos"])
        assert m["descanso"]["hidratos"] == max(50, redondear5((total - m["perientreno"]["hidratos"]) * 0.75))

    def test_revision_cuadra(self):
        # Recomendado H80/20 vol: 170 comidas + 50 peri = 220. Reporta 220 -> cuadra.
        res = calcular_macros_v2(80, "hombre", 20, "volumen",
                                 dieta_reportada={"hc_entreno": 220})
        assert res["revision"]["requiere_revision"] is False

    def test_revision_no_cuadra(self):
        res = calcular_macros_v2(80, "hombre", 20, "volumen",
                                 dieta_reportada={"hc_entreno": 400})
        assert res["revision"]["requiere_revision"] is True
        assert res["revision"]["hc_recomendados"] == 220
        assert res["revision"]["umbral"] == UMBRAL_REVISION

    def test_revision_compara_contra_recomendado_con_modificadores(self):
        # Con muy activo el recomendado sube a 187+50 = 237: reportar 250 cuadra (5.5%)
        res = calcular_macros_v2(80, "hombre", 20, "volumen", actividad_diaria="muy_activo",
                                 dieta_reportada={"hc_entreno": 250})
        assert res["revision"]["requiere_revision"] is False


class TestSuelosYRedondeo:
    def test_suelo_hc_comidas_entreno(self):
        # Reporta 120 en volumen: peri 50, comidas 70 -> descanso 52.5 -> 50 (suelo no salta)
        # Reporta 100: peri 50, comidas 50 (justo el suelo); 90: comidas 40 -> suelo 50
        res = calcular_macros_v2(80, "hombre", 20, "volumen",
                                 dieta_reportada={"hc_entreno": 90})
        assert res["macros"]["entreno"]["hidratos"] == 50
        assert res["macros"]["descanso"]["hidratos"] == 50
        assert any(d["paso"] == "suelos" for d in res["desglose"])

    def test_todo_multiplo_de_5(self):
        for kwargs in ({}, {"actividad_diaria": "muy_activo"}, {"farmacologia": True},
                       {"dieta_reportada": {"hc_entreno": 263}},
                       {"actividad_diaria": "muy_activo", "deporte_extra": True, "facilidad_engordar": "casi_no"}):
            res = calcular_macros_v2(77, "hombre", 18, "volumen", **kwargs)
            for grupo in res["macros"].values():
                for v in grupo.values():
                    assert v % 5 == 0, (kwargs, res["macros"])

    def test_redondeo_half_even(self):
        assert redondear5(142.5) == 140
        assert redondear5(247.5) == 250
        assert redondear5(187) == 185
        assert redondear5(188) == 190


class TestAjustesToKwargs:
    def test_none(self):
        kw = ajustes_to_kwargs(None)
        assert kw["dieta_reportada"] is None
        assert kw["actividad_diaria"] is None

    def test_dieta_solo_si_sigue_dieta_con_numeros(self):
        kw = ajustes_to_kwargs({"sigue_dieta": True, "dieta_hc_entreno": 250,
                                "dieta_grasa_entreno": 60, "dieta_texto": "arroz y pollo"})
        assert kw["dieta_reportada"] == {"hc_entreno": 250, "grasa_entreno": 60, "texto": "arroz y pollo"}
        # sin numeros no hay rama de dieta reportada aunque diga que sigue dieta
        kw2 = ajustes_to_kwargs({"sigue_dieta": True, "dieta_texto": "como limpio"})
        assert kw2["dieta_reportada"] is None

    def test_pipeline_completo_desde_ajustes(self):
        kw = ajustes_to_kwargs({"actividad_diaria": "muy_activo", "deporte_extra": True,
                                "facilidad_engordar": "normal"})
        res = calcular_macros_v2(80, "hombre", 20, "volumen", **kw)
        assert res["macros"]["entreno"]["hidratos"] == 185
        assert res["macros"]["descanso"]["hidratos"] == 205  # 170*1.2 = 204 -> 205
