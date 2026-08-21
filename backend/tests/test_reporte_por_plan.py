"""
Qué reporte le toca a cada cliente, y con qué bloques (T7, T8 y T9 del doc 16-08).

EL PLAN ES UN DATO, NUNCA UN NOMBRE. El doc habla de Gold, Silver y Bronze porque son
los planes que hoy se llevan cada reporte, pero lo que decide los bloques son las
habilitaciones: si lleva quincenal, y qué rutina incluye. Estos tests fijan eso, que es
lo que se rompe en cuanto alguien renombre un plan o entre uno nuevo.

Cálculo puro: ni base de datos ni HTTP.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.datos_reporte import bloques_del_mensual, fecha_larga, perfil_de_reporte  # noqa: E402
from models.user import PLAN_CATALOG  # noqa: E402


def _hab(plan):
    return PLAN_CATALOG[plan]["habilitaciones"]


class TestQuienEsQuien:
    def test_el_que_lleva_quincenal_hace_el_reporte_completo(self):
        # gold legacy y nivel2 llevan quincenal: los dos, reporte completo.
        assert perfil_de_reporte(_hab("gold")) == "completo"
        assert perfil_de_reporte(_hab("nivel2")) == "completo"

    def test_con_rutina_del_mes_pero_sin_quincenal(self):
        assert perfil_de_reporte(_hab("silver")) == "con_rutina"

    def test_sin_rutina_en_el_plan_es_el_que_ve_la_oferta(self):
        # bronze lleva la rutina como "opcional": no es suya, se la vende.
        assert perfil_de_reporte(_hab("bronze")) == "sin_rutina"
        # nivel1 lleva la del mes desde el doc 19-08 ("Rutina: La del mes"): con_rutina.
        assert perfil_de_reporte(_hab("nivel1")) == "con_rutina"

    def test_sin_habilitaciones_no_revienta(self):
        assert perfil_de_reporte(None) == "sin_rutina"
        assert perfil_de_reporte({}) == "sin_rutina"


class TestLosBloques:
    def test_el_completo_lleva_trece(self):
        bloques = bloques_del_mensual("completo")
        assert len(bloques) == 13
        assert "lesiones" in bloques and "cardio" in bloques

    def test_los_otros_dos_llevan_once_y_sin_lesiones_ni_cardio(self):
        for perfil in ("con_rutina", "sin_rutina"):
            bloques = bloques_del_mensual(perfil)
            assert len(bloques) == 11, perfil
            assert "lesiones" not in bloques and "cardio" not in bloques, perfil

    def test_el_orden_es_el_del_doc(self):
        # Peso, medidas y fotos AL PRINCIPIO: es lo que cambia respecto al de antes,
        # donde las fotos estaban debajo del botón de enviar.
        assert bloques_del_mensual("completo")[:5] == [
            "peso", "medidas", "fotos", "dieta", "entreno"]
        assert bloques_del_mensual("completo")[-1] == "sugerencias"

    def test_la_numeracion_cambia_con_el_plan(self):
        # La suplementación es la 08 del completo y la 06 de los otros dos.
        assert bloques_del_mensual("completo").index("suplementacion") == 7
        assert bloques_del_mensual("con_rutina").index("suplementacion") == 5


class TestElFormularioCorto:
    """El corto (quincenal, semanal y el mensual «rápido») también mira la rutina.

    Antes la lista era fija y al cliente sin rutina se le preguntaba «¿Algún ejercicio
    de la rutina te da molestias?» y por el entreno previo: sin rutina cargada, esos
    dos bloques no salen (el mismo criterio que el mensual aplica a su bloque de
    entreno). El import va dentro para no arrastrar el router al resto del fichero.
    """

    def test_con_rutina_lleva_los_cinco(self):
        from routes.reports import bloques_del_rapido
        assert bloques_del_rapido(True) == [
            "entreno_previo", "peso", "molestias", "sensaciones", "libre"]

    def test_sin_rutina_ni_molestias_ni_entreno_previo(self):
        from routes.reports import bloques_del_rapido
        bloques = bloques_del_rapido(False)
        assert "molestias" not in bloques
        assert "entreno_previo" not in bloques
        assert bloques == ["peso", "sensaciones", "libre"]


class TestFechas:
    def test_como_lo_dice_el_doc(self):
        assert fecha_larga("2026-08-10") == "10 de agosto"
        assert fecha_larga("2026-08-10T22:15:00+00:00") == "10 de agosto"

    def test_sin_fecha_no_inventa(self):
        assert fecha_larga(None) is None
        assert fecha_larga("no es una fecha") is None
