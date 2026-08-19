"""
Las dos columnas nuevas de la pestaña de Clientes (doc del 19-08, apartado 04):
semanas sin reporte (contando desde el lunes) y reportes sin responder (seguidos, por el
calendario de su plan).
"""
from datetime import date

from core.calendario_reportes import calendario_del_plan
from core.cartera import reportes_sin_responder, semanas_sin_reporte

# Miércoles 19 de agosto de 2026.
HOY = date(2026, 8, 19)

# Un plan tipo Gold: quincenal las semanas pares, mensual la 3.
CAL_GOLD = calendario_del_plan({"habilitaciones": {"reportes": ["quincenal", "mensual"]}})
# Un plan de solo mensual (semana 3 de cada 4).
CAL_MENSUAL = calendario_del_plan({"habilitaciones": {"reportes": ["mensual"]}})


class TestSemanasSinReporte:
    def test_lo_mando_el_viernes_y_esta_al_dia(self):
        """La recogida del lunes 17 lo incluyó: 0 semanas sin reporte."""
        assert semanas_sin_reporte("2026-08-14", None, HOY) == 0

    def test_tres_lunes_despues_son_dos_recogidas_en_vacio(self):
        # Reporte el 29-07 (miércoles): recogido el lunes 3; los lunes 10 y 17, en vacío.
        assert semanas_sin_reporte("2026-07-29", None, HOY) == 2

    def test_sin_reporte_nunca_se_cuenta_desde_que_arranco(self):
        # Arrancó el lunes 3 de agosto: las recogidas del 10 y el 17 pasaron sin nada.
        assert semanas_sin_reporte(None, "2026-08-03", HOY) == 2

    def test_recien_llegado_sin_reporte_no_debe_nada(self):
        assert semanas_sin_reporte(None, "2026-08-18", HOY) == 0

    def test_sin_nada_de_donde_contar(self):
        assert semanas_sin_reporte(None, None, HOY) is None


class TestReportesSinResponder:
    def test_al_dia_no_debe_ninguno(self):
        """Mandó el de la semana pasada (semana 6, quincenal): nada pendiente."""
        # Semana actual 7; su reporte fue hace una semana (un lunes atrás) → semana 6.
        assert reportes_sin_responder(CAL_GOLD, 7, "2026-08-12", HOY) == 0

    def test_un_gold_que_lleva_un_mes_sin_mandar(self):
        """Último reporte en la semana 3 (hace 4 lunes); semanas 4 y 6 traían quincenal y
        no llegó ninguno: debe 2. La semana en curso (7... no trae) no se cuenta."""
        assert reportes_sin_responder(CAL_GOLD, 7, "2026-07-21", HOY) == 2

    def test_el_de_mensual_no_debe_por_semanas_vacias(self):
        """Entre mensual y mensual pasan lunes de sobra sin deber nada."""
        # Semana actual 4; mandó el de la semana 3 (un lunes atrás): 0.
        assert reportes_sin_responder(CAL_MENSUAL, 4, "2026-08-12", HOY) == 0

    def test_sin_reporte_nunca_se_cuentan_los_que_tocaron(self):
        # Semana 5 de un gold sin un solo reporte: tocaron la 2, la 3 y la 4 → 3.
        assert reportes_sin_responder(CAL_GOLD, 5, None, HOY) == 3

    def test_plan_sin_reportes_devuelve_none(self):
        cal_vacio = calendario_del_plan({"habilitaciones": {"reportes": []}})
        assert reportes_sin_responder(cal_vacio, 5, None, HOY) is None

    def test_el_tope_corta_el_paseo(self):
        assert reportes_sin_responder(CAL_GOLD, 120, None, HOY, tope=12) == 12
