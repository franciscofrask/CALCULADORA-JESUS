# -*- coding: utf-8 -*-
"""El bloque 11 del doc 19-08: los reportes y el check-in.

- «No puedo esta semana» apaga los recordatorios de ESE reporte (el aviso de apertura
  no, que se dispara antes de que exista el aplazamiento).
- La rutina del mes aplazada una semana: el aviso sale el día elegido, no antes.
- La tabla de «quién recibe qué» contra el catálogo: reportes, feedback y audio.
- «El rápido, mensual» de la Calculadora va como habilitación, no como nombre de plan.
"""
from datetime import datetime, timezone

from core.avisos_cliente import avisos_condicionados, avisos_de_calendario_doc
from core.tiempo import MADRID
from models.user import PLAN_CATALOG

AHORA = datetime(2026, 8, 19, 10, 0, tzinfo=timezone.utc)

_es = lambda *a: datetime(*a, tzinfo=MADRID)


def _ventana_mensual(aplazado=False, mandado=False):
    # Una ventana mensual que abrió el viernes 14-08 y cerró el lunes 17-08 a las 18:00.
    return [{"tipo": "mensual", "semana": 4,
             "abre": _es(2026, 8, 14, 10), "cierra": _es(2026, 8, 17, 18),
             "mandado": mandado, "aplazado": aplazado}]


class TestElAplazadoNoRecibeRecordatorios:
    def test_sin_aplazar_el_domingo_le_recuerda(self):
        avisos = avisos_de_calendario_doc(ahora_es=_es(2026, 8, 16, 11),
                                          ventanas=_ventana_mensual())
        assert any(a["familia"] == "mensual_ultimo" for a in avisos)

    def test_aplazado_el_domingo_no_se_le_insiste(self):
        avisos = avisos_de_calendario_doc(ahora_es=_es(2026, 8, 16, 11),
                                          ventanas=_ventana_mensual(aplazado=True))
        assert not any(a["familia"] == "mensual_ultimo" for a in avisos)

    def test_aplazado_tampoco_el_martes_de_no_me_llego(self):
        avisos = avisos_de_calendario_doc(ahora_es=_es(2026, 8, 18, 10),
                                          ventanas=_ventana_mensual(aplazado=True))
        assert not any(a["familia"] == "reporte_no_llego" for a in avisos)

    def test_el_de_apertura_no_se_toca(self):
        # El viernes que abre, el aviso sale aunque luego aplace: se dispara antes de que
        # el aplazamiento exista, y anunciar la apertura no es insistir.
        avisos = avisos_de_calendario_doc(ahora_es=_es(2026, 8, 14, 11),
                                          ventanas=_ventana_mensual(aplazado=True))
        assert any(a["familia"] == "mensual_abierto" for a in avisos)


class TestRutinaDelMesAplazada:
    def test_antes_del_dia_no(self):
        assert avisos_condicionados(ahora=AHORA, rutina_mes_aplazada_hasta="2026-08-20") == []

    def test_el_dia_elegido_si_y_una_vez(self):
        avisos = avisos_condicionados(ahora=AHORA, rutina_mes_aplazada_hasta="2026-08-19")
        assert len(avisos) == 1
        # Plural desde el 23-08 (punto 57).
        assert avisos[0]["variantes"][0]["titulo"] == "¿Te preparamos la rutina del mes?"
        # La clave lleva la fecha del aplazamiento: sale una vez por aplazamiento.
        assert avisos[0]["clave"] == "rutina_mes_aplazada:2026-08-19"

    def test_sin_aplazamiento_nada(self):
        assert avisos_condicionados(ahora=AHORA, rutina_mes_aplazada_hasta=None) == []


class TestQuienRecibeQue:
    """La tabla del bloque 11, contra el catálogo. Los nombres del doc son los planes."""

    def _hab(self, plan):
        return PLAN_CATALOG[plan]["habilitaciones"]

    def test_mantenimiento_ninguno(self):
        assert self._hab("mantenimiento").get("reportes") in ([], None)

    def test_elm_el_rapido_al_renovar(self):
        hab = self._hab("elm")
        assert hab.get("reportes") == []          # va con la renovación, no con el calendario
        assert hab.get("reporte_rapido") is True  # y si sale, es el corto

    def test_calculadora_el_rapido_mensual(self):
        hab = self._hab("nivel1")
        assert hab.get("reportes") == ["mensual"]
        assert hab.get("reporte_rapido") is True
        assert hab.get("audio_feedback") is False

    def test_bronze_mensual_sin_feedback_sin_audio(self):
        hab = self._hab("bronze")
        assert hab.get("reportes") == ["mensual"]
        assert "no feedback" in hab.get("feedback", "")
        assert hab.get("audio_feedback") is False

    def test_silver_mensual_sin_feedback_con_audio(self):
        hab = self._hab("silver")
        assert hab.get("reportes") == ["mensual"]
        assert "no feedback" in hab.get("feedback", "")
        assert hab.get("audio_feedback") is True

    def test_gold_quincenal_y_mensual_con_feedback_y_audio(self):
        hab = self._hab("gold")
        assert sorted(hab.get("reportes") or []) == ["mensual", "quincenal"]
        assert hab.get("feedback") == "Con cada reporte"
        assert hab.get("audio_feedback") is True

    def test_los_grandes_no_llevan_el_rapido(self):
        # El formulario corto es de la Calculadora y ELM; a los de coach no se les recorta.
        for plan in ("gold", "silver", "bronze", "nivel2", "nivel3"):
            assert not self._hab(plan).get("reporte_rapido"), plan
