# -*- coding: utf-8 -*-
"""LA PROMESA DEL REPORTE (doc «El día», 31-08).

Al mandar el reporte se le dice una fecha -- «antes del viernes tienes tus ajustes nuevos» --
y el «te aviso por aqui» ya funciona. El agujero es el otro lado: si nadie le contesta, no
pasa nada y el cliente espera una fecha que ya paso.

Se avisa AL EQUIPO el mismo dia, no al cliente: decirle «no te hemos contestado» no le da
sus ajustes, le confirma que no los tiene.
"""
from datetime import date

import pytest

from core.promesa_del_reporte import (DIA_PROMETIDO, a_quien_le_toca, dia_de_la_promesa,
                                      texto_del_aviso, vence_hoy)

# Agosto de 2026: el 31 es lunes, asi que el viernes de esa semana es el 4 de septiembre.
LUNES = date(2026, 8, 31)
VIERNES = date(2026, 9, 4)
SABADO = date(2026, 9, 5)
DOMINGO = date(2026, 9, 6)


class TestQueDiaSeLePrometio:
    def test_el_quincenal_promete_el_viernes(self):
        assert dia_de_la_promesa("quincenal", LUNES) == VIERNES

    def test_el_mensual_tambien_promete_el_viernes(self):
        """VIERNES DESDE EL 3-09, no sabado (decision de Francisco).

        El doc «El dia» del 31-08 puso sabado para el mensual con feedback. Despues, CUATRO
        documentos suyos dijeron viernes -- «El reporte mensual» y «El informe del mes», los
        dos del 1-09 --, y eligio la mayoria: «si 4 documentos dicen viernes entonces es
        viernes». Si vuelve a ser sabado, se cambia `DIA_PROMETIDO` y este test con el.
        """
        assert dia_de_la_promesa("mensual", LUNES) == VIERNES
        assert dia_de_la_promesa("mensual", LUNES) != SABADO

    def test_el_semanal_promete_el_domingo(self):
        """«El domingo tienes mi feedback: empiezas el lunes sabiendo que cambia.»"""
        assert dia_de_la_promesa("semanal", LUNES) == DOMINGO

    def test_mandado_el_mismo_dia_prometido_pasa_a_la_semana_siguiente(self):
        """No se le puede prometer una respuesta para dentro de dos horas."""
        assert dia_de_la_promesa("quincenal", VIERNES) == date(2026, 9, 11)

    def test_mandado_despues_espera_al_de_la_semana_siguiente(self):
        # Sabado: el viernes ya paso, asi que le toca el siguiente.
        assert dia_de_la_promesa("quincenal", SABADO) == date(2026, 9, 11)

    def test_un_tipo_raro_cae_en_el_viernes(self):
        assert dia_de_la_promesa(None, LUNES) == VIERNES
        assert dia_de_la_promesa("loquesea", LUNES) == VIERNES


class TestAQuienLeToca:
    def _reporte(self, **kw):
        base = {"id": "r1", "tipo": "quincenal", "created_at": LUNES.isoformat(),
                "informe_estado": "pendiente"}
        base.update(kw)
        return base

    def test_el_dia_prometido_y_sin_contestar_entra(self):
        assert vence_hoy(self._reporte(), VIERNES) is True

    def test_antes_del_dia_no_entra(self):
        """El aviso salta el dia prometido, ni antes ni despues: el objetivo es que la
        promesa se cumpla, no dejar constancia de que se rompio."""
        for d in (date(2026, 9, 2), date(2026, 9, 3)):
            assert vence_hoy(self._reporte(), d) is False

    def test_despues_tampoco(self):
        assert vence_hoy(self._reporte(), date(2026, 9, 5)) is False

    def test_si_ya_se_contesto_no_entra(self):
        assert vence_hoy(self._reporte(informe_estado="entregado"), VIERNES) is False

    def test_los_migrados_de_calma_no_cuentan(self):
        """En la base hay 3.414 reportes y los 3.414 vienen de Calma: son historia, no
        trabajo pendiente. A esa gente no se le prometio nada por esta app."""
        assert vence_hoy(self._reporte(calma_migrated=True), VIERNES) is False

    def test_el_contestado_a_mano_tampoco(self):
        """El informe es de T9; hay reportes anteriores contestados escribiendo el feedback
        y sin pasar por «Publicar»."""
        assert vence_hoy(self._reporte(trainer_feedback='te subo 10 g'), VIERNES) is False
        # Pero un feedback vacio no cuenta como contestado.
        assert vence_hoy(self._reporte(trainer_feedback='   '), VIERNES) is True

    def test_sin_fecha_no_revienta(self):
        assert vence_hoy({"tipo": "quincenal"}, VIERNES) is False
        assert vence_hoy({"tipo": "quincenal", "created_at": "no es una fecha"}, VIERNES) is False

    def test_filtra_la_lista(self):
        reportes = [
            self._reporte(id="a"),                                  # le toca hoy
            self._reporte(id="b", informe_estado="entregado"),       # ya contestado
            self._reporte(id="c", created_at="2026-09-01"),          # su viernes es el mismo
            # El mensual TAMBIEN vence el viernes desde el 3-09: antes era el sabado y por
            # eso este quedaba fuera de la lista del viernes.
            self._reporte(id="d", tipo="mensual"),
        ]
        ids = {r["id"] for r in a_quien_le_toca(reportes, VIERNES)}
        assert ids == {"a", "c", "d"}
        # Y el sabado ya no le toca a nadie: es la otra cara del mismo cambio.
        assert a_quien_le_toca(reportes, SABADO) == []


class TestElTexto:
    def test_uno_y_varios_no_se_escriben_igual(self):
        uno = texto_del_aviso(1)
        varios = texto_del_aviso(4)
        assert "1 cliente" in uno["titulo"]
        assert "4 clientes" in varios["titulo"]

    def test_dice_el_plazo_y_no_solo_que_hay_pendientes(self):
        """Un aviso que no dice el plazo se lee como una lista mas."""
        for n in (1, 3):
            t = texto_del_aviso(n)
            assert "hoy" in t["titulo"].lower()
            assert "esperando" in t["mensaje"].lower()


def test_no_lleva_interruptor():
    """Francisco, 31-08: «no quiero mas interruptores». Es del equipo, no del cliente, y no
    se apaga: si se pudiera apagar, la promesa se rompe en silencio, que es justo lo que
    esto viene a arreglar."""
    import inspect

    import core.promesa_del_reporte as modulo
    fuente = inspect.getsource(modulo)
    for palabra in ("pantalla_activa", "avisos.get", "interruptor "):
        assert palabra not in fuente
