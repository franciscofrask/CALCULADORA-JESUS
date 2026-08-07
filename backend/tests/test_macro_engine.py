"""Tests del motor de macros v2.

Spec vigente: el DOC DE JESUS DEL 29-07-2026, que rehizo siete reglas del motor del 18-07
(commit 5ef6034). Estos tests se actualizaron a ese doc el 31-07: antes comprobaban la spec
del 18-07 y fallaban 20 de ellos, no porque el motor estuviese mal sino porque el metodo
habia cambiado y los tests se quedaron atras.

Lo que cambio, y donde se comprueba aqui:
  - Deporte extra: +10% en definicion y +20% en volumen (antes 10% fijo).
  - "Engordo lo normal" cobra el +20% igual que "casi no lo noto" (grasa <= 20%).
  - Regla dura nueva: el descanso NUNCA por encima del entreno; si se pasa, sube el entreno.
  - Bandas de peri: <=300 -> 40, <=350 -> 50, <=400 -> 60, <=450 -> 75, resto 90.
  - Suelo de hidratos de entreno: 60 en comidas (75 con el peri). Antes 50.
  - Paso 5: la grasa de partida sale de la que ya come (<=60 -> 60, <=90 -> 70, >90 -> 80).
  - Paso 4: que se hace con la dieta real depende de `como_va` (matriz por objetivo), no
    de recortes fijos por tramo. Sin `como_va` se usa "mantengo", el caso neutro.
  - TRT desactivada: se guarda y no se aplica, a la espera de que Jesus confirme la regla.

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
    UMBRAL_REVISION, _banda_peri,
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

    def test_deporte_extra_volumen_sube_20(self):
        # Doc 29-07: el deporte extra sube +20% en volumen (+10% en definicion) y SOLO toca
        # el descanso. 170*1.2 = 204 -> 205. Como el descanso queda por encima del entreno
        # (170), la regla dura obliga a subir el entreno hasta igualarlo: 205 tambien.
        res = calcular_macros_v2(80, "hombre", 20, "volumen", deporte_extra=True)
        assert m8(res) == (190, 205, 60, 45, 50, 225, 205, 60)
        assert any(d["paso"] == "nivelar_descanso" for d in res["desglose"])

    def test_deporte_extra_definicion_sube_10(self):
        res = calcular_macros_v2(80, "hombre", 20, "definicion", deporte_extra=True)
        base = calcular_macros_v2(80, "hombre", 20, "definicion")
        # descanso de tabla 130 -> +10% = 143 -> 145
        assert res["macros"]["descanso"]["hidratos"] == 145
        assert base["macros"]["descanso"]["hidratos"] == 130

    def test_casi_no_engorda_hombre_seco(self):
        res = calcular_macros_v2(80, "hombre", 20, "volumen", facilidad_engordar="casi_no")
        # 170*1.2 = 204 -> 205
        assert m8(res) == (190, 205, 60, 45, 50, 225, 205, 60)

    def test_casi_no_engorda_no_aplica_bf_alto(self):
        res = calcular_macros_v2(80, "hombre", 25, "volumen", facilidad_engordar="casi_no")
        base = calcular_macros_v2(80, "hombre", 25, "volumen")
        assert m8(res) == m8(base)
        assert any(d["paso"] == "no_engorda" and d["estado"] == "no_aplica_bf"
                   for d in res["desglose"])

    def test_casi_no_engorda_mujer_YA_aplica(self):
        """Desde el 06-08-2026 sí se aplica en mujeres, con umbral del 30 % (el mismo
        punto del recorrido que el 20 % en hombres). Antes estaba muerto: no se ejecutó
        nunca. Lo suyo está en test_engorda_mujeres.py."""
        res = calcular_macros_v2(60, "mujer", 20, "volumen", facilidad_engordar="casi_no")
        base = calcular_macros_v2(60, "mujer", 20, "volumen")
        assert m8(res) != m8(base)
        assert "engorda_mujer" not in res["no_aplicados"]

    def test_ejemplo_spec_modificadores_al_max(self):
        # Ejemplo 5: def, muy activo + casi no engorda (bf 20) -> +30%/+30%
        res = calcular_macros_v2(80, "hombre", 20, "definicion",
                                 actividad_diaria="muy_activo", facilidad_engordar="casi_no")
        # 140*1.3 = 182 -> 180; 130*1.3 = 169 -> 170
        assert m8(res) == (190, 180, 60, 45, 40, 225, 170, 60)

    def test_topes_30_40(self):
        # muy activo (10/10) + deporte (0/20 en volumen) + casi no (20/20) = 30/50, recortado
        # al tope +30% entreno / +40% descanso. Entreno 170*1.3 = 221 -> 220; descanso
        # 170*1.4 = 238 -> 240. Y como el descanso queda por encima, la regla dura del doc
        # 29-07 sube el entreno hasta 240.
        res = calcular_macros_v2(80, "hombre", 20, "volumen", actividad_diaria="muy_activo",
                                 deporte_extra=True, facilidad_engordar="casi_no")
        assert m8(res) == (190, 240, 60, 45, 50, 225, 240, 60)
        assert any(d["paso"] == "tope" for d in res["desglose"])
        assert any(d["paso"] == "nivelar_descanso" for d in res["desglose"])

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
    """Doc 03-08: +10 g de proteina en descanso, y la regla dura de que entreno + peri
    tiene que quedar por encima del descanso."""

    def test_ejemplo_del_doc(self):
        # Hombre 80 kg / 20% / volumen. Tabla: 190 entreno, 45 peri, 225 descanso.
        # Con farmacologia el descanso sube a 235, con lo que 190+45=235 ya no lo supera:
        # se suben tambien 10 g en entreno -> 200 + 45 = 245 > 235.
        base = calcular_macros_v2(80, "hombre", 20, "volumen")
        assert (base["macros"]["entreno"]["proteina"], base["macros"]["perientreno"]["proteina"],
                base["macros"]["descanso"]["proteina"]) == (190, 45, 225)

        res = calcular_macros_v2(80, "hombre", 20, "volumen", farmacologia=True)
        assert res["macros"]["descanso"]["proteina"] == 235
        assert res["macros"]["entreno"]["proteina"] == 200
        assert any(d["paso"] == "farmacologia" and d["estado"] == "aplicado"
                   for d in res["desglose"])
        assert any(d["paso"] == "farmacologia_nivelar_entreno" for d in res["desglose"])

    def test_entreno_no_se_toca_si_la_regla_dura_se_sigue_cumpliendo(self):
        # Si entreno + peri sigue por encima del descanso tras los +10, el entreno no se mueve.
        for peso, bf, obj in ((80, 15, "definicion"), (70, 20, "volumen"), (90, 25, "volumen")):
            base = calcular_macros_v2(peso, "hombre", bf, obj)
            res = calcular_macros_v2(peso, "hombre", bf, obj, farmacologia=True)
            pr_e, pr_pe = base["macros"]["entreno"]["proteina"], base["macros"]["perientreno"]["proteina"]
            pr_d = base["macros"]["descanso"]["proteina"]
            assert res["macros"]["descanso"]["proteina"] == pr_d + 10
            if pr_e + pr_pe > pr_d + 10:
                assert res["macros"]["entreno"]["proteina"] == pr_e, (peso, bf, obj)

    def test_la_regla_dura_nunca_se_rompe_por_la_farmacologia(self):
        # Ojo: hay 79 celdas de la tabla (de 2.244) donde entreno + peri YA no supera al
        # descanso sin farmacologia, todas de hombre con grasa alta (80 kg / 28% da
        # 180 + 40 = 220 contra 220). Eso es de la tabla y no lo arregla esta excepcion.
        # Lo que si se exige: si la combinacion lo cumplia, con farmacologia lo sigue
        # cumpliendo.
        for peso in (60, 70, 80, 90, 100):
            for bf in (10, 15, 20, 25, 30):
                for obj in ("volumen", "definicion"):
                    for sexo in ("hombre", "mujer"):
                        b = calcular_macros_v2(peso, sexo, bf, obj)["macros"]
                        if b["entreno"]["proteina"] + b["perientreno"]["proteina"] <= b["descanso"]["proteina"]:
                            continue  # ya venia roto de la tabla
                        m = calcular_macros_v2(peso, sexo, bf, obj, farmacologia=True)["macros"]
                        assert m["entreno"]["proteina"] + m["perientreno"]["proteina"] > m["descanso"]["proteina"], \
                            (peso, sexo, bf, obj)

    def test_sin_farmacologia_no_cambia_nada(self):
        base = calcular_macros_v2(80, "hombre", 20, "volumen")
        res = calcular_macros_v2(80, "hombre", 20, "volumen", farmacologia=False)
        assert m8(res) == m8(base)
        assert not any(d["paso"].startswith("farmacologia") for d in res["desglose"])

    def test_hidratos_y_grasas_no_se_tocan(self):
        base = calcular_macros_v2(80, "hombre", 20, "volumen")["macros"]
        con = calcular_macros_v2(80, "hombre", 20, "volumen", farmacologia=True)["macros"]
        for dia in ("entreno", "descanso"):
            assert con[dia]["hidratos"] == base[dia]["hidratos"]
            assert con[dia]["grasa"] == base[dia]["grasa"]
        assert con["perientreno"] == base["perientreno"]


class TestDietaReportada:
    def test_volumen_reparto_bandas(self):
        # X=250 > T=220 y "mantengo" (neutro) -> en volumen se le pone X tal cual.
        # Banda del doc 29-07: 250 <= 300 -> peri 40. Comidas 210. Descanso, un 20% por
        # debajo de las comidas: 210*0.8 = 168 -> 170.
        res = calcular_macros_v2(80, "hombre", 20, "volumen",
                                 dieta_reportada={"hc_entreno": 250})
        m = res["macros"]
        assert m["perientreno"]["hidratos"] == 40
        assert m["entreno"]["hidratos"] == 210
        assert m["descanso"]["hidratos"] == 170
        assert m["entreno"]["proteina"] == 190     # proteina siempre la de tabla
        # sin grasa reportada no entra el paso 5: se queda la de tabla
        assert m["entreno"]["grasa"] == 60
        assert m["descanso"]["grasa"] == 60

    def test_volumen_bestia_se_acota(self):
        """X=420 con T=220: antes se le daban los 420 tal cual. Desde el 06-08-2026 la
        dieta modula y no manda, así que se queda en el tope (+20 % = 264).

        Lo que NO cambia: el reparto interno (peri por banda, descanso un 20 % por debajo)
        y la grasa por la dieta que trae."""
        res = calcular_macros_v2(80, "hombre", 20, "volumen",
                                 dieta_reportada={"hc_entreno": 420, "grasa_entreno": 75})
        m = res["macros"]
        total = m["entreno"]["hidratos"] + m["perientreno"]["hidratos"]
        assert total == 265                        # 264 redondeado a múltiplo de 5
        assert m["perientreno"]["hidratos"] == 40  # banda del total ya acotado
        assert m["descanso"]["hidratos"] == redondear5(m["entreno"]["hidratos"] * 0.8)
        assert m["entreno"]["grasa"] == 70         # 75 g de grasa -> tramo 60-90
        assert m["descanso"]["grasa"] == 70
        assert any(d["paso"] == "tope_dieta" for d in res["desglose"])

    @pytest.mark.parametrize("grasa_reportada,esperada", [(50, 60), (60, 60), (75, 70),
                                                          (90, 70), (95, 80), (120, 80)])
    def test_grasa_por_dieta(self, grasa_reportada, esperada):
        # Paso 5 del doc 29-07: <=60 -> 60, <=90 -> 70, >90 -> 80. Igual en entreno y descanso.
        res = calcular_macros_v2(80, "hombre", 20, "volumen",
                                 dieta_reportada={"hc_entreno": 470,
                                                  "grasa_entreno": grasa_reportada})
        assert res["macros"]["entreno"]["grasa"] == esperada
        assert res["macros"]["descanso"]["grasa"] == esperada

    @pytest.mark.parametrize("total,peri", [(250, 40), (300, 40), (350, 50), (400, 60),
                                            (450, 75), (500, 90)])
    def test_bandas_peri(self, total, peri):
        """Bandas del doc 29-07: <=300 -> 40, <=350 -> 50, <=400 -> 60, <=450 -> 75, resto 90.

        Se prueba la función directamente. Antes se hacía a través del motor reportando
        esas cantidades, pero desde que la dieta se acota a +-20 % ya no se puede llegar
        a un total de 500 por esa vía: el motor lo recorta antes, y el test acababa
        comprobando el tope en vez de las bandas."""
        assert _banda_peri(total) == peri

    @pytest.mark.parametrize("hc", [150, 200])
    def test_volumen_por_debajo_de_la_tabla_manda_la_tabla(self, hc):
        # X < T con "mantengo" en volumen -> manda la tabla, no se toca nada. El peri
        # sigue siendo el de tabla (50), no el de banda.
        res = calcular_macros_v2(80, "hombre", 20, "volumen",
                                 dieta_reportada={"hc_entreno": hc})
        base = calcular_macros_v2(80, "hombre", 20, "volumen")
        assert m8(res) == m8(base)
        assert res["macros"]["perientreno"]["hidratos"] == 50

    def test_ejemplo_spec_en_las_ultimas(self):
        # Ejemplo 3: "Llega en las ultimas" (H80/20 def, reporta 60 g)
        res = calcular_macros_v2(80, "hombre", 20, "definicion",
                                 dieta_reportada={"hc_entreno": 60})
        assert m8(res) == (190, 60, 50, 45, 15, 225, 50, 60)

    # Definicion, hombre 80/20: la tabla da 140 de comidas + 40 de peri, o sea T = 180.
    # Sin `como_va` se usa "mantengo": X > T -> el 75% de X ; X < T -> X - 10.
    # Y desde el 06-08-2026 el resultado se queda a +-20% de T: entre 144 y 216.
    @pytest.mark.parametrize("hc,total_esperado", [
        (200, 150.0),    # 200 > 180 -> 75% = 150, dentro de la banda
        (250, 187.5),    # 75% = 187,5, dentro
        (300, 216.0),    # 75% = 225 -> se recorta al tope de 216
        (350, 216.0),    # 75% = 262,5 -> tope
        (400, 216.0),    # 75% = 300 -> tope
        (480, 216.0),    # 75% = 360 -> tope
    ])
    def test_definicion_por_encima_de_la_tabla_va_al_75_acotado(self, hc, total_esperado):
        res = calcular_macros_v2(80, "hombre", 20, "definicion",
                                 dieta_reportada={"hc_entreno": hc})
        m = res["macros"]
        peri = m["perientreno"]["hidratos"]
        # el peri sale de la banda del total ya recortado, y el resto va a las comidas
        assert peri == _banda_peri(total_esperado)
        assert m["entreno"]["hidratos"] == redondear5(total_esperado - peri)
        # descanso: un 20% por debajo de las comidas (doc 29-07), con suelo de 50
        assert m["descanso"]["hidratos"] == max(50, redondear5((total_esperado - peri) * 0.8))

    def test_definicion_por_debajo_de_la_tabla_resta_10(self):
        # X=150 < T=180 -> X-10 = 140, y 140 se va por debajo del suelo del -20% (144),
        # asi que se queda en 144. En esta rama el doc ata el arranque: peri 15, el resto
        # a comidas, descanso un 20% por debajo y la grasa a 50/60.
        res = calcular_macros_v2(80, "hombre", 20, "definicion",
                                 dieta_reportada={"hc_entreno": 150})
        m = res["macros"]
        assert m["perientreno"]["hidratos"] == 15
        assert m["entreno"]["hidratos"] == 130      # 144 - 15 = 129 -> 130
        assert m["descanso"]["hidratos"] == 105     # 129 * 0,8 = 103,2 -> 105
        assert m["entreno"]["grasa"] == 50
        assert m["descanso"]["grasa"] == 60

    def test_como_va_cambia_el_resultado(self):
        """"bien" deja X tal cual; "mantengo" (neutro) lo baja al 75 %.

        Con X=300 los dos se salen del +20 % (T=180, tope 216) y acaban en el tope, así
        que para ver la diferencia hace falta una X dentro de la banda. Que los dos topen
        no es un fallo: es justo lo que hace el tope."""
        def total(**kw):
            r = calcular_macros_v2(80, "hombre", 20, "definicion",
                                   dieta_reportada={"hc_entreno": 210}, **kw)
            return r["macros"]["entreno"]["hidratos"] + r["macros"]["perientreno"]["hidratos"]
        assert total(como_va="bien") == 210          # se le deja lo que ya come
        assert total() == 160                        # el 75% de 210 = 157,5 -> 160
        assert total(como_va="bien") > total()

    def test_con_dietas_altas_los_dos_topan(self):
        def total(**kw):
            r = calcular_macros_v2(80, "hombre", 20, "definicion",
                                   dieta_reportada={"hc_entreno": 300}, **kw)
            return r["macros"]["entreno"]["hidratos"] + r["macros"]["perientreno"]["hidratos"]
        assert total(como_va="bien") == 215          # 216 redondeado
        assert total() == 215

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
        """Doc 29-07: el suelo del día de entreno son 75 g totales = 60 en comidas + 15 de peri.

        Con una mujer pequeña en definición: la tabla da poco, y al restar llega al suelo.
        Antes se llegaba aquí reportando 80 g en un hombre de 80 kg, pero eso ahora entra
        por la excepción del que "llega en las últimas" (menos de 75 g) o se acota, así que
        el suelo ya no era lo que se estaba probando."""
        res = calcular_macros_v2(50, "mujer", 20, "definicion",
                                 dieta_reportada={"hc_entreno": 95})
        assert res["macros"]["entreno"]["hidratos"] >= 60
        assert res["macros"]["perientreno"]["hidratos"] == 15

    def test_suelo_no_salta_si_ya_esta_por_encima(self):
        # Reportando 170 con T=180: X-10 = 160, dentro de la banda. Peri 15, comidas 145,
        # muy por encima del suelo de 60 -> no interviene.
        res = calcular_macros_v2(80, "hombre", 20, "definicion",
                                 dieta_reportada={"hc_entreno": 170})
        assert res["macros"]["entreno"]["hidratos"] == 145
        assert not any(d["paso"] == "suelos" for d in res["desglose"])

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
        # Doc 29-07: "engordo lo normal" con grasa <= 20% cobra el +20% igual que "casi no lo
        # noto" (antes solo subia "casi no"). Con muy_activo (+10/+10), deporte en volumen
        # (+0/+20) y normal (+20/+20) se llega al tope 30/40 y luego la regla dura nivela.
        kw = ajustes_to_kwargs({"actividad_diaria": "muy_activo", "deporte_extra": True,
                                "facilidad_engordar": "normal"})
        res = calcular_macros_v2(80, "hombre", 20, "volumen", **kw)
        assert res["macros"]["entreno"]["hidratos"] == 240
        assert res["macros"]["descanso"]["hidratos"] == 240
        assert any(d["paso"] == "no_engorda" and d["estado"] == "aplicado"
                   for d in res["desglose"])
