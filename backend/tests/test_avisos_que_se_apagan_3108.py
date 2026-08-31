# -*- coding: utf-8 -*-
"""QUE PUEDE APAGAR EL CLIENTE Y QUE NO (doc «El día», 31-08).

«Lo que interrumpe si, lo que informa no.» El riesgo de este apartado no es que un
interruptor no apague: es que apague DE MAS y deje al cliente sin enterarse de que se le
caduca la suscripcion. Por eso casi todos los casos de aqui miran el lado de «esto no se
puede apagar».
"""
import pytest

from core.avisos_cliente import (FAMILIAS_POR_INTERRUPTOR, NUNCA_SE_APAGAN,
                                 filtrar_por_preferencias)

TODOS = [
    {"familia": "cierra_dia"},          # el de las 20:00
    {"familia": "sin_cerrar"},          # «llevas N dias sin apuntar nada»
    {"familia": "quincenal_abierto"},
    {"familia": "quincenal_ultimo"},
    {"familia": "mensual_abierto"},
    {"familia": "mensual_ultimo"},
    {"familia": "peso_miercoles"},
    {"familia": "peso_jueves"},
    {"familia": "reporte_no_llego"},    # el fuera de plazo del jueves
    {"familia": "fin_ciclo"},           # la renovacion
    {"familia": "ciclo_terminado"},
    {"familia": "volvemos"},
    {"familia": "sin_entrar"},
]

familias = lambda avisos: {a["familia"] for a in avisos}


class TestLosCuatroQueNoSeApagan:
    def test_con_todo_apagado_siguen_saliendo(self):
        """El caso que de verdad importa: el cliente lo apaga TODO y aun asi se entera de
        que ha perdido el ajuste y de que se le acaba el ciclo."""
        apagado = {k: False for k in FAMILIAS_POR_INTERRUPTOR}
        apagado["avisos_en_la_app"] = False
        quedan = familias(filtrar_por_preferencias(TODOS, apagado))
        assert quedan == NUNCA_SE_APAGAN

    def test_la_renovacion_no_se_puede_apagar(self):
        """«Va de su contrato, no de su entrenamiento: si lo apaga, se le caduca la
        suscripcion sin enterarse y luego la culpa es tuya.»"""
        for f in ("fin_ciclo", "ciclo_terminado", "volvemos"):
            assert f in NUNCA_SE_APAGAN

    def test_el_fuera_de_plazo_tampoco(self):
        """«No le pide nada: le dice que ha perdido el ajuste de esta quincena.»"""
        assert "reporte_no_llego" in NUNCA_SE_APAGAN

    def test_ningun_interruptor_los_nombra(self):
        """Ni por descuido: que ninguna familia intocable este en la lista de alguno."""
        for interruptor, fams in FAMILIAS_POR_INTERRUPTOR.items():
            assert not (fams & NUNCA_SE_APAGAN), interruptor


class TestCadaInterruptor:
    def test_por_defecto_no_apaga_nada(self):
        assert familias(filtrar_por_preferencias(TODOS, {})) == familias(TODOS)
        assert familias(filtrar_por_preferencias(TODOS, None)) == familias(TODOS)

    @pytest.mark.parametrize("interruptor,se_van", [
        ("recordar_cierre", {"cierra_dia", "sin_cerrar"}),
        ("recordatorio_quincenal", {"quincenal_abierto", "quincenal_ultimo"}),
        ("recordatorio_mensual", {"mensual_abierto", "mensual_ultimo"}),
        ("recordatorio_peso", {"peso_miercoles", "peso_jueves"}),
    ])
    def test_apaga_lo_suyo_y_solo_lo_suyo(self, interruptor, se_van):
        quedan = familias(filtrar_por_preferencias(TODOS, {interruptor: False}))
        assert quedan == familias(TODOS) - se_van

    def test_avisos_en_la_app_se_lo_lleva_todo_menos_los_cuatro(self):
        quedan = familias(filtrar_por_preferencias(TODOS, {"avisos_en_la_app": False}))
        assert quedan == NUNCA_SE_APAGAN

    def test_apagar_uno_no_toca_a_los_demas(self):
        """El del peso no puede llevarse por delante el del reporte."""
        quedan = familias(filtrar_por_preferencias(TODOS, {"recordatorio_peso": False}))
        assert {"quincenal_abierto", "mensual_abierto", "cierra_dia"} <= quedan


class TestElCorreo:
    def test_apagar_el_correo_no_calla_lo_que_no_se_apaga(self):
        """La trampa de `core/correo_avisos`: FAMILIAS_CORREO incluye el fuera de plazo y
        los dos del contrato, asi que apagar el correo NO puede ser saltarse al cliente."""
        from core.correo_avisos import FAMILIAS_CORREO
        siguen = FAMILIAS_CORREO & NUNCA_SE_APAGAN
        assert siguen, "con el correo apagado tiene que seguir saliendo algo"
        assert "fin_ciclo" in siguen and "reporte_no_llego" in siguen
